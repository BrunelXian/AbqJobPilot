# Run024 — Crash Recovery 只读适配

## 公共入口

认证且 Project 绑定的既有 Client 新增：

```python
client.inspect_interrupted_execution(run_id)
client.preview_interrupted_recovery(run_id)
```

Supervisor OPERATIONS 能力列表公布这两项。请求只接受 `run_id`，额外 `approved`、`observe_os` 等字段被精确字段检查拒绝。客户端/GUI 不提交任意 ProjectContext，不读取凭据到显示文本。

首项委托 Store 的 CR-D02 只读检查，使用默认 `observe_os=False`；第二项委托 CR-D03 `preview_interrupted_recovery`。不存在新的 Apply、authorize、resume 或写 RPC。GUI 没有增加操作员权限。既有老管理通道不因本次只读适配而扩权。

## 一致性与时效

Reader 独立线程取得 health、Project 分页、Run、validation、bounded progress/events 和两个诊断。列表每页32，事件/进度保留原窗口边界，Tk 主线程只渲染消息。每项核心诊断/preview 具有自己的 revision/digest/观察时间；不能将多次 SQL/IPC 及 OS 数据说成跨系统原子快照。

缺能力显示 CAPABILITY_UNAVAILABLE；单项诊断失败显示结构化 error code，不伪造 Interrupted；连接失效使整个显示成为 stale 并保留最后成功时间。更换 Project 不复用旧 Run 缓存。GUI 不升级服务。

## 显示投影

- 原 Run execution 始终单独显示。
- 只有核心 display_projection=UNKNOWN_INTERRUPTED 显示 `Interrupted (Unverified)` / `异常中断（结果未验证）`；其他 UNKNOWN/UNRESOLVED 保留原码。
- Evidence 展示原 owner/成员/exit、managed scope、revision、reason_evidence、unknowns 和原始投影；不凭 PID 消失或文件存在判断结束。
- Recovery 展示 KEEP_BLOCKED 或可考虑的证据/行政处置，以及 prerequisites/effects/禁止动作；“可考虑”不是授权。
- Solver、DAT、Artifact、ODB 与 managed completion 各自显示。RECOVERY_APPLIED 不能替代 EXECUTION_VERIFIED。
- Classic raw UNKNOWN_INTERRUPTED 仅修复显示和筛选，不修改 normalize_status/数据库、真实 FAILED 映射或恢复状态机。

## 证据

新的 Windows RPC 测试在自己创建的隔离固定 Python owner 崩溃后重新建立测试 owner，逐项比较 GUI/RPC 与核心 diagnosis、decision_digest、preview_digest；重复读取比较 revision、gate、Run、slot、events/Grant 等快照，且拒绝新 Apply 操作及 observe_os 字段。新主窗口活 worker 读取前后数据库字节 SHA-256 也一致。详见 WINDOWS_EVIDENCE_INDEX.json 与 TEST_RESULTS.json。

没有对历史真实 Run 执行诊断/Apply，没有更改 CR-D03 授权、排他锁、事务或 Schema。其未提交源码按本轮开始摘要原样保留。
