# Run018 — 已有服务连接契约

本轮以 Develop@271c6f82fd6a4599dbae2df30d903dab2cef1f63、0.3.0.dev0 为实际起点；Git 原始状态和1135项已有文件身份见 BASELINE.json。已有大量未提交成果保留。Run017草案与本轮指令一致：只连接已有服务，不建设启动管理。数据库格式3、执行契约af-experiment-v1及原IPC版本均不变。

## 接缝与权限

| 文件／入口 | 本轮变更 | 副作用边界 |
|---|---|---|
| `run_gui.py → gui_app.main` | 正常无参数进入已有 ExecutionView 的连接模式；增加显式 `--legacy` | 默认模式不加载 legacy config、Runtime、Recent、Runner；旧类直接构造及旧显式查看参数继续兼容 |
| `service_discovery.project_identity/discover`（新增） | 从选定目录校验实例，再认证已有owner | 只读明确元数据、短暂保留只读OS进程引用和IPC；不打开数据库、不扫描端口、不拿执行锁 |
| `ReadOnlyStore.project_view → ExecutionService.project_view → Supervisor._invoke → FakeClient.project_view` | 唯一新增RPC `project_view(before_row, limit)` | 原认证、命名空间、Project绑定；只读短事务；无Backend／批准／派发操作 |
| `execution_gui.Reader/ExecutionView` | Project选择、重新连接、32项分页、Run选择；继续复用run/events/progress/validations/preview_closeout | 后台读线程；Tk只渲染；不直接写DB、不双写legacy历史 |
| `Open_Dev_GUI.vbs`（新增） | 调用登记pythonw与正常run_gui入口 | 只打开GUI，不启动owner；不是安装包或服务部署 |
| 测试驱动和helper | 正常入口UI动作、实际GUI/venv身份、70项列表、读取陷阱 | 只在新临时实例；应用不包含测试动作通道 |

Backend、授权消费、幂等提交、所有权锁、自动收尾、行政处置和恢复状态机均未改动。service/client/supervisor只增加查询分支。

## 明确的发现范围

1. 用户选择已有 Agent-first Project 目录（含`experiment.json`），不从Recent、旧GUI选择、全局Runtime或环境扫描推断。
2. 本版支持**现有实验格式3、Project直接位于显式instance root下**的布局。manifest身份、根路径、目录设备/inode、storage_generation和内容摘要构成既有ProjectContext。不存在／legacy／旧格式／未来格式拒绝，不建库或迁移。格式没有人类可读名称，界面显示所选目录及Project/instance ID，不伪造名称。
3. 默认只查明确位置`<instance root>/private/connection.json`，这是现有可信演示启动器的交接约定。可显式另选同instance root内、Project目录外的私有connection文件。没有凭据时只显示未连接。禁止UNC、相对路径、`..`、ADS及链接／重解析路径；文件上限64KiB。
4. 候选端点必须与Project的`owner.json`完全一致，再核对Project/instance、context_digest、execution_store、协议和127.0.0.1。元数据本身不是连接成功证明。
5. 根据已记录PID、OS创建时间和映像打开只读进程引用；拒绝复用或无法核实身份，认证health后再次核对真实owner进程与服务能力。连接秘密沿用原连接认证，不能通过端口存活或文件存在跳过。
6. 每次刷新／重连重新验证上述链；同Reader禁止Project改绑。切换Project销毁旧显示缓存和选择，旧线程仅完成其有界请求后退出。重连同Project保留所选Run和最后视图，但在重新认证前标为非实时。

连接文件仍按现有可信操作者交接和OS账户访问边界保管；本轮不改变ACL、不把凭据复制进Project或报告，也不声称能抵御同一OS用户主动改写代码/数据。只读进程检查只核对owner，不重新探测Solver或补造历史退出证据。

**兼容限制：**旧的已在运行owner可能未加载`project_view`。返回`CAPABILITY_UNAVAILABLE`，绝不替它重启／升级。Run016保留owner不作为本轮目标，继续用原查看入口；本轮未读取其存储或连接材料。实验布局之外的Project与生产迁移留待后续。

## 有界查询

`project_view(before_row=0, limit=32)`返回`af-project-view-v1`：Project/instance/context身份、当前gate/slot、一页Run/Job/Plan/backend及各状态、原始接收回执公开ID/key/时间、下一页rowid游标、读取时间。

- 同一短`mode=ro`、`query_only`、DELETE-journal事务读Run/receipt/plan/gate/slot；busy timeout0.2秒、查询预算0.75秒；关闭事务后才解析投影与传输。
- 按既有服务端命名空间过滤；倒序rowid keyset，最多32项（内部多读1项判断下一页）。各页是不同快照，不承诺跨页原子视图。槽位可引用未在当前页的Run，绝不能因列表没出现就宣称空槽。
- 单Run和Plan原始字节各64KiB、receipt4KiB、整页原始内容256KiB；公开字段仅标量白名单，经既有`bounded_tree`限制，结果最多128KiB，仍小于原IPC响应上限。超限明确拒绝，不静默截断声称完整。
- 不输出Grant、authority、credential、输入路径、任意事件payload或环境。标识是公开关联字段，不是通用匿名化；列表不代替完整诊断导出。
- 缺库、损坏、未来格式、journal/WAL、繁忙等沿用已有拒绝；不会隐式初始化／恢复／修复。

## GUI状态与关闭

Project列表来自一次数据库快照；所选Run、验证、日志与事件是随后独立的有界公共查询。页脚明确这不是数据库／文件／进程的统一原子快照。日志最多128条、事件最多64条；事件游标是Project全局序号，其他Run的序号空隙不当作丢失。

显示原Run/回执、Job/Plan、owner身份、实际持久阶段、gate/slot、受管范围及其历史活动数、退出证据、Solver、Artifact、DAT/ODB及对账／行政资源保留；没有字段时写未记录。固定Python一直显示TEST、Solver NOT_RUN。范围结束不提升Solver/数值状态。

IPC工作在线程，Tk不等待网络。失败显示DISCONNECTED、稳定原因码、中文说明、最后成功时间及“缓存不是实时”；失败不表示任务取消／结束。关闭只停止本GUI读线程和窗口，不发送任何控制RPC、删除凭据／锁或释放Run句柄。重开需重新选择明确Project与Run，不记忆生产目标。旧legacy界面仍单独使用；只有用户明确进入legacy时才执行其原初始化。

## 本轮不支持

自动启动/接管owner、真实批准UI、GUI任务提交、MCP/CLI写能力、迁移、主机级资源协调、Windows Service、注销／关机／终端关闭生命周期均未实现或验收。下一切片应设计独立的Supervisor正常启动管理，不能把测试启动器中的prepare/grant隐藏到GUI连接流程。
