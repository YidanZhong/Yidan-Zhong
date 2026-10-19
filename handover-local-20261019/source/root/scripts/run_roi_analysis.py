#!/usr/bin/env python3
"""LFT-W02 Phase A/B entry, invoked through run_non_global_env.sh.

Use --phase prepare|raycast|analyze|propose. Docker creation must already be
authorized by the user; raycast uses the existing 4.5.0 image, GPU isolation and
workspace caches. No scene move is applied by this runner.
"""
from __future__ import annotations

import argparse
import ast
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import numpy as np

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/"benchmark"))
from airground_benchmark.ground_truth import GroundTruthError, load_target_annotations
from airground_benchmark.lftw02 import collect_gpu_preflight
from airground_benchmark.roi_analysis import annotation_roi, sha256, snapped_roi, write_json
from airground_benchmark.scenes import is_paper_class, scene_slug


def scene_inputs(targets: Path, scene_usd: Path | None, resolution: float) -> tuple[str, Path, str]:
    manifest=load_target_annotations(targets)
    scene=scene_usd or REPO/'AirStack/scenes'/manifest.scene_id/(manifest.scene_id+'_Export.usd')
    scene=scene.resolve()
    if not scene.is_relative_to(REPO):
        raise GroundTruthError('Docker scene asset must be inside the mounted repository')
    if not np.isfinite(resolution) or resolution<=0:
        raise GroundTruthError('Resolution must be finite and positive')
    precision=max(2,len(str(resolution).partition('.')[2]))
    stem=f"{scene_slug(manifest.scene_id).replace('-','_')}_gt_aabb_{resolution:.{precision}f}".replace('.','p')
    return manifest.scene_id,scene,stem


def run(command: list[str], output: Path) -> None:
    logging.info("Running %s",command)
    with output.open("w",encoding="utf-8") as stream:
        result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,check=False)
    if result.returncode: raise GroundTruthError(f"command exited {result.returncode}; see {output}")


def host_sample(gpu: str) -> dict[str, Any]:
    memory={line.split(":")[0]:int(line.split()[1])*1024 for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith(("MemTotal:","MemAvailable:"))}
    used,total=map(float,subprocess.check_output(["nvidia-smi",f"--id={gpu}","--query-gpu=memory.used,memory.total","--format=csv,noheader,nounits"],text=True).strip().split(","))
    failures=[]
    if memory["MemAvailable"] < 64*1024**3: failures.append("available_host_RAM_below_64GiB")
    if 1-memory["MemAvailable"]/memory["MemTotal"] > .9: failures.append("host_memory_fraction_above_0.90")
    if used/total > .85: failures.append("GPU_memory_fraction_above_0.85")
    return {"available_memory_bytes":memory["MemAvailable"],"gpu_memory_fraction":used/total,"failures":failures}


def validate_mapping_runtime(execution: dict[str, Any], log_text: str, *, diagnostic: bool = False) -> dict[str, Any]:
    if execution.get("status")!="ok" or execution.get("exit_code")!=0 or execution.get("guard_failed") is not False:
        raise GroundTruthError("mapping requires successful guarded real raycast evidence")
    if diagnostic:
        return {"status":"diagnostic_only","ground_support_policy":"original_terrain_not_runtime_equivalent"}
    if execution.get("runtime_environment",{}).get("AIRGROUND_ENABLE_GROUND_SUPPORT_PLANE")!="true":
        raise GroundTruthError("ground support plane differs from runtime; use explicit diagnostic mode or reraycast")
    observed=None
    marker="AirGround ground support plane ensured: "
    for line in log_text.splitlines():
        if marker in line:
            try: observed=ast.literal_eval(line.split(marker,1)[1])
            except (ValueError,SyntaxError) as exc: raise GroundTruthError("invalid ground support observation") from exc
    if not isinstance(observed,dict) or observed.get("status")!="ok" or observed.get("geometry")!="plane" or observed.get("top_z_m")!=0.0 or observed.get("collision_enabled_after_create") is not True:
        raise GroundTruthError("raycast log does not prove the runtime z=0 support plane exists")
    return {"status":"ok","ground_support_policy":"match_runtime_z0_support_plane","observed":observed}


def validate_cuda_evidence(output: Path, execution: dict[str, Any], targets: Path | None=None) -> None:
    command=execution.get("command",[])
    if "--backend" not in command or command[command.index("--backend")+1]!="warp":
        return
    try:
        backend=json.loads((output/"raycast_backend.json").read_text())
        comparison=json.loads((output/"gpu_physx_comparison.json").read_text())
        navigation=json.loads((output/"gpu_navigation_comparison.json").read_text())
    except (OSError,ValueError) as exc:
        raise GroundTruthError("CUDA artifact is missing real query/comparison evidence") from exc
    checksum=sha256(output/"raycast_seed.npz")
    if backend.get("backend")!="warp_cuda" or backend.get("device")!="cuda:0" or backend.get("cpu_scene_query_count_generation")!=0:
        raise GroundTruthError("CUDA generation must use the single visible GPU without CPU fallback")
    if backend.get("npz_sha256")!=checksum or comparison.get("gpu_npz_sha256")!=checksum:
        raise GroundTruthError("CUDA comparison does not bind this artifact checksum")
    if backend.get("geometry_source")!="live_physx_scene_repx":
        raise GroundTruthError("CUDA navigation requires actual live PhysX collision shapes")
    if navigation.get("inputs_sha256",{}).get("candidate_npz")!=checksum:
        raise GroundTruthError("CUDA navigation comparison checksum mismatch")
    topology=navigation.get("topology",{})
    expected_count=31
    if targets is not None:
        manifest=load_target_annotations(targets)
        expected_ids=sorted(t.instance_id for t in manifest.instances if is_paper_class(manifest.scene_id,t.semantic_class))
        if (not expected_ids or navigation.get('scene_id')!=manifest.scene_id or
            navigation.get('inputs_sha256',{}).get('targets')!=sha256(targets) or
            sorted(t.get('instance_id','') for t in navigation.get('targets',[]))!=expected_ids):
            raise GroundTruthError('CUDA target scene/hash/identity mismatch')
        expected_count=len(expected_ids)
        if manifest.scene_id=='RetroNeighborhood' and expected_count!=31:
            raise GroundTruthError('Retro requires 31 paper targets')
    if (navigation.get("status")!="ok" or
        navigation.get("acceptance_rule")!="navigation_safety_and_component_correspondence_v2" or
        navigation.get("safety",{}).get("unsafe_navigation_cells")!=0 or
        topology.get("status")!="ok" or
        any(topology.get(key)!=[] for key in ("reference_components_split","candidate_components_merged","reference_components_missing","candidate_components_added")) or
        navigation.get("selection",{}).get("same_region") is not True or
        navigation.get("target_count")!=expected_count or len(navigation.get("targets",[]))!=expected_count or
        navigation.get("changed_target_ids")!=[] or
        any(row.get("same_membership") is not True for row in navigation.get("targets",[]))):
        raise GroundTruthError("CUDA map has unsafe navigation cells or different connectivity/target membership")


def raycast(args: Any, roi: dict[str, Any], output: Path) -> None:
    rendering = args.phase == "render-target"
    if not args.gpu.isdecimal(): raise GroundTruthError("exactly one explicit integer GPU is required")
    preflight=collect_gpu_preflight(isaac_gpu=args.gpu,rayfronts_device="cpu")
    write_json(output/"gpu_preflight.json",preflight)
    if preflight["status"]!="ok": raise GroundTruthError("GPU preflight failed")
    initial=host_sample(args.gpu)
    if initial["failures"]: raise GroundTruthError(f"host guard failed: {initial['failures']}")
    image=json.loads(subprocess.check_output(["docker","image","inspect",args.image],text=True))[0]
    env=dict(item.split("=",1) for item in image["Config"]["Env"] if "=" in item)
    driver=subprocess.check_output(["nvidia-smi",f"--id={args.gpu}","--query-gpu=driver_version","--format=csv,noheader"],text=True).strip()
    floor=env.get("MIN_DRIVER_VERSION")
    if not floor or tuple(map(int,driver.split("."))) < tuple(map(int,floor.split("."))):
        raise GroundTruthError("host driver does not meet selected image floor")
    scene_id,scene,_=scene_inputs(args.targets,args.scene_usd,args.resolution_m)
    if not scene.exists(): raise GroundTruthError(f"missing scene: {scene}")
    container=f"airground-roi-{output.name.lower().replace('_','-')}"
    # HOME is isolated by the wrapper; infer the workspace from the repo instead.
    cache_root=REPO.parent/"docker"
    cache_mounts=[("cache/main","/isaac-sim/.cache"),("cache/computecache","/isaac-sim/.nv/ComputeCache"),("logs","/isaac-sim/.nvidia-omniverse/logs"),("config","/isaac-sim/.nvidia-omniverse/config"),("data","/isaac-sim/.local/share/ov/data"),("pkg","/isaac-sim/.local/share/ov/pkg")]
    command=["docker","run","--name",container,"--gpus",f"device={args.gpu}","--cpus","30","--memory","48g","--memory-swap","48g","--pids-limit","2048","--network","host","--entrypoint","/bin/bash"]
    for source,target in [(REPO,"/workspace"),(REPO/"AirStack","/isaac-sim/AirStack"),(REPO/"assets/cache","/isaac-sim/AirGroundAssets"),(REPO/"assets/cache","/isaac-sim/assets/cache"),(REPO/"AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator","/isaac-sim/.local/share/ov/data/documents/Kit/shared/exts/pegasus.simulator")]:
        command += ["-v",f"{source}:{target}:ro" if source!=REPO else f"{source}:{target}:rw"]
    for source,target in cache_mounts:
        directory=cache_root/"isaac-sim"/source; directory.mkdir(parents=True,exist_ok=True)
        command += ["-v",f"{directory}:{target}:rw"]
    runtime_env={"ACCEPT_EULA":"Y","PRIVACY_CONSENT":"Y","NVIDIA_VISIBLE_DEVICES":args.gpu,"NVIDIA_DRIVER_CAPABILITIES":"all","OMNI_KIT_ALLOW_ROOT":"1","ROS_DISTRO":"humble","ISAAC_SIM_ROS_PACKAGE":"isaacsim","ISAAC_SIM_KIT_VERSION":"4.5","ISAAC_VERSION":"4.5.0","AIRGROUND_BENCHMARK_PACKAGE":"/workspace/benchmark/airground_benchmark","AIRGROUND_ASSET_ROOT":"/isaac-sim/AirGroundAssets/6.0.1","AIRGROUND_ENV_URL":str(Path("/workspace")/scene.relative_to(REPO)),"AIRGROUND_HEADLESS":"true","AIRGROUND_RENDER":"false","AIRGROUND_SCENE_COLLIDER_MODE":"profiled","AIRGROUND_ENABLE_GROUND_SUPPORT_PLANE":"false" if args.diagnostic_no_ground_support_plane else "true","AIRGROUND_ENABLE_SENSOR_GRAPHS":"false","AIRGROUND_ENABLE_UAV_STATE_PUBLISHERS":"false","AIRGROUND_ENABLE_UGV_STATE_PUBLISHERS":"false","AIRGROUND_ENABLE_UGV_CONTACT_PUBLISHER":"false","AIRGROUND_UAV_PX4_AUTOLAUNCH":"false","AIRGROUND_CREATE_DOCK_JOINT":"false","AIRGROUND_ALIGN_UAV_TO_DOCK":"false","PLAY_SIM_ON_START":"false"}
    if rendering:
        runtime_env["AIRGROUND_RENDER"] = "true"
    for key,value in runtime_env.items(): command += ["-e",f"{key}={value}"]
    container_output=Path("/workspace")/output.relative_to(REPO)
    command += [args.image,"/isaac-sim/python.sh","/isaac-sim/AirStack/simulation/isaac-sim/tools/generate_traversability_raycast.py","--backend",args.backend,"--origin-x-m",str(roi["origin_xy_m"][0]),"--origin-y-m",str(roi["origin_xy_m"][1]),"--rows",str(roi["shape"][0]),"--cols",str(roi["shape"][1]),"--resolution-m",str(roi["resolution_m"]),"--ray-start-z-m","8.0","--ray-end-z-m","-2.0","--min-ground-normal-z","0.35","--obstacle-band-min-height-m","0.05","--obstacle-band-max-height-m","1.0","--settle-steps","5","--output-metadata",str(container_output/"raycast_metadata.json"),"--output-npz",str(container_output/"raycast_seed.npz"),"--output-summary",str(container_output/"raycast_summary.json")]
    if rendering:
        if not args.render_prim:
            raise GroundTruthError("render-target requires --render-prim")
        command = command[:command.index(args.image)] + [args.image, "/isaac-sim/python.sh",
            "/isaac-sim/AirStack/simulation/isaac-sim/tools/render_prim_snapshot.py",
            "--scene", runtime_env["AIRGROUND_ENV_URL"], "--prim", args.render_prim,
            "--output-dir", str(container_output)]
    else:
        command += ['--scene-id',scene_id,'--scene-usd',runtime_env['AIRGROUND_ENV_URL']]
    if args.reference_run:
        reference=args.reference_run.resolve()
        reference_execution=json.loads((reference/"raycast_execution.json").read_text())
        validate_mapping_runtime(reference_execution,(reference/"raycast.log").read_text())
        if reference_execution["roi"]["shape"] != roi["shape"] or reference_execution["roi"]["origin_xy_m"] != roi["origin_xy_m"] or reference_execution["roi"]["resolution_m"] != roi["resolution_m"]:
            raise GroundTruthError("reference run must have exactly the same grid")
        if reference_execution["scene_sha256"] != sha256(scene):
            raise GroundTruthError("reference scene checksum mismatch")
        command += ["--reference-npz",str(Path("/workspace")/reference.relative_to(REPO)/"raycast_seed.npz")]
    if args.verify_physx: command += ["--verify-physx"]
    if args.save_repx: command += ["--save-repx"]
    for x,y in args.query_world or []: command += ["--query-world",str(x),str(y)]
    evidence={"schema_version":"1.0.0","simulator_version":"4.5.0","ros_distro":"humble","container":container,"image":args.image,"image_id":image["Id"],"driver":driver,"min_driver_version":floor,"scene_sha256":sha256(scene),"source_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO,text=True).strip(),"command":command,"runtime_environment":runtime_env,"roi":roi,"asset_provenance":"pinned 6.0 payload compatibility input for 4.5; actual cache path recorded","ros_evidence":"not applicable: static PhysX scene-query; no ROS mission or scoring run"}
    evidence["scene_id"]=scene_id
    evidence["targets_sha256"]=sha256(args.targets)
    evidence["ground_support_policy"]="diagnostic_original_terrain_only" if args.diagnostic_no_ground_support_plane else "match_runtime_z0_support_plane"
    evidence_name = "render_execution.json" if rendering else "raycast_execution.json"
    log_name = "render.log" if rendering else "raycast.log"
    if rendering:
        evidence.update(operation="static_prim_render", ros_evidence="not applicable: USD RGB review, no ROS mission", ground_support_policy="not applicable: target appearance review")
    write_json(output/evidence_name,evidence)
    failures=0; guard_failed=False
    started=time.monotonic()
    with (output/log_name).open("w") as log,(output/"resource_guard.jsonl").open("w") as samples:
        process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        try:
            while process.poll() is None:
                sample=host_sample(args.gpu); sample["diagnostic_elapsed_wall_s"]=round(time.monotonic()-started,3)
                samples.write(json.dumps(sample,sort_keys=True)+"\n"); samples.flush()
                failures=failures+1 if sample["failures"] else 0
                if failures>=2 or time.monotonic()-started > args.timeout:
                    guard_failed=True
                    subprocess.run(["docker","stop","--time","10",container],check=False,stdout=log,stderr=log)
                    break
                time.sleep(1)
            exit_code=process.wait(timeout=30)
        finally:
            if process.poll() is None:
                subprocess.run(["docker","stop","--time","10",container],check=False,stdout=log,stderr=log)
    evidence.update({"exit_code":exit_code,"guard_failed":guard_failed,"elapsed_wall_s":round(time.monotonic()-started,3),"status":"ok" if exit_code==0 and not guard_failed else "failed"})
    required = ('snapshot_report.json', 'front_oblique.png', 'rear_oblique.png') if rendering else ('raycast_seed.npz','raycast_metadata.json','raycast_backend.json')
    if evidence['status']=='ok' and args.backend!='probe' and not all((output/name).is_file() for name in required):
        evidence.update({'status':'failed','failure_reason':'generator_did_not_write_required_artifacts'})
    write_json(output/evidence_name,evidence)
    if evidence["status"]!="ok": raise GroundTruthError(f"execution failed; see {output/log_name}")
    if not rendering and args.backend=="warp" and (args.reference_run or args.verify_physx):
        validation=[sys.executable,str(REPO/"scripts/validate_gpu_navigation.py"),"--run-dir",str(output),"--targets",str(args.targets)]
        validation += ["--reference-run",str(args.reference_run)] if args.reference_run else ["--same-live-scene"]
        run(validation,output/"navigation_validation.log")


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase",choices=("prepare","raycast","analyze","propose","render-target"),required=True)
    parser.add_argument("--render-prim",help="existing prim path for a static RGB inspection")
    parser.add_argument("--targets",type=Path,required=True)
    parser.add_argument('--scene-usd',type=Path,help='Scene asset inside the repository; default follows target scene_id')
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--gpu",default="0")
    parser.add_argument("--backend",choices=("physx","warp","probe"),default="warp")
    parser.add_argument("--resolution-m",type=float,default=.05)
    parser.add_argument("--reference-run",type=Path)
    parser.add_argument("--verify-physx",action="store_true")
    parser.add_argument("--save-repx",action="store_true")
    parser.add_argument("--query-world",nargs=2,type=float,action="append")
    parser.add_argument("--roi-json",type=Path,help="explicit diagnostic/verification grid; no default ROI change")
    parser.add_argument("--verification-window",nargs=4,type=float,metavar=("XMIN","YMIN","XMAX","YMAX"),help="diagnostic grid, snapped to requested resolution")
    parser.add_argument("--image",default="airlab-docker.andrew.cmu.edu/airstack/airstack:v0.16.2_isaac-sim-4.5.0")
    parser.add_argument("--timeout",type=float,default=10800)
    parser.add_argument("--starts",type=Path,action="append")
    parser.add_argument("--diagnostic-no-ground-support-plane",action="store_true",help="diagnostic only: differs from runtime/old GT; never use for final ROI acceptance")
    args=parser.parse_args(argv)
    if not REPO.is_relative_to(Path("/home/LFT-W02/jun")):
        raise GroundTruthError("ROI execution is restricted to the LFT-W02 ~/jun workspace")
    # The isolated HOME deliberately omits the user's Docker context. Keep
    # using the already authorized rootless daemon, as the benchmark wrapper
    # does, rather than silently reaching the system daemon.
    os.environ.setdefault("DOCKER_HOST", f"unix:///run/user/{os.getuid()}/docker.sock")
    output=args.output_dir.resolve()
    if not output.is_relative_to(REPO/"runs"): raise GroundTruthError("ROI artifacts must live in repository runs/")
    output.mkdir(parents=True,exist_ok=True)
    scene_id,scene,stem=scene_inputs(args.targets,args.scene_usd,args.resolution_m)
    roi=annotation_roi(load_target_annotations(args.targets),resolution_m=args.resolution_m)
    if args.verification_window:
        x0,y0,x1,y1=args.verification_window
        if x0>=x1 or y0>=y1: raise GroundTruthError("verification window must have positive area")
        if args.roi_json: raise GroundTruthError("choose window or ROI file")
        roi=snapped_roi(np.array([[x0,y0,0],[x1,y1,0]]),margin_m=0,resolution_m=args.resolution_m)
        roi["basis"]="diagnostic_verification_window"
    if args.roi_json:
        roi=json.loads(args.roi_json.read_text())
        if roi["resolution_m"] != args.resolution_m: raise GroundTruthError("ROI resolution differs from requested resolution")
    write_json(output/"gt_aabb_roi.json",roi)
    python=str(REPO/".venv/bin/python"); cli=str(REPO/".venv/bin/airground")
    if args.phase in ("raycast", "render-target"): raycast(args,roi,output)
    elif args.phase=="analyze":
        execution=json.loads((output/"raycast_execution.json").read_text())
        validate_cuda_evidence(output,execution,args.targets)
        validation=validate_mapping_runtime(execution,(output/"raycast.log").read_text(),diagnostic=args.diagnostic_no_ground_support_plane)
        validation["raycast_execution_sha256"]=sha256(output/"raycast_execution.json")
        write_json(output/"mapping_runtime_validation.json",validation)
        sweep=output/"footprint_sweep"; package=output/"package"; reach=output/"reach"
        run([cli,"gt","traversability","validate","--metadata",str(output/"raycast_metadata.json"),"--npz",str(output/"raycast_seed.npz")],output/"raycast_validate.json")
        run([cli,"gt","traversability","sweep-footprint","--metadata",str(output/"raycast_metadata.json"),"--npz",str(output/"raycast_seed.npz"),"--output-dir",str(sweep),"--stem",stem,"--max-step-height","0.05","--yaw-samples","16"],output/"sweep.log")
        run([cli,"gt","traversability","package","--metadata",str(sweep/f"{stem}.metadata.yaml"),"--npz",str(sweep/f"{stem}.npz"),"--output-dir",str(package),"--stem",stem],output/"package.log")
        run([cli,"gt","traversability","validate","--metadata",str(package/f"{stem}.metadata.yaml"),"--npz",str(package/f"{stem}.npz")],output/"package_validate.json")
        run([cli,"gt","traversability","reach-region","--metadata",str(package/f"{stem}.metadata.yaml"),"--npz",str(package/f"{stem}.npz"),"--output-dir",str(reach),"--stem",stem],output/"reach.log")
        run([python,str(REPO/"scripts/roi_component_report.py"),"--targets",str(args.targets),"--metadata",str(reach/"package"/f"{stem}.metadata.yaml"),"--npz",str(reach/"package"/f"{stem}.npz"),"--base-metadata",str(package/f"{stem}.metadata.yaml"),"--base-npz",str(package/f"{stem}.npz"),"--output-dir",str(output/"component_report")],output/"component_report.log")
    elif args.phase=="propose":
        if not args.starts: parser.error("--phase propose requires --starts")
        command=[python,str(REPO/"scripts/propose_object_moves.py"),"--targets",str(args.targets),"--component-report",str(output/"component_report/component_report.json"),"--npz",str(output/"reach/package"/f"{stem}.npz"),"--base-npz",str(output/"package"/f"{stem}.npz"),"--metadata",str(output/"reach/package"/f"{stem}.metadata.yaml"),"--scene-usd",str(scene),"--output-dir",str(output/"movement_review")]
        for path in args.starts: command += ["--starts",str(path)]
        run(command,output/"movement_review.log")
    return 0


if __name__=="__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
