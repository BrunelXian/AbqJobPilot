# Run 005 — R5逐项验收

最终 **239 passed，0 failed，0 errors，0 skipped，118.04s**，其中原189项回归和新增50项均实际通过。

以下测试以本轮最终JUnit为依据，完整参数化名称见[TEST_RESULTS.xml](TEST_RESULTS.xml)。L为[本地诊断与导出测试](../../../tests/test_run_diagnostics.py)，P为[独立Supervisor测试](../../../tests/test_diagnostic_supervisor.py)。同一测试可支持多项要求，不能把行数相加当作测试总数。

| ID | 结果 | 实际测试名称 | 观察及边界 |
| --- | --- | --- | --- |
| R5-01 | PASS | L `test_pending_completed_and_historical_validation_are_distinct`；`test_uncertain_insufficient_then_reconciled_paused_then_resumed`；`test_actual_validator_failure_is_reported_without_rerunning_it`；`test_actual_blocked_error_code_is_preserved_without_free_message`；`test_missing_history_and_unrecognized_error_not_success` | 实际接受/执行/失败/对账状态产生不同解释；历史PASS后删除产物仍只说明历史；无错误不等于成功，Solver NOT_RUN，进程/退出NOT_APPLICABLE；缺历史和未知分类明确列出 |
| R5-02 | PASS | L `test_snapshot_real_read_write_interleaving_and_transaction_released`；`test_global_event_gaps_are_not_run_history_gaps`；P `test_windows_three_stage_diagnostic_export_and_detached_response` | 真实SQLite读事务在读Run后停在Event屏障，另一线程写Run/事件/门并等待提交，报告只见完整旧组合；连接关闭后writer即提交，下一报告见完整新组合。真实IPC应答延迟期间管理写入也成功；全局序号1,3,4,5对应本Run 1,2,3,4不误判缺口 |
| R5-03 | PASS | L `test_readonly_all_business_records_and_effect_traps`；P三阶段测试 | inventory包含整个实验库和文件bytes/mtime，诊断前后完全相同；Backend、validator、preview/manage、transaction和owner lease check均设陷阱，重复诊断未触发；没有读原产物 |
| R5-04 | PASS | L `test_honest_read_failures_no_repair_or_path_disclosure`（7种）；`test_schema_two_reports_missing_gate_without_migration`；`test_inconsistent_persisted_bindings_are_not_misreported`（5种） | 缺库、损坏、未来格式、journal/wal/shm、真实EXCLUSIVE锁忙均明确拒绝且无修复；旧格式无门标未知；Run/Project/Plan/事件/Artifact记录错绑拒绝，无伪空报告 |
| R5-05 | PASS | P `test_authenticated_bound_diagnostic_rejects_dangerous_parameters_and_echo` | 实际TCP错误凭据、Project、额外export_path、坏Run ID均拒绝且业务inventory不变；普通认证只读查询无需执行或管理授权 |
| R5-06 | PASS | L `test_whitelist_secret_injection_and_export`；`test_reconciliation_private_fields_and_storage_error_are_not_echoed`；P认证测试及三阶段测试 | 向grant字段、自由路径、事件载荷、错误、环境/命令、对账preview/snapshot注入秘密，响应/导出/固定错误均无秘密；真实IPC credential不能经request_id回显；无绝对根或授权ID输出 |
| R5-07 | PASS | L `test_limits_explicit_no_truncation`（6种）；`test_each_evidence_collection_has_hard_record_limit`（3种）；`test_diagnostic_connection_metadata_and_manifest_are_bounded`（4种）；并发事务释放测试；原R3帧/连接限额测试 | 事件/每类证据、单记录/累计字节、字段字符数、manifest/meta/门、序列化和截止均拒绝超限；SQL锁等待有界；事务先结束才规则计算/传输/导出；未放宽原IPC限制 |
| R5-08 | PASS | L `test_export_original_view_offline_without_store_network_or_owner`；`test_report_rule_computation_is_deterministic_for_same_snapshot`；P三阶段测试 | 取得PENDING报告后真实执行完成、关闭owner并封锁所有查询，导出仍逐字节等于原报告；摘要只覆盖public body，读取时间独立于历史时间，同快照规则输出确定 |
| R5-09 | PASS | L `test_export_path_and_failure_boundaries`（8种）；`test_export_cleanup_failure_leaves_identifiable_partial_and_no_success` | 逃逸、..、已有目标、真实Windows junction、fsync失败、发布竞态拒绝；旧文件不覆盖，业务库不变；失败只清理自有partial；清理失败保留可识别partial且无成功目标 |
| R5-10 | PASS | L `test_export_original_view_offline_without_store_network_or_owner`；`test_audit_cannot_be_submitted_as_execution_or_management_request`；导出篡改字段/摘要参数case | 离线JSON可解析且标明未含Artifact字节、未重新验证、非许可；报告不能直接当submit/apply/resume请求；导出投影结构和摘要校验拒绝新增秘密字段 |
| R5-11 | PASS | P `test_windows_three_stage_diagnostic_export_and_detached_response` | 真实owner在Fake产物后退出→新owner暂停→待对账报告→显式授权对账→仍暂停报告→独立恢复→OPEN报告；原Run只一次START_INTENT/原产物不变，另一个合法PENDING才执行；三份真实JSON见examples |
| R5-12 | PASS | R2/R3/R4全部189个原case；本轮L/P新增组；原进程fixture | 实际重跑原断线、幂等、单槽、对账/恢复契约；只扩展隔离AST的精确client→audit_export→diagnostics依赖，不删旧断言。Windows进程退出、连接凭据清理与测试目录清单另见进程证据 |

最终统计、执行命令、迭代失败记录和清理信息见[测试与进程证据](TEST_AND_PROCESS_EVIDENCE.md)。没有跳过关键验收；不把本轮PASS推广为真实Solver、断电恢复或跨Project协调通过。
