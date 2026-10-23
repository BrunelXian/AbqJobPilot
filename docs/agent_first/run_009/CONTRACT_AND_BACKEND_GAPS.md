# Run009 离线预览契约与真实 Backend 静态接缝

本轮只新增 `abqjobpilot.abaqus_preview` 和独立普通客户端示例。没有新增执行核心、可执行 Backend、IPC 操作、数据库表或迁移。目标安装声明来自 Dev `abqjobpilot/config.py:ABAQUS_CMD` 的 abq2024 名称；只读该行，没有导入 config、探测该路径或执行程序。

## 实际接口及复用表

| 入口/实际函数 | 权限、行为及本轮处理 |
|---|---|
| `execution/client.py:FakeClient.health/inspect_plan/submit`；`supervisor.py:_invoke` | 原认证、Project/context/owner 绑定。health 仅 Fake 和显式配置的 Python fixture；inspect_plan 读取原存储计划。没有通用 prepare/convert/approve RPC。本轮完全不改。 |
| `execution/models.py:Document/canonical_json/digest/ExecutionError` | 复用不可变规范化文档、无浮点 JSON、SHA256 和结构化原因码。新类型不是 ExecutionPlan；原计划的内容、摘要、授权匹配、幂等不变。 |
| `execution/service.py:prepare/_request/submit/_check`；`planning.py:prepare_plan/check_plan` | prepare 只接严格 JobSpec、TXT 测试输入；存储中持久计划须命中既有 Backend/动作/策略。submit 只查已登记 Plan，不接受客户端计划对象。本轮未改。 |
| `execution/test_authority.py:issue_process_execution`；`authorization.py:check_grant` | 操作者 TEST_ONLY 授权只针对已存储固定 Python fixture，原 Fake 工厂只能产生测试声明；check_plan 先拒绝其他 Backend。预览没有 Plan ID/Grant/Run。没有真实授权 issuer。 |
| `execution/paths.py:local_path/no_reparse` | 复用路径基本限制；新增 `abaqus_preview/inputs.py:_open_pinned` 用 Windows OS 引用核对实际路径及文件身份、阻止普通写入/删除。没有使用默认 Runtime/Recent。 |
| `abaqus_preview/preview.py:prepare`（新增公开） | 普通离线客户端，显式 Project ID/instance 声明、Profile、engineering_root、submission_cwd、main_input、job_name → AbaqusPlanPreview。只读取允许输入/目录元数据；不读取 Project DB，不认证这些声明的真实注册归属。 |
| `abaqus_preview/preview.py:inspect`（新增公开） | 对同一预览做格式、界限、声明一致性和摘要检查；不读取输入/DB/进程。摘要不是批准、来源认证或签名；重算摘要不能取得执行能力。 |
| `abaqus_preview/preview.py:export_preview`（新增公开） | 在调用者显式且独立的导出根创建一个新 JSON。仅导出原对象，不再次准备或读取输入。不生成运行目录、脚本、锁或资源租约。 |
| `api/client.py:preflight/enqueue`、`api/models.py:JobRequest`、`mcp/tools.py:prepare_enqueue` | 旧 queue-only 路径接 JobRequest 的工程路径等字段；MCP固定dry_run。静态核查无离线预览导入/转换或执行服务注册。本轮没有运行这些旧路径。用户另行构造旧任务是独立操作，不等于本预览被批准或执行。 |

源码模块全部通过新模块 AST 依赖检查；执行核心、授权、Supervisor、旧 API/CLI/MCP、GUI/Runner 均未修改。没有动态插件、命令字符串、环境字典、arbitrary_args、eval/exec/runpy 或 Abaqus 环境文件求值。

## 数据与身份

`AbaqusPlanPreview` 封套包含 `body`、`content_digest`、`observation`。schema=`abaqus-offline-preview-v1`，支持档案=`windows-standard-static-subset-v1`。底层规范化沿用 `execution.models.canonical_json`：排序键、紧凑 UTF-8 JSON、无浮点值。输入中的实数保留在原字节的摘要里，不转成浮点 JSON。

body 固定 Project/public instance 声明、Profile ID/整数版本及完整声明摘要、产品/声明版本/阶段、主输入和全部受支持依赖的实际字节数/摘要、有序 INCLUDE 边、工程根/提交 cwd、根目录卷与文件 ID、资源、job、候选输出键、scratch 声明、检查范围和限制。内容相同则 body/digest 相同；输入字节（含注释）、依赖、配置、资源、输出或 Project 关联变更都会反映在摘要中。`observation.read_at` 不进入 body 摘要。

Profile 精确字段：profile_id、profile_version、platform=`windows-local`、product=`Abaqus/Standard`、declared_version=`2024`、phase=`analysis`、cpus=1、gpus=0、memory_mb=64..4096、wall_seconds=1..3600、scratch_relative。CPU/内存/时限是请求声明和本档案限制，既不确认可用，也不实现限制。无远程队列、用户程序、恢复或其他结果导入入口。

状态分别固定为：static_check=COMPLETED_FOR_SUPPORTED_SUBSET；dependency_coverage=COMPLETE_FOR_SUPPORTED_SUBSET；solver_input_semantics/runtime=NOT_VERIFIED；resources/output=NOT_RESERVED；real_execution_capability=UNAVAILABLE；run=NOT_CREATED；solver_conclusion/artifact_validation=NOT_RUN。没有 ready 总开关。这些是离线声明，不写入任何 Run 的状态或验证记录。

输出键是 `digest({directory_identity, job_name_casefold})`，刻意不含 Project ID。相同物理目录和 job 的不同 Project 候选得到同一键。它不是占有权：目录重建、挂载别名、其他进程、已有输出和未来竞争仍需要执行前真实保护。当前 owner 锁和槽只约束每个实验存储。保守拒绝根目录已知输入 basename 与 job 相同，不扫描旧输出，也不将其当证据。scratch 和输出分别声明；scratch 不创建，已有非目录/重解析路径拒绝。

Project 只拥有元数据与索引；外部工程内容保持外部引用，不复制、展开、改写或迁入 Project。当前读取不建立长期内容副本或以后执行的许可。

## 支持输入子集与文献范围

本轮成功取得的材料是 **SIMULIA 2025 厂商手册内容在 Virginia Tech 的镜像**，不是该校二手教程。2024 对应页面返回403，官方帮助站页面工具无法取得。此限制进入每个预览的 `reference_manual_version=2025` 和 `TARGET_2024_DOCUMENTATION_NOT_CONFIRMED`，不能因此宣布2024安装/参数行为已核验。以下是本工具独立、刻意更窄的离线词法档案；真实2024接入前必须补对应版本手册及实际行为验收。

2025 [Input Syntax Rules](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEMODRefMap/simamod-c-inputsyntax.htm) 规定相对输入引用以提交目录为基准。本工具显式令 submission_cwd=engineering_root，所有层级 INCLUDE 均按该根解释，无被包含文件父目录回退。该页还描述 ASCII、关键词大小写、注释、参数、引号与续行；本轮只实现下表和后续限制，不声称支持手册全部语法。

| 关键词 | 精确参数组合 | 数据行（词法/形状检查） | 外部依赖 |
|---|---|---|---|
| HEADING | 无 | 恰一行，1..80 ASCII字母数字/空格/下划线/点/短横线 | 无 |
| NODE | 无 | 每行 nodeID,x,y,z，ID正整数最多9位，坐标显式有界数字 | 其他INPUT参数拒绝；[NODE手册](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEKEYRefMap/simakey-r-node.htm)中的额外参数不进入本档案 |
| ELEMENT | TYPE=T3D2、ELSET=label，顺序不限 | 每行 elementID,node1,node2 正整数 | FILE/INPUT/用户单元等拒绝；[ELEMENT手册](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEKEYRefMap/simakey-r-element.htm) |
| MATERIAL | NAME=label | 无 | 无 |
| ELASTIC | 无 | 恰一行两个数字 E,nu；不检查物理合理性 | 温度/依赖/分布等不支持；[ELASTIC手册](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEKEYRefMap/simakey-r-elastic.htm) |
| SOLID SECTION | ELSET=label、MATERIAL=label | 恰一行截面积数字 | 其他参数拒绝；[SOLID SECTION手册](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEKEYRefMap/simakey-r-solidsection.htm) |
| STEP / END STEP | 无 | 无 | 只允许恰一个最终step，不支持restart等 |
| STATIC | 无 | 恰一行4个显式数字（初始增量、步长、最小、最大增量） | 仅检查形状；[STATIC手册](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEKEYRefMap/simakey-r-static.htm)的其他分析方式不支持 |
| BOUNDARY | 无 | 每行nodeID,firstDOF,lastDOF,value；前三列正整数 | 不支持命名集/用户定义/FILE |
| CLOAD | 无 | 每行nodeID,DOF,value；前两列正整数 | 不支持amplitude/用户载荷等 |
| INCLUDE | 仅INPUT=relative.inp | 无数据；递归读完整选项块 | 唯一支持外部引用；PASSWORD拒绝，[INCLUDE手册](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEKEYRefMap/simakey-r-include.htm) |

label/job 为 `[A-Za-z][A-Za-z0-9_]{0,31}`，job拒绝Windows保留设备名。所有其他关键词或参数均拒绝。数字单项最多32字符，支持正负号、小数及E/D指数（指数最多3位）；不检查单位、材料范围、节点/单元连接、集合匹配、约束充分性、收敛性或Solver工程语义。

只支持ASCII、LF/CRLF且文件以换行结束；每行1..256字符，空行/制表符/控制字符拒绝。仅原始列1、2为`**`的行是注释；关键词/参数/TYPE大小写不敏感，必须全拼（包括SOLID SECTION/END STEP中的一个空格）。引号、末逗号续行、空数据项、重复参数、参数化、加密和缩写明确拒绝。每文件的选项及其数据必须完整，不跨 INCLUDE 拆块。重复包含也拒绝，不能静默去重改变模型。模型关键字在STEP前，STATIC/载荷在该STEP内；此浅层顺序检查不是通用INP解释器。

路径只允许显式固定本地Windows盘；拒绝UNC/驱动器相对路径/ADS/设备别名/绝对INCLUDE/`..`/`.`/空组件/空格/引号/环境变量/重解析/符号链接/多硬链接。只接受.inp依赖。读取前检查路径，打开不继承的Windows引用，核对最终路径、普通单链接文件身份；持有输入引用时禁止普通写和删除，最终再查身份与字节摘要。目录引用也不允许删除。Python3.12的path/fd ctime语义不一致，不作为内容身份；必须使用内容摘要。不提供对同OS用户任意调试/改程序的安全保证，也不声称文件系统全局原子快照。普通OS I/O故障明确拒绝；字节量有界不等于保证内核磁盘I/O硬实时截止。

固定限额：8文件；主文件depth0、最多4层include；单文件64KiB，总256KiB；512选项块；单个预览/导出32KiB。超限不截断。主要原因码：UNSUPPORTED_KEYWORD/PARAMETER/DATA/SYNTAX/STAGE/PROFILE/PATH、INPUT_NOT_FOUND/CYCLE/DUPLICATE/UNSTABLE/READ_FAILED、LIMIT_EXCEEDED、OUTPUT_SCOPE_VIOLATION、OUTPUT_INPUT_COLLISION、RESOURCE_LIMIT、INVALID_PREVIEW、EXPORT_EXISTS、PREVIEW_UNAVAILABLE。消息不回显原字节或底层异常。

## 导出与失败语义

`inspect`只检查已持有对象；导出也不重读源文件。JSON含显式工程路径、公开Project关联、Profile、清单/摘要/范围和读取时间，不含输入原始字节、Runtime全量、数据库、环境变量、命令、授权或连接凭据。不是通用匿名化导出；调用者明确提供的工程路径会保留。content_digest只覆盖规范化body，非观察时间、签名或来源认证。离线文件不能导入成执行/对账许可。

导出根须已存在、无重解析且与工程根分离；target仅单个相对.json文件名。先独占创建随机.partial、flush/fsync，再Windows无覆盖rename。失败只清理本调用持有文件身份的partial，不删别人的目标。突然崩溃可能遗留.partial，查询不自动清理；不会把partial声明为成功导出。预览不保存证据快照或生成可运行脚本。

## 真实 Abaqus Backend 接入前的最小证据

下面均为未来设计/待验收，不是本轮新增运行功能。2025执行手册将job与输出文件命名关联、input与输入选择关联、scratch与临时文件目录关联；本轮据此声明候选输出目录/cwd/job及scratch，不生成实际命令。[执行过程手册](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEEXCRefMap/simaexc-c-analysisproc.htm) 只作为2025参考，2024包装器行为仍未知。

| 未来契约 | 当前可复用 | 首次真实实验前必须取得的证据 |
|---|---|---|
| 工程任务/输入 | 显式Context、预览摘要及白名单 | 对应2024文档；支持依赖闭包及使用限制；执行前重新读固定字节或显式内容固定，预览后变化必须使原批准失效；真实环境依赖不在INP子集闭包内 |
| 启动入口 | service领取/START_INTENT、固定process_backend的参数序列模式 | 实际.bat/Windows包装器、交互/后台语义、准确解释器/执行对象与参数白名单；本轮仅读config字符串，没有确认安装 |
| 成员集合完整性 | R6四角色身份交接/持有句柄、R7完整集合要求 | Abaqus真实launcher、Standard求解器及必要辅助成员/阶段集合；候选身份须OS核验；不能把测试Python四成员照搬，也不能以已登记数等于完整 |
| 退出证据 | process_backend.execute→PROCESS_EXIT_OBSERVED独立提交 | 角色、Run/Plan/attempt、创建时间/映像、观察owner/时间/来源及可信OS退出码；launcher退出或PID消失不证明求解器退出 |
| Solver结论 | 独立维度和UNKNOWN | 对应产品/版本/analysis阶段的日志/状态组合、矛盾及缺失证据策略；exit0、文件存在、旧成功日志不等于求解成功 |
| Artifact身份 | observation/validation及明确来源时间 | 本attempt新生成输出的身份、摘要、覆盖/冲突策略；ODB等格式与内容完整性；只由独立validator产生验证结果，不伪造历史 |
| 真实授权 | 接受事务、幂等、精确Plan绑定、过期检查 | 独立可信人类批准入口，绑定真实Backend/版本/输入/资源/cwd/输出/阶段/期限/次数；TEST_ONLY不可升级；同OS用户任意shell不属权限隔离保证 |
| 输出与资源 | 每实验存储owner锁/单槽 | 主机/跨Project实际输出物理身份排他，在启动瞬间保留；CPU/内存/scratch/许可证的占有及释放条件。目录为空不等于无竞争 |
| 崩溃窗口 | 接受→领取→意图→OS创建→身份→退出观察→终态 | 每窗口真正owner退出与存储失败；没PID不等于没启动；锁释放不等于旧Solver退出；不自动接管/重跑/强制收尾 |
| GUI/上层监督 | 当前公开状态/证据/管理回执读取 | 展示精确候选计划与未验证项、可信批准、原回执与当前状态分离、阻断原因/独立验证/恢复；不从GUI当前Project猜上下文 |

厂商环境层级参考包括站点、用户和作业目录设置，环境文件使用Python语法；本轮既不读取这些真实文件，也不求值或运行任何环境查询。未来须固定或明确记录实际生效环境，不能把Profile声明当已验证Runtime。[环境设置手册（2025）](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEEXCRefMap/simaexc-c-envfile.htm)。

未来必须分别呈现接受、启动尝试、进程证据、完整成员退出、Solver结论、Artifact身份完整性及独立验证。R6/R7只是固定测试成员集合的证据。本轮不实现活进程重挂接、观察会话、自动接管/Retry、任意进程树控制。SP-InvOpt、RL-LAM-ScanOpt等科研目标、目标函数与算法继续属于上层项目。
