# Run 007 — R7逐项验收

**R7-01～12全部PASS；最终343 passed，0 failed/errors/skipped，241.96s。**

下表测试均位于 [test_recorded_exit_reconciliation.py](../../../tests/test_recorded_exit_reconciliation.py)，另注明的R2～R6回归仍使用原文件。最终数量、实际参数实例和结果以 [TEST_RESULTS.xml](TEST_RESULTS.xml)、[TEST_OUTPUT.txt](TEST_OUTPUT.txt) 为准；过程与限制见 [TEST_AND_PROCESS_EVIDENCE.md](TEST_AND_PROCESS_EVIDENCE.md)。测试计数不跨轮次相加。

| ID | 验收与实际测试映射 |
| --- | --- |
| R7-01 | `test_real_exit_commit_owner_crash_reconcile_and_separate_resume`：normal/nonzero/invalid_result均由真实Windows执行；PROCESS_EXIT_OBSERVED四次提交后在process:after_exit屏障真正终止owner，重启PAUSED，原Run成为相应候选。不是改库生成正向退出资格 |
| R7-02 | `test_preview_readonly_no_probe_artifact_validator_or_observer`：数据库及文件inventory不变，对ProcessReference、Backend、validator、线程和写事务设trap，禁止打开process_runs；`test_preview_consistent_read_transaction_and_serialized_owner_writer`：真实BEGIN/query_only视图与另一持锁owner写事务交错，旧revision/门同时读出，事务关闭后writer才提交；下一预览为完整新组合 |
| R7-03 | 端到端及 `test_concurrent_apply_conflict_replay_and_consumption`：同Run、原receipt、phase_attempt、全部历史退出保持，revision仅+1、管理消费/决定一次；physical-launches与控制器保留句柄身份核对只有一次物理启动；`test_apply_never_probes_or_validates_and_expired_execution_grant_is_history`：后来过期的执行Grant不否定历史事实，独立管理授权有效 |
| R7-04 | 端到端normal/nonzero分别COMPLETED/FAILED，均NOT_RUN Artifact；invalid_result场景也不能按预期补造INVALID。`test_existing_independent_validation_preserved_without_revalidation`：真实独立validator产生PASS/FAIL/UNKNOWN历史测试夹具，原值/时间/记录保持，apply有validator trap。这些夹具不生成OS退出事实；无新产品验证RPC |
| R7-05 | `test_incomplete_or_conflicting_required_set_rejected`：缺worker身份/退出、成员依据、仅PID、混入attempt、矛盾退出、额外START_INTENT、投影不同和缺新合同均拒绝；不能以已登记数量推导必需成员齐全 |
| R7-06 | `test_result_self_report_controller_exits_are_not_service_evidence`：真实owner在身份后、结果已出现但worker等待、控制器已看到退出但服务未提交时退出；均无候选、继续阻断。R6原 `test_exit_code_query_failure_on_real_exited_reference_is_unknown`、`test_identity_mismatch_is_not_exit_or_permission_to_kill`继续验证消失/身份不明不能生成退出码 |
| R7-07 | `test_exact_management_authority_required`、`test_wrong_exact_scope_cannot_reinterpret_approved_operation`、`test_caller_cannot_supply_execution_facts`：Fake动作、过期、错owner/Project/Backend/Run/Plan/attempt/指纹、执行Grant、scope/max_uses错误以及target_state/exit_code/members_complete/approved拒绝。端到端使用真实认证连接证明执行Grant不能替代管理许可、额外RPC参数拒绝 |
| R7-08 | `test_changed_preview_preconditions_refused`：revision或退出证据改变、旧owner条件拒绝；`test_lost_management_response_and_new_owner_replay`：实际换owner后旧授权不能换新键作新转换。完整成员/退出/门都参与摘要，要求重新预览、重新精确授权 |
| R7-09 | `test_lost_management_response_and_new_owner_replay`：管理已提交、响应被屏障阻塞，真正终止客户端；原key返回同回执，无重复事件/决定/消费；再次真正终止owner并重启后，原成功回执仍可重放，门仍PAUSED |
| R7-10 | `test_concurrent_apply_conflict_replay_and_consumption`：四线程同键仅一次转换，同键异内容冲突；`test_atomic_management_failure_and_unknown_commit`、`test_unknown_sql_commit_queries_original_key`：提交前回滚、提交后应答失败和实际commit后抛确认异常均不伪造成功，原键查询解决，Backend不再调用；原R4不同键竞争共用事务的回归也运行 |
| R7-11 | 端到端证明对账不恢复派发，另一个真实接受任务须独立resume才执行；`test_other_unresolved_run_still_blocks_resume`在第二个真实接受Run上注入不确定性，收尾第一个后仍拒绝resume；原R4 Plan/Grant失效及旧resume回执不打开新owner门的回归保留 |
| R7-12 | R2～R6相关全部原293个case重跑，旧测试文件不改；新增Windows组及诊断规则v3。`test_preview_bound_and_maintenance_no_repair`明确超限和journal拒绝、不修复。全部本轮进程/句柄、外层解释器及私有凭据的清理见结构化证据；没有Stable、生产数据或Abaqus验收 |

正向退出资格全部来自真实服务路径。受控损坏、合成不确定状态和历史Validation登记仅验证拒绝/保留规则，不作为正常进程证据，也不作为新增生产写入口。范围只含每实验存储的固定四成员集合，未验收遗留worker重新观察/接管、通用树、主机或跨Project资源协调。
