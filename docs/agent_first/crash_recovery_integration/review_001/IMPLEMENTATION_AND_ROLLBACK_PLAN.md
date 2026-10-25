# CR-D01 — 分阶段实施与回退计划

这是下一轮可执行的开发任务拆分，**不是本轮授权执行脚本**。每阶段单一写入者、先复核 HEAD/工作区/环境、只用新临时实例。禁止以修改旧真实 Run、删锁、停止历史 owner 或复制 Stable 数据来验证。

## CR-D02：只读异常识别（已具备实施条件）

开始条件：批准本设计；锁定当前源码基线；接受“中断”为诊断而非 Run 新状态。无需先做 GUI 或取得真实实验许可。

最小切片：
1. 新增 execution/interruption.py（拟议）：无存储/进程创建副作用的纯规则和白名单序列化。输入是已有快照事实，输出版本化分类、reason、unknowns、evidence refs。
2. execution/store.py 仅增加/提取有界一致只读快照适配，复用 diagnose 的只读连接和错误处理；不改 _SCHEMA/transaction/owner acquisition。不能分别调用 run/events/gate 再声称同一快照。
3. 可独立新增 execution/interruption_probe.py（拟议）：显式有限、只针对已记录身份的查询；可复用 process_handles.ProcessReference(cleanup=False)，返回的是新观察，不替代旧 exit evidence。boot来源应通过可测试provider注入；调用者不能自报可信事实。无任务管理器/任意进程名扫描、无任务终止权限。
4. 新 tests/test_interruption_diagnostics.py（拟议）先纯事实矩阵，再新临时Store读写陷阱；tests/test_interruption_probe.py（拟议）验证身份冲突/查询失败/时钟误差/句柄关闭。不得实机重启。
5. D02先提供可复用内部/离线只读Python入口，public IPC/GUI适配归D04；离线入口必须接受明确Project与Run，不能默认Recent或自动start。

停止条件：所有 D02 测试通过，快照/导出无业务写，未知处理封闭；没有新Apply、全局状态、Schema或真实Backend变化。若boot语义无法可靠证明，只保留UNKNOWN并交付缺口，不能“估算后当真”。

回退：只撤下新增只读入口及诊断投影；保留导出证据和现有功能，不改数据库。这里“撤下”是后续经授权的代码回退设计，本轮不执行 Git restore/reset。

## CR-D03：复用管理事务的受限恢复

开始条件：D02报告可解释且被确认；对管理所有权写入、权限、action效果及适用Project类型完成独立评审。普通连接凭据不能批准。

切片1（优先）：
- 新产品恢复适配器（拟议 recovery_management.py，位置在产品层）复用 product_project.open_project、local_credentials、LocalOwnerLock/acquire_supervisor_store、ExecutionService、closeout.issue 和 reconciliation.manage。
- 首先支持**已有Run的非空Store、已有明确closeout策略**。拒绝空项目进入管理模式：底层通用acquire对全新空实例可能按历史规则建立OPEN；管理入口不能依赖“通常不是fresh”保证PAUSED。限定非空未决历史、锁内重评估、建立无dispatcher会话并验证PAUSED；不修改正常启动默认策略。
- 产品DPAPI/operator授权范围单独定义到动作；不要导出明文bootstrap凑合调用旧示例，不把真实Solver operator能力扩大为恢复许可。
- 活动owner锁冲突：返回OWNER_BUSY；未获锁不能使用连接超时、PID不匹配或自建锁替代。取得锁不是确认所有worker停止。
- 保持原PENDING、Grant消费、Run身份和历史；管理会话退出仅关闭自己持有的资源，不停止历史owner/worker。

切片2（另行明确评审后）：
- 证据充分的 managed proof 未完成提交：研究独立 policy，与 managed_process.check_completion/standard_backend.persist_result 相关，但不能直接重跑Backend/validator。必须证明原scope创建/查询/绑定/后续加入封闭，且只更新未提交部分。若原证据缺失则拒绝。
- reboot/exit缺失：版本化**行政**政策，仅记录残余风险接受及逻辑槽决定；绝不扩大 standard-closeout-v1。持续隔离/PAUSED，默认只retain；关键活跃身份、锁/路径/证据冲突拒绝。不能为了完成此切片取消 product lifecycle 的 UNKNOWN/admin 停服限制。
- 如需要新的观察记录，以 observations/reconciliations 的新source/policy描述新时点；原exit、Solver、DAT不覆盖。不在此阶段实现继续观察或重新挂接。

涉及实际模块：execution/closeout.py、reconciliation.py、store.py、authorization.py（仅精确新管理scope必要时）、local_credentials.py、product_project.py、service_lifecycle.py（只诊断桥接，不放松start/stop）；新适配器。不是全都必须修改，先最小薄封装。

停止条件：原授权政策回归不变；幂等/丢应答/并发/崩溃测试全部通过；原UNKNOWN/输出/PAUSED保留；任何未知提交可查原key；不存在自动retry/resume/stop。条件不足交PARTIAL，不扩范围。

回退：关闭新action的登记与新操作入口，**保留已提交decision/receipt读取与验证**。不能删除管理记录、重新占回已经改变的槽或倒改旧状态。新字段必须可由旧reader明确拒绝，不误解为完成。若需DDL则停下另立迁移计划。

## CR-D04：Agent接口与GUI

开始条件：D02机器语义稳定；如提供Apply，D03相应policy与权限已验收。读写可以分开发版，不能让GUI展示一个尚无服务支持的可点Apply。

最小改动：
- execution/client.py / supervisor.py：只读操作白名单和能力发现、版本检查；普通query无grant mint、无恢复副作用。离线只读模式保持独立，不为了展示启动owner。
- execution_gui.py Reader/ExecutionView：异步有界读取诊断、最后刷新时间、历史/新观察分组；断线缓存过期；选择Project清空缓存；点击中断标签定位source refs。
- 配合Run023既定单根窗口/导航，由Run024负责壳层；此阶段只交付诊断组件/数据适配，不另起恢复窗口主循环。
- gui_presentation.py 与 tests/test_g2_task_workspace.py、tests/test_run006_native_evidence.py：Classic UNKNOWN_INTERRUPTED映射修正单独小补丁，检查status filter/raw/canonical一致；现有用例仅保证中断非success，需补准确标签断言。不改LegacyDB状态、Runner或token权限。
- api/cli.py、mcp/tools.py：先评估只读结构输出的新版本，五个旧工具语义不改；写入恢复工具需独立审批，本阶段默认不提供。

停止条件：GUI/Python相同报告摘要和reason；没有Tk独立恢复状态；无真实执行、自动恢复、初始化或格式迁移。多语言标签由显示资源决定，机器字段不变。

回退：隐藏新增组件/操作，继续提供现有证据查询；不改变Store决定。避免把历史诊断翻译资源删除导致审计不可读。

## CR-D05：隔离新尝试（不能提前并入Apply）

开始条件：独立需求和授权；历史处置与路径风险已明确；精确新授权和一次启动规则设计审查。Standard当前INVALID_RETRY及产品单固定Plan是实际阻断，必须显式评审扩展，不能通过将旧Run强制FINISHED绕过。

设计模块范围：execution/service.py 的新Run关联/禁止旧预算复用、product_standard.py 固定配置准备、execution/product_standard.py 单次许可、standard_contract.py 新输出身份、必要Store关系与测试。这里只列补丁边界，不承诺无需Schema或兼容审查。

测试先新固定Python替身。新Run/phase/Plan/Grant/输出+幂等身份独立，旧消费/历史/证据保留，旧路径不能复用，其他QUEUED/PENDING不动。新准备不等于可执行；真实Abaqus Retry及原生Restart分别需要后续授权和验收。

停止条件：仅新尝试准备/API通过隔离验收，未真实执行；无恢复后自动派发。若不能满足新输出隔离与严格单次限制，不提供该能力。

回退：禁用新尝试创建，保留已生成的关联与审计；不得删除已发生副作用的Run或退还Grant。

## 发布门槛与不重做清单

本轮没有修改上述任何代码。CR-D02只读工作不必等待新Schema/审批UI；CR-D03的宽政策不能借D02通过自动获得授权。每阶段只运行受影响回归，真实Solver预算始终另行申请。

已有 managed scope、normal closeout、单次派发、真实Grant、idle stop、DPAPI、public IPC、旧closeout政策保持；不复制Stable Runner、Tk token registry、JSON recovery transaction，不建设Windows Service或长期恢复daemon。

