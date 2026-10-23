# Run 011 实现、证据与 Run 010 差异

## 基线与范围

实际 Dev：Develop@fb7912ec9e0107b18f65948b147c87579c87cded，0.3.0.dev0，无冲突。开始读取 Dev AGENTS、现行环境登记、已有协议与 Run010/real_001/operator_handoff_001。历史 Run001 协议记录的是迁移前解释器，采用现行登记的 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，3.12.10；无依赖安装。

全部新增内容在 `docs/agent_first/run_011`，包括独立 controller、独立 tests、候选清单和报告。没有修改已有正式执行包或原冻结代码；旧 106 项文件字节核对不变，原清单 34 项引用仍匹配。所有测试数据位于 TEST_ROOT_*.txt 指向的新临时根，未向原实验根写意图、日志或假求解结果。已有三个拒绝清理目录和中间脚本未动。

## 模块与调用链

| 文件/函数 | 职责与副作用 |
|---|---|
| controller/probe.py:main | 仅 check / execute / report；默认 check。参数只允许操作及 candidate-digest。check/report 增加进程/数据库/网络调用哨兵，无外部执行。 |
| frozen.py:load_candidate / verify_before_attempt | 固定原清单摘要、配置和路径，核对新旧材料；复用原只读 review() 的 prepare/inspect 和输入检查。只读，不调用 review.main() 的永久哨兵后再偷偷解锁。 |
| windows_host.py:current_host / admit | 当前进程 PID、创建时间、实际映像、解释器、标准句柄类型、时间与 IsProcessInJob；成功且不属于任意 Job 才准入。未创建/修改 Job。 |
| engine.py:run_once | 同进程重新检查 → 独占意图/fsync → 文件日志 → 一次固定 spawn → 有限观察 → 有界结果 → 独占报告。测试 DI 只在独立 tests/fixture_driver.py，真实 CLI 不暴露。 |
| frozen.py:spawn_frozen | 唯一真实 Popen 位置，从原 body 读取原命令行/实际 executable/cwd/完整环境，不接受任意命令或模型。本轮只用捕获替身检查参数，没有执行创建。 |
| windows_host.py:ObservedProcesses | 直接 Popen 保留句柄核实身份/退出；Toolhelp 元数据快照用于候选后代发现。复用旧 ProcessReference 核对候选 PID/创建时间/映像及持有退出引用；候选关系不等于已证明的 Solver 成员。 |
| printed_results.py:parse | 本实验的显式文本表子集。未知版式、错误、缺表、重复、错实体/分量、非有限数、未完成文本均不通过。无 ODB/CAE/Viewer 调用。 |
| engine.py:read_report | 仅历史记录，1 MiB 上限；不探测进程、重读 DAT、运行验证器、修复或写入。 |

原模型、原调用预算、原环境字典、原准入风险不变。新增的是实际实现，不宣称原包已有控制器。没有 Supervisor、正式 Run、Project DB、MCP/Agent SDK、Backend 注册或通用授权平台。

## 一次尝试与崩溃窗口

唯一保护路径固定为原实验的 `observations/attempt.json`，与 output_identity=`sha256:6f0f38365eb3d798f24be2fee936f28f7e12a6968d43f46df930c4f60e0a5d39` 关联。O_EXCL（xb）是竞争领取；完整写入后 os.fsync 成功才允许走到外部创建。不同进程、候选摘要或调用 cwd 不改变这个路径。无释放、删意图、修复、重试或换身份接口。

| 窗口 | 后续事实/行为 |
|---|---|
| 材料/Job 准入失败 | 无意图、无外部调用；返回明确拒绝 |
| 意图创建/写入/fsync 失败 | 不启动；若留下空/部分文件也永久阻断协议重用 |
| 意图完成但未调用入口时崩溃 | START_INTENT 不代表 Solver 启动；重开只读报告显示不确定，不自动再次创建 |
| CREATE_CALL_ENTERING 已写、Popen 报错或答复丢失 | 该事件不是 OS 成功证明；调用结果不确定，保留意图，不重放 |
| 进程已创建、身份/返回事实尚未写出时控制器退出 | 没有 PID 记录也不能推断未启动；测试独立登记只用于清理，不补写业务事实 |
| 观察/报告写入失败 | 已知事实与缺口分开，保持 UNKNOWN_NO_RETRY；不终止后代、不将报告缺失当成空运行 |

这是遵守协议的本地控制器的一次尝试限制。os.fsync 是操作系统确认的文件提交，不承诺磁盘硬件、断电、文件系统回滚或同一 OS 用户主动删除/篡改下的 exactly-once。外部创建与意图文件没有跨系统原子事务。

## 生命周期与时间含义

真实 execute 不读取旧 check 的准入结果；在创建意图前由同一个实际 Python 进程重新调用 IsProcessInJob(NULL)。API 成功且 false 是唯一条件，失败/unknown/true 都拒绝。[Microsoft IsProcessInJob](https://learn.microsoft.com/en-us/windows/win32/api/jobapi/nf-jobapi-isprocessinjob) 明确 NULL 检查任意 Job，并区分 API 返回成功与成员结果。

采用单调时钟，意图前开始 300 秒总观察预算；文件意图与创建耗时计入预算。创建前预算已尽则不调用。Popen 返回后若已超过期限，不新增等待。每轮检查期限，50ms 为目标间隔，OS 查询/写盘开销可能使最后一个正在执行的有限操作越过名义时间点。实际记录创建耗时、观察耗时、报告返回时间；不声称 300 秒是 Solver wall-time 或精确的进程调用返回上限。

没有后台线程、自动重挂接、进程终止 API、subprocess.run(timeout)、Popen 上下文管理或等待后代结束的 finally。父侧关闭自己的普通文件和进程引用，不关闭 Job 对象。Python 3.12 私有 Popen Handle.Close 与 `_child_created` 使用被限定到已固定的解释器/stdlib版本；用于关闭引用并避免析构函数轮询已关闭句柄，不篡改退出码。版本改变必须拒绝/重审。[Python subprocess 文档](https://docs.python.org/3.12/library/subprocess.html) 说明 run(timeout) 会杀直接子进程，以及创建阶段可能无法被超时中断；本地实际 3.12.10 subprocess.py 已纳入冻结材料，在线文档当前显示 3.12.15，不据此声称本机版本改变。

记录时间：`*_at_ns` 是 Unix 纳秒；复用 ProcessReference 的 `exit_observed_at` 是 Unix 秒；`creation_time_100ns` 是 Windows 进程创建 FILETIME 身份。`last_sample_at_ns` 指历史最后采样，不是 report 调用时健康。句柄整数不持久化为跨重启凭据。

stdout/stderr 是独占新建文件，不通过管道等待读者。报告保留文件目标/来源；控制器自身借用的标准句柄只查询类型，不关闭。真实子进程只按冻结配置继承标准文件句柄，环境不含控制器凭据或默认用户配置。

## 进程集合与结果边界

直接进程有准确 Popen OS 引用。候选后代仅从当前保留身份仍存活的父进程及创建时间关系发现，最多 128 个、8 层、单快照 16384 条；无关快照项不落盘，不记录命令行或环境。发现失败、短命遗漏、身份冲突保留未知。所有已观察引用退出不等于必需成员集合完整，因此 `member_completeness`、`overall_exit` 始终 UNKNOWN，候选实验报告整体 PARTIAL。这是首次实机调查前的诚实限制，不把 Python 夹具成员套到 Abaqus。

文件依据包括事前 job.* 不存在、固定输出位置、意图时间、后续文件身份/创建时间/修改时间/摘要、两次稳定读取，以及结果采集时原输入摘要仍匹配。最多 64 个输出元数据项；DAT/每材料 16 MiB，JSON记录 1 MiB，事件单条 64 KiB/最多20000条。日志大小没有操作系统磁盘配额；写盘失败不会触发 kill 或自动重试。没有主机/跨 Project 输出租约。

有本次 DAT、已观察成员退出、唯一版本/产品/步骤/时间/完成标志和三张完整表，才形成 VALID_TEXT_SUBSET 或 NUMERICAL_FAIL；仍不是进程证明或 ODB 验证。正常/非零退出事实独立保留，不用数值结果覆盖。没有实际 2024 DAT 样本，解析器仅承认本轮明确且可审查的文本子集，真实版式不支持时返回 EVIDENCE_INSUFFICIENT；人工样例不充当厂商输出证据。

Run010 计划中的多个观察 JSONL 合并为 controller_events.jsonl/报告，数值结果不另复制到 extracted/measurements.json。这是新候选的明确材料差异；原方案与清单不改写。报告中的来源始终为外部实验控制器，不冒充 ExecutionService 当时已持久化记录。

## 授权与复核范围

原摘要只覆盖原材料。新候选 body 引用原摘要并固定新增六个控制器文件、九个复用源码及原清单/解释器/运行库/配置/stdlib，共21项。候选清单自身不进入自身材料数组；测试支架、报告和说明不参与真实执行导入，也不在执行摘要中。

本轮没有真实批准记录。execute 是操作者将来在获得明确批准后主动调用的固定操作；摘要参数是变更检测，控制器不伪装成人类审批系统。同一 OS 用户的任意 shell/代码/文件权限不在机制可隔离范围内。内部测试 DI 可以模拟准入和固定 Python 创建，未暴露为真实 CLI 参数；也没有开放 approve/mint/force-success。
