"""Navigation safety and component correspondence for generated GT maps.

Raw fields are diagnostic. Boundary sampling differences are accepted only
with independent footprint collision, step, normal and headroom evidence;
the component partition, selection and target memberships must stay equal.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from .ground_truth import GroundTruthError, TargetAnnotationManifest, TraversabilityMetadata
from .roi_analysis import arrival_mask
from .scenes import is_paper_class
from .traversability import build_reach_region


def compare_component_partition(reference: np.ndarray, candidate: np.ndarray) -> dict[str, Any]:
    """Compare shared cell connectivity independently of arbitrary label IDs."""
    if reference.ndim!=2 or reference.shape!=candidate.shape:
        raise GroundTruthError('navigation component grids must have the same 2D shape')
    nr=int(reference.max())+1; ng=int(candidate.max())+1
    shared=(reference>=0)&(candidate>=0)
    if nr==0 or ng==0:
        raise GroundTruthError('navigation comparison requires nonempty reachable maps')
    codes=reference[shared].astype(np.int64)*ng+candidate[shared]
    pairs,counts=np.unique(codes,return_counts=True)
    ref_to_gpu={i:[] for i in range(nr)}; gpu_to_ref={i:[] for i in range(ng)}
    overlaps=[]
    for code,count in zip(pairs,counts):
        r,g=divmod(int(code),ng)
        ref_to_gpu[r].append(g); gpu_to_ref[g].append(r)
        overlaps.append({'reference_component':r,'candidate_component':g,'shared_cells':int(count)})
    split=[r for r,ids in ref_to_gpu.items() if len(ids)>1]
    merged=[g for g,ids in gpu_to_ref.items() if len(ids)>1]
    missing=[r for r,ids in ref_to_gpu.items() if not ids]
    added=[g for g,ids in gpu_to_ref.items() if not ids]
    return {'status':'ok' if not (split or merged or missing or added) else 'different',
            'reference_component_count':nr,'candidate_component_count':ng,
            'reference_components_split':split,'candidate_components_merged':merged,
            'reference_components_missing':missing,'candidate_components_added':added,
            'candidate_to_reference':{str(g):ids[0] for g,ids in gpu_to_ref.items() if len(ids)==1},
            'overlaps':overlaps}


def compare_navigation_maps(reference: np.ndarray, candidate: np.ndarray,
                            metadata: TraversabilityMetadata,
                            manifest: TargetAnnotationManifest, *, expected_targets: int | None=None,
                            reference_physical_footprint: np.ndarray | None=None) -> dict[str, Any]:
    if manifest.scene_id!=metadata.scene_id:
        raise GroundTruthError('target and navigation map scenes differ')
    if expected_targets is None and manifest.scene_id=='RetroNeighborhood':
        expected_targets=31
    if reference.shape!=metadata.shape or candidate.shape!=metadata.shape:
        raise GroundTruthError('navigation mask shape does not match metadata')
    reference=np.asarray(reference,dtype=bool); candidate=np.asarray(candidate,dtype=bool)
    different_free=candidate&~reference
    justified=np.zeros_like(reference)
    if reference_physical_footprint is not None:
        from scipy import ndimage
        if reference_physical_footprint.shape!=reference.shape:
            raise GroundTruthError('physical footprint evidence grid mismatch')
        # A digit-induced edge shift can move the finite-difference slope
        # corner by one cell. Require the full reference footprint to pass
        # actual surface normal, obstacle, step and headroom checks, and stay
        # next to its original free region. Connectivity is checked separately.
        boundary=ndimage.binary_dilation(reference,structure=np.ones((3,3),bool))
        justified=different_free & np.asarray(reference_physical_footprint,dtype=bool) & boundary
    unsafe=different_free&~justified
    removed=reference&~candidate
    ref_reach=build_reach_region(reference,resolution_m=metadata.resolution_m)
    gpu_reach=build_reach_region(candidate,resolution_m=metadata.resolution_m)
    topology=compare_component_partition(ref_reach.reach_component,gpu_reach.reach_component)
    mapping=topology['candidate_to_reference']
    paper=sorted((i for i in manifest.instances if is_paper_class(manifest.scene_id,i.semantic_class)),key=lambda i:i.instance_id)
    if not paper:
        raise GroundTruthError('no paper targets in scene manifest')
    if expected_targets is not None and len(paper)!=expected_targets:
        raise GroundTruthError(f'expected {expected_targets} paper targets, got {len(paper)}')
    ref_counts=[0]*ref_reach.component_count; gpu_counts=[0]*gpu_reach.component_count
    targets=[]
    for instance in paper:
        ids=[]
        for reach,counts in ((ref_reach,ref_counts),(gpu_reach,gpu_counts)):
            window,arrival=arrival_mask(instance.obb,metadata,reach.reach_mask)
            members=np.unique(reach.reach_component[window][arrival]).tolist()
            for component in members: counts[component]+=1
            ids.append(members)
        mapped=[mapping.get(str(g),-1) for g in ids[1]]
        targets.append({'instance_id':instance.instance_id,'reference_components':ids[0],
                        'candidate_components':ids[1],'candidate_mapped_to_reference':sorted(mapped),
                        'same_membership':sorted(mapped)==ids[0]})
    def select(counts: list[int],sizes: tuple[int,...]) -> int:
        return max(range(len(counts)),key=lambda i:(counts[i],sizes[i],-i))
    ref_selected=select(ref_counts,ref_reach.component_cell_counts)
    gpu_selected=select(gpu_counts,gpu_reach.component_cell_counts)
    same_selected=mapping.get(str(gpu_selected))==ref_selected
    target_diff=[row['instance_id'] for row in targets if not row['same_membership']]
    safe=not unsafe.any()
    return {'schema_version':'1.0.0','scene_id':manifest.scene_id,'acceptance_rule':'navigation_safety_and_component_correspondence_v2',
            'status':'ok' if safe and topology['status']=='ok' and same_selected and not target_diff else 'different',
            'raw_height_normal_equality_required':False,
            'safety':{'status':'ok' if safe else 'different','candidate_free_reference_blocked_cells':int(different_free.sum()),
                      'accepted_boundary_sampling_cells':int(justified.sum()),'unsafe_navigation_cells':int(unsafe.sum()),
                      'boundary_sampling_max_distance_m':metadata.resolution_m*2**.5,
                      'conservative_removed_cells':int(removed.sum()),
                      'first_candidate_free_reference_blocked_cell_indices':np.argwhere(different_free)[:32].tolist(),
                      'first_accepted_boundary_cell_indices':np.argwhere(justified)[:32].tolist(),
                      'first_unsafe_cell_indices':np.argwhere(unsafe)[:32].tolist()},
            'topology':topology,'reach_rule':ref_reach.summary(),
            'selection':{'reference_component':ref_selected,'candidate_component':gpu_selected,'same_region':same_selected},
            'target_count':len(targets),'changed_target_ids':target_diff,'targets':targets,
            'scope':'static footprint and reach graph; does not certify a ROS/Nav2 drive or authorize Phase C scene moves'}
