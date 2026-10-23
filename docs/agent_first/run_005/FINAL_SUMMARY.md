# Agent-first Run 005 — 最终交付

**PASS_ABQJOBPILOT_AGENT_FIRST_RUN005_READONLY_DIAGNOSTICS_EXPORT_READY**

仅表示单个临时实验Run的一致只读诊断与有界JSON导出通过；不表示真实Backend、Abaqus、跨Project资源协调、完整恢复平台或正式0.3.0通过。

## 实际基线与修改

Dev仍为 `Develop@fb7912ec9e0107b18f65948b147c87579c87cded`，应用0.3.0.dev0、实验格式3均未改变。起始50个Run002～004未提交文件保留，前置25个源码/测试匹配Run004哈希。

新增diagnostics.py与audit_export.py，以及test_run_diagnostics.py、test_diagnostic_supervisor.py。增量修改store.py（有界一致只读事务）、supervisor.py（唯一新增diagnose RPC及安全传输ID）、client.py（薄查询与本地导出入口）、test_execution_isolation.py（精确新依赖白名单）。其他21个前置源码/测试哈希不变；未改执行状态机、授权消费、领取互斥、所有权、对账/恢复、旧GUI/Runner/Project/MCP或Schema。见[基线](BASELINE.md)、[契约](READING_AND_EXPORT_CONTRACT.md)、[源码哈希](SOURCE_HASHES.json)。

## 读取事实、推断及未知

一次只读事务读取明确Run、原接收回执、原Plan身份、该Run的事件/观察/验证/对账记录，以及持久派发门。Run revision、双事件序号覆盖和读取时间绑定同一SQL视图；不把进程/文件系统宣称为原子快照。退出事务后才做规则投影、序列化、传输和导出。

解释规则区分接受、等待、领取、执行不确定、历史验证FAIL/PASS、显式对账和暂停。缺持久验证只推断“记录不足以确认验证结果”；不读取当前产物补判断。无错误不意味着成功；历史PASS不是本次重新验证；对账不是恢复派发；Fake进程/退出仍NOT_APPLICABLE、Solver仍NOT_RUN。

仍未知：当前Artifact内容、owner/worker和进程即时健康、当前授权有效性、未记录的Failure Classification及缺失历史字段。报告不给置信百分比或执行许可，建议仅为需另行授权和重新检查的候选步骤。

## 导出范围

客户端将已经取得的同一份白名单报告写入明确独立目录的一个JSON；不再次查询，不让Supervisor接收写文件路径。拒绝逃逸/重解析/覆盖，写入失败只清理本次身份匹配partial，可能残留时不假报成功。

包含公开关联身份、历史状态/时间/证据引用及摘要；不含原Artifact字节、日志、完整DB/Runtime、配置/环境、绝对路径、原始载荷/错误文本、连接秘密或执行/管理许可。public body摘要与历史Plan/Artifact摘要区分，不提供签名或来源认证。三份真实样例见[三阶段证据](TEST_AND_PROCESS_EVIDENCE.md)。

## 实际验收与清理

**239 passed，0 failed，0 errors，0 skipped，118.04s**：原189项重新执行全部通过，新增48项本地测试与2项Windows多进程测试。R5-01～12均有实际测试和观察映射，见[验收矩阵](ACCEPTANCE_MATRIX.md)。首轮测试夹具自身失败与修正如实保留，没有删除旧断言或跳过关键测试。

真实SQLite并发屏障证明不混合读取前后状态；独立owner真实退出/重启后，三份报告依次记录待对账、对账仍暂停、独立恢复。诊断传输被阻塞时管理事务仍可完成；旧报告导出不混入新状态。

最终53个实际Python进程全部退出，9次故障终止仅使用核验身份且持有的测试进程句柄；私有连接凭据已清理。四次迭代全部163条进程记录均已检查退出，非秘密临时数据和故障partial保留作证据。环境使用已登记绝对解释器，未变动共享依赖。

## 未验收与停止

真实Abaqus/Solver/ODB、跨Project或主机资源协调、完整恢复控制、生产审批与迁移、断电/OS崩溃仍未验收。本轮真实测试进程仅证明指定Windows本地Fake与有界诊断/导出场景；非Windows发布、其他文件系统及更广泛故障模型没有声明支持。

Stable未访问，生产Project/Runtime/Recent/数据库未访问，未启动真实Solver/Datacheck/旧Runner，未关闭用户其他进程。没有commit/push或其他Git写操作，没有版本调整，没有迁移或自动清理旧证据。交付具备本轮限定审查条件，工作到此停止，不自动开始Run006。
