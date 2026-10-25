# CR-D02 — 最小实现与保护范围

本轮依据 CR-D01 review_001 的 Inspect 设计实现只读诊断，不实施恢复。Develop 基线 `271c6f82fd6a4599dbae2df30d903dab2cef1f63`，版本 `0.3.0.dev0`。开始时25个 tracked 修改，1512个既有非忽略候选文件的 SHA-256 在 [BASELINE.json](BASELINE.json)。历史未提交成果属于基线，不执行清理或恢复。

## 实际改动

| 文件 / 函数 | 本轮变化 | 复用与权限 |
|---|---|---|
| `abqjobpilot/execution/store.py` / `ReadOnlyStore._diagnostic_snapshot` | 从原 diagnose 提取相同有界事务；中断查询额外读取同事务的 slot、meta.owner_id、消费关系与已提交管理操作ID | 原 mode=ro/query_only、身份验证、sidecar拒绝、0.75秒读预算；无 owner lease、DDL、事务写入 |
| 同模块 / `diagnose` | 原 JSON 投影继续调用原 build_report；返回契约不变 | 原诊断/IPC/导出回归验证 |
| 同模块 / `inspect_interrupted_execution` | 新只读方法，默认不查询OS | 显式 context + Run；不调用 ExecutionService 的执行或管理方法 |
| `execution/interruption.py` | 版本化纯分类、证据引用、内容摘要；离线 Python 入口 | 复用 diagnostics 的白名单、限额、错误脱敏；复用 managed_process.check_completion 的纯校验 |
| `execution/interruption_probe.py` | 可选当前 Windows 观察；只访问快照已记录身份和绑定的 owner.json | ProcessReference(cleanup=False)；查询后关闭句柄；不枚举进程、不取得Job句柄、不启动或终止 |
| `tests/test_interruption_{diagnostics,standard,probe,windows}.py` | 新隔离诊断、故障事实、实际Windows固定Python测试 | Standard 创建接缝被原测试替身替换；模拟事实与OS证据分别标识 |
| `tests/test_execution_isolation.py` | 精确允许 probe 的 ctypes 依赖；新增只读模块禁止创建、终止、Apply、写文件的AST断言 | 旧隔离边界和原断言保留 |
| `tests/test_closeout_windows.py` / `Fixture.finish_observation` | 等待原PAUSED与quiescent-owner前提，记录查询样本 | 修复测试对Run提交先于派发退出窗口的同步假设；原eligible断言不变，未改产品策略 |

仅三个既有文件修改，其余为新文件。没有修改 ExecutionService、Supervisor、Backend、授权/派发/收尾/对账状态机、GUI、数据库Schema、版本、既有Plan摘要算法或历史报告。

## 没有重复实现的能力

Run014 的行政释放、原 UNKNOWN 与路径隔离；Run015/016 的受管范围及正常事务收尾；Run018/019 的发现认证及生命周期；Run020 的产品Project/本机凭据；Run021B 的精确真实Grant及单次派发均保持原实现。D02读取其持久结果，不重新计算或提交这些决定。

新入口不启动/连接 Supervisor。在线 owner 仍使用同一个 Store 权威；诊断对该Store做有界只读快照，不先抢owner锁。SQL事务关闭后才可进行OS观察。连接权限不被扩大成恢复授权；此轮没有新增IPC、CLI、MCP或GUI操作。CR-D04负责跨进程客户端的能力协商与展示。

## 保护与并发

写入前重算1512项基线摘要，除本轮明确修改的 store.py、test_execution_isolation.py 外没有变化；分支/HEAD未变，无冲突。最终复核见 FINAL_CHECKS.json。未触及外部历史真实Project、owner、输出或Stable安装。只读参考范围为Dev源码/文档及已授权交接副本；本轮没有执行Stable代码。

新测试根均由本轮驱动显式创建，Runtime/Recent/用户显示路径均隔离。仅固定Python测试进程；故障测试的终止仅针对夹具自己保留并核验的原句柄。诊断本身不具备终止权限。后查不能取得进程对象时不倒推历史退出；历史退出由测试所持句柄和清理记录支持。

回退单元仅为新增读入口/投影与只读快照提取；未来若撤回，不需要数据迁移或回滚Run。本轮不执行Git回退。
