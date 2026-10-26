# RC-G02 — Credential Risk Remediation & Reproducible Fixture Closure

**PARTIAL：工作树修复和回归闭包完成；公开历史凭据的安全处置尚待独立决定。** 不使用 `PASS_ABQJOBPILOT_RC_G02_CHECKPOINT_REMEDIATION_READY`。

- Develop / `9553755a24ff521dd2ac694ea39cab5a03f88466` / 0.3.0.dev0；未改 index、分支或共享环境。
- 已确认公开 remote Develop 包含原 CLEANUP：1 个随机明文测试连接凭据、44 个 DPAPI 容器。不是固定哑数据，也不能将容器数量等同于泄露的有效秘密数量。源测试没有外部 owner，原清理记录覆盖全部源文件移除，但未对其他信任副本做认证探测或撤销。
- CLEANUP 工作树仅 45 个秘密字段脱敏，其他事实保留；修正导出先脱敏与负向测试哑数据。**旧提交和辅助 tree 中的原对象仍存在。**
- 两份合成 fixture 完成：原始 DAT/诊断 JSON 本地未改；维护测试不再读取它们；455 项源副本闭包验证无缺失产品相对导入，209 Python 语法通过。
- 本轮 **763 个唯一测试最终 PASS，0 FAIL/SKIP**；保留首次 Tk 初始化 ERROR、Legacy SKIP及错误选集空跑记录，原用例在独立进程通过。未修改产品核心或 GUI 行为。
- 1,159 项重新分类：19 项仅提出取消跟踪建议，1,136 项可留 Git/排除安装包，4 项待披露审查；不是批量索引删除计划。
- 历史 45 个目录、RC-G01 四根及本轮 13 根保留；本轮 311 加密容器和 2 固定明文负例不进入白名单。日志扫描无已采集凭据值匹配；新测试记录身份无匹配存活，不据消失补写历史退出。
- README 已指向实际 Compact Cockpit / Agent Command / Classic Queue，English 默认与法德 Preview、NOT_OBSERVED / UNKNOWN / NOT_RUN 边界保留。

## 三个决策

| 决策 | 结论 |
|---|---|
| 本地 Develop 检查点 | 技术上可准备：依 `CANDIDATE_MANIFEST.json` 精确白名单保存修复及既有成果，仍需明确 Git 授权；不会净化祖先 |
| 远端 push | 当前不建议批准：先对已公开历史材料作可信失效确认/风险接受，或批准精确撤销及必要历史治理 |
| Release Candidate | 尚未就绪：安全处置与独立打包/非登记主机部署门槛未闭合；不是发现新的执行状态机 P0 |

## 一次性后续授权建议

可以单独批准：在最终清单摘要和逐文件 hash 再核对后，仅按 SOURCE_TEST、DOC_RESOURCE、AUDIT 及自描述清单白名单建立两个**本地 Develop commit**；不取消跟踪19项、不清理、不 push、不重写历史。完整数量与变更规模见 `CANDIDATE_COUNTS.json`。

另需明确历史处置决定：接受有依据的隔离测试材料残余风险并保留历史，或批准针对仍受信任副本的核验/撤销以及必要的历史治理设计。当前证据不足以由本代理自行认定无需处理，也不授权任何历史 owner 操作。未获得 push/历史治理专项批准前停止在本地提交范围。

本轮真实 Abaqus **0 次**，真实恢复 **0 次**，Git add/rm/commit/push/历史重写 **0 次**。未访问 Stable、操作历史 owner 或修改真实 Run。完成后停止。
