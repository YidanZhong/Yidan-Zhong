"""Geometry boundary checks; these tests do not establish target ownership."""
from pathlib import Path
import math
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_annotation_mesh_faces import face_candidates


class FaceCandidates(unittest.TestCase):
    def test_crossing_polygon_is_not_wholly_owned(self):
        points=np.asarray([[-.2,0,0],[.2,0,0],[0,.3,0],[-2,-2,0],[2,-2,0],[0,4,0],
                           [3,3,0],[4,3,0],[3,4,0]])
        box={'center_xyz_m':[0,0,0],'size_xyz_m':[2,2,2],'orientation_rpy_rad':[0,0,0]}
        result=face_candidates(points,np.array([3,3,3]),np.arange(9),box)
        self.assertEqual(result['all_vertices_inside'].tolist(),[0])
        self.assertEqual(result['vertex_mean_inside'].tolist(),[0,1])
        self.assertEqual(result['aabb_overlap_broad_phase'].tolist(),[0,1])

    def test_world_translation_and_yaw_do_not_change_membership(self):
        points=np.asarray([[10,21.4,0],[10,21.6,0],[9.8,21.5,0],
                           [11.4,20,0],[11.6,20,0],[11.5,20.2,0]])
        box={'center_xyz_m':[10,20,0],'size_xyz_m':[4,2,2],'orientation_rpy_rad':[0,0,math.pi/2]}
        result=face_candidates(points,np.array([3,3]),np.arange(6),box)
        self.assertEqual(result['all_vertices_inside'].tolist(),[0])
        with self.assertRaisesRegex(ValueError,'topology'):
            face_candidates(points,np.array([3]),np.array([0,1,99]),box)


if __name__=='__main__':unittest.main()
