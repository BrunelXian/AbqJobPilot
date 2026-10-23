# Agent-first Run 003 — 最终交付

**PASS_ABQJOBPILOT_AGENT_FIRST_RUN003_FAKE_SUPERVISOR_RECONNECT_READY**

仅表示独立Fake所有者与客户端重连验收通过；不是完整模拟MVP、主机资源协调、真实Abaqus或正式0.3.0验收。

## 1. 基线与改动

Dev `Develop@fb7912ec9e0107b18f65948b147c87579c87cded`，应用保持0.3.0.dev0。起始Run002的20个未跟踪文件保留；13个源码/测试与前置哈希一致。详见[基线](BASELINE.md)。没有要求工作区干净，也没有提交或推送。

新增4个实验模块：ownership、protocol、client、supervisor；修改原store/service以接入OS锁、独立owner生命周期、保守重启与只读幂等重放。Fake、计划、授权校验、独立验证实现及旧Runner/Settings行为不变。新实验格式为2，格式1只读兼容、写入接管拒绝，无迁移。

新增2个测试模块与2个进程harness文件；仅对原隔离AST测试增加新模块的精确依赖白名单，原启动trap与契约断言保留。Run002原契约/存储/夹具文件不改。当前源码相对Run002变动文件只有store.py、service.py、test_execution_isolation.py，另8个源码/测试为本轮新增。21个最终源码/测试绑定于[SOURCE_HASHES.json](SOURCE_HASHES.json)。

新增本目录基线、[实现与协议](IMPLEMENTATION_AND_PROTOCOL.md)、[逐项验收](ACCEPTANCE_MATRIX.md)、[生命周期与隔离](PROCESS_AND_ISOLATION_EVIDENCE.md)、总结，以及JUnit/输出/进程证据/哈希。历史Run001R/Run002报告、根AGENTS、README保留。

## 2. 实现行为

- 一个显式Supervisor绑定一个临时实验存储，持有Windows排他锁及原ExecutionService；每存储单槽，跨进程竞争或旧受支持写入口不能绕过活跃owner。
- 独立工作线程读取数据库中的已接受Run，再调用原execute_pending。提交应答、客户端等待和Fake存活解耦；六个有界短JSON RPC共享原提交/查询契约。
- 连接凭据、固定服务端namespace和精确TEST_ONLY授权分离；每次握手校验Project/实例/context/owner；无批准、反射、任意命令或动态Backend入口。
- 客户端退出/超时/丢应答不终止owner或Run。重连按原业务key返回原receipt/Run，无重复授权消费或Fake。
- owner真实崩溃后，重启默认只读暂停；已领取未终结Run暴露RECONCILIATION_REQUIRED，PENDING单独保留；不自动对账、释放槽或重跑。原receipt可只读重放。

## 3. 实际验收

最终 **125 passed，0 failed，0 errors，0 skipped，52.10s**：95项Run002完整回归、28项Supervisor/协议测试、2项所有权/格式补充。R3-01～12逐项PASS，测试名与证据见[验收矩阵](ACCEPTANCE_MATRIX.md)，没有用总数代替矩阵。初轮27项失败及后续修正完整记录。

Windows实测27个多进程case、39个实际Python进程；4次故障终止均通过已核验且持续持有的内核句柄。最终全部实际进程和启动器退出、句柄关闭。私有连接凭据已清理，其余临时测试数据保留作审计证据。

解释器为登记的绝对路径 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python3.12.10/SQLite3.49.1/pytest9.1.0，无依赖变动。无GUI多进程复现命令见[实现说明](IMPLEMENTATION_AND_PROTOCOL.md)。没有运行无关旧GUI/Solver全量测试。

## 4. 剩余限制

当前仅Windows本机固定盘、单实验存储、一个Fake槽；所有Supervisor重启均暂停，没有自动恢复或对账解除。没有主机总槽、跨Project输出身份协调、IPC长连接订阅、GUI/MCP接入、真实批准隔离域、真实Backend、生产迁移或发布。进程终止验收不等于断电/OS崩溃恢复；SQLite sidecar需维护时明确拒绝，不在查询中修复。

同一OS用户任意shell/改程序/读凭据仍不属于应用级强对抗边界。Fake完成与Artifact验证分开，Solver始终NOT_RUN。没有影响本切片实施/验收的未解决缺口。

## 5. 下一最小切片建议（未执行）

继续Fake与临时存储，单独授权一个Run设计并实现显式诊断与人工对账契约：给不确定Run绑定不可变证据摘要/owner代际，可信harness确认后记录对账事件；保留旧Run和产物，不原地重跑；对未领取PENDING定义明确的恢复派发授权。验收应覆盖旧证据/旧owner/重复对账拒绝、对账前禁止派发、事务失败不解除门禁。暂不加入真实Backend、GUI/MCP或主机调度。

本轮到此停止，不自动进入该切片。

## 6. 操作边界

Stable完全排除且未访问；未启动Solver/Datacheck/旧Runner，未访问生产Project/Runtime/Recent/数据库，未改变共享环境，未关闭用户其他进程。未安装系统服务或启动项；未执行切分支、reset/restore/clean/stash写入/merge/rebase/commit/push；未清理恢复备份和保护引用。所有成果留在Dev本地未提交工作区。

## 7. 结束检查

最终分支/完整HEAD与起始一致，版本仍0.3.0.dev0，无冲突、无已跟踪文件diff，git diff --check通过。前置20个文件之外，本轮新增8个源码/测试和9个报告/证据文件；另对前置3个源码/测试作必要修改，均已区分来源。

21个源码/测试哈希与最终测试快照匹配；95个旧case身份完整包含于125个最终PASS；12行R3矩阵的18处测试名引用均存在并通过；30个本地文档链接目标存在且限Dev，代码围栏及行尾检查通过。Run002原JUnit和源码哈希文件保持原SHA-256，没有覆盖旧证据。
