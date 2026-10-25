# Run015 基线与改动归属

实际仓库根 `D:\Projects\abqjobpilot_dev`，分支Develop，HEAD `271c6f82fd6a4599dbae2df30d903dab2cef1f63`，版本0.3.0.dev0。开始与结束均没有未合并文件；未为了匹配历史SHA进行Git写操作。已读取实际AGENTS、环境登记及Run013/014报告、处置交接与相关源码。沿现有`docs/agent_first/run_NNN`协议新增本目录，未覆盖旧报告。

## 进入本轮时已有成果

已有修改：execution下client、diagnostics、reconciliation、service、standard_contract、supervisor，execution_gui，以及tests/run003_process.py。已有未跟踪成果：execution/closeout.py、Run014文档、standard_closeout_operator.py、tests/run014_process.py、test_closeout_windows.py、test_standard_closeout.py。均完整保留。

`BASELINE.json`保存开始时34份实现/支架摘要及394份保护材料摘要，`before/`保存本轮前源码。后来补充静态隔离测试原文；GUI产品测试开始时干净，其原文用只读`git show HEAD:tests/test_execution_gui.py`补存。不能把当前总Git diff全部归于Run015。

## 本轮新增与修改

| 范围 | 文件 / 接入函数 | 作用 |
|---|---|---|
| 新原生适配 | execution/managed_process.py：ManagedScope.create/query、check_completion | 创建时JOB_LIST、原句柄范围查询，无终止/重开/接管 |
| Backend与固定计划 | process_backend.py：ProcessFixtureConfig.binding/verify、ProcessBackend.execute；process_contract.py；process_fixture.py | 新实例显式managed档案、固定后代场景、保留关键角色退出；无普通请求动态命令 |
| 收尾事务 | service.py：ExecutionService.execute_pending | 范围证据、终态与槽释放同事务；失败PAUSED |
| 保守恢复 | process_reconciliation.py | managed未决Run不能沿旧四角色证据路径收尾 |
| 公开读取与GUI | public_workflow.py、diagnostics.py、execution_gui.py | 计划可审阅、历史范围白名单、范围/退出/验证分维度显示 |
| 原演示入口 | examples/agent_first/dev_gui_demo.py及5份R15 VBS薄入口 | 同一服务支持两个预置任务，公共提交、只读双Run查看 |
| 测试 | 新test_managed_scope.py；run003_process.py、supervisor_helpers.py、test_execution_gui.py、test_execution_isolation.py | 原生启动白名单、故障及Windows生命周期、旧契约回归 |

共修改13份已有文件，新增2份Python文件及5个薄入口，另新增本轮文档/证据。最终精确差异见`RUN015_CHANGES_FINAL.patch`和`FINAL_AUDIT_002.json`；前一份`RUN015_CHANGES.patch`保留为中间记录。

没有修改Standard Backend、存储Schema、应用版本、安装/共享环境，也没有扩大TEST_ONLY授权。默认旧ProcessFixture档案保持原行为；新机制只由可信设置在新隔离实例启用。

## 历史保护

394项保护材料结束时哈希全部一致，包含Run010/011冻结包、Run013/014报告及原真实执行数据库。历史`r_609c9bbfd9c54b3ca2fce23bbd6059e4`的revision21行政释放、UNKNOWN、PAUSED和路径保留没有被新机制重写。只做原文件摘要对照，没有对旧owner发起停止、重启、接管、恢复派发或新执行。
