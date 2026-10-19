# 显式静态实例碰撞清单

ConstructionSite 导出中有 5,075 个可见实例代理没有碰撞 API。普通子节点遍历会跳过这些网格，导致采样和运行时低估障碍。新的可选接口使用已核对的清单，将实例展开到会话层，并从顶点和拓扑字节完全一致、已启用碰撞的非代理网格继承物理分类。

`simulation/isaac-sim/utils/scene_instance_colliders.py` 的 `prepare_static_instance_colliders()` 要求本地资产及清单。它检查资产 SHA256、default prim、路径范围、重复目标、几何哈希、原型分类及动态刚体，包括场景根的动态祖先。未被清单覆盖的无碰撞可见代理会被拒绝。展开后再次核对世界变换、几何和可见性；异常会恢复原会话层。接口不保存 USD，不设置目标 `verified`，也不推断语义归属。

清单结构为：

```json
{
  "schema": "static-instance-collision-manifest-v1",
  "asset_sha256": "<source USD SHA256>",
  "asset_default_prim": "/World",
  "scene_root": "/World/stage",
  "human_gt_approved": false,
  "unmatched_count": 0,
  "ambiguous_count": 0,
  "matches": [{
    "path": "/World/stage/ExampleCopy/Mesh",
    "donor": "/World/stage/Example/Mesh",
    "geometry_sha256": "<points, face counts and indices SHA256>",
    "profile": "static_obstacle"
  }]
}
```

直接 `open_stage` 时不传 `reference_root`。资产引用到 `/World/stage` 时传该路径；接口将资产 default prim 映射到引用挂载点。因此源 `/World/stage/ConstructionSite/...` 会成为运行时 `/World/stage/stage/ConstructionSite/...`。返回的 `profile_overrides` 必须同时传给 `add_profiled_colliders()` 和 `configure_airground_physics_profile()`，以保持碰撞近似与物理材质使用同一分类。

共享启动器通过 `AIRGROUND_INSTANCE_COLLIDER_MANIFEST` 显式启用此流程，且只允许 `profiled` 碰撞模式。未设置时保留原启动行为。可见性 CLI 提供 `--instance-collider-manifest`，并在 `.scene-runtime.json` 中记录实际准备摘要。资产、清单和目标路径映射仍须分别匹配；提供碰撞清单不代表地图有效或目标已审核。

2026-10-19 验证：20 项相关 CPU 检查通过；实际 ConstructionSite 在原生和引用两种组合方式下均补齐 5,075 个代理，5,757 个场景网格碰撞清单与此前真实 PhysX `construction-instances-a02` 完全一致。世界几何和源文件保持不变，CPU 峰值约 322 MiB。证据在顶层 `runs/construction_adaptation_20261019/portable-instance-runtime-cpu.json`，清单 SHA256 为 `1ae5e19324ac6381b502a31c673fe637862b237c805672327e26935fed027d90`。

本提交的新接口和共享启动路径尚未完成新的真实仿真验收。此前 PhysX 窗口、当前全图采样使用独立冻结实现；不得把清单一致或 CPU 检查写成新接口的真实烹制、S8、导航或 K=M 通过。当前冻结任务不受此提交影响，后续须在资源空闲时做独立有界实测。
