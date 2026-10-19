"""Route topology and safety regressions independent of raw raycast equality."""
from __future__ import annotations

import numpy as np
import pytest

from airground_benchmark.ground_truth import GroundTruthError, OrientedBoundingBox, TargetAnnotationManifest, TargetInstance, TraversabilityMetadata
from airground_benchmark.navigation_map_validation import compare_component_partition, compare_navigation_maps


def fixture(shape: tuple[int,int]) -> tuple[TraversabilityMetadata,TargetAnnotationManifest]:
    metadata=TraversabilityMetadata.model_validate({'schema_version':'1.0.0','scene_id':'RetroNeighborhood','frame':'map','origin':{'x_m':0,'y_m':0,'z_m':0},'resolution_m':.1,'shape':shape,'generator':'test','generator_version':'test'})
    target=TargetInstance(instance_id='RetroNeighborhood.yellow_car.0000',semantic_class='yellow car',source_class='yellow car',source_index=0,usd_prim_path='/World/car',obb=OrientedBoundingBox(frame='map',center_xyz_m=(3,3,.5),size_xyz_m=(1,1,1),orientation_rpy_rad=(0,0,0)))
    manifest=TargetAnnotationManifest(schema_version='1.0.0',scene_id='RetroNeighborhood',frame='map',source_format='raven_obb_json',source_path='test',instances=(target,))
    return metadata,manifest


def test_component_numbers_are_not_region_identities() -> None:
    reference=np.array([[0,0,-1,1,1],[0,0,-1,1,1]])
    candidate=np.array([[1,1,-1,0,0],[1,1,-1,0,0]])
    report=compare_component_partition(reference,candidate)
    assert report['status']=='ok'
    assert report['candidate_to_reference']=={'0':1,'1':0}


def test_small_barrier_splitting_a_corridor_fails_even_with_high_overlap() -> None:
    reference=np.zeros((100,100),dtype=np.int32)
    candidate=reference.copy(); candidate[:,50]=-1; candidate[:,51:]=1
    report=compare_component_partition(reference,candidate)
    assert report['status']=='different'
    assert report['reference_components_split']==[0]


def test_false_opening_merging_regions_is_detected() -> None:
    reference=np.zeros((100,100),dtype=np.int32); reference[:,50]=-1; reference[:,51:]=1
    candidate=np.zeros_like(reference)
    assert compare_component_partition(reference,candidate)['candidate_components_merged']==[0]


def test_conservative_boundary_cells_can_change_without_changing_navigation() -> None:
    ref=np.ones((80,80),bool); ref[:,:2]=False
    gpu=ref.copy();gpu[:,2]=False
    report=compare_navigation_maps(ref,gpu,*fixture(ref.shape),expected_targets=1)
    assert report['status']=='ok'
    assert report['safety']['conservative_removed_cells']==80
    assert report['raw_height_normal_equality_required'] is False


def test_identical_connectivity_does_not_excuse_false_free_obstacle_cells() -> None:
    ref=np.ones((80,80),bool);ref[20,20]=False
    gpu=np.ones_like(ref)
    report=compare_navigation_maps(ref,gpu,*fixture(ref.shape),expected_targets=1)
    assert report['topology']['status']=='ok'
    assert report['safety']['candidate_free_reference_blocked_cells']==1
    assert report['status']=='different'


def test_a_missing_or_added_component_is_not_silently_dropped() -> None:
    ref=np.array([[0,0,-1,1,1]])
    candidate=np.array([[0,0,-1,-1,-1]])
    assert compare_component_partition(ref,candidate)['reference_components_missing']==[1]
    assert compare_component_partition(candidate,ref)['candidate_components_added']==[1]


def test_reference_requires_complete_paper_target_list() -> None:
    grid=np.ones((80,80),bool)
    with pytest.raises(GroundTruthError,match='expected 31'):
        compare_navigation_maps(grid,grid,*fixture(grid.shape))


def test_construction_uses_its_paper_classes_and_rejects_scene_mix() -> None:
    grid=np.ones((80,80),bool)
    meta,old=fixture(grid.shape)
    target=old.instances[0].model_copy(update={'instance_id':'ConstructionSite.biotoilet.0000',
        'semantic_class':'biotoilet','source_class':'biotoilet'})
    manifest=old.model_copy(update={'scene_id':'ConstructionSite','instances':(target,)})
    with pytest.raises(GroundTruthError,match='scenes differ'):
        compare_navigation_maps(grid,grid,meta,manifest)
    report=compare_navigation_maps(grid,grid,meta.model_copy(update={'scene_id':'ConstructionSite'}),manifest)
    assert report['status']=='ok' and report['target_count']==1
    assert report['targets'][0]['instance_id']=='ConstructionSite.biotoilet.0000'


def test_target_membership_uses_boolean_arrival_selection() -> None:
    # Reach masks are serialized as uint8. Integer advanced indexing would
    # select rows 0/1, report blocked (-1), and count the wrong component.
    grid=np.ones((80,80),bool)
    grid[:2,:]=False
    report=compare_navigation_maps(grid,grid,*fixture(grid.shape),expected_targets=1)
    assert report['targets'][0]['reference_components']==[0]
    assert report['targets'][0]['candidate_components']==[0]
    assert report['selection']['reference_component']==0


def test_boundary_sampling_difference_requires_physical_footprint_evidence() -> None:
    reference=np.ones((80,80),bool);reference[30,30]=False
    candidate=np.ones_like(reference)
    physical=np.ones_like(reference)
    report=compare_navigation_maps(reference,candidate,*fixture(reference.shape),expected_targets=1,reference_physical_footprint=physical)
    assert report['status']=='ok'
    assert report['safety']['candidate_free_reference_blocked_cells']==1
    assert report['safety']['accepted_boundary_sampling_cells']==1
    assert report['safety']['unsafe_navigation_cells']==0
    # A real obstacle, excessive step, slope, or low ceiling fails the
    # independently swept physical footprint; it cannot receive this exception.
    physical[30,30]=False
    report=compare_navigation_maps(reference,candidate,*fixture(reference.shape),expected_targets=1,reference_physical_footprint=physical)
    assert report['status']=='different'
    assert report['safety']['unsafe_navigation_cells']==1


def test_physical_evidence_does_not_allow_large_interior_changes_or_merges() -> None:
    reference=np.ones((80,80),bool);reference[20:30,20:30]=False
    candidate=reference.copy();candidate[25,25]=True
    report=compare_navigation_maps(reference,candidate,*fixture(reference.shape),expected_targets=1,reference_physical_footprint=np.ones_like(reference))
    assert report['status']=='different'
    assert report['safety']['accepted_boundary_sampling_cells']==0
    reference=np.ones((80,80),bool);reference[:,40]=False
    report=compare_navigation_maps(reference,np.ones_like(reference),*fixture(reference.shape),expected_targets=1,reference_physical_footprint=np.ones_like(reference))
    assert report['status']=='different'
    assert report['topology']['candidate_components_merged']==[0]
