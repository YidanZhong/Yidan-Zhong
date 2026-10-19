from pathlib import Path
from html.parser import HTMLParser
import hashlib,json,shutil,zipfile
root=Path(r'D:\xprogram\RAVEN-AirGround-github');run=root/'runs/full_map_postprocess_20261019';report=run/'teacher-report'
e=json.loads((run/'postprocess-evidence.json').read_text(encoding='utf-8'))
e['cleanup']=json.loads((run/'full-post-cleanup.json').read_text(encoding='utf-8-sig'))
assert e['cleanup']['active_raven_processes']==0 and e['cleanup']['data_retained']
e['visual_qa']={'images':['full-map-overview.png','target-coverage.png'],
 'result':'Directly inspected both plots; readable axes, distinct map categories and target numbers; close labels 1/2 and 3/4 separated and re-inspected.',
 'browser_render':'Not performed; local file browser automation unavailable.',
 'scope':'Overview is downsampled for display; checks operate on original full-resolution arrays.'}
for destination in [run/'postprocess-evidence.json',report/'evidence.json',root/'docs/development/ugv-ogn/full-map-postprocess-20261019.json']:
    destination.write_text(json.dumps(e,ensure_ascii=False,indent=2),encoding='utf-8')
reviewed=run/'source-reviewed';reviewed.mkdir(exist_ok=True)
for source in [root/'scripts/postprocess_terrain_tiles.py',root/'tests/test_terrain_tile_stitch.py']:
    shutil.copy2(source,reviewed/source.name)
class Links(HTMLParser):
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if key in ('href','src') and value and not value.startswith('#'):
                assert (report/value).is_file(),value
Links().feed((report/'查看进展.html').read_text(encoding='utf-8'))
with zipfile.ZipFile(run/'teacher-report.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(report.iterdir()):z.write(p,p.name)
with zipfile.ZipFile(run/'teacher-report.zip') as z:assert z.testzip() is None
plan=root/'IMPLEMENTATION_PLAN.md';lines=plan.read_text(encoding='utf-8').splitlines()
for i,line in enumerate(lines):
    if '- [ ] Scene1-FullMap-Completion：' in line:
        lines[i]='    - [x] Scene1-FullMap-Completion（2026-10-19）：527 块 / 32,235,504 格 / 0.05 m 原始采样完成，`full-post-a01` 完成磁盘拼接及 8 字段回读一致、无遗漏重叠；全图坡度/台阶重算及块缝超差值 0，两个先前真实 PhysX 窗口的原始字段及 5 cm 台阶配置下 footprint/reach 内部区域对照超差值 0（剔除局部窗口边界影响）。显式 0.508×0.430 m /16 yaw /15°/0.05 m 台阶/0.5 m 顶部余量，footprint 29,275,763 格；其上 0.1075 m 净空及 8 连通 reach 28,880,101 格/63 区域。按论文目标覆盖数、面积选 C0，27,551,898 格/68,879.745 m²，31/31 目标仅几何候选相交，均保持未审核且不可正式计分。生成 footprint/reach/selected 未审核 Nav2 YAML/PGM/NPZ，全部导出格点与上下方向校验通过。命令和退出 0 见 `runs/full_map_postprocess_20261019/full-post-a01/execution.json`；耗时 133.05 s，峰值提交 2.960 GiB，14 GiB 等守护门不变。拼接 2 项检查两台通过，随后新增拒绝已有输出目录以保护旧报告的 CLI 检查，本地 3 项通过，数值算法未变，实际运行源码与加固版本分开保留。证据 `docs/development/ugv-ogn/full-map-postprocess-20261019.json`；图文包 `runs/full_map_postprocess_20261019/teacher-report.zip`。临时采样/后处理任务与进程已清理，数据保留。此项只验收全图诊断后处理，不代表老师地图等价、人工 GT、真实导航或正式 episode 验收。'
        lines.insert(i+1,'    - [ ] Scene1-FullMap-Nav2Validation：将已生成的未审核全图接入现有 Isaac 4.5 / Humble Nav2 诊断，在有界仿真中检查起点、坐标、静态/动态代价地图一致性和多个目标导航；记录实际轨迹、转角净空、停止条件、ROS/TF 与原始截图。不得把几何 31/31 候选覆盖写成实跑 K=M；人工审核、正式到达集与 episode 仍需单独验收。')
        break
else:raise RuntimeError('Pending completion item not found')
plan.write_text('\n'.join(lines)+'\n',encoding='utf-8')
for path,link in [(root/'benchmark/README.md','../docs/development/ugv-ogn/full-map-postprocess-20261019.json'),
                  (root/'docs/benchmark_zh.md','development/ugv-ogn/full-map-postprocess-20261019.json')]:
    lines=path.read_text(encoding='utf-8').splitlines()
    for i,line in enumerate(lines):
        if line.startswith('> 本机全图原始采样完成'):
            lines[i]=f'> 本机全图后处理完成（2026-10-19）：527 块/32,235,504 格/0.05 m 已拼接，全图导数、块缝及两个真实 PhysX 小窗口内部对照通过。显式 5 cm 台阶、16 朝向车体检查后，生成 0.1075 m 净空和 63 个 reach 连通区域；选定 C0 覆盖 31/31 论文目标的几何候选到达区，所有目标仍未审核且不可正式计分。未审核 Nav2 图导出并逐格核验方向，退出 0、133.05 s、峰值提交内存 2.960 GiB，运行任务已清理。下一步为全图 Nav2 真实验证；人工 GT、到达集及正式 episode 仍未验收。见[全图后处理证据]({link})。'
            break
    else:raise RuntimeError('Status paragraph missing')
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
index=root/'docs/development/ugv-ogn/README.md'
text=index.read_text(encoding='utf-8')
text=text.replace('仅验收跳过已保存块并继续提交；全图及论文复现仍待完成。','记录采样恢复阶段；后续全图后处理结果见下文，论文复现仍待验收。')
text+='\n全图诊断后处理（2026-10-19）：[拼接、块缝、可通行性与目标候选证据](full-map-postprocess-20261019.json)。原始采样及后处理已完成；31/31 仅为未审核几何候选覆盖，下一步进行真实 Nav2 验证。\n'
index.write_text(text,encoding='utf-8')
print('PASS: report links, ZIP CRC, visual inspection record, provenance, cleanup, evidence and documentation synchronized.')
