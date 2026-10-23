# Run 006 — 固定进程Backend与证据契约

## 复用与依赖

复用ExecutionService.submit的接收事务、不可变原回执、Grant消费、幂等键/摘要冲突、retry_of与新attempt；复用execute_pending原子claim、每存储slot、ExperimentStore排他所有权和Supervisor独立工作线程。没有第二套队列、存储、调度器或启动RPC。

只在受信任构造时显式提供ProcessFixtureConfig，普通Supervisor入口仍默认只有Fake。IPC submit仍只引用既存Plan/Grant；所有参数白名单、身份握手、连接秘密、帧限额和超时沿用Run003。health补充process_fixture_enabled，未增加执行命令、批准或进程控制RPC。

旧process_identity.py经utils导入config，且其“PID不存在”可进入CONFIRMED_EXITED，不能作为本轮退出证明。旧文件不改、不导入；实验process_handles.py只采用独立的Windows查询/同步句柄。进程权限不进入FakeBackend，旧Fake执行仍受有效Popen/os启动陷阱保护。process_validation只依赖纯process_contract、models和paths，不导入启动模块。

## 固定计划与权限

Backend `python-process-fixture-v1`，version1，phase PROCESS_FIXTURE，action `launch_fixed_python_fixture`。原Fake仍fake-v1/emit_fixture_result。新计划以原JobSpec、输入manifest、配置快照、expiry、资源和输出契约为基础，绑定：

- 登记解释器绝对路径、实际Python映像及两者SHA-256；
- 固定process_fixture.py SHA-256，固定Backend/version；
- normal、launcher_early、result_wait、nonzero、invalid_result枚举；
- 5～60秒固定生命周期预算（默认40秒），不接受命令参数集合；
- 单存储槽及原固定资源声明，输出固定process_runs/{run_id}/result.json、不可覆盖、上限64KiB；
- process-fixture-result-v1独立验证政策。

解释器/脚本/场景绑定在准备、接收和派发前复核；领取后若启动等待，还会在Popen前再检查owner、Plan、Grant、输入、配置及执行对象。改变或过期后拒绝，不重建计划、不返还消费或自动放槽。这里核验文件摘要和当前解释器配对，不证明整个Python依赖供应链，也不防同一OS用户在检查之后任意改程序。四个固定进程成员、生命周期和输出字节有界；原simulated_cpus资源声明不冒充操作系统CPU或内存配额。

授权仍由可信harness在持有本地owner时登记；issuer必须ProcessGrantFixture、TEST_ONLY且allowed_action明确为launch_fixed_python_fixture，绑定精确Plan/Project/资源/有效期/一次消费。FakeGrant、仅TEST_ONLY标记、自报approved或普通连接凭据不能启动进程。没有mint/approve RPC。重连不会重复消费。

## 进程拓扑与正常退出

固定夹具由登记解释器以 `-I -S -B` 启动；参数只含固定脚本、角色和内部生成的Run目录。shell=False、close_fds=True，标准输入/输出/错误使用DEVNULL。仅提供SystemRoot和PYTHONDONTWRITEBYTECODE，worker继承这一受限环境，不继承Supervisor的环境、IPC/Grant秘密、DB连接或owner锁。

Windows venv存在两个层次：launcher_transport（Popen实际启动对象）→launcher（运行夹具的Python）；launcher再启动worker_transport→worker。本轮只声明支持这个固定集合，两个角色可能在其他解释器布局中合一；目标环境实测为四个不同进程。没有通用进程树或Abaqus成员识别。

夹具身份文件提供候选PID、创建时间、映像与Run/Project/phase/Plan绑定。Supervisor对候选逐个OpenProcess，核对GetProcessTimes、QueryFullProcessImageNameW、固定映像、启动转发器关联及存活观察；保持不可继承的OS句柄。全部身份持久化后才写owner-bound握手，允许launcher退出和worker执行。父子PID只是一项关联检查，不能单独建立身份。

每个角色的退出必须由其保留句柄WaitForSingleObject已信号以及GetExitCodeProcess成功取得。没有PID/找不到进程、JSON自报完成、launcher退出都不是worker退出证明。缺失/失败保持UNKNOWN或PARTIAL。句柄数值不持久化，重启不复用。

Run process_records保存角色、PID/创建时间、映像、已核验脚本/映像摘要、观察时间；process_exits追加角色对应退出码、观察时间和retained_windows_handle来源。事件记录对应投影变更。原phase_attempt_id作为预先持久化的启动尝试身份；Run同时绑定Project实例与固定Plan。

只在全部成员已退出并有退出码后记录exit_verification=VERIFIED。退出集合的验证时间由PROCESS_COMPLETED事件的observed_at/recorded_at给出，与各角色exit_observed_at、本次诊断read_at分开；不把观察时间伪称OS实际退出时刻。全零为backend_outcome=COMPLETED，否则FAILED；独立产物验证仍可分别PASS/FAIL/UNKNOWN。Solver始终NOT_RUN，验证scope=simulation。有效产物+非零退出不会抹掉进程失败；正常退出+无效产物不会获得有效结果。只有正常确定终结才释放slot。

## 存储、只读诊断与兼容

实验Schema仍为3，复用Run JSON和追加事件，不迁移、不初始化旧库。旧Fake格式/状态不变。新Backend未配置时不能执行其Plan；旧版代码对新Backend无法通过Fake Plan检查，不获得执行能力。

新进程报告使用af-run-diagnostic-v2/process-diagnostic-rules-v2。Fake继续输出v1；导出器同时接受两种明确白名单报告。新增历史进程角色、PID/创建时间、摘要、观察/退出时间与退出来源；不输出映像绝对路径、命令、环境、授权或原始payload。读取时间仍独立；诊断不探测进程、不重新验证文件。最后一次身份存活观察不表述为现在存活；缺完整退出证据有PROCESS_EXIT_NOT_ESTABLISHED。进程完成不落入FAKE_COMPLETED默认分支。

Run005一致短只读事务、记录/字段/总字节/等待限额、无覆盖导出、原快照导出均不变。v1历史报告不补造进程证据。Run004 Fake采纳在读产物前明确拒绝PROCESS_FIXTURE；不存在本轮进程对账、强制成功或自动释放入口。

## 故障顺序与界限

1. 接收事务创建Run/回执/消费记录。
2. claim原子占槽并写START_INTENT，已有phase_attempt_id。
3. 创建固定manifest后，在process:before_create屏障前尚未启动OS进程。
4. Popen及直接转发器句柄后到process:after_create；候选worker可能已存在，业务库仍无身份记录。
5. 受限握手核验并提交PROCESS_IDENTITIES；process:after_identity之后才放行worker。
6. process:before_exit_record可停在真实退出之后、首条退出记录写入之前；每个退出观察随后分别提交。process:after_exit具有全部退出观察，但最终“集合齐全”投影尚未提交。
7. PROCESS_COMPLETED后独立验证，process:before_terminal在终态事务之外；最后一个事务写ArtifactObservation/Validation/FINISHED和释放slot。

任何owner退出都不证明worker停止。接管OS锁只建立新owner管理身份；旧START_INTENT/VALIDATING及占用slot继续阻断，新owner默认PAUSED。不自动领养、续监、重试、杀遗留进程或采纳已有结果。普通客户端退出/超时不改变工作线程。

写入身份、退出或终态失败保留既有确定事实，并进入不确定语义；DB回滚不撤销进程或文件。没有PID不推断从未启动。SQLite有journal/WAL/SHM时仍沿用明确维护拒绝，不因本轮功能隐式恢复。事务内部被杀导致维护条件与“提交前、无开放写事务”的进程崩溃窗口分别说明，不能伪称同一种恢复能力。

清理控制器额外持有的身份和退出码只用于测试观察/清理，不注入被测服务。清理之后原不确定Run仍待未来显式对账，未改为成功。
