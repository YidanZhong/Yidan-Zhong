import hashlib
import html
import json
from pathlib import Path
import shutil
import struct
import zipfile

root = Path(r'D:\xprogram\RAVEN-AirGround-github')
run = root / 'runs/rtx_first_frame_20261018'
target = run / 'teacher-screenshots'
target.mkdir(exist_ok=True)
items = [
    ('retro-render-a02-frames/view-0.png', '01-scene1-street.png', '场景一地面街景：960×600 原始 RTX 相机图像；相机高度 1.2 m。'),
    ('retro-render-a02-frames/view-1.png', '02-scene1-overview.png', '场景一俯视图：960×600 原始 RTX 相机图像；可见停车场、车辆、道路和房屋。'),
    ('retro-render-a02-frames/ui-camera-preview-0.png', '03-isaac-street-window.png', 'Isaac 实际运行窗口截图：内置诊断预览面板显示上述相机原始图像及实测帧号、仿真时间。'),
    ('retro-render-a02-frames/ui-camera-preview-1.png', '04-isaac-overview-window.png', 'Isaac 实际运行窗口截图：俯视相机图像预览，帧号 365，仿真时间约 5.867 秒。'),
    ('cube-a13-frames/view-0.png', '05-cube-validation.png', '最小场景验证：真实方块下落至地面后，相机成功输出 RGB。')
]
captions = []
for source, name, caption in items:
    src = run / source
    dst = target / name
    shutil.copy2(src, dst)
    raw = dst.read_bytes()
    assert raw[:8] == b'\x89PNG\r\n\x1a\n'
    width, height = struct.unpack('>II', raw[16:24])
    assert raw == src.read_bytes()
    captions.append({'file': name, 'source': source, 'caption': caption,
                     'width': width, 'height': height,
                     'sha256': hashlib.sha256(raw).hexdigest()})
(target / 'image-provenance.json').write_text(json.dumps(captions, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
report = json.loads((run / 'retro-render-a02-frames/report.json').read_text())
execution = json.loads((run / 'retro-render-a02/execution.json').read_text())
assert report['status'] == 'passed' and execution['exit_code'] == 0
assert len(report['frames']) == 2
samples = [json.loads(s) for s in (run / 'retro-render-a02/resources.jsonl').read_text().splitlines()]
gpu_peak = max(s['gpu_memory_fraction'] for s in samples) * 8188 / 1024
intro = f'''RAVEN-AirGround 场景一：RTX 出图与运行截图
日期：2026-10-18

可向老师汇报：
已在本地第二台 RTX 4060 电脑完成 Isaac Sim 4.5、ROS Humble 和 Nav2 的环境准备，场景一 RetroNeighborhood 已实际加载，物理仿真和 RTX 相机出图验证通过。已保存地面与俯视两个视角的原始图像及运行窗口截图。下一步是接通 Windows 仿真与 Linux ROS，再接入机器人导航。完整论文实验尚未完成，正式 episode 数量为 0。

本轮证据：
场景对象数：27,986 prim；场景 USD SHA-256：{report['scene_sha256']}
原始 RGB：两张 960×600；非黑像素比例分别为 {report['frames'][0]['nonblack_fraction']:.2%} 和 {report['frames'][1]['nonblack_fraction']:.2%}。
实测仿真时间：地面图 {report['frames'][0]['sim_time_s']:.3f} s；俯视图 {report['frames'][1]['sim_time_s']:.3f} s。
本次进程正常退出 0；耗时 {execution['elapsed_s']:.2f} s；峰值进程提交内存 {execution['peak_job_commit_gib']:.3f} GiB；采样峰值显存约 {gpu_peak:.2f} GiB。

本轮修复与限制：
此前捕获 LLVM ERROR: out of memory，并观察到系统提交余量耗尽及 10 GiB 诊断上限。经用户同意，保留 C 盘系统管理，在 D 盘新增初始 16 GiB、最大 24 GiB 分页文件；新容量立即生效，总提交容量约 49.61 GiB，未重启。诊断上限调整为 14 GiB，保留主机与显存保护。
普通相机诊断使用 Vulkan/NVIDIA ICD 过滤、有限权限桌面会话、延后建场景、异步加载、16 个 CPU 线程、1 个 shader 编译并发及关闭 Motion BVH。这是经过验证的组合，未单独证明每个参数的因果作用，也未验证 RTX 雷达/激光雷达。
修复了仅看数组形状和方差就接受近黑首帧的问题，增加非黑像素比例检查及 60 帧稳定等待。所有展示图均经过人工查看，未做图像编辑。
窗口截图里的面板显示实际保存的 RGB，相机帧号和时间来自运行数据；它不代表已经完成机器人闭环。导航、GT、论文任务包与评分仍待完成。正式 benchmark 资源门未修改。

文件说明：
'''
intro += '\n'.join(f'{x["file"]}：{x["caption"]}' for x in captions)
(target / '说明.txt').write_text(intro + '\n', encoding='utf-8-sig')
cards = ''.join(f'<figure><img src="{x["file"]}" alt="{html.escape(x["caption"])}"><figcaption>{html.escape(x["caption"])}</figcaption></figure>' for x in captions)
page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>场景一 RTX 出图证据</title><style>body{font:17px/1.65 "Microsoft YaHei",sans-serif;background:#f4f6f8;color:#142332;max-width:1100px;margin:35px auto;padding:0 24px}h1{font-size:30px}.status{background:#e1f3e9;padding:18px;border-left:5px solid #218553}figure{background:white;padding:18px;margin:24px 0;border-radius:10px}img{max-width:100%;display:block;margin:auto}figcaption{padding-top:12px;color:#42596c}pre{white-space:pre-wrap;background:white;padding:22px;font:14px/1.65 "Microsoft YaHei",sans-serif}</style><h1>场景一：真实 RTX 相机出图</h1><p class="status">2026-10-18 · 相机出图检查通过 · 完整导航与论文实验尚未完成</p>'''
page += cards + '<h2>运行说明</h2><pre>' + html.escape(intro) + '</pre></html>'
(target / '查看截图.html').write_text(page, encoding='utf-8')
for name in ('report.json',):
    shutil.copy2(run / 'retro-render-a02-frames' / name, target / 'render-report.json')
shutil.copy2(run / 'retro-render-a02/execution.json', target / 'execution.json')
with zipfile.ZipFile(run / 'teacher-screenshots.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for p in sorted(target.iterdir()):
        z.write(p, p.name)
with zipfile.ZipFile(run / 'teacher-screenshots.zip') as z:
    assert z.testzip() is None
print(json.dumps({'images': len(captions), 'archive_bytes': (run / 'teacher-screenshots.zip').stat().st_size, 'gpu_peak_gib': gpu_peak}))

# Synchronize the current result at the top of both benchmark guides.
for relative, prefix in [('benchmark/README.md', '../docs/development/ugv-ogn/'),
                         ('docs/benchmark_zh.md', 'development/ugv-ogn/')]:
    p = root / relative
    lines = p.read_text(encoding='utf-8').splitlines()
    indices = [i for i, s in enumerate(lines) if s.startswith('> 第二台电脑进展（2026-10-18）')]
    assert len(indices) == 1
    lines[indices[0]] = '> 第二台电脑进展（2026-10-18）：Windows 原生 Isaac 4.5、Humble 和 Nav2 已安装，Linux ROS 实际收发通过。真实 Retro 场景加载、PhysX 抽样及 **RTX 相机双视角出图已通过**：27,986 个 prim，两张 960×600 原始 RGB，经图像检查、稳定等待及人工查看；最新运行退出码 0，耗时 51.31 s，峰值进程提交内存约 10.424 GiB。经用户同意新增 D 盘 16–24 GiB 分页文件（16 GiB 已即时启用），独立诊断上限 14 GiB，保留主机与显存保护；正式 benchmark 资源门未改。当前采用普通相机诊断配置并关闭 Motion BVH，不能替代完整机器人/RTX 雷达验收。原始道路抽样未添加正式 runtime 的 z=0 支持平面，不能当作 GT；跨系统 ROS、导航与正式 episode 尚未验收。见[最新 RTX 证据](' + prefix + 'rtx-first-frame-20261018.json)；早期失败过程见[运行记录](' + prefix + 'second-pc-runtime-20261018.json)。'
    p.write_text('\n'.join(lines) + '\n', encoding='utf-8')
history = root / 'docs/development/ugv-ogn/second-pc-runtime-20261018.json'
prior = json.loads(history.read_text(encoding='utf-8'))
prior['historical_record'] = 'Snapshot before the later successful RTX first-frame work; original measurements and verdicts are preserved.'
prior['superseded_by'] = 'rtx-first-frame-20261018.json'
history.write_text(json.dumps(prior, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
