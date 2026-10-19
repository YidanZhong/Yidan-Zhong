"""Scene identifiers and literal task wording from RAVEN Table A.3.

This registry declares input support, not simulator readiness.  In particular,
SnowyVillage's tower/water-tower identity remains unreviewed.  Shipyard's printed
Type II query ``ship silo`` is preserved verbatim and explicitly interpreted as
the two classes ship and silo; this interpretation needs protocol review.
"""
from __future__ import annotations

from typing import Literal, get_args
import re

SceneId = Literal[
    "RetroNeighborhood", "FireAcademy", "ConstructionSite", "AbandonedFactory",
    "AbandonedCity", "SnowyVillage", "DowntownWest", "ModernCityDowntown",
    "MilitaryBase", "Shipyard",
]
SCENE_IDS: tuple[str, ...] = get_args(SceneId)
SceneCatalogId = Literal[
    "benchmark-v1.0-retro", "benchmark-v1.0-fire-academy",
    "benchmark-v1.0-construction-site", "benchmark-v1.0-abandoned-factory",
    "benchmark-v1.0-abandoned-city", "benchmark-v1.0-snowy-village",
    "benchmark-v1.0-downtown-west", "benchmark-v1.0-modern-city-downtown",
    "benchmark-v1.0-military-base", "benchmark-v1.0-shipyard",
]


def validate_scene_catalog(scene_id: str, catalog_id: str) -> None:
    if catalog_id != f"benchmark-v1.0-{scene_slug(scene_id)}":
        raise ValueError("catalog_id must correspond to scene_id")

# Candidate-name hints only. These neither establish object identity nor approve GT.
# In particular, a tower is not automatically a water tower.
EXTRA_USD_ALIASES: dict[str, tuple[str, ...]] = {
    "water tower": ("water_tower", "watertower"),
    "tower": ("tower",),
    "radio tower": ("radio_tower", "radiotower", "antenna"),
    "green container": ("green_container", "shippingcontainer", "container"),
    "fuel tank": ("fuel_tank", "fueltank", "tank"),
    "building": ("building", "factory", "warehouse"),
    "red building": ("building",),
    "white silo": ("silo",),
    "silo": ("silo",),
    "pipe": ("pipe",),
    "blue tarp": ("tarp", "tarpaulin"),
    "orange tarp": ("tarp", "tarpaulin"),
    "orange towercrane": ("towercrane", "tower_crane", "crane"),
    "yellow towercrane": ("towercrane", "tower_crane", "crane"),
    "cabling winches": ("winch", "cable", "cabling"),
    "bio toilet": ("biotoilet", "bio_toilet", "toilet"),
    "biotoilet": ("biotoilet", "bio_toilet", "toilet"),
    "construction lift": ("construction_lift", "lift"),
    "asphalt roller": ("asphalt_roller", "roller"),
    "forklift": ("forklift",),
    "car": ("car", "vehicle", "nissan"),
    "yellow motorhome": ("motorhome", "camper", "rv"),
    "human": ("human", "person", "character"),
    "bridge": ("bridge",),
    "pond": ("pond",),
    "outhouse": ("outhouse",),
    "fire hydrant": ("fire_hydrant", "hydrant"),
    "food cart": ("food_cart", "foodcart"),
    "trash bin": ("trash_bin", "trashbin", "trash_can", "trashcan"),
    "traffic light": ("traffic_light", "trafficlight"),
    "obelisk": ("obelisk",),
    "yellow truck": ("truck",),
    "cafe table": ("cafe_table", "cafetable", "table"),
    "bankomat": ("bankomat", "atm"),
    "helicopter": ("helicopter",),
    "atv": ("atv", "quadbike"),
    "guard tower": ("guard_tower", "guardtower", "watchtower"),
    "mobile radar": ("mobile_radar", "radar"),
    "airfield": ("airfield", "runway"),
    "ship": ("ship", "boat"),
    "ship construction": ("ship_construction", "shipconstruction", "ship"),
    "crane": ("crane",),
}
PAPER_SCENE_NAMES = {
    "RetroNeighborhood": "Neighborhood", "FireAcademy": "Fire Academy",
    "ConstructionSite": "Construction Site", "AbandonedFactory": "Abandoned Factory",
    "AbandonedCity": "Abandoned City", "SnowyVillage": "Snowy Village",
    "DowntownWest": "Downtown West", "ModernCityDowntown": "Modern City Downtown",
    "MilitaryBase": "Military Base", "Shipyard": "Shipyard",
}

# Four single-class, three unordered multi-class, three ordered dual-class tasks.
PAPER_QUERIES: dict[str, tuple[tuple[str, ...], ...]] = {
    "RetroNeighborhood": (
        ("blue container", "bus stop", "yellow car", "house"),
        ("bus stop, blue container", "red container, yellow car, billboard", "tunnel, blue container, red car"),
        ("bus stop -> blue container", "yellow car -> billboard", "blue container -> tunnel")),
    "FireAcademy": (
        ("water tower", "radio tower", "green container", "fuel tank"),
        ("water tower, fuel tank", "radio tower, blue container", "red container, water tower"),
        ("water tower -> radio tower", "radio tower -> fuel tank", "green container -> water tower")),
    "ConstructionSite": (
        ("blue tarp", "orange towercrane", "cabling winches", "bio toilet"),
        ("orange towercrane, forklift", "construction lift, asphalt roller", "blue tarp, bio toilet, yellow towercrane"),
        ("blue tarp -> orange towercrane", "orange towercrane -> blue tarp", "cabling winches -> bio toilet")),
    "AbandonedFactory": (
        ("white silo", "water tower", "pipe", "building"),
        ("water tower, pipe", "white silo, building", "building, pipe"),
        ("water tower -> white silo", "building -> white silo", "white silo -> pipe")),
    "AbandonedCity": (
        ("building", "car", "bus stop", "yellow motorhome"),
        ("yellow motorhome, car", "car, bus stop", "bus stop, yellow motorhome"),
        ("building -> car", "car -> bus stop", "bus stop -> car")),
    "SnowyVillage": (
        ("human", "bridge", "pond", "car"),
        ("tower, car", "human, outhouse", "outhouse, pond"),
        ("pond -> tower", "tower -> bridge", "outhouse -> car")),
    "DowntownWest": (
        ("fountain", "fire hydrant", "food cart", "trash bin"),
        ("food cart, trash bin", "fountain, food cart", "fountain, trash bin"),
        ("fountain -> food cart", "trash bin -> fountain", "food cart -> fountain")),
    "ModernCityDowntown": (
        ("obelisk", "yellow truck", "cafe table", "bankomat"),
        ("obelisk, yellow truck", "cafe table, bankomat", "bankomat, yellow truck"),
        ("cafe table -> obelisk", "obelisk -> bankomat", "yellow truck -> cafe table")),
    "MilitaryBase": (
        ("radio tower", "helicopter", "ATV", "bridge"),
        ("radio tower, guard tower", "helicopter, radio tower, mobile radar", "radio tower, bridge, helicopter"),
        ("guard tower -> helicopter", "radio tower -> bridge", "bridge -> guard tower")),
    "Shipyard": (
        ("ship", "crane", "silo", "ship construction"),
        ("ship, crane", "ship silo", "ship construction, crane"),
        ("crane -> ship", "ship -> silo", "silo -> ship")),
}

SCENE_REVIEW_NOTES = {
    "AbandonedCity": ("Upstream annotations lack car and yellow motorhome; add scene-evidenced annotations before review.",),
    "SnowyVillage": ("Do not alias tower to water tower until USD/RGB identity is reviewed.", "No validated dual-robot launch configuration is available."),
    "Shipyard": ("Table A.3 prints 'ship silo' without a comma; interpreted as ship + silo for Type II, pending protocol review.",),
}


def scene_slug(scene_id: str) -> str:
    if scene_id not in SCENE_IDS:
        raise ValueError(f"unsupported scene: {scene_id}")
    if scene_id == "RetroNeighborhood":
        return "retro"
    return re.sub(r"(?<!^)(?=[A-Z])", "-", scene_id).lower()


def query_classes(scene_id: str, family_index: int, query: str) -> tuple[str, ...]:
    if scene_id == "Shipyard" and family_index == 1 and query == "ship silo":
        return ("ship", "silo")
    return tuple(word.strip() for word in query.split("->" if family_index == 2 else ","))


def paper_classes(scene_id: str) -> tuple[str, ...]:
    scene_slug(scene_id)  # validate before indexing
    return tuple(sorted({word.lower() for index, group in enumerate(PAPER_QUERIES[scene_id])
                         for query in group for word in query_classes(scene_id, index, query)}))


def paper_class_key(value: str) -> str:
    key = re.sub(r"[^a-z0-9]", "", value.lower())
    return {"biotoilet": "biotoilet", "whitesilo": "silo"}.get(key, key)


def is_paper_class(scene_id: str, semantic_class: str) -> bool:
    return paper_class_key(semantic_class) in {paper_class_key(c) for c in paper_classes(scene_id)}
