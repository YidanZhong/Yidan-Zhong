"""Read-only full-map adapter and bounded trajectory audit for Nav2 diagnostics."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import shutil
from typing import Any
import numpy as np


def sha(path: Path) -> str:
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):value.update(chunk)
    return value.hexdigest()


def load_map(manifest_path: Path, output: Path, center: list[float], goals: list[list[float]]) -> dict[str,Any]:
    from PIL import Image
    import yaml
    config=json.loads(manifest_path.read_text(encoding='utf-8'))
    for name,entry in config['files'].items():
        if sha(Path(entry['path']))!=entry['sha256']:raise ValueError(f'Full-map input hash mismatch: {name}')
    source=Path(config['files']['map_yaml']['path'])
    metadata=yaml.safe_load(source.read_text())
    if metadata['resolution']!=.05 or metadata.get('negate',0)!=0:raise ValueError('Unexpected map encoding')
    pgm=Path(config['files']['map_pgm']['path'])
    if (source.parent/metadata['image']).resolve()!=pgm.resolve():raise ValueError('Map YAML image mismatch')
    image=np.asarray(Image.open(pgm));mask=image[::-1]==254
    if list(mask.shape)!=config['grid']['shape']:raise ValueError('Full-map dimensions differ')
    origin=metadata['origin'][:2];res=metadata['resolution']
    for label,point in [('spawn',center)]+[(f'goal-{i}',p) for i,p in enumerate(goals)]:
        col,row=np.floor((np.asarray(point)-origin)/res).astype(int)
        if not (3<=row<mask.shape[0]-3 and 3<=col<mask.shape[1]-3) or not mask[row-3:row+4,col-3:col+4].all():
            raise ValueError(f'{label} lacks center-map clearance')
    shutil.copy2(pgm,output/'local-map.pgm')
    metadata['image']='local-map.pgm'
    (output/'local-map.yaml').write_text(yaml.safe_dump(metadata,sort_keys=False),encoding='utf-8')
    Image.fromarray(image).resize((1558,827),Image.Resampling.NEAREST).save(output/'local-map.png')
    result={'method':'checksum-pinned full PhysX terrain, footprint sweep and selected reach component',
        'scope':'unreviewed_full_map_diagnostic','resolution_m':res,'width':mask.shape[1],'height':mask.shape[0],
        'origin':origin,'occupied_cells':int((~mask).sum()),'free_cells':int(mask.sum()),'unknown_cells':0,
        'reviewed':False,'scene_sha256':config['scene_sha256'],'source_manifest_sha256':sha(manifest_path),
        'source_map_pgm_sha256':sha(pgm),'config':config,
        'limitations':'center-space conservative map; no formal GT/localization or global-route coverage acceptance'}
    (output/'map-evidence.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


def geometry(output: Path, info: dict[str,Any], points: list[list[float]]) -> dict[str,Any]:
    """Exact point-to-raw-obstacle-cell distance within 2 m; cap larger distances conservatively."""
    from PIL import Image
    res=info['resolution_m'];origin=np.asarray(info['origin']);xy=np.asarray(points)[:,:2]
    raw=np.load(info['config']['files']['obstacle']['path'],mmap_mode='r')
    support=np.load(info['config']['files']['support']['path'],mmap_mode='r')
    indices=np.floor((xy-origin)/res).astype(int)
    c0,r0=np.maximum(0,np.floor((xy.min(axis=0)-2-origin)/res).astype(int))
    c1,r1=np.minimum([raw.shape[1],raw.shape[0]],np.ceil((xy.max(axis=0)+2-origin)/res).astype(int)+1)
    blocked=np.asarray(raw[r0:r1,c0:c1])|~np.asarray(support[r0:r1,c0:c1])
    cells=np.argwhere(blocked)
    centers=origin+(cells[:,::-1]+[c0,r0]+.5)*res
    minimum=2.
    for offset in range(0,len(xy),64):
        if not len(centers):break
        delta=np.maximum(np.abs(xy[offset:offset+64,None,:]-centers[None,:,:])-res/2,0)
        minimum=min(minimum,float(np.sqrt((delta*delta).sum(axis=2)).min()))
    selected=np.asarray(Image.open(output/'local-map.pgm'))[::-1]
    outside=occupied=center_map_blocked=0
    for col,row in indices:
        if not (0<=row<raw.shape[0] and 0<=col<raw.shape[1]):outside+=1;continue
        occupied+=int(raw[row,col] or not support[row,col])
        center_map_blocked+=int(selected[row,col]!=254)
    return {'min_center_clearance_m':minimum,
        'min_circumscribed_footprint_clearance_m':minimum-math.hypot(.508/2,.430/2),
        'center_samples_on_obstacles':occupied,'center_samples_unknown_or_outside':outside,
        'center_samples_outside_selected_map':center_map_blocked,
        'clearance_method':'distance to raw obstacle/unsupported cell rectangles, conservatively capped at 2 m'}
