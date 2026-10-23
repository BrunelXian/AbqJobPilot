# Run 007 — 已持久化退出证据收尾契约

本轮只支持 python-process-fixture-v1/version1 的新建隔离实验实例；复用 Schema3，不迁移。应用仍为0.3.0.dev0。Run006的Backend版本和固定脚本不改，新增Plan绑定 `fixed-windows-members-v1` 与四个必需角色：launcher_transport、launcher、worker_transport、worker。旧Plan缺该绑定或旧退出记录缺精确关联时只读可查，但本轮对账拒绝；不补造历史证据。

## 实际复用与证据缺口

Run006 ProcessBackend.execute 已通过保留的Windows句柄取得各角色退出码，ExecutionService.record 在 process_observe 事务逐条保存 PROCESS_EXIT_OBSERVED，早于 PROCESS_COMPLETED 和 terminal。无需拆分原接受/Grant消费事务，也不需要新表。原记录含OS身份和来源，但没有明确持久化的完整成员契约、每条退出的原owner/Plan/attempt绑定。本轮补足这些字段，并严格核对不可变事件与Run投影；旧记录不自动取得资格。

固定夹具合同只覆盖上述四个角色。身份握手候选仍经OS对象验证，全部句柄已取得、身份已提交之后才释放worker执行；membership记录表示Supervisor已经绑定全体必需成员，而非扫描到的成员计数。其依据是原Plan的脚本摘要与固定拓扑合同，不声称任意进程树完整。选定Windows venv的四个角色须为不同OS身份。

每条退出记录绑定Project instance、Run、Plan及digest、phase_attempt_id、原owner_id/epoch、角色、PID/创建时间/映像及执行对象摘要、身份观察时间、退出观察时间、retained_windows_handle来源。原append-only事件作为退出观察账本；重复同一完整观察是no-op，累计前缀或同角色矛盾被拒绝。所有退出观察提交成功前不推进集合终结；进程已退出不代表终态已持久化。

## 只读预览与分类

preview_process_reconciliation 在显式BEGIN只读事务内读取Run、原Plan、接受回执/消费、单个START_INTENT、成员依据、完整事件及历史Validation。最多64事件、16验证，每条16KiB、每类累计256KiB；超限无候选，不静默截断。事务不使用immutable，不修复sidecar或Schema。

它不调用ProcessReference、Backend、validator，不打开产物、当前解释器或夹具文件，不创建观察任务。当前owner/门通过已有排他所有权和持久门确认；OS进程/文件系统不属于数据库一致视图。输出精确原身份、revision、门、事件引用、成员指纹、证据指纹、规则版本、确定性摘要及拒绝原因；不输出映像路径或授权秘密。

资格要求：原Plan明确必需集合；唯一接受及启动尝试；一次完整OS核验成员事件；每个必需角色恰有一个绑定同身份、原owner及attempt的退出事实；累计事件与当前投影一致。未知PID、缺worker、跨attempt、矛盾退出、结果/控制器自报均无资格。全部退出码0推导COMPLETED，任一非零推导FAILED，二者都只是固定测试执行结论。Artifact原NOT_RUN/UNKNOWN/INVALID/VALID不变，Solver始终NOT_RUN。

## 授权、提交与门禁

新动作 reconcile_recorded_process_exits 与Fake采纳、resume、执行Grant和IPC credential分离。复用现有TEST_ONLY_MANAGEMENT登记，可信harness必须经活跃owner登记，不提供mint RPC。

scope精确含Run、预期revision、preview摘要、Plan/id/digest、phase_attempt_id、Backend/id/version、evidence_fingerprint；外层管理Grant绑定context digest（含存储代际）、Project instance、当前owner、action、期限与max_uses=1。指纹覆盖成员依据、全部退出及历史记录；preview摘要还绑定门版本。调用者不能提供target_state、exit_code、members_complete或approved。

复用reconciliation.manage的同一management事务：先查原幂等回执，才检验未消费授权和当前前置条件；新操作重新读取资格及摘要；追加reconciliation决定和事件、更新原Run/revision、释放仅该Run对应slot、保存管理回执与消费。没有新Run、退款、Backend调用、验证记录或Artifact快照。原事实、接收回执、attempt与执行消费保持。后来过期的执行Grant不抹掉历史退出事实；本次必须有有效的新管理Grant。

同键同内容返回原回执，跨owner重放也不再转换；同键异内容冲突。事务失败回滚全部业务写，提交确认不明必须查原键。新owner不能用旧授权创建新转换。对账不打开PAUSED门，resume仍是另一精确授权。

现有resume策略检查未解执行、slot、维护状态与门版本；它没有要求所有历史Artifact必须PASS的全局策略。本轮不添加或放松该策略：NOT_RUN/INVALID仍不能称作结果已验证成功，但已确认退出后，另一个独立合法任务可经单独resume继续，派发前仍重检自身Plan/Grant。没有把验证缺失改成VALID。真正执行失败仍保留FAILED。

## 诊断与未实施能力

进程报告保持af-run-diagnostic-v2的白名单结构，解释规则升为process-diagnostic-rules-v3；旧v2规则报告仍可离线导出，Fake v1不改。新增明确的历史退出收尾决定/引用/时间，不调用本轮preview或apply，不重新探测。

本轮不提供遗留worker观察、重挂接、等待会话、自动接管/Retry、人工填写退出码、force-close/abandon、进程控制或通用进程树。未来观察会话必须另行设计身份集合、独立权限、幂等、等待预算、句柄关闭和观察owner再次崩溃；不能藏入刷新/诊断/对账。测试授权不是生产人类批准，不能抵御同OS用户任意改程序或数据库。
