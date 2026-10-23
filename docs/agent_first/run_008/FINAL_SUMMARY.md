# Agent-first Run 008 — 最终交付

**PASS_ABQJOBPILOT_AGENT_FIRST_RUN008_PUBLIC_CLIENT_WORKFLOW_READY**

仅表示公开程序化客户端在隔离TEST_ONLY环境中完成操作者预置Plan及授权的固定测试Backend流程。不表示真实Abaqus、通用工程任务准备、真实人类审批、完整Agent自主工作流或正式0.3.0通过。

## 实际改动与结果

Dev保持`Develop@fb7912ec9e0107b18f65948b147c87579c87cded`、应用0.3.0.dev0、实验Schema3。前轮38个源码/测试起始匹配R7，历史交付完整保留。本轮新增public_workflow/test_authority、两个独立示例和两组测试；增量修改六个实验模块，32个前置文件（含所有旧测试）未变。[改动范围](CHANGE_SCOPE.json)、[基线](BASELINE.md)。

复用薄客户端和原核心，仅补公开固定Plan读取、精确管理授权下的显式独立验证包装/RPC，以及可信TEST_ONLY登记入口；客户端导入延迟加载，避免连带加载writer。没有新增第二套SDK、CLI、队列或执行框架。

实际Windows非仓库cwd示例：操作者预置Plan/执行许可→独立owner→A提交并退出→worker继续→B按原公开标识重连/重放→单独授权的显式验证→同一诊断快照导出。原Run和receipt不变，只有一次物理Backend启动，固定四角色退出均有服务OS证据。普通客户端既不批准自身，也不使用控制器额外PID/屏障事实判断成功。通用Plan准备仍是明确缺口。

**359 passed，0 failed/errors/skipped，421.60秒**；原343项全部重跑，新增16项。见[R8逐项矩阵](ACCEPTANCE_MATRIX.md)、[使用说明](USAGE.md)、[契约映射](PUBLIC_CLIENT_CONTRACT.md)、[测试/进程/清理](TEST_AND_PROCESS_EVIDENCE.md)。最终示例和harness均有进程退出/句柄关闭及凭据清理记录；跨所有试验核查1698个本轮登记身份，未发现匹配存活；2个旧PID当前查询被拒绝，但均有精确身份的既有句柄退出记录，当前PID所属保持未知。失败迭代如实保留。

请求接受、执行完成、退出验证、Backend结果、Artifact验证分别表达；Solver始终NOT_RUN。显式验证追加实际验证时点和记录，不修改退出结论或自动恢复派发；diagnose只是随后读取持久化历史，导出不再次查询或验证。原断线、幂等、对账、重启暂停、崩溃阻断语义保持。

## 真实Abaqus Backend接入缺口

下表依据当前实验代码和Run001R已记录的旧架构限制；本轮没有访问Stable、运行Abaqus、查询许可证或重新验收旧Runner。

| 方面 | 当前可复用 | 尚需明确与实机验收 |
|---|---|---|
| Job/Plan工程输入与依赖 | 显式Context、固定摘要、配置/资源/输出快照；当前仅临时TXT与枚举场景 | CAE/INP/include/用户子程序等依赖闭包、版本/命令适配、外部引用边界及通用Plan公开准备；不默认复制工程文件 |
| launcher/Solver进程集合 | OS创建时间/映像、角色交接、保留句柄退出及不确定阻断 | 当前仅固定Python四角色，不能等同Abaqus实际启动器/求解器/子进程集合；各版本真实生命周期、成员完整性、退出码可得性尚未验收 |
| Solver完成与结果验证 | 执行/退出/Artifact维度独立，独立validator和历史证据 | 实际Solver日志/状态/ODB有效性和attempt归属、Datacheck证据充分性；不能用exit0或文件存在放行，Solver目前永远NOT_RUN |
| 输出身份/资源 | 单实验存储owner锁和单槽、固定临时输出不覆盖 | 外部工程路径/别名跨Project冲突、启动瞬间占用、主机CPU/GPU/许可证限制；当前不支持主机或跨Project调度 |
| TEST_ONLY与真实批准 | 计划精确绑定、可信登记、消费/幂等、管理动作分权 | 测试issuer和本地控制不是可信人类审批；真实批准入口、可审核授权生命周期与真实Backend允许动作需独立设计/验收 |
| GUI人类监督最小接口 | 公开health/Plan检查/submit/receipt/run/events/validation/diagnose；恢复与对账独立 | GUI展示固定计划与批准范围、真实批准入口、历史/当前状态区分、阻断原因和精确控制回执；不能由GUI当前Project或布尔字段暗自批准 |

## 限制与下一最小切片

真实Backend、遗留worker观察/接管、自动Retry/对账/恢复、通用进程树、跨Project协调未实现。导出不是执行许可/签名或当前进程健康证明。同OS用户任意修改代码/数据库不在此机制的隔离保证内。

建议下一次另行授权后，先定义并实现有限的公开Plan准备/检查契约，继续仅固定测试Backend，将工程输入依赖规范与真实批准入口作为单独审查议题；不把本轮示例扩大为真实Solver入口。未自动开始该工作。

Stable、生产数据完全未访问；未运行Abaqus/Datacheck/旧Runner，未改共享环境、应用版本或Schema，未操作其他用户进程。没有Git切换/恢复/commit/push或同步。本轮到此停止。
