"""UGV-centric open-set object-goal navigation task catalog.

This module migrates the upstream RAVEN task definitions into a machine-readable
catalog for the UGV-scored benchmark lane introduced on 2026-09-13:

- the word lists are taken from RAVEN (arXiv 2509.23563) appendix Table A.3
  for all ten scenes; spelling and protocol caveats are recorded in scenes.py;
- the goal set of a task is the set of *ground-reachable* annotated instances
  of the queried classes (``ground_reachable == "reachable"`` with a reachable
  confirmation region);
- tasks whose goal set is empty are marked ``blocked`` and are not scored; tasks
  where at least one queried class contributes no reachable instance but the
  union is non-empty are marked ``degraded``.

The catalog deliberately keeps the upstream wording in ``query_text`` while
exposing normalized ``query_classes`` so the metric layer and the RayFronts
query prompt use the same class list.
"""

from __future__ import annotations

from airground_benchmark.scenes import (SceneId, PAPER_QUERIES, PAPER_SCENE_NAMES, query_classes, scene_slug)

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from airground_benchmark.config.schema import SCHEMA_VERSION
from airground_benchmark.ground_truth import (
    TargetAnnotationManifest,
    target_annotations_sha256,
)


class TaskCatalogError(ValueError):
    """Raised when a task catalog cannot be built or validated."""


class StrictModel(BaseModel):
    """Base class for strict catalog artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


CATALOG_ID = "benchmark-v2-ugv-ogn-retro"
CATALOG_GENERATOR = "airground-ugv-ogn-task-catalog-v1"
CATALOG_GENERATOR_VERSION = "2026-09-13"
UPSTREAM_TABLE_REF = "RAVEN arXiv:2509.23563 Table A.3 (Neighborhood)"

# Reach window shared by M and the reach predicate.  The reviewed
# confirmation-region GT was generated with the same 1.5-8.0 m window, so both
# the catalog and the metric must declare it explicitly.
REACH_WINDOW_MIN_M = 1.5
REACH_WINDOW_MAX_M = 8.0

TaskFamily = Literal["type_i", "type_ii", "type_iii"]
TaskStatus = Literal["ok", "degraded", "blocked"]


@dataclass(frozen=True)
class UpstreamTaskSpec:
    """One upstream task from the RAVEN paper appendix task table."""

    task_id: str
    family: TaskFamily
    query_text: str
    query_classes: tuple[str, ...]
    sequence_classes: tuple[tuple[str, ...], ...] = ()


# Upstream Table A.3 lists four Type I tasks, three Type II tasks and three
# Type III tasks for the Neighborhood scene.  Type III entries encode the
# sequential reveal order: the first class is queried first, the second class is
# revealed after the first class has been reached.
NEIGHBORHOOD_UPSTREAM_TASKS: tuple[UpstreamTaskSpec, ...] = (
    UpstreamTaskSpec(
        task_id="retro-type-i-blue-container",
        family="type_i",
        query_text="blue container",
        query_classes=("blue container",),
    ),
    UpstreamTaskSpec(
        task_id="retro-type-i-bus-stop",
        family="type_i",
        query_text="bus stop",
        query_classes=("bus stop",),
    ),
    UpstreamTaskSpec(
        task_id="retro-type-i-yellow-car",
        family="type_i",
        query_text="yellow car",
        query_classes=("yellow car",),
    ),
    UpstreamTaskSpec(
        task_id="retro-type-i-house",
        family="type_i",
        query_text="house",
        query_classes=("house",),
    ),
    UpstreamTaskSpec(
        task_id="retro-type-ii-bus-stop-blue-container",
        family="type_ii",
        query_text="bus stop, blue container",
        query_classes=("bus stop", "blue container"),
    ),
    UpstreamTaskSpec(
        task_id="retro-type-ii-red-container-yellow-car-billboard",
        family="type_ii",
        query_text="red container, yellow car, billboard",
        query_classes=("red container", "yellow car", "billboard"),
    ),
    UpstreamTaskSpec(
        task_id="retro-type-ii-tunnel-blue-container-red-car",
        family="type_ii",
        query_text="tunnel, blue container, red car",
        query_classes=("tunnel", "blue container", "red car"),
    ),
    UpstreamTaskSpec(
        task_id="retro-type-iii-bus-stop-to-blue-container",
        family="type_iii",
        query_text="bus stop -> blue container",
        query_classes=("bus stop", "blue container"),
        sequence_classes=(("bus stop",), ("blue container",)),
    ),
    UpstreamTaskSpec(
        task_id="retro-type-iii-yellow-car-to-billboard",
        family="type_iii",
        query_text="yellow car -> billboard",
        query_classes=("yellow car", "billboard"),
        sequence_classes=(("yellow car",), ("billboard",)),
    ),
    UpstreamTaskSpec(
        task_id="retro-type-iii-blue-container-to-tunnel",
        family="type_iii",
        query_text="blue container -> tunnel",
        query_classes=("blue container", "tunnel"),
        sequence_classes=(("blue container",), ("tunnel",)),
    ),
)

def upstream_tasks(scene_id: str) -> tuple[UpstreamTaskSpec, ...]:
    """Return literal Table A.3 tasks; preserve the existing Retro task IDs."""
    if scene_id == "RetroNeighborhood":
        return NEIGHBORHOOD_UPSTREAM_TASKS
    prefix = scene_slug(scene_id)
    tasks = []
    for index, queries in enumerate(PAPER_QUERIES[scene_id]):
        family = ("type_i", "type_ii", "type_iii")[index]
        for query in queries:
            classes = query_classes(scene_id, index, query)
            suffix = ("-to-" if index == 2 else "-").join(
                re.sub(r"[^a-z0-9]+", "-", item.lower()).strip("-") for item in classes
            )
            tasks.append(UpstreamTaskSpec(
                task_id=f"{prefix}-{family.replace('_', '-')}-{suffix}",
                family=family, query_text=query, query_classes=classes,
                sequence_classes=tuple((item,) for item in classes) if index == 2 else (),
            ))
    return tuple(tasks)


# Cross-scene spelling differences between the paper word lists and the
# RayFronts annotation files.  Matching is done on a normalized semantic key,
# so only genuinely different names need an explicit alias group.
CLASS_ALIAS_GROUPS: tuple[tuple[str, ...], ...] = (
    ("bio toilet", "biotoilet"),
    ("silo", "white silo"),
)


def semantic_class_key(value: str) -> str:
    """Return the normalized matching key for a semantic class name."""

    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())


def _class_key_aliases(requested_class: str) -> frozenset[str]:
    keys = {semantic_class_key(requested_class)}
    if not keys or "" in keys:
        raise TaskCatalogError("semantic class names must contain alphanumeric characters")
    for group in CLASS_ALIAS_GROUPS:
        group_keys = {semantic_class_key(member) for member in group}
        if keys & group_keys:
            keys |= group_keys
    return frozenset(keys)


class ClassResolution(StrictModel):
    """Reachable-instance resolution for one requested class."""

    requested_class: str
    matched_classes: tuple[str, ...]
    reachable_instance_count: int = Field(ge=0)
    reachable_instance_ids: tuple[str, ...]


class TaskCatalogEntry(StrictModel):
    """One catalog task with its resolved goal set and status."""

    task_id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    family: TaskFamily
    query_text: str = Field(min_length=1)
    query_classes: tuple[str, ...] = Field(min_length=1)
    upstream_table_ref: str = Field(min_length=1)
    goal_instance_ids: tuple[str, ...]
    m: int = Field(ge=0)
    status: TaskStatus
    classes_without_reachable_instances: tuple[str, ...]
    class_resolutions: tuple[ClassResolution, ...]
    sequence_classes: tuple[tuple[str, ...], ...] = ()
    sequence_phase_instance_counts: tuple[int, ...] = ()


class TaskCatalog(StrictModel):
    """Versioned UGV-centric task catalog for one scene."""

    schema_version: Literal[SCHEMA_VERSION]
    catalog_id: str = Field(min_length=1)
    scene_id: SceneId
    generator: Literal["airground-ugv-ogn-task-catalog-v1"]
    generator_version: str = Field(min_length=1)
    upstream_table_ref: str = Field(min_length=1)
    reach_window_min_m: float = Field(gt=0.0)
    reach_window_max_m: float = Field(gt=0.0)
    source_annotation_path: str | None = None
    source_annotation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_count: int = Field(ge=0)
    type_i_count: int = Field(ge=0)
    type_ii_count: int = Field(ge=0)
    type_iii_count: int = Field(ge=0)
    runnable_count: int = Field(ge=0)
    degraded_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    entries: tuple[TaskCatalogEntry, ...]

    @model_validator(mode="after")
    def validate_counts(self) -> "TaskCatalog":
        if self.reach_window_max_m < self.reach_window_min_m:
            raise ValueError("reach window upper bound must be >= lower bound")
        if self.task_count != len(self.entries):
            raise ValueError("task_count must match the number of entries")
        family_counts = {
            "type_i": sum(1 for entry in self.entries if entry.family == "type_i"),
            "type_ii": sum(1 for entry in self.entries if entry.family == "type_ii"),
            "type_iii": sum(1 for entry in self.entries if entry.family == "type_iii"),
        }
        if family_counts["type_i"] != self.type_i_count:
            raise ValueError("type_i_count must match the number of Type I entries")
        if family_counts["type_ii"] != self.type_ii_count:
            raise ValueError("type_ii_count must match the number of Type II entries")
        if family_counts["type_iii"] != self.type_iii_count:
            raise ValueError("type_iii_count must match the number of Type III entries")
        blocked = sum(1 for entry in self.entries if entry.status == "blocked")
        degraded = sum(1 for entry in self.entries if entry.status == "degraded")
        if blocked != self.blocked_count:
            raise ValueError("blocked_count must match the number of blocked entries")
        if degraded != self.degraded_count:
            raise ValueError("degraded_count must match the number of degraded entries")
        if self.runnable_count != self.task_count - blocked:
            raise ValueError("runnable_count must equal task_count - blocked_count")
        return self


def _reachable_instances(manifest: TargetAnnotationManifest) -> dict[str, tuple[str, str]]:
    """Return ``instance_id -> (semantic_class, region_id)`` for reachable targets."""

    regions_by_instance = {
        region.instance_id: region
        for region in manifest.confirmation_regions
        if region.reachable
    }
    reachable: dict[str, tuple[str, str]] = {}
    for instance in manifest.instances:
        if instance.ground_reachable != "reachable":
            continue
        if instance.excluded_reason is not None:
            continue
        region_id = instance.confirmation_region_id
        if region_id is None:
            continue
        region = regions_by_instance.get(instance.instance_id)
        if region is None or region.region_id != region_id:
            continue
        reachable[instance.instance_id] = (instance.semantic_class, region_id)
    return reachable


def _validate_reach_window(
    manifest: TargetAnnotationManifest,
    *,
    reach_window_min_m: float,
    reach_window_max_m: float,
) -> None:
    """Fail closed when the reviewed regions do not match the declared window."""

    if reach_window_max_m < reach_window_min_m:
        raise TaskCatalogError("reach window upper bound must be >= lower bound")
    for region in manifest.confirmation_regions:
        if not region.reachable:
            continue
        for pose in region.poses:
            if not (
                reach_window_min_m - 1.0e-9
                <= pose.distance_to_target_m
                <= reach_window_max_m + 1.0e-9
            ):
                raise TaskCatalogError(
                    "confirmation region "
                    f"{region.region_id} has pose distance {pose.distance_to_target_m} "
                    f"outside the declared reach window "
                    f"[{reach_window_min_m}, {reach_window_max_m}] m"
                )


def build_task_catalog(
    manifest: TargetAnnotationManifest,
    *,
    tasks: Sequence[UpstreamTaskSpec] | None = None,
    catalog_id: str | None = None,
    source_annotation_path: str | None = None,
    reach_window_min_m: float = REACH_WINDOW_MIN_M,
    reach_window_max_m: float = REACH_WINDOW_MAX_M,
) -> TaskCatalog:
    """Resolve upstream task word lists against reachable annotated instances."""

    tasks = upstream_tasks(manifest.scene_id) if tasks is None else tasks
    catalog_id = catalog_id or f"benchmark-v2-ugv-ogn-{scene_slug(manifest.scene_id)}"
    table_ref = f"RAVEN arXiv:2509.23563 Table A.3 ({PAPER_SCENE_NAMES[manifest.scene_id]})"
    _validate_reach_window(
        manifest,
        reach_window_min_m=reach_window_min_m,
        reach_window_max_m=reach_window_max_m,
    )
    reachable = _reachable_instances(manifest)
    instances_by_key: dict[str, list[tuple[str, str]]] = {}
    for instance_id, (semantic_class, _region_id) in reachable.items():
        instances_by_key.setdefault(semantic_class_key(semantic_class), []).append(
            (semantic_class, instance_id)
        )
    for values in instances_by_key.values():
        values.sort()

    entries: list[TaskCatalogEntry] = []
    for spec in tasks:
        resolutions: list[ClassResolution] = []
        goal_instance_ids: list[str] = []
        missing: list[str] = []
        resolutions_by_class: dict[str, ClassResolution] = {}
        for requested_class in spec.query_classes:
            matched_classes: set[str] = set()
            matched_ids: list[str] = []
            for key in sorted(_class_key_aliases(requested_class)):
                for semantic_class, instance_id in instances_by_key.get(key, ()):
                    matched_classes.add(semantic_class)
                    matched_ids.append(instance_id)
            unique_ids = sorted(set(matched_ids))
            if not unique_ids:
                missing.append(requested_class)
            goal_instance_ids.extend(unique_ids)
            resolution = ClassResolution(
                requested_class=requested_class,
                matched_classes=tuple(sorted(matched_classes)),
                reachable_instance_count=len(unique_ids),
                reachable_instance_ids=tuple(unique_ids),
            )
            resolutions.append(resolution)
            resolutions_by_class[requested_class] = resolution
        deduped_goals = tuple(sorted(set(goal_instance_ids)))
        m = len(deduped_goals)
        phase_counts = tuple(
            len(
                {
                    instance_id
                    for requested_class in phase_classes
                    for instance_id in resolutions_by_class[requested_class].reachable_instance_ids
                }
            )
            for phase_classes in spec.sequence_classes
        )
        phase_blocked = any(count == 0 for count in phase_counts)
        if m == 0:
            status: TaskStatus = "blocked"
        elif phase_blocked:
            status = "blocked"
        elif missing:
            status = "degraded"
        else:
            status = "ok"
        entries.append(
            TaskCatalogEntry(
                task_id=spec.task_id,
                family=spec.family,
                query_text=spec.query_text,
                query_classes=tuple(spec.query_classes),
                upstream_table_ref=table_ref,
                goal_instance_ids=deduped_goals,
                m=m,
                status=status,
                classes_without_reachable_instances=tuple(sorted(missing)),
                class_resolutions=tuple(resolutions),
                sequence_classes=tuple(tuple(group) for group in spec.sequence_classes),
                sequence_phase_instance_counts=phase_counts,
            )
        )

    task_ids = [entry.task_id for entry in entries]
    if len(set(task_ids)) != len(task_ids):
        raise TaskCatalogError("task ids must be unique within a catalog")

    return TaskCatalog(
        schema_version=SCHEMA_VERSION,
        catalog_id=catalog_id,
        scene_id=manifest.scene_id,
        generator=CATALOG_GENERATOR,
        generator_version=CATALOG_GENERATOR_VERSION,
        upstream_table_ref=table_ref,
        reach_window_min_m=reach_window_min_m,
        reach_window_max_m=reach_window_max_m,
        source_annotation_path=source_annotation_path or manifest.source_path,
        source_annotation_sha256=target_annotations_sha256(manifest),
        task_count=len(entries),
        type_i_count=sum(1 for entry in entries if entry.family == "type_i"),
        type_ii_count=sum(1 for entry in entries if entry.family == "type_ii"),
        type_iii_count=sum(1 for entry in entries if entry.family == "type_iii"),
        runnable_count=sum(1 for entry in entries if entry.status != "blocked"),
        degraded_count=sum(1 for entry in entries if entry.status == "degraded"),
        blocked_count=sum(1 for entry in entries if entry.status == "blocked"),
        entries=tuple(entries),
    )


def canonical_task_catalog_json(catalog: TaskCatalog) -> str:
    """Serialize a task catalog into checksum-stable JSON."""

    return (
        json.dumps(
            catalog.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def task_catalog_sha256(catalog: TaskCatalog) -> str:
    """Return the checksum of the canonical catalog JSON."""

    return hashlib.sha256(canonical_task_catalog_json(catalog).encode("utf-8")).hexdigest()


def load_task_catalog(path: Path) -> TaskCatalog:
    """Load and validate a task catalog JSON file."""

    resolved = Path(path).expanduser().resolve(strict=True)
    value: Any = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise TaskCatalogError(f"{resolved} is not a JSON object")
    return TaskCatalog.model_validate(value)


def find_catalog_entry(catalog: TaskCatalog, task_id: str) -> TaskCatalogEntry:
    """Return one catalog entry by task id."""

    for entry in catalog.entries:
        if entry.task_id == task_id:
            return entry
    raise TaskCatalogError(f"unknown task id: {task_id}")


def runnable_catalog_entries(catalog: TaskCatalog) -> tuple[TaskCatalogEntry, ...]:
    """Return non-blocked entries in deterministic order."""

    return tuple(entry for entry in catalog.entries if entry.status != "blocked")


def catalog_entries_by_family(
    catalog: TaskCatalog,
    family: TaskFamily,
) -> tuple[TaskCatalogEntry, ...]:
    """Return entries of one task family in catalog order."""

    return tuple(entry for entry in catalog.entries if entry.family == family)


def task_goal_classes(
    manifest: TargetAnnotationManifest,
    entry: TaskCatalogEntry,
) -> tuple[str, ...]:
    """Return the semantic classes of the entry's resolved goal instances."""

    instances = {instance.instance_id: instance for instance in manifest.instances}
    classes: list[str] = []
    for instance_id in entry.goal_instance_ids:
        instance = instances.get(instance_id)
        if instance is None:
            raise TaskCatalogError(f"catalog goal references unknown instance: {instance_id}")
        classes.append(instance.semantic_class)
    return tuple(classes)


def catalog_diagnostics(catalog: TaskCatalog) -> dict[str, Any]:
    """Return a compact human-readable summary of catalog statuses."""

    return {
        "catalog_id": catalog.catalog_id,
        "task_count": catalog.task_count,
        "runnable_count": catalog.runnable_count,
        "degraded_count": catalog.degraded_count,
        "blocked_count": catalog.blocked_count,
        "blocked_tasks": [
            entry.task_id for entry in catalog.entries if entry.status == "blocked"
        ],
        "degraded_tasks": [
            entry.task_id for entry in catalog.entries if entry.status == "degraded"
        ],
        "tasks": [
            {
                "task_id": entry.task_id,
                "family": entry.family,
                "query_text": entry.query_text,
                "m": entry.m,
                "status": entry.status,
                "classes_without_reachable_instances": list(
                    entry.classes_without_reachable_instances
                ),
            }
            for entry in catalog.entries
        ],
    }


def iter_task_ids(tasks: Iterable[UpstreamTaskSpec]) -> tuple[str, ...]:
    """Return task ids for a task spec sequence (test/diagnostic helper)."""

    return tuple(task.task_id for task in tasks)
