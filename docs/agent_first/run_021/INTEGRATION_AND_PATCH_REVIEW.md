# Run021 — 产品 Standard 接入审查（PARTIAL）

## 当前事实与阻断

实际 Dev 为 Develop@271c6f82fd6a4599dbae2df30d903dab2cef1f63，版本0.3.0.dev0。已读取根AGENTS及环境登记，适用上级未发现AGENTS。沿用追加Run目录保存，不覆盖历史报告。Run016实机结论来自其real_001报告，未查询/停止任何历史owner，也没有访问其工程或数据库。

| 接缝 | 实际代码依据 | 本轮判断 |
|---|---|---|
| 普通产品创建 | product_project.create_project | 新目录、format1产品封装+format3存储、PAUSED、无Grant/Run/service；可复用 |
| 独立客户端认证 | local_credentials + service_discovery.discover | 当前用户DPAPI、context/host/物理身份、owner/协议认证；可复用 |
| 产品服务配置 | service_lifecycle.configure_lifecycle/_profile、service_owner.main | 只接受process_config；没有固定Standard配置或精确计划绑定 |
| 产品启动/停服 | execution.lifecycle.require_idle、supervisor.FakeSupervisor.__init__ | 拒绝Standard计划和Run；lifecycle存在时要求standard_config=None |
| 受管Standard计划 | standard_contract.prepare/check_plan | managed模式必须standard-managed-pair-plan-v1和standard_sequence；Job限定r016_bar_[ab]；无单项产品计划模式 |
| 真实许可 | standard_contract.issue_execution/_issue | 现有可信入口需owner lease；独立脚本不能绕过已运行Supervisor写库；无精确计划的在线操作者登记入口 |
| 接受与派发 | ExecutionService.submit、store.dispatch_scope/pending_for_owner | PAUSED只允许原回执重放，不接受新Run；不存在“先接受唯一Run、再显式只派发该Run”的产品契约 |
| 管理恢复 | reconciliation.resume_dispatch | 原精确管理Grant打开整个gate；不是固定计划单次派发，也不是自动归PAUSED的单次窗口 |
| 正常范围收尾 | standard_backend.persist_result | 受管范围EMPTY确认与证据/槽释放同事务；成功时保留OPEN，失败PAUSED。不能直接满足本轮单次产品验收结束策略 |
| GUI | execution_gui、public project_view/progress/diagnose | 可显示分维度状态；连接/选择/关闭不批准、不提交、不恢复。无需另一套GUI |

两个新增测试直接复现：未提供pair的managed prepare拒绝且0Plan；只有无Grant的pair计划也使产品start在预约/进程创建前拒绝。它们不是“新链路通过”，而是证实缺口及现有保守保护仍生效。

## 自动审批阻断及范围解释

本轮尝试提交一个新 `execution/product_standard.py` 控制入口补丁，用原owner事务、management_receipts、grants实现精确Plan操作者登记和单次派发。自动审批拒绝，补丁**未写入**。原始理由：

> 该补丁新增可签发真实 Grant 并打开派发门的持久化控制能力，超出 Run021 明确要求的“不得创建真实 Grant、打开派发门或提交 Run”及复用既有授权机制的范围。

用户同时允许必要最小接入实现及替身测试，但自动审批对上述新增能力与本轮禁止实际许可/开门的解释发生冲突。本轮没有重试写入、换工具绕过、放宽现有保护或改用独立控制器。继续完成与此无关的材料、既有路径测试、审计。需要的是**允许实现和隔离测试这项新增能力的范围确认**，不是现在批准真实Grant或Abaqus调用。

## 待评审的最小补丁范围（未实施）

1. 在新产品的首次准备租约内，登记一个明确的受管Standard配置及**唯一Plan摘要**；新建默认TEST_ONLY配置不变。凭据另用现有DPAPI保护，不复用连接或生命周期能力批准任务。失败配置不得可启动。
2. 增加独立的单项managed Plan模式和严格Job规则，复用现有固定输入、入口、资源、managed_process身份及DAT政策，不修改旧pair摘要/授权语义。
3. 真实批准发生在活跃owner内，通过精确本机操作者能力和原transaction/management receipt登记，字段仅含绑定Plan、owner、有效期、幂等键和实际授权来源；无任意Backend、命令、目标状态或approved布尔值。普通连接credential与Stop能力不能批准。
4. 接受和派发分开：仅此Plan可在PAUSED提交；Grant消费与原回执仍同一接受事务。显式单次派发绑定原Run、revision、gate版本和当前owner，并核对无其他未决任务。
5. 派发许可建议30秒启动窗口、真实Grant最多600秒；实际创建前再次核验。领取/持久启动意图事务中消费单次派发机会并归PAUSED；该已领取Run仅凭同owner精确许可继续，其他任务不可执行。窗口到期/崩溃/证据失败不补发、不重跑。最终设计还需测试证明，当前未成立。
6. 空闲停服仅对同一受管单项Plan、COMMITTED_EMPTY_SCOPE、无active_dispatch/slot/未决启动/行政释放/保留处置风险成立；证据与工程路径仍保留，停服不等于物理资源全集结束。严格检查与PAUSED+stop receipt同事务。重启始终PAUSED，不恢复一次权限。

新控制能力需要单独审查权限、并发、响应丢失、事务提交不确定、当前owner变化、窗口届满、槽释放和历史兼容；不能只写成功路径。此设计不是已安装协议，也不能据此生成真实许可。

## 宿主与证据边界

Run016使用独立实验启动器及原Supervisor；产品使用ServiceLifecycleManager固定 `-I -S -B service_owner.py`，磁盘stdout/stderr、CREATE_NO_WINDOW、close_fds，无breakaway或系统服务。新Windows回归分别验证产品ProcessFixture链和旧Standard受管替身链；**两者不是尚未实现的产品Standard组合链**。

原standard_process.check_host在实际owner检查IsProcessInJob成功、登记解释器和磁盘输出；完整Job层级仍UNKNOWN。GUI及venv退出后的Python存活不证明真实Standard在产品宿主已兼容。Run016历史真实Job范围仅覆盖根及继承的后代，不是全机所有Abaqus进程、许可证/域外服务或资源互斥。仍需后续精确授权的实机测试。
