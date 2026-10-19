"""Protect human-review boundaries and scene identity in camera preparation."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_scene_review_manifest import build


class ReviewBoundaryTests(unittest.TestCase):
    def setUp(self):
        base=ROOT/'runs/scene_gt_adaptation_20261017/ConstructionSite'
        if not base.exists():self.skipTest('Local diagnostic inputs are not release fixtures')
        self.inputs=[json.loads((base/name).read_text(encoding='utf-8')) for name in
            ('targets.unreviewed.json','prim_candidates.json','binding.report.json')]

    def test_unbound_instances_get_context_without_fabricated_prim(self):
        original=copy.deepcopy(self.inputs)
        result=build(*self.inputs,'a'*64)
        missing=[r for r in result['rows'] if r['candidate'] is None]
        self.assertEqual(len(missing),3)
        self.assertEqual(result['view_count'],56)
        self.assertTrue(all(r['target']['usd_prim_path'] is None and len(r['views'])==2 for r in missing))
        self.assertEqual(original,self.inputs)

    def test_cross_scene_candidates_rejected(self):
        self.inputs[1]['scene_id']='RetroNeighborhood'
        with self.assertRaisesRegex(ValueError,'Cross-scene'):build(*self.inputs,'a'*64)

    def test_approved_input_cannot_masquerade_as_review_candidate(self):
        self.inputs[0]['instances'][0]['verified']=True
        with self.assertRaisesRegex(ValueError,'unreviewed'):build(*self.inputs,'a'*64)


if __name__=='__main__':unittest.main()
