# Agent-first Run 006 — 最终交付

**PASS_ABQJOBPILOT_AGENT_FIRST_RUN006_PROCESS_FIXTURE_LIFECYCLE_READY**

仅表示固定、受限Python测试进程的正常监督、独立结果验证和真实owner崩溃后的保守阻断通过；不表示自动接管、真实进程恢复、Abaqus、跨Project资源协调或完整0.3.0通过。

## 基线与实际改动

Dev保持 `Develop@fb7912ec9e0107b18f65948b147c87579c87cded`、应用0.3.0.dev0、实验Schema3。Run002～005前置成果保留；起始29个源码/测试与Run005哈希一致。

新增5个实验模块：process_contract、process_backend、process_fixture、process_handles、process_validation，以及2个相关测试文件。增量修改6个前置实验文件和3个测试支持文件；其余20个前置源码/测试哈希不变。详细文件列表见[CHANGE_SCOPE.json](CHANGE_SCOPE.json)，最终36文件测试快照见[SOURCE_HASHES.json](SOURCE_HASHES.json)。未改旧GUI、Runner、Settings、Datacheck、Project、MCP行为，未修改应用版本或迁移数据。

复用原Service/Store/owner锁/单槽/幂等/独立工作线程；只在可信启动配置中启用新Backend。Plan绑定固定脚本和解释器摘要、场景及资源时间上限；专用TEST_ONLY动作授权不能被Fake Grant替代。普通IPC没有命令、动态Backend、批准、杀进程或文件路径能力。原Fake仍没有进程启动能力。

## Windows实测与证据

**293 passed，0 failed、0 errors、0 skipped，175.29秒**：原239项契约完整重跑，新34项本地契约及20项真实Windows集成测试。R6-01～12逐项关联实际测试，见[验收矩阵](ACCEPTANCE_MATRIX.md)。早期失败及修正、补充清理记录保留，未削弱旧断言。领取后如因等待发生授权过期或输入变化，创建OS进程前仍再次拒绝；消费不返还、槽不自动释放。

最终52个多进程case：82个owner/client实际Python进程、21次Backend物理启动和84个fixture角色进程；外层解释器转发器也已wait退出。每次物理启动由独立受控启动登记与PID/创建时间核对，不以结果文件数替代。最终全部已登记进程退出、句柄关闭，私有连接凭据残留0。18次owner/client故障终止和16次fixture清理终止仅使用本轮身份核验后的句柄。环境、角色、窗口、退出/清理证据见[测试和进程证据](TEST_AND_PROCESS_EVIDENCE.md)及[结构化证据](PROCESS_EVIDENCE.json)。

正常路径核验launcher/worker及其venv转发器，保留OS引用并取得真实退出码。launcher退出或结果先出现时，worker仍活着，单槽不释放；有效产物+非零退出、正常退出+无效产物分别记录。Solver始终NOT_RUN。

真正终止owner后，worker在目标Windows继续存活；新owner可取得原锁，但保持PAUSED和未解Run阻断。七个受控窗口区分：尚未创建、已创建但未提交身份、已提交身份、握手后worker运行、已退出但退出记录未提交、退出观察已提交但集合投影未提交、验证/终态事务尚未提交。没有缺PID就重跑、没有补造未知退出码、没有按结果文件解锁。

## 服务事实、控制器观察与仍未知事项

服务持久化原回执/Run/phase_attempt_id、START_INTENT、实际核验身份、已取得的退出观察、独立Artifact验证及状态事件。库内缺少身份/退出/验证时保留UNKNOWN或既有不确定语义。

控制器额外持有的句柄、物理启动登记、owner终止与worker继续存活证据单独记录，不注入重启服务。即使控制器已确认退出或进行了清理，缺证据的业务Run仍待未来显式对账，原slot保持保护。

Run004 Fake采纳明确拒绝新Backend，包括精确Fake管理授权；恢复也不能绕过未解执行。Run005 v2报告仅投影历史进程事实，正常Fake继续v1；旧v1导出兼容保留。不查询当前进程，不把历史活跃观察写成当前存活，不把缺退出记录的完成投影当作完整退出证明。

示例：[正常完成](examples/normal.json)、[owner崩溃后仍暂停](examples/owner_crash_blocked.json)。包含原回执公开字段、Plan/Run关联、历史进程/退出/Artifact验证与事件；不含授权、连接秘密、命令、环境、原Artifact字节或原始日志。报告是声明时点的只读数据库视图，不是当前状态证明、签名或执行许可。

## 作用域、限制与停止

单槽只保护一个实验存储；进程集合只覆盖固定夹具的四个角色。没有主机总槽、跨Project保护、任意进程树/Job Object、自动领养或恢复监控，没有真实进程对账/终止平台。SQLite维护拒绝保持，未验收断电或OS崩溃恢复；解释器/脚本摘要不是完整依赖供应链证明。同OS用户任意shell/调试/改库不在隔离威胁模型内。

下一最小切片建议：另行授权后先定义测试进程Backend的显式对账与遗留进程观察契约，明确何种退出证据可以采纳；继续禁止自动接管、重试或强制成功。本轮不实现、不启动该切片。

Stable和生产数据未访问；未运行Abaqus/Datacheck/旧Runner，未改共享环境，未关闭其他用户进程。没有Git切换/恢复/commit/push，没有版本调整或迁移。成果留在Dev未提交工作区，到此停止，不进入Run007。
