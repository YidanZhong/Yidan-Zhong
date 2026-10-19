"""CPU scene-selection safety checks; these do not exercise PhysX visibility."""
from pathlib import Path
import hashlib
import importlib.util

import pytest


@pytest.fixture
def runner(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "tools/validate_confirmation_visibility_raycast.py"
    package = path.parents[4] / "benchmark/airground_benchmark"
    monkeypatch.setenv("AIRGROUND_BENCHMARK_PACKAGE", str(package))
    monkeypatch.delenv("AIRGROUND_ENV_URL", raising=False)
    monkeypatch.delenv("AIRGROUND_PROJECT_ROOT", raising=False)
    spec = importlib.util.spec_from_file_location("visibility_scene_selection", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_nonretro_cannot_silently_use_retro_even_with_environment_override(runner, monkeypatch, tmp_path):
    asset = tmp_path / "ConstructionSite_Export.usd"
    asset.write_text("test fixture, not a valid USD")
    monkeypatch.setenv("AIRGROUND_ENV_URL", str(asset))
    with pytest.raises(ValueError, match="require --scene-usd"):
        runner._resolve_scene_asset("ConstructionSite", None)


def test_known_cross_scene_filename_and_changed_asset_are_rejected(runner, tmp_path):
    wrong = tmp_path / "FireAcademy_Export.usd"
    wrong.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="annotations identify ConstructionSite"):
        runner._resolve_scene_asset("ConstructionSite", wrong)
    correct = tmp_path / "ConstructionSite_Export.usd"
    correct.write_bytes(b"fixture")
    expected = hashlib.sha256(correct.read_bytes()).hexdigest()
    assert runner._resolve_scene_asset("ConstructionSite", correct, expected) == (correct.resolve(), expected)
    correct.write_bytes(b"changed fixture")
    with pytest.raises(ValueError, match="SHA256 differs"):
        runner._resolve_scene_asset("ConstructionSite", correct, expected)


def test_retro_default_respects_project_root_and_cli_wins_over_environment(runner, monkeypatch, tmp_path):
    default = tmp_path / "scenes/RetroNeighborhood/RetroNeighborhood_Export.usd"
    default.parent.mkdir(parents=True)
    default.write_bytes(b"retro fixture")
    monkeypatch.setenv("AIRGROUND_PROJECT_ROOT", str(tmp_path))
    assert runner._resolve_scene_asset("RetroNeighborhood", None)[0] == default.resolve()
    other = tmp_path / "ConstructionSite_Export.usd"
    other.write_bytes(b"construction fixture")
    monkeypatch.setenv("AIRGROUND_ENV_URL", str(other))
    assert runner._resolve_scene_asset("RetroNeighborhood", default)[0] == default.resolve()
    with pytest.raises(ValueError, match="annotations identify RetroNeighborhood"):
        runner._resolve_scene_asset("RetroNeighborhood", None)


def test_real_annotations_fail_before_simulation_import_without_explicit_scene(runner, monkeypatch, tmp_path):
    from types import SimpleNamespace
    repository = Path(__file__).resolve().parents[4]
    annotations = repository / "runs/scene_gt_adaptation_20261017/ConstructionSite/targets.bound.json"
    # A real manifest is available in the reproduction workspace, not in clean CI.
    if not annotations.exists():
        annotations = repository / "runs/scene_gt_adaptation_20261017/ConstructionSite/targets.unreviewed.json"
    if not annotations.exists():
        pytest.skip("real unreviewed annotation artifact unavailable")
    args = SimpleNamespace(settle_steps=5, sensor_frame_count=5, sensor_frame_stride_steps=25,
                           sensor_report_output=None, sensor_topic_report_output=None,
                           sensor_topic_spin_s=1., annotations=annotations, scene_usd=None,
                           scene_sha256=None)
    monkeypatch.setattr(runner, "_parse_args", lambda: args)
    monkeypatch.setattr(runner, "_load_retro_launch_module", lambda *_: pytest.fail("Isaac must not start"))
    with pytest.raises(ValueError, match="require --scene-usd"):
        runner.main()


def test_reference_namespace_mismatch_rejected_with_real_usd_composition(runner):
    from types import SimpleNamespace
    from pxr import Usd
    repository = Path(__file__).resolve().parents[4]
    asset = repository / "AirStack/scenes/ConstructionSite/ConstructionSite_Export.usd"
    if not asset.exists():
        pytest.skip("downloaded ConstructionSite asset unavailable")
    stage = Usd.Stage.CreateInMemory()
    stage.DefinePrim("/World/stage").GetReferences().AddReference(str(asset))
    manifest = SimpleNamespace(instances=[SimpleNamespace(
        usd_prim_path="/World/stage/ConstructionSite/AsphaltRoller")])
    with pytest.raises(RuntimeError, match="reference namespace"):
        runner._validate_runtime_target_paths(manifest, stage)
    original = Usd.Stage.Open(str(asset))
    assert runner._validate_runtime_target_paths(manifest, original) == 1


def test_reference_projection_preserves_actual_gt_and_rejects_geometry_shift(runner):
    from pxr import Usd, UsdGeom, Gf
    repository = Path(__file__).resolve().parents[4]
    asset = repository / "AirStack/scenes/ConstructionSite/ConstructionSite_Export.usd"
    annotations = repository / "runs/scene_gt_adaptation_20261017/ConstructionSite/targets.unreviewed.json"
    if not asset.exists() or not annotations.exists():
        pytest.skip("real ConstructionSite inputs unavailable")
    original_bytes = annotations.read_bytes()
    manifest = runner.load_target_annotations(annotations)
    stage = Usd.Stage.CreateInMemory()
    stage.DefinePrim("/World/stage").GetReferences().AddReference(str(asset))
    projected, mapping = runner._project_reference_target_paths(manifest, stage, asset, "/World/stage")
    assert len(mapping) == 25
    assert runner._validate_runtime_target_paths(projected, stage) == 25
    assert annotations.read_bytes() == original_bytes
    for original, runtime in zip(manifest.instances, projected.instances):
        assert original.model_dump(exclude={"usd_prim_path"}) == runtime.model_dump(exclude={"usd_prim_path"})
        if original.usd_prim_path:
            assert original.usd_prim_path.startswith("/World/stage/ConstructionSite/")
            assert runtime.usd_prim_path.startswith("/World/stage/stage/ConstructionSite/")
        else:
            assert runtime.usd_prim_path is None
    # The authored scene resets its transform stack below the mount, so shift
    # a target itself to exercise an actual world-geometry change.
    UsdGeom.Xformable(stage.GetPrimAtPath(mapping[0]["runtime_prim"])).AddTranslateOp(
        opSuffix="test_shift").Set(Gf.Vec3d(.1, 0., 0.))
    with pytest.raises(RuntimeError, match="world geometry changed"):
        runner._project_reference_target_paths(manifest, stage, asset, "/World/stage")
