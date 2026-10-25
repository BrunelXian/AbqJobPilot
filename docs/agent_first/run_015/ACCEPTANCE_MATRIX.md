# Run015 逐项验收

本表中的 Windows 行为均由真实 Python 进程完成；故障注入与真实 owner 终止分别标记。详细结果见 `final_affected.xml`、`regression.xml`、`isolation_final.xml`，原始场景证据见 `verified_final/`，实际产品入口证据见 `gui_final/product_entries_managed.json`。没有真实 Abaqus 调用。

| ID | 场景及实际断言 | 测试（tests/test_managed_scope.py，另注除外） | 证据 / 结果 |
|---|---|---|---|
| R15-01 | 两个精确授权请求各有一个物理根启动；第一项范围结束、验证和释放槽事务提交后，第二项才有START_INTENT；同请求重放不再启动 | `test_managed_two_normal_tasks_are_transactionally_sequential`；`test_execution_gui.py::test_product_entries_starter_exits_and_owner_is_independent[True]` | PASS；`test_managed_two_normal_tasks_0.json`；产品入口事件全局序号严格有序 |
| R15-02 | launcher及四个关键角色全部退出，延迟后代仍存活时仍占槽，第二项PENDING | `test_managed_delayed_grandchild_holds_slot_without_pid_list_completion` | PASS；`test_managed_delayed_grandchil0.json`中的partial、branch/leaf保留句柄身份及退出证据 |
| R15-03 | worker → branch → 延迟leaf的真实创建；branch退出后leaf仍持槽；不是按预设四角色数量收尾 | 同上 | PASS；Job累计计数大于四角色；后代释放固定屏障并自行退出后才完成 |
| R15-04 | 六个快速子任务及其venv启动链不依赖逐PID枚举；直接查询Job为空才完成 | `test_managed_transient_children_counted_without_individual_pid_poll` | PASS；`test_managed_transient_childre0.json`；累计24进程、四个关键角色记录，不能将两者混为完整退出码列表 |
| R15-05 | 未启动的空Job不算完成；属性关联失败发生在CreateProcess之前，不降级；已持久START_INTENT后失败保持未决 | `test_empty_unstarted_job_and_association_query_failures_are_not_success`；`test_managed_fault_never_releases_slot_or_restarts[managed:before_scope]`、`[managed:before_create]` | PASS；真实空Job查询 + Win32失败返回替身；外部创建陷阱和物理启动计数0 |
| R15-06 | OS创建后失败、查询故障、terminal提交故障均保持槽和PAUSED；真正owner在已查空但未提交时退出，重启不释放槽 | `test_managed_fault_never_releases_slot_or_restarts[managed:after_create]`、`[managed:before_query]`、`[terminal:before_commit]`；`test_managed_true_crash_after_empty_before_commit_does_not_release` | PASS；`test_managed_fault_never_relea2..4.json`及`test_managed_true_crash_after_0.json`；异常注入与真实OS终止都有明确来源 |
| R15-07 | 现有GUI正常WM_CLOSE；GUI及venv启动器实际退出；owner/Run/Job不变、worker仍存活、日志继续增长；重开同Run | `test_managed_actual_gui_close_and_reconnect_does_not_own_job_handle`；产品入口测试 | PASS；`test_managed_actual_gui_close_0.json`含两次GUI退出证据、重连读值及最终COMMITTED_EMPTY_SCOPE；未隐藏窗口冒充退出 |
| R15-08 | 真正终止本测试创建的owner；原worker保留身份仍存活；新owner取得存储权后保持PAUSED/RECONCILIATION_REQUIRED，不重新创建Job替代旧证明 | `test_managed_owner_crash_leaves_worker_alive_and_restart_blocked` | PASS；`test_managed_owner_crash_leave0.json`；worker随后通过固定屏障自行退出，清理没有补写业务收尾 |
| R15-09 | 第一项执行时门变PAUSED，即使正常收尾第二项仍PENDING；非零退出与无效产物也不自动继续 | `test_managed_paused_gate_survives_first_terminal_commit`；`test_managed_empty_scope_does_not_turn_failure_into_success_or_continue[nonzero]`、`[invalid_result]` | PASS；独立门状态、Backend结果和Artifact结论均保留；Solver始终NOT_RUN |

## 既有契约与失败边界

- 授权与配置：`test_process_contract.py`整组，涵盖专用TEST_ONLY、错误Backend/输入/配置、期限、任意命令参数拒绝和派发前再检查；旧Fake不能创建进程。
- 原子领取、提交幂等与所有权：`test_execution_contract.py`、`test_execution_store.py`、`test_execution_ownership.py`。不复制新的服务、授权或数据库。
- Run007对账：`test_recorded_exit_reconciliation.py`回归；新managed未决Run显式拒绝旧四角色采纳，`test_managed_fault_never_releases_slot_or_restarts`同时检查此拒绝。
- 只读诊断：`test_run_diagnostics.py`、`test_diagnostic_supervisor.py`；managed新增白名单范围字段与rules-v4，不能暗中重新查Job或产生收尾记录。
- GUI和受限真实Backend边界：`test_execution_gui.py`、`test_standard_backend.py`、`test_standard_supervisor.py`、`test_standard_closeout.py`。Standard测试仍是受控替身，未调用Abaqus。
- 静态启动隔离：`test_execution_isolation.py`保留原Fake/客户端/诊断的无启动约束，并限定新模块唯一CreateProcessW、JOB_LIST、禁止继承和禁止终止/重开/事后Assign/breakaway接口。

## 不由本表证明

没有测试终端关闭、Windows注销/重启、任意外部服务或远程进程、Abaqus包装器/求解链；没有声明完整外层Job政策；没有逐瞬时后代取得退出码。VBS入口路径和参数已静态核对，实际Windows测试运行的是其等价CLI路径，并未另行双击VBS进行重复演示。旧真实owner、行政处置及工程隔离均未变更。
