# Run014 公共收尾接口与操作者使用

本轮已实现、仅在隔离实例验证。当前真实 Run **尚未处置**。新代码不热加载到旧owner；原Run013候选清单不覆盖本轮源码，旧授权也不是新的行政处置授权。

## 只读公共客户端与 GUI

沿用 `FakeClient`（历史类名，并非所有Backend都为Fake）、现有127.0.0.1 JSON IPC与连接认证。没有匿名查询、mint、自动恢复或停止Solver接口。

```python
# client 是用明确的私有连接材料创建的既有 FakeClient。
assessment = client.preview_closeout(run_id)
run = client.run(run_id)
gate = client.dispatch_gate()
decisions = client.reconciliations(run_id)
# 如已有由当前可信 owner 登记的精确许可及请求：
result = client.apply_closeout(exact_request)
# 回执与当前视图不同；响应丢失时用原 operation/key 查询，不能换新键。
receipt = client.management_receipt(exact_request['operation'], exact_request['idempotency_key'])
```

`preview_closeout`只读；`apply_closeout`显式写入，普通客户端本身不能签发许可。参数之外的 `approved/target_state/force` 均不接受。详细字段、错误及事务见 CONTRACT.md和实际代码。

原Dev GUI入口仍是：

`D:\Projects\abqjobpilot_dev\examples\agent_first\R13_04_Open_Dev_GUI.vbs`

它只连接，不启动/批准/提交。对于提供新 `preview_closeout` 能力的owner，同一现有状态表增加逻辑slot、路径保留、独立行政处置、评估摘要、可审阅动作和UNKNOWN。刷新在后台公共reader中；界面没有含义模糊的“完成”或“释放全部”按钮。旧owner不提供该操作时保留旧显示，失联则明确显示断开，不伪装实时。

**目前旧endpoint查询超时**，打开此GUI不能使owner恢复。不要为了显示新行而重开真实服务或再次提交。

## 当前实例的无 Solver 读取：已经实际执行

以下命令已在非仓库cwd `C:\Users\wuxia\AppData\Local\Temp` 用登记解释器执行，输出见 OPERATOR_READONLY_OUTPUT.json。只读取显式库，不取得owner，也不运行Backend。

```powershell
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B 'D:\Projects\abqjobpilot_dev\examples\agent_first\standard_closeout_operator.py' preview --test-root 'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run013_e52135d71d2c43d2a45301c586cbfb7e' --bootstrap 'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run013_e52135d71d2c43d2a45301c586cbfb7e\private\bootstrap.json' --run-id r_609c9bbfd9c54b3ca2fce23bbd6059e4
```

预期 `source=offline_read_only_no_current_owner_admission`、owner_id=null、reasons含CURRENT_QUIESCENT_OWNER_REQUIRED。这是具体可审阅的评估，不是已有可执行授权或当前进程健康检查。bootstrap仅复用原context/authority/namespace资料，不输出其连接凭据。

## 可信操作者处置入口：当前实例尚未执行，须先取得具体确认

`standard_closeout_operator.py review-and-decide` 是小型本地可信入口，复用已有 `acquire_supervisor_store`、`ExecutionService`、管理事务，不新建执行器、监听器或调度线程，不配置StandardBackend，不创建子进程。它先取得现有OS排他所有权；活跃owner导致OWNER_BUSY，不能因IPC超时就抢占。

该操作**不是只读**：取得管理owner会更新owner/gate版本，保持PAUSED。必须先获准这一所有权交接，再在同一持锁进程查看新评估并选择动作。不能拿离线预览的null owner或旧摘要直接提交。

得到针对当前Run和残余风险的明确确认后，唯一建议动作是 `release_standard_logical_slot`；不恢复派发，不删除隔离。以下为已实现入口的准确命令，**本轮未对真实实例运行**：

```powershell
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B 'D:\Projects\abqjobpilot_dev\examples\agent_first\standard_closeout_operator.py' review-and-decide --test-root 'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run013_e52135d71d2c43d2a45301c586cbfb7e' --bootstrap 'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run013_e52135d71d2c43d2a45301c586cbfb7e\private\bootstrap.json' --run-id r_609c9bbfd9c54b3ca2fce23bbd6059e4
```

入口打印当前owner绑定评估；可以按Enter退出而不登记处置（owner交接及PAUSED仍已发生）。要执行时，输入精确 eligible action、接受的残余风险/理由和真实授权来源。通过现有可信issue登记单次≤300秒管理许可，再调用同一服务apply。没有自报`approved=true`，没有导入任意命令或读取任意工程的选项。此交互是可信操作者工具，不是不可伪造的人类认证；同OS用户任意shell仍是既定信任边界。

动作提交前输出操作key/Run/owner以便应答丢失后确认。成功返回原子管理回执，不将打印回执等同于当前Run证据已完整。成功后关闭的是本工具自己的无worker管理lease；当前旧owner没有被该入口停止或杀死。后续需要恢复派发时应另行review并调用可信 `closeout.issue_resume` + 既有 `resume_dispatch`，本入口没有一键恢复选项。

若首次连接旧owner仍有活跃OS锁，或日志需要维护、证据/评估不匹配、记录数超限，应停止并报告，不能删锁、清journal、修改记录、重建Project或换key强行继续。

## 停服限制

当前真实owner身份不能确认，**不要执行旧stop入口或按PID终止**。正常停服契约只在当前owner可确认、worker已返回、记录已持久化时成立；停止服务不是Solver退出证明。新服务实现停服前持久PAUSED，重启不派发未决Run。

原冻结 `standard_service.py stop` 会先校验旧候选源码摘要；新源码导致不匹配时应尊重拒绝。本轮没有更新旧摘要、改安装、发stop文件或使用其他方式绕过。若用户同意当前处置，下一步先核实旧owner/排他锁，再用本版管理lease重评；不得把此前“找不到匹配PID”写成完整历史退出。

## 可复现的隔离验收

从Dev目录运行，使用新临时根，测试代码只启动固定Python替身：

```powershell
$r14root = Join-Path $env:TEMP ('AbqJobPilot_R14_repeat_' + [guid]::NewGuid().ToString('N'))
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B -m pytest tests/test_standard_closeout.py tests/test_closeout_windows.py -q --basetemp=$r14root
```

这是复现命令模板；本轮实际命令、唯一临时路径与结果另见 `*_TEMP*.txt`、各测试日志/XML、TEST_RESULTS.md。不要复用已存在basetemp（pytest可能清理它），不要把真实实验根传给测试。

## 主要拒绝与恢复前提

| 原因码 | 含义及后续 |
|---|---|
| OWNER_BUSY / OWNER_UNCONFIRMED | 不持有效排他所有权；不抢占、不删锁 |
| STALE_OWNER / STALE_PREVIEW | owner、revision或证据/门禁已改变；重新评估并取得新许可 |
| MANAGEMENT_GRANT_REQUIRED / MANAGEMENT_SCOPE_MISMATCH / MANAGEMENT_GRANT_EXPIRED | 独立管理许可缺失或范围/期限错误；执行Grant/TEST_ONLY不能代替 |
| CLOSEOUT_PRECONDITION_FAILED / EVIDENCE_INSUFFICIENT | 本版不允许该处置；继续占槽/隔离，无force路径 |
| RESOURCE_RETAINED / OUTPUT_CONFLICT | 旧工程或输出仍保留；不换Job名绕过 |
| IDEMPOTENCY_CONFLICT | 原键绑定不同请求；审查实际操作，不能盲目换键 |
| ACCEPTANCE_UNKNOWN | 按原namespace/action/key查询，不再次创造动作 |
| STORE_REQUIRES_MAINTENANCE | journal/sidecar或存储条件要求维护；查询及启动不隐式修复 |
| LIMIT_EXCEEDED / STORE_UNAVAILABLE | 有界读取拒绝；不是空报告、不是安全完成 |
