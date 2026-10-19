"""Regression checks for RetroNeighborhood static USD scene audit."""

from pathlib import Path
import sys

import pytest


ISAAC_SIM = Path(__file__).parents[1]
SCENE = ISAAC_SIM.parents[1] / "scenes/RetroNeighborhood/RetroNeighborhood_Export.usd"
sys.path.insert(0, str(ISAAC_SIM / "utils"))

from scene_audit import (  # noqa: E402
    audit_usd_scene,
    classify_scene_mesh,
    collision_approximation_for_profile,
)


def test_scene_profile_classifier_rules():
    assert (
        classify_scene_mesh(
            "/World/stage/Neighborhood/Main_Road/SM_Asphalt",
            has_collision=True,
            has_rigid_body=False,
        )
        == "ground"
    )
    assert (
        classify_scene_mesh(
            "/World/stage/Neighborhood/BP_Car/SM_Car",
            has_collision=True,
            has_rigid_body=False,
        )
        == "static_obstacle"
    )
    assert (
        classify_scene_mesh(
            "/World/stage/Neighborhood/BP_Door/SM_Door",
            has_collision=True,
            has_rigid_body=True,
        )
        == "dynamic"
    )
    assert (
        classify_scene_mesh(
            "/World/Environment/sky/AxisNorth/SkySphere/Sphere",
            has_collision=False,
            has_rigid_body=False,
        )
        == "visual_only"
    )
    assert collision_approximation_for_profile("ground") == "meshSimplification"
    assert collision_approximation_for_profile("static_obstacle") == "convexDecomposition"
    assert collision_approximation_for_profile("dynamic") is None


def test_construction_terrain_preserves_concavity_without_broad_name_matches():
    for suffix in ("Landscape/Landscape_0", "Landscape2/Landscape2"):
        path = "/World/stage/ConstructionSite/Land/" + suffix
        profile = classify_scene_mesh(path, has_collision=True, has_rigid_body=False)
        assert collision_approximation_for_profile(profile) == "meshSimplification"
        assert classify_scene_mesh(path, has_collision=True, has_rigid_body=True) == "dynamic"
        # Referencing the same asset under another parent must retain its policy.
        assert classify_scene_mesh("/World/Scene" + path[6:], has_collision=True,
                                   has_rigid_body=False) == "ground"
    for path in (
        "/World/stage/OtherScene/Land/Landscape2/Landscape2",
        "/World/stage/ConstructionSite/Land/Landscape2/Landscape2Decoration",
        "/World/stage/ConstructionSite/Land/Landscape2/Landscape2/Decoration",
    ):
        assert classify_scene_mesh(path, has_collision=True,
                                   has_rigid_body=False) == "static_obstacle"


def test_retro_neighborhood_scene_audit_contract():
    pytest.importorskip("pxr")

    report = audit_usd_scene(SCENE, sample_limit=5)

    assert report["schema_version"] == "1.0.0"
    assert report["scene"]["sha256"] == (
        "2a7141ce928c432f031f78a6b1c3798eaa932431d5a1735f8bad513694afce32"
    )
    assert report["stage"]["default_prim"] == "/World"
    assert report["stage"]["meters_per_unit"] == 1.0
    assert report["stage"]["up_axis"] == "Z"
    assert report["stage"]["root_prims"] == [
        "/Render",
        "/World",
        "/OmniverseKit_Persp",
        "/OmniverseKit_Front",
        "/OmniverseKit_Top",
        "/OmniverseKit_Right",
    ]
    assert report["counts"] == {
        "prims": 27986,
        "meshes": 4280,
        "materials": 3919,
        "physics_scenes": 1,
        "collision_api": 4278,
        "meshes_without_collision": 2,
        "rigid_body_api": 0,
        "mass_api": 0,
    }
    assert report["samples"]["physics_scenes"] == ["/World/PhysicsScene"]
    assert report["samples"]["meshes_without_collision"] == [
        "/World/Environment/sky/AxisNorth/SkySphere/Sphere",
        "/World/Environment/sky/AxisNorth/ArrowsNWSE/Compass",
    ]
    assert report["profile"]["counts"] == {
        "ground": 545,
        "static_obstacle": 3733,
        "dynamic": 0,
        "visual_only": 2,
        "uncategorized": 0,
    }
    assert report["profile"]["samples"]["ground"][0] == (
        "/World/stage/Neighborhood/Alley_Ground/SM_AlleyGround/SM_AlleyGround_01"
    )
    assert report["profile"]["samples"]["visual_only"] == [
        "/World/Environment/sky/AxisNorth/SkySphere/Sphere",
        "/World/Environment/sky/AxisNorth/ArrowsNWSE/Compass",
    ]
    assert report["profile"]["rules"]["collision_approximation_policy"] == {
        "ground": "meshSimplification",
        "static_obstacle": "convexDecomposition",
        "dynamic": None,
        "visual_only": None,
        "uncategorized": None,
    }
    assert report["geometry_diagnostics"]["counts"] == {
        "duplicate_physics_scenes": 0,
        "deep_min_z_lt_minus_1m": 0,
        "entirely_below_minus_1m": 0,
        "invisible_colliders": 0,
        "thin_z_lt_2cm": 365,
        "thin_any_dim_lt_2cm": 795,
        "floating_ground_min_z_gt_0_5m": 0,
        "thin_vertical_wall_candidates": 127,
    }
    assert report["geometry_diagnostics"]["samples"]["thin_z_lt_2cm"][0]["path"] == (
        "/World/stage/Neighborhood/Alley_Ground/SM_AlleyGround/SM_AlleyGround_01"
    )
    assert report["geometry_diagnostics"]["samples"]["thin_vertical_wall_candidates"][0]["path"] == (
        "/World/stage/Neighborhood/Fences/SM_Fence_04/SM_Fence_04/Section1"
    )
