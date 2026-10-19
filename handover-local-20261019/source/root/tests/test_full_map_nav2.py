"""Offline map-contract checks, not a replacement for Isaac/ROS validation."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from probe_full_map_nav2 import load_map, geometry, sha


class FullMapChecks(unittest.TestCase):
    def fixture(self, root):
        image=np.full((80,100),254,dtype=np.uint8)
        image[59,20]=0
        Image.fromarray(image).save(root/'map.pgm')
        (root/'map.yaml').write_text('image: map.pgm\nresolution: 0.05\norigin: [0.0, 0.0, 0.0]\nnegate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n')
        raw=np.zeros((80,100),dtype=bool);raw[20,20]=True
        np.save(root/'obstacle.npy',raw);np.save(root/'support.npy',np.ones_like(raw))
        config={'scene_sha256':'fixture','grid':{'shape':[80,100]},'files':{}}
        for name,file in {'map_yaml':'map.yaml','map_pgm':'map.pgm','obstacle':'obstacle.npy','support':'support.npy'}.items():
            config['files'][name]={'path':str(root/file),'sha256':sha(root/file)}
        manifest=root/'manifest.json';manifest.write_text(json.dumps(config))
        output=root/'output';output.mkdir()
        return manifest,output

    def test_orientation_and_exact_cell_rectangle_clearance(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);manifest,output=self.fixture(root)
            info=load_map(manifest,output,[2.,2.],[[3.,2.]])
            blocked=geometry(output,info,[[1.025,1.025]])
            self.assertEqual(blocked['center_samples_on_obstacles'],1)
            self.assertEqual(blocked['center_samples_outside_selected_map'],1)
            self.assertEqual(blocked['min_center_clearance_m'],0.)
            clear=geometry(output,info,[[1.55,1.025]])
            self.assertAlmostEqual(clear['min_center_clearance_m'],.5)
            self.assertEqual(clear['center_samples_outside_selected_map'],0)

    def test_modified_input_is_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);manifest,output=self.fixture(root)
            with (root/'map.pgm').open('ab') as stream:stream.write(b'changed')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):
                load_map(manifest,output,[2.,2.],[[3.,2.]])
            self.assertFalse((output/'local-map.pgm').exists())

    def test_goal_near_blocked_cell_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);manifest,output=self.fixture(root)
            with self.assertRaisesRegex(ValueError,'goal-0'):
                load_map(manifest,output,[2.,2.],[[1.1,1.025]])


if __name__=='__main__':unittest.main()
