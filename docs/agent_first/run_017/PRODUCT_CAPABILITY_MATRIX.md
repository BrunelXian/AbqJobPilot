# Run017 — 公开能力与GUI产品边界

判定依据：实际源码 + 本轮测试ID（[TEST_RESULTS.json](TEST_RESULTS.json)）+ 明确标注的历史实测。本轮没有重跑真实Abaqus。IMPLEMENTED_TESTED仅表示下文限定的测试范围；不等于通用产品能力。

## 跨入口矩阵

| 能力 | Python SDK | CLI | MCP | GUI |
|---|---|---|---|---|
| Project管理 | PARTIAL：legacy CRUD/归档已测；AF仅可信create_experiment，无普通管理RPC | LEGACY_ONLY：api.cli Project选择/CRUD/归档 | LEGACY_ONLY：启动显式绑定legacy Project；无CRUD工具 | LEGACY_ONLY：默认GUI Project；新查看器仅连接明确实例 |
| Plan准备/查询 | PARTIAL：离线prepare/inspect已测；执行Plan由可信设置预置，普通client.inspect_plan已测 | PARTIAL：独立offline示例已测；主CLI仍legacy预览 | LEGACY_ONLY：preflight/prepare_enqueue不产生AF执行计划 | PARTIAL：显示backend/Run关联，未有通用Plan编辑/审核 |
| 执行授权 | PARTIAL：可信issue函数已测，普通客户端不能mint；非生产人类审批系统 | NOT_IMPLEMENTED：主CLI无AF批准；examples可信authorize为开发入口 | NOT_IMPLEMENTED | NOT_IMPLEMENTED：展示不提供批准 |
| Job提交 | IMPLEMENTED_TESTED：FakeClient固定Plan+精确Grant；Fake/Python/Standard替身本轮，真实Standard见R16 | LEGACY_ONLY：--enqueue-only；独立standard_client示例不是主CLI | NOT_IMPLEMENTED：prepare_enqueue只dry-run | LEGACY_ONLY：默认GUI能启动旧Runner；新连接模式只读 |
| Run状态/事件 | IMPLEMENTED_TESTED：run/receipt/events/progress/gate，认证Project绑定 | LEGACY_ONLY：旧status/list；AF例子提供有限流程报告 | LEGACY_ONLY：job_status/list_jobs/locate_outputs，旧Project语义 | IMPLEMENTED_TESTED：显式连接的单请求查看，真实Tk进程关闭/重连本轮固定Python替身通过 |
| 诊断/验证 | IMPLEMENTED_TESTED：diagnose/export同快照；独立validate_run，需既有精确权限 | LEGACY_ONLY：旧preflight/status；AF示例诊断不是通用命令集 | LEGACY_ONLY：预览/输出定位；不验证ODB或AF Run | PARTIAL：显示进程/Solver/validation分维度；无显式验证/诊断导出按钮 |
| 控制/对账 | IMPLEMENTED_TESTED：精确管理许可下Fake采纳、记录退出收尾、closeout、resume | NOT_IMPLEMENTED：主CLI无AF控制 | NOT_IMPLEMENTED | PARTIAL：只读呈现部分待对账/closeout；legacy stop_after_current独立 |
| 正常服务发现/任务列表 | NOT_IMPLEMENTED：须已知endpoint/credential及请求键 | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED：默认run_gui.py仍legacy |

不存在“普通Agent客户端拥有批准能力”的解释。SDK表格的可信准备函数和连接客户端是不同角色；同OS用户能直接运行Python不等于权限隔离完成。CLI脚本、GUI按钮、MCP tool也不能仅靠approved=true穿透执行服务。

## 实际接口与副作用

| 入口 | 调用者/输入输出 | 业务写入及许可 | 证据 |
|---|---|---|---|
| `abqjobpilot.execution.client.FakeClient` | endpoint+credential，Project/owner绑定；health/inspect_plan/receipt/run/events/progress/validations/diagnose | 查询无业务写入；无法发现任意服务 | fake_supervisor、public_workflow、diagnostic_supervisor、run_diagnostics |
| `submit` | 明确Plan ID/digest、Grant、幂等键→原回执和Run | 接受事务；权限由服务校验；重放不二次执行 | execution_contract、standard_backend、standard_managed_windows |
| `validate_run` | 明确Run及精确测试validation许可 | 独立验证可追加记录，不能当查询 | public_workflow；不提供任意新真实ODB验证 |
| `preview_* / apply_* / resume_dispatch` | 明确Run/revision/owner/摘要、独立操作key | preview只读；apply/resume精确管理许可且分开；原回执可重放 | fake/process reconciliation、standard_closeout、closeout_windows |
| `abaqus_preview.prepare/inspect/export_preview` | 显式Project声明、Profile、工程root/cwd、输入→不可执行预览 | 有界文件读；显式客户端新文件导出；无Store/Grant/Runner | abaqus_preview、integration非仓库进程 |
| `api.AbqJobPilotClient` / `api.cli` | legacy Project/Runtime JobRequest | dry-run默认；实际enqueue仅JSON队列，无Solver-start | public_api、queue_only_enqueue、project_*；CLI未全量实跑 |
| `mcp.ReadOnlyTools` | 显式legacy Project | 五个只读/预览工具，无入队/批准/执行 | mcp_readonly本轮11项测试 |
| `examples/agent_first/*service.py` | 可信开发设置+启动/批准/停服入口 | 可持有写owner/铸造限定许可；不能暴露为普通Agent任意工具 | standard_admission、standard_supervisor、managed_windows；历史实测清单另存 |

MCP保持原五工具：`abq_preflight`、`abq_list_jobs`、`abq_job_status`、`abq_locate_outputs`、`abq_prepare_enqueue`。没有为功能对齐增加写工具。其capabilities的solver_start=false描述该legacy表面，并不否认另一个授权服务的真实Backend。

## GUI字段核查

`gui_app.py`显式连接分支与`execution_gui.py`是现有窗口的适配，不是新演示窗口。`Reader`后台读取，Tk线程从有界队列取最新视图；故障显示断线和最后更新时间，不以缓存当当前实时状态。

| 信息 | 当前表现 | 缺口 |
|---|---|---|
| Project/instance、Run、回执 | 已显示；连接文件根身份固定 | 不会自动发现Project；仅一个request_key |
| Job/Plan | Run含逻辑关联，显示Backend及执行阶段 | 缺独立清晰Job与Plan审核行；不能冒充完整任务浏览器 |
| 接受、等待、启动、运行、验证 | queue/execution/phase/outcome分开；实时进度有界 | 全屏由多次读组成，无同一原子时刻保证 |
| 连接/最后更新时间/日志 | 已显示，后台有界刷新；慢IPC不锁Tk | 新owner凭据交接需可信入口；GUI不自动修复 |
| 进程、退出、受管范围 | last observed/exit/managed scope及closure展示 | 历史观察不是本次OS探测；外部成员完整性仍可UNKNOWN |
| Solver、DAT、Artifact/ODB | 分维度显示；Fake不显示Abaqus成功 | 通用验证工作流与ODB内容未实现 |
| 对账/行政/路径保留 | Standard closeout评估可读、UNKNOWN不掩盖 | 不提供人工批准、全历史决定列表或资源全景 |
| PAUSED/OPEN与槽 | gate读取已显示；Standard closeout显示slot关系 | 缺通用Project级槽/任务摘要；Run018宜补最小只读接口 |
| GUI退出/重开 | 只结束Reader/窗口；不停止owner，不提交/批准/resume | 注销、关机、重启不在已验收保证内 |

## README修正

两份README只修正当前Dev段落及笼统的“仅GUI执行/真实验收尚未发生”：区分legacy入口与独立服务，链接Run016历史真实结果及本轮基线。旧发布记录、Run001R、Run010/011/013/016准备报告保留原时点。历史USAGE中的“仅准备、调用0”不改写成现在状态，应结合各自real_001报告阅读，不重新点击历史执行入口。

## 产品债务优先级

- P1：默认启动/服务发现缺口；连接描述符和request_key是开发支架，Run018收敛只读attach和任务列表。
- P1：真实准备/批准仍固定本机和固定模型；发布前需要可审查的Runtime Profile、可信批准界面和配置安全边界，不能扩任意命令透传。
- P1：legacy与AF工程路径没有跨权威租约；生产开放混用前必须隔离或统一保护。
- P2：历史Fake命名、文档段落、重复证据转换器、示例文件硬编码；逐项契约回归后整理。
- P2：GUI尚无完整Job/Plan审核、资源保留和历史处置列表；先复用公共投影，不直接写库。

本轮未确认需要立即改写核心的P0执行安全缺陷。该结论限于已审源码与测试，不能推导为形式化无漏洞证明或已达到生产发布门槛。
