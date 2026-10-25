# Run018 — 逐项验收

以下PASS仅适用于本轮新建隔离实例与固定Python进程；无真实Abaqus、旧实例或生产数据参与。测试结果以TEST_RESULTS.json最终case为准。

| ID | 场景及实际结果 | 主要测试／证据 |
|---|---|---|
| R18-01 | 正常无参数Dev入口→显式选择Project→Run列表/选择；无默认Runtime/Recent、无DB直接访问 | `test_normal_dev_entry_managed_worker_survives_gui_chain_and_reconnect`；`run018_gui` import/DB/launch/RPC陷阱 |
| R18-02 | 无服务不启动；legacy/未来格式拒绝，Project/owner/进程创建身份/凭据/协议错误拒绝；旧能力不给自动重启 | `test_service_attachment`全部10项，Project字节前后不变 |
| R18-03 | 有界一致读取、命名空间过滤、标量白名单；缺失/损坏/journal/繁忙/过大拒绝，无修复 | `test_project_view`全部15项，SQL交错屏障和事务外投影证明 |
| R18-04 | 两个明确Project切换清空旧Run/日志/回执；无服务缓存不串Project | `test_explicit_project_switch_missing_service_and_unknown_stay_readonly`；`project_switch_and_paused_unknown.json` |
| R18-05 | 70个真实接受Run，32/32/6分页；Tk持续心跳、窗口可正常关闭 | `test_normal_gui_large_run_list_pages_without_blocking_ui`；`large_list.json` |
| R18-06 | progress持续增长且有界，事件按全局游标过滤；慢IPC不阻塞Tk、失联缓存标过期和最后成功时间 | 新正常GUI场景；原`test_progress_auth_bounds_readonly_and_corruption`、`test_stalled_ipc_keeps_tk_responsive_and_close_is_bounded` |
| R18-07 | worker运行期间整个GUI及专属venv真实exit0，owner身份保持且worker匹配存活；退出后日志继续增长 | `normal_gui_lifecycle.json`的retained Windows handle、worker与owner创建身份、progress顺序 |
| R18-08 | 正常Dev重开连接同Run/原回执，物理启动1次；选Run/重连均不重提 | 同上；原client/Supervisor幂等与多客户端回归 |
| R18-09 | UI读取不变更Grant/消费/Run revision/事件/gate/slot；不用展示逻辑替代状态机 | 等待屏障期间DB摘要不变、公有记录相等、RPC白名单陷阱；namespace与敏感字段测试 |
| R18-10 | owner异常后的UNKNOWN/PAUSED不恢复；完成后重启仍PAUSED；自动收尾保持原政策 | 切换场景、原`test_gui_observes_crashed_owner_uncertainty_without_recovery`、managed_scope PAUSED/故障组 |
| R18-11 | Legacy主要GUI、Project切换/Queue/Results/历史、格式隔离保持；新旧路径来源明确 | 独立legacy15项通过；不将其收集进AF隔离断言进程 |
| R18-12 | 相关授权/所有权/IPC/受管范围/替身Standard回归通过；新测试进程与凭据收尾 | 最终262唯一PASS；CLEANUP/FINAL_CHECKS；未调用Abaqus或改变历史owner |

公开协议与格式不变，仅新增project_view读操作。服务端能力不足时拒绝是预期兼容行为，不能为了连接历史owner而重启它。所有失败迭代和未运行范围见TEST_RESULTS.md。
