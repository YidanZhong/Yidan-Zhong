"""Persistence failure checks; real PhysX acceptance is recorded separately."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from resumable_terrain_store import FIELDS, TileStore, dataset_lock


class TilePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.contract={'grid':{'shape':[5,7],'tile_cells':4,'resolution_m':.05,'origin_xy_m':[0.,0.]},'source':'pinned'}
    def tearDown(self): self.tmp.cleanup()
    def arrays(self,tile):
        r0,r1,c0,c1=tile['core'];shape=(r1-r0,c1-c0)
        return {k:np.ones((*shape,3) if k=='normal' else shape,dtype=d) for k,d in FIELDS.items()}
    def test_resume_preserves_committed_tiles_and_covers_grid(self):
        with dataset_lock(self.root):
            store=TileStore(self.root,self.contract);tile=store.tiles[0]
            record=store.commit(tile,self.arrays(tile),{'session':'first'})
        with dataset_lock(self.root):
            resumed=TileStore(self.root,self.contract)
            self.assertEqual(resumed.completed[tile['id']],record)
            coverage=np.zeros((5,7),dtype=int)
            for t in resumed.tiles:
                r0,r1,c0,c1=t['core'];coverage[r0:r1,c0:c1]+=1
            self.assertTrue((coverage==1).all())
            with self.assertRaises(ValueError):resumed.commit(tile,self.arrays(tile),{})
    def test_corrupt_committed_tile_rejected(self):
        with dataset_lock(self.root):
            store=TileStore(self.root,self.contract);tile=store.tiles[0]
            store.commit(tile,self.arrays(tile),{})
            (self.root/'tiles'/(tile['id']+'.npz')).write_bytes(b'truncated')
            with self.assertRaises(ValueError):TileStore(self.root,self.contract)
    def test_contract_change_rejected(self):
        with dataset_lock(self.root):
            TileStore(self.root,self.contract)
            with self.assertRaises(ValueError):TileStore(self.root,{**self.contract,'source':'changed'})
    def test_orphan_npz_is_not_completed(self):
        with dataset_lock(self.root):
            store=TileStore(self.root,self.contract);tile=store.tiles[0]
            (self.root/'tiles'/(tile['id']+'.npz')).write_bytes(b'uncommitted')
            resumed=TileStore(self.root,self.contract)
            self.assertFalse(resumed.completed)
            resumed.commit(tile,self.arrays(tile),{})
            self.assertEqual(len(TileStore(self.root,self.contract).completed),1)
    def test_bad_shape_and_nan_rejected(self):
        with dataset_lock(self.root):
            store=TileStore(self.root,self.contract);tile=store.tiles[0]
            arrays=self.arrays(tile);arrays['height'][0,0]=np.nan
            with self.assertRaises(ValueError):store.commit(tile,arrays,{})
            arrays=self.arrays(tile);arrays['height']=np.ones((1,1),dtype=np.float32)
            with self.assertRaises(ValueError):store.commit(tile,arrays,{})
    def test_concurrent_writer_rejected(self):
        with dataset_lock(self.root):
            with self.assertRaises(OSError):
                with dataset_lock(self.root): pass


if __name__=='__main__':unittest.main()
