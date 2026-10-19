"""Disk assembly checks; real scene validation is performed by the diagnostic run."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from resumable_terrain_store import FIELDS,TileStore,dataset_lock
from postprocess_terrain_tiles import stitch, main


class StitchTests(unittest.TestCase):
    def test_existing_output_report_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)
            sentinel=output/'report.json';sentinel.write_text('original evidence')
            argv=['postprocess_terrain_tiles.py']
            for name in ('dataset','output','benchmark-package','targets','reference-dir'):
                argv.extend(['--'+name,str(output)])
            with patch.object(sys,'argv',argv), self.assertRaises(SystemExit) as error:
                main()
            self.assertEqual(error.exception.code,2)
            self.assertEqual(sentinel.read_text(),'original evidence')

    def test_partial_edges_and_every_channel_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'source'
            contract={'grid':{'shape':[5,7],'tile_cells':4,'resolution_m':.05,'origin_xy_m':[0.,0.]}}
            values=np.arange(35,dtype=np.float32).reshape(5,7)
            expected={k:(np.stack((values,values+1,values+2),axis=-1) if k=='normal' else
                         (values%2==0) if dtype=='bool' else values).astype(dtype) for k,dtype in FIELDS.items()}
            with dataset_lock(root):
                store=TileStore(root,contract)
                for tile in reversed(store.tiles):
                    r0,r1,c0,c1=tile['core']
                    store.commit(tile,{k:v[r0:r1,c0:c1] for k,v in expected.items()},{})
                actual,evidence=stitch(store,Path(directory)/'merged')
                self.assertEqual(evidence['cells'],35)
                for key in FIELDS:
                    np.testing.assert_array_equal(actual[key],expected[key])
                    actual[key]._mmap.close()

    def test_incomplete_dataset_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'source'
            with dataset_lock(root):
                store=TileStore(root,{'grid':{'shape':[5,7],'tile_cells':4,'resolution_m':.05,'origin_xy_m':[0.,0.]}})
                output=Path(directory)/'merged'
                with self.assertRaisesRegex(ValueError,'Incomplete'):
                    stitch(store,output)
                self.assertFalse(output.exists())


if __name__=='__main__':
    unittest.main()
