# Run021B — 精确产品控制契约

本轮用户明确扩展了开发授权：允许实现、隔离测试真实 Grant 登记、单次派发和安全停服；不批准当前候选的真实执行。先重新审查源码，未恢复上轮被拒补丁。新增代码本轮通过正常工具审批落盘，没有规避审批。真实 Abaqus 调用为 0。

## 实际调用链与复用

`正常 Dev GUI / 独立 Python → ServiceLifecycleManager / Public Client → 同一 Supervisor → ExecutionService → 既有 StandardBackend → 原 Store / Job Object / DAT validator`。

| 实际文件／函数 | 本轮职责 |
|---|---|
| `product_standard.prepare_product` | 在原 initial preparation lease 内验证空产品 Project；写一个 Job/Plan及两个DPAPI准备文件，不创建Grant/Run/服务 |
| `product_standard.inspect_preparation` | 原只读Store读取固定Plan，复核输入/Runtime/输出冲突；不竞争执行所有权 |
| `product_standard.StandardOperator.request` | 读取独立受保护操作者能力，经原认证IPC向当前owner发请求；不是直接写库 |
| `execution.product_standard.ProductStandardControl` | 精确批准／派发、版本与期限核对、原management事务和回执 |
| `standard_contract.prepare/check_plan/check_grant` | 新single模式；原unmanaged及pair摘要语义不变。固定入口、输入、Job、资源、管理策略分别核对 |
| `service.submit/_execute_pending` | 原接收事务、Grant消费、slot/START_INTENT、Backend调用及异常阻断；single分支保持PAUSED |
| `store.dispatch_scope` | 原owner锁内，只允许当前control选中的Run进入执行工作域 |
| `supervisor` | 同一执行线程、原IPC；产品动作仍需独立能力，普通连接不签发许可 |
| `service_lifecycle/service_owner/lifecycle.require_idle` | 读取明确单项产品扩展；启动及停服共用精确Plan范围和空闲检查 |
| `examples/agent_first/product_standard_acceptance.py` | 薄的固定清单核验及显式操作者步骤；没有进程启动实现，未新增执行核心 |

不改Schema：仍为product manifest v1 / execution store v3 / af-local-json-v1 / 0.3.0.dev0。没有数据库迁移，没有GUI布局或MCP写工具修改。默认New仍生成空TEST能力配置，无任何任务Grant；单项Standard配置只能由可信初始准备操作明确安装，不能靠客户端改Backend字段升级。

## 权限

三类能力独立：连接credential、lifecycle operator、Standard operator。Standard能力新建为32随机字节的hex串，以现有当前Windows用户DPAPI保护；private目录继承原当前用户/SYSTEM DACL，绑定Project上下文。普通FakeClient不能读取该能力。生命周期Start/Stop权限不能替代执行批准；GUI没有批准入口。

同一OS用户的任意代码/文件权限仍是信任边界，这不是生产级人类签名审批平台。`subject/source`只是操作者记录的实际授权来源，不能单独授权。不得填写虚假的授权出处。

真实Grant复用原grants表、TrustedStandardOperator/REAL_FIXED_STANDARD类别及原消费事务。新增精确product_scope绑定Project/context、Plan ID/digest、Backend、入口材料、输入字节、Job/cwd/scratch/output、资源、受管策略、单次预算；还记录subject/source、owner、批准操作ID与有效期（最多600秒、且不超过Plan）。TEST_ONLY不满足此范围。每Plan至多一次成功批准，每Grant至多一个Run；本轮候选未登记任何Grant。

## 全局PAUSED下的精确单次派发

选择了更窄的政策：**不打开全局OPEN**。先接受精确已批准Plan，原接收回执、Run和消费原子提交；此时仍PLANNED/PENDING且PAUSED，无外部创建。随后独立操作者动作绑定Run、当前owner、revision、gate版本和截止时间。要求同库仅此一个Run、槽空、无输出冲突、当前Grant/输入仍有效。

派发许可写入原Run的single_dispatch=ARMED，并同事务写管理回执和control event。owner执行线程只选该Run。slot领取、START_INTENT、single_dispatch=CLAIMED和观察上界在同一claim事务提交。全局gate仍PAUSED。实际创建前再次核验原Plan、Grant、owner、许可及窗口，原生创建API在属性准备后也检查deadline。许可只能消费一次，不存在通用OPEN机会。

服务允许的启动窗口最多30秒；冻结候选明确选25秒。观察从CreateProcess返回的monotonic时点最多300秒，并被claim时间+300秒截断；创建耗时可能缩短可观察时间，不是Solver强制运行上限。到期仅结束观察，既有Backend不kill、不重试、不删除。

消费后owner崩溃、创建不确定、记录失败或证据不足，不重新选取CLAIMED Run。dispatch异常也设置本owner的保守阻断；重启新owner不会复活旧owner许可。窗口到期可记录DISPATCH_BLOCKED，不能迟到执行或自动补发。未决Run使产品start/stop拒绝，需要未来独立恢复流程，本轮没有添加恢复捷径。

幂等使用原management_receipts。命名空间分别为 `product_standard_authorize`、`product_standard_dispatch_once`。认证和Project绑定后，同键同内容返回原回执；旧owner回执可重放但不能形成新转换。不同内容冲突。普通公共只读 `management_receipt(action,key)` 可确认提交结果。请求中的operator_token不参与持久请求摘要、不写入回执。应答未知先查原键，不换键；示例持久化原操作参数以保留原owner与原deadline，不延长窗口。

## 正常收尾、停止与重启

沿用Run015/016的创建时JOB_LIST和无KILL_ON_JOB_CLOSE策略。scope结束、Solver、数值、ODB和物理全集互相独立。正常scope结束证据、事件、状态与slot释放沿用原事务，single路径始终PAUSED。行政释放不满足正常managed completion要求。

Stop仍需独立lifecycle权限、精确owner，同一owner mutex/事务内先写PAUSED、再检查active_dispatches=0、slot为空、无PENDING/UNKNOWN/未决启动/行政处置。Standard只支持扩展绑定的single Plan，必须FINISHED、reconciliation NONE、COMMITTED_EMPTY_SCOPE、有效管理证明及原STANDARD_MANAGED_COMPLETED事件。失败检查回滚，不删除历史或输出。停止不证明域外进程已退出。

正常停服后记录原stop receipt和停止标记，重启新owner始终PAUSED；Grant消费、Run、原回执、历史证据不变。仍有未决Run时拒绝重启而非接管。已消耗或失效的授权不返还。

## 宿主及未验证事项

产品owner由既有ServiceLifecycleManager固定解释器、`-I -S -B service_owner.py`、磁盘stdout/stderr、close_fds、CREATE_NO_WINDOW启动；未使用breakaway、服务、计划任务或伪造父进程。Standard在实际owner中核对Job查询、解释器、磁盘标准句柄，再由原managed API绑定根进程。

Windows替身证明正常GUI完整退出后，该产品宿主和受管Python仍运行；不证明真实Standard产品宿主已兼容。scope只覆盖根和继承的CreateProcess后代；不证明完整Job层级、域外服务、终端关闭、注销、关机、整机资源互斥或所有物理资源归还。真实兼容与本次实际数值仍待新授权。历史DAT样本仅用于离线替身验证，未导入候选Run。
