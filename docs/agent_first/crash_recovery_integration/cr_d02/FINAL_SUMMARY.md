# CR-D02 — 中断只读诊断就绪

**PASS_ABQJOBPILOT_CR_D02_INTERRUPTION_DIAGNOSTICS_READY**

已在当前执行核心实现 `inspect_interrupted_execution(context, run_id, observe_os=False)`，复用原有界一致只读快照、白名单投影、受管范围校验和行政处置记录。可区分未启动、历史完成、活动进程、监督疑似中断、证据冲突及行政释放。`UNKNOWN_INTERRUPTED`仅为版本化诊断投影，**没有新增Run状态或Schema**。

默认不探测OS；明确请求时仅查询记录中的身份。原进程PID复用、无法重新取得退出进程映像、boot估计及丢失的Job证据均不会被补成完整退出。诊断不改原Solver/Artifact/DAT/ODB、revision、Grant、gate、槽和路径隔离，不赋予Apply权限。

## 实际改动与验证

- 新增 `execution/interruption.py`、`interruption_probe.py`；`store.py`只提取/扩展读取接缝。三个既有文件发生本轮差异：store.py、依赖隔离测试，以及R14测试夹具的明确quiescent同步。没有改执行/授权/派发/收尾状态机、Backend、Supervisor或GUI。
- **最终353个唯一用例全部通过，0 FAIL / 0 SKIP**：新诊断47、相关核心回归170、产品回归127、依赖隔离9。历史测试数字不混入。首次失败、测试同步修正及审计输出脱敏修正完整列于 TEST_AND_ACCEPTANCE.md，原始XML保留。
- 实际Windows固定Python owner/worker查询、测试owner退出而worker仍活、受管范围正常完成均有证据；系统重启/时钟场景是模拟。Run018–021B既有认证、GUI关闭重连、凭据与单次控制/停服回归通过，不代表新诊断已经接入GUI。
- 本轮测试身份后查匹配存活0；保留句柄与私有材料清理见CLEANUP.json。清理审计不终止进程。没有Abaqus调用，没有接触历史真实实例、Stable或共享环境。

## 明确限制与下一步

1. 当前Store没有历史boot/session标识；墙钟减uptime仅支持疑似判断，不能证明Windows确切重启或所有后代退出。原owner进程身份若未持久化/元数据已替换，明确缺失。
2. 在线写入可能触发原有SQLite sidecar拒绝；诊断安全失败，不执行修复。OS与DB不是原子快照，当前进程观察不能回填旧owner退出证据。
3. 本轮提供内部/本地Python接口；新IPC、CLI/MCP和GUI显示留待CR-D04/Run024。普通查询、服务连接及报告摘要都不能批准恢复。
4. Run024必须修复Classic UNKNOWN_INTERRUPTED显示Failed的P1；顶部Scene左侧常驻Classic Queue，并在Classic提供Execution Workspace返回。详见交接，不以HTML代替原生GUI。
5. CR-D03最小范围是产品可信管理桥接、原owner同一排他锁、锁内精确预览/授权/事务，先复用已有policy。缺exit的行政政策及managed终态缺失对账仍需独立评审。本轮没有实施Recovery Apply、新Attempt、Requeue或Retry。

未确认新的P0执行安全缺陷；Run022的受限RC判断不扩大为“通用Crash Recovery完成”。历史真实证据的NOT_OBSERVED、域外UNKNOWN、ODB NOT_RUN不变。

## 交付

- [实现范围](IMPLEMENTATION_AND_SCOPE.md)、[诊断契约](DIAGNOSTIC_CONTRACT.md)、[Python使用](USAGE.md)
- [353项结果与26项阶段矩阵](TEST_AND_ACCEPTANCE.md)、[逐用例结果](TEST_RESULTS.json)
- [Windows诊断证据](WINDOWS_DIAGNOSTIC_EVIDENCE.json)、[清理记录](CLEANUP.json)
- [Run024显示/导航交接](RUN024_GUI_HANDOFF.md)、[CR-D03建议](CRD03_NEXT_STEPS.md)
- [基线](BASELINE.json)、[最终保护核验](FINAL_CHECKS.json)

Develop / `271c6f82fd6a4599dbae2df30d903dab2cef1f63` / `0.3.0.dev0` 保持。未提交、推送或切换分支。完成后停止，等待CR-D03实施授权。
