from pathlib import Path
import datetime,hashlib,json
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/construction_adaptation_20261019'
logs=run/'review-a03-evidence/logs';execution=json.loads((logs/'construction-review-a03/execution.json').read_text());report=json.loads((logs/'construction-review-a03-frames/report.json').read_text())
assert report['status']=='failed' and len(report['frames'])==12
qa={'scope':'assistant visual inspection of actual RGB; not human GT verification',
    'inspected':['view-0.png','view-3.png','12-image contact sheet'],
    'findings':['view-2 faces an intervening building interior; target not clearly exposed in that view.','view-10 and view-11 are heavily occluded/dark or blocked by containers; the intended biotoilet cannot be reliably confirmed from this pair.','view-0/1/3 show rollers; views4-9 show groups of blue portable toilets, but overlapping objects and candidate identity still need human review.'],
    'accepted_image_quality_does_not_imply_target_visible':True,'human_verified_count':0,
    'need_follow_up':['Generate alternative camera azimuths for obstructed targets without changing target annotations or semantic approval.','Retain raw buffers and image statistics for any next rejected camera view.']}
(run/'review-a03-visual-qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
result={'job':'construction-review-a03','scope':'partial static review material; batch failed','execution':execution,'error':report['error'],
    'saved_valid_rgb':12,'expected_rgb':56,'targets_with_two_images':6,'targets_in_inventory':28,'formal_accepted':False,
    'archive_sha256':'f564ecc2923a9360806b8d7935bc2f84bc1e45041954943327b77da7abad6d1c','verified_files':33,
    'image_packet':'runs/construction_adaptation_20261019/teacher-review-a03/查看进展.html',
    'packet_sha256':hashlib.sha256((run/'teacher-review-a03.zip').read_bytes()).hexdigest(),'visual_qa':qa,
    'next':'Smaller batches retain quality criteria, record and skip failed views; no blind rerun of the full 56-view job.'}
p=root/'docs/development/ugv-ogn/construction-review-failure-20261019.json';d=json.loads(p.read_text(encoding='utf-8'));d['warm_cache_a03']=result;p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
p=run/'teacher-review-a03/查看进展.html';s=p.read_text(encoding='utf-8').replace('<h1>','<aside style="padding:16px;background:#fff0d9">图像检查补充：view-2、view-10、view-11存在明显遮挡；图像质量合格不等于目标可见。12张图只覆盖前6个候选的视角，其他目标没有图片。全部人工审核仍为0。<a href="../review-a03-visual-qa.json">检查记录</a>。原始运行包和原图保持不变。</aside><h1>',1);p.write_text(s,encoding='utf-8')
p=root/'IMPLEMENTATION_PLAN.md';s=p.read_text(encoding='utf-8').replace('ConstructionSite warm-cache a03已保存12张真实RGB，后续视角在原首帧限时内等待；不宣称整批完成。','ConstructionSite warm-cache a03保存12/56张真实RGB（前6个候选双视角），第13视角480s稳定帧门失败；707.78s/峰值11.731GiB，guard无正常子进程退出码，33文件核验。view-2/10/11明显遮挡，质量合格不等于目标可见；部分审核包已生成，人工批准仍0。');p.write_text(s,encoding='utf-8')
p=root/'runs/autonomous_handover_20261019/progress.json';d=json.loads(p.read_text(encoding='utf-8'));d.update(updated_at=datetime.datetime.now().astimezone().isoformat(),phase='ConstructionSite新碰撞全图首批采样；部分真实审核截图已保存',last_observed_process='construction-instancemap-a01 已实际启动，原14GiB/1200s保护；截图a03已失败结束并归档',remote_log='D:/RAVEN-4060/logs/construction-instancemap-a01/execution.json')
d['completed_this_window'].append('ConstructionSite审核渲染首次获得12张合格原始RGB，33文件哈希归档；部分审核图文包和空白表已生成。第13视角稳定帧门失败，整批不通过，明显遮挡视角已单列。')
d['failed_results'].append('construction-review-a03：12/56图后第13视角稳定帧超时（形状600×960×4）；707.78s、峰值11.731GiB，guard_or_launch_failed，无正常子进程退出码。原图保留，非完整审核包。')
d['reader_summary'][1]='ConstructionSite碰撞补全通过51,200格真实验证；旧图已失效，独立数据集全图首批正在采样。'
d['reader_summary'].insert(2,'已保存ConstructionSite 12张真实RGB和部分审核页面；第13视角失败，部分图片被建筑/集装箱遮挡，不能据此批准GT。')
d['prepared_next']['ConstructionSite']='新碰撞全图首批已实际启动；续采队列仅准备，未启动。14GiB/1200s，20新块/900s采样。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
for rel in ['benchmark/README.md','docs/benchmark_zh.md']:
    p=root/rel;s=p.read_text(encoding='utf-8').replace('须新契约重采。FireAcademy','新契约首批正在重采。ConstructionSite另有12张真实RGB部分审核材料，第13视角失败且部分图有遮挡，人工批准仍0。FireAcademy');p.write_text(s,encoding='utf-8')
p=root/'docs/development/ugv-ogn/README.md';s=p.read_text(encoding='utf-8');s+='\n- ConstructionSite真实RGB部分审核包：`runs/construction_adaptation_20261019/teacher-review-a03/查看进展.html`（12/56图，整批失败，遮挡已记录，人工批准0）。\n';p.write_text(s,encoding='utf-8')
print('Partial RGB evidence and visual limitations recorded; fresh map actually started.')
