# Run022 — 0.3.0 Agent-first Execution MVP 范围冻结

审查日：2026-10-25。版本仍为 **0.3.0.dev0**；本文是 RC preflight，不是发布声明。源码基线与文件摘要见 [BASELINE.json](BASELINE.json)。本轮没有真实 Abaqus 调用，没有查询或控制历史实例；以下真实运行事实只来自 Dev 内已保存的历史证据。

## 可冻结的 MVP 声明

AbqJobPilot 是 Windows 本机、显式 Project 绑定的工程执行平台。新产品 Project、公共 Python 客户端、独立 Supervisor 与现有 GUI 共用执行存储和服务权威。真实执行目前仅支持已经固定的 **Abaqus 2024 / Standard / 轴向杆输入字节 / 单阶段 analysis / CPU1 / GPU0 / 2048MB 内存请求**。准备 Plan、连接服务、授权、提交、派发、进程范围收尾、Solver 结论及独立 DAT 验证是不同动作。

“Agent-first”指程序化接口可独立于 GUI 工作，不表示软件具有自主工程决策或可以无人监督批准任意 Solver。受信任本机操作者与同一 Windows 用户的任意代码不构成 OS 安全隔离。

| 能力 | 当前实际范围及源码 | 证据／限制 |
|---|---|---|
| 新 Project | `product_project.create_project/open_project/inspect_project`；显式全新目录，manifest v1，执行存储 v3；初始 PAUSED，0 Grant/Run；无服务自动启动 | Run020；本轮 product_project/product_windows 回归；失败创建保留不可打开的 incomplete 标记，不假称不存在任何残留 |
| 服务发现/生命周期 | `service_discovery.discover` 校验 Project、磁盘身份、凭据、协议、owner OS 身份及认证 health；`ServiceLifecycleManager` 显式 start/connect/disconnect/stop | Run018–020；并发启动、丢应答保留 reservation，不能删除记录重试；旧 owner 缺能力时拒绝，不自动替换 |
| 本地凭据 | `local_credentials`：当前用户 DPAPI、用户/SYSTEM DACL、host/context 绑定；连接、生命周期、固定真实执行操作者能力分开 | 本机同用户实测；复制/移动保守拒绝；异主机/异用户真实部署与重新配置未验收 |
| 精确真实授权 | `execution.product_standard.ProductStandardControl.invoke` / `product_standard` 可信准备；范围绑定 Plan/输入/入口/资源/位置/期限，持久管理回执及消费 | Run021B；普通 IPC 凭据、TEST_ONLY 或 `approved=true` 不成为真实许可；不是通用审批系统 |
| 单次派发 | `ProductStandardControl.start_check/claim/pending` + `ExecutionService`；精确 Run/Grant/owner、短时许可、创建前再校验；全局 PAUSED | Run021B；25秒是该实验冻结窗口，代码政策上限30秒，不把最大值改写为历史授权；重连不续期 |
| 执行身份/幂等 | 原接收、Grant消费同事务；Run 预先存在；领取后写启动意图再创建；丢应答按原键查询 | Run002–008、013–016、021B；外部进程创建与数据库不承诺 exactly-once，未知窗口阻断自动重跑 |
| 受管生命周期 | `ManagedScope`：原始无名 Job 句柄，创建时 JOB_LIST 纳入根及继承 CreateProcess 后代；无 kill-on-close/breakaway，无不受管回退 | Run015/016/021B；空范围来自 OS accounting，非已枚举 PID 列表。外部服务及整机资源不在范围内 |
| 正常收尾 | `standard_backend.persist_result`：scope证明、事件、Run投影、槽释放同事务；Solver/DAT分开；失败保持保守派发 | Run016及021B；owner崩溃/句柄失效不补证明，不自动接管 |
| 结果 | `standard_dat` 严格2024版式/CP936，当前 Run DAT/STA/MSG 身份与时间归属；三项固定检查 | U1=.01mm±1e−6；S11=1MPa±1e−4；RF1=−1N±1e−4。其他未打印项 NOT_RECORDED，ODB NOT_RUN |
| GUI | `gui_app.main` 默认 `ExecutionView`；异步公共查询、Project/Run选择、有界日志及断线陈旧提示 | Run018–021B；关闭只断开；管理按钮不等于执行许可。Classic 另一入口，尚非统一导航 |
| 安全空闲停服 | `LifecycleControl.stop/require_idle`：owner mutex + 原事务，先 PAUSED 后检查 slot/active dispatch/Run/managed completion；正常停止不杀 Solver | Run019–021B；重启保留历史并 PAUSED。UNKNOWN、未决启动或行政收尾不足以满足产品正常停服条件 |

## 三次真实验收不能合并成一次

以下文件均已读取实际内容，未读取其引用的外部实验根。基线清单给出本轮读取时文件摘要；历史报告中的当时观察时间不能解释为现在还活着。

| 实验 | 实际路径/环境 | 已成立的事实 | 不能外推的事实 |
|---|---|---|---|
| Run013 real_001 | 原固定 Standard 服务、公共提交、既有主窗口的只读验收遥测；登记 Python3.12.10，Windows本机会话；尚无Run015受管创建 | [报告](../run_013/real_001/FINAL_SUMMARY.md)、[GUI退出后](../run_013/real_001/AFTER_GUI_CLOSE.json)：GUI16664、venv12700 exit0 后，owner17528及同身份 standard612句柄仍未退出；一次分析、三项DAT通过 | 11个已观察退出不证明成员全集；原Run整体PARTIAL。后续Run014行政释放不倒推该实验正常范围收尾 |
| Run016 real_001 | `StandardBackend → ManagedScope`、预配置实验Project、A→B客户端与服务端条件；Windows11 build26300 / Python3.12.10 / Abaqus2024 | [报告](../run_016/real_001/FINAL_SUMMARY.md)、[GUI退出后](../run_016/real_001/AFTER_GUI_CLOSE.json)、FINAL_EVENTS：A/B各一次，A收尾后B创建；GUI24936/venv24748 exit0后，同owner2792与standard17292仍活；重连同Run；两项三数通过 | 不是Run020新建产品Project路径；9/8个保留个体退出不等同于每个Job累计12个个体退出码；全局UNKNOWN保留；最终OPEN不授权新任务 |
| Run021B real_001 | 正常VBS GUI、新产品Project、产品生命周期、精确Grant、PAUSED下单次派发、受管Standard | [报告](../run_021b/real_001/FINAL_SUMMARY.md)、[摘要](../run_021b/real_001/EVIDENCE_SUMMARY.json)、OS_TIMELINE_REVIEW、FINAL_READONLY_STATE：1次analysis，范围total12/active0，event42/43正常提交，DAT三数通过，GUI/venv正常退出而owner继续，重连、安全停服及重启PAUSED/原回执消费保持 | **同一时点 GUI/venv全退出且Solver仍活 NOT_OBSERVED**；原报告PARTIAL。该次不能借Run016证据改成完整E2E PASS。域外UNKNOWN、ODB NOT_RUN |

Run021B 时序：最后Solver存活 `1792906104.6387055`；首次Solver已退出 `1792906105.20373`；首次GUI和venv均退出 `1792906105.7273748`。采样缺口不是数据证明的生命周期失败，也不是跨关闭存活证明。

**发布判断：** 不阻碍冻结“独立服务架构、跨GUI关闭在Run013/016受限真实路径及新产品固定Python路径验收过”的窄声明；阻碍“Run021B产品真实E2E全部项目一次通过”“所有Windows宿主均支持”的宽声明。RC发布说明必须保留限定。若发布方必须承诺当前产品入口在真实Solver跨GUI退出中有直接重叠样本，则单列P1待验，不改历史记录。

最小可选补验（本轮不执行/不建Grant）：后续另批准全新产品Project同一固定模型、最多一次analysis，预备GUI与独立身份句柄观察；在标准求解进程首次可确认存活时正常关闭本次GUI/启动器，记录两者退出后同owner/Solver仍活并重连。结束太快仍NOT_OBSERVED；不得延长模型、增加重试或降低判据。无需为本轮preflight强制补跑。

## 接口与数据权威

| 表面 | 当前可声明 | 不可混淆 |
|---|---|---|
| Python service client | 认证查询/提交已精确授权Plan、事件/证据/验证/诊断；可信管理能力通过各自受控入口 | `FakeClient`是历史类名，不表示只支持Fake，也不是许可工厂 |
| GUI | 新建/打开显式Project、显式生命周期、Run读取/日志；无真实审批/提交UI | Classic Queue由旧Runner负责，不能说该路径已统一迁移为新Supervisor |
| legacy Python API / JSON CLI | Project/预览/显式queue-only/状态与输出定位 | 没有新产品真实批准/派发入口；queue-only不等于Solver启动 |
| MCP | 既有5个只读/预览、绑定Classic显式Project | 没有入队/执行/真实授权工具；不宣称产品服务能力与Python已对齐 |

Classic `project.json` schema1.0与其数据库契约，和 `agent_project.json` v1 + experiment schema3不是同一个格式。新服务只写受支持的显式新存储；不自动初始化、迁移或打开生产库。连接元数据、当前用户凭据不可作为可移植工程包。Project owns its data；外部INP/CAE/ODB默认不复制，不把原外部文件变成应用私产。

## 明确排除

通用CAE、任意Abaqus分析/模型/资源组合、ODB内容验证、跨Project/整机资源互斥、跨主机/用户移动、自动领养未知worker、自动故障重试、无人监督任意真实批准、Windows注销/关机/重启自动恢复、生产迁移及正式0.3.0发布均不在本MVP验收声明中。已知VS2022包装器路径风险不能通过本轮修改安装解决。
