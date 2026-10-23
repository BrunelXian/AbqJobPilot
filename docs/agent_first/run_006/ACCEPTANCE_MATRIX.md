# Run 006 — R6逐项验收

**R6-01～12全部PASS；最终293 passed，0 failed/errors/skipped，175.29s。** 实际参数实例见[TEST_RESULTS.xml](TEST_RESULTS.xml)、[TEST_OUTPUT.txt](TEST_OUTPUT.txt)。G指[进程契约测试](../../../tests/test_process_contract.py)，P指[Windows集成测试](../../../tests/test_process_fixture.py)。相关前置组完整重跑，原239项case身份全部包含于最终通过集合；数量和实际证据见[测试证据](TEST_AND_PROCESS_EVIDENCE.md)。

| ID | 实际测试及观察 |
| --- | --- |
| R6-01 | P `test_real_process_exit_and_independent_artifact_dimensions`：固定Plan和专用Grant经原IPC提交，身份屏障时原Run/回执已经存在；四个实际进程角色、退出码和独立Artifact验证分别查询，Solver NOT_RUN。正常完成报告可离线导出 |
| R6-02 | G `test_process_requires_exact_dedicated_test_grant_before_any_launch`、`test_execution_object_identity_and_budget_rejected`、`test_scenario_is_a_strict_enum_not_a_command`、`test_client_cannot_supply_process_controls`、`test_accepted_process_plan_is_rechecked_at_dispatch_without_start`、`test_no_process_configuration_cannot_dispatch_process_plan`、`test_dedicated_process_grant_cannot_expand_original_fake`、`test_opt_in_process_capability_does_not_change_fake_no_launch_path`：旧Fake/错误动作/授权/解释器/夹具摘要/expiry/越界资源/任意命令参数均在启动前拒绝；这些测试保留原有效启动trap |
| R6-03 | P `test_multiclient_replay_lost_response_and_client_exit_do_not_start_twice`：接受提交后应答被屏障阻断，真实结束客户端，四个并发重放仍只有原Run/回执；真实Popen登记只有一次，与launcher_transport PID/创建时间吻合；继续完成不依赖原连接。原R2幂等异内容冲突及R3多客户端组再次通过 |
| R6-04 | P `test_launcher_exit_and_result_do_not_end_worker_or_release_slot[launcher_early]`：控制器持有句柄确认launcher退出、worker仍活；Run保持START_INTENT/PARTIAL，第二Run仍PENDING且无启动目录，查询可响应；只有worker释放并完成后第二Run才启动；第二Run也在确定身份屏障登记 |
| R6-05 | P上述测试`[result_wait]`证明结果已出现不等于退出；`test_real_process_exit_and_independent_artifact_dimensions`的nonzero与invalid_result分别得到FAILED+VALID和COMPLETED+INVALID；G `test_process_validator_rejects_lookalike_content_without_process_authority`额外拒绝bool冒充版本、重复键和错实例/phase |
| R6-06 | P `test_actual_owner_crash_windows_preserves_uncertainty_no_relaunch`的after_identity/after_handoff：真正结束owner，worker在终止前后和新owner取得锁后仍未退出；after_handoff已写结果且launcher实际退出。新owner保持PAUSED、旧Run需对账、第二Run不派发，没有再次物理启动 |
| R6-07 | P同测试before_create：START_INTENT和phase_attempt_id已提交，受控屏障位于Popen之前；控制器启动登记0条、无launcher候选。重启仍不推测或重试，无身份信息标UNKNOWN |
| R6-08 | P同测试after_create：控制器核验并保留实际launcher/worker等四个句柄，但业务process_records为空；真正结束owner并重启，无PID记录仍阻断。控制器身份不注入服务；物理启动登记1条，清理只用控制器句柄 |
| R6-09 | P同测试before_exit_record：控制器已观察全体退出，但业务退出记录尚无，重启exit UNKNOWN；after_exit：四个退出观察已提交而集合投影仍PARTIAL；before_terminal：VERIFIED已提交而验证/终态未提交。全部真正杀owner，均不重启Run；P `test_post_creation_storage_failure_never_releases_claim_or_restarts[terminal:before_commit]`另测事务失败回滚 |
| R6-10 | P `test_identity_mismatch_is_not_exit_or_permission_to_kill`、`test_actual_candidate_identity_mismatch_blocks_owner_without_guessing`、`test_exit_code_query_failure_on_real_exited_reference_is_unknown`、`test_post_creation_storage_failure_never_releases_claim_or_restarts`：创建时间错配、不能打开候选、退出码读取失败、启动后身份/终态存储失败均不伪造成功、不杀非匹配进程、不放槽；G `test_missing_historical_exit_records_are_not_filled_from_projection`拒绝由完成投影补造历史退出 |
| R6-11 | P全部崩溃窗口在新owner下测试Fake preview无候选，精确Fake管理授权apply也拒绝，resume因未解不确定性拒绝；P `test_process_diagnosis_is_historical_readonly_redacted`对进程探测设trap，完整文件inventory不变、无解释器/临时路径/连接秘密。v2区分历史身份与当前未知，v1 Fake回归保留 |
| R6-12 | 原R2～R5全部239个case重新执行；新增G/P和原隔离AST检查。P `test_fixture_does_not_inherit_private_owner_environment`验证受限子进程环境；原锁未继承由存活worker期间新owner取锁证明。最终每个已登记本轮进程等待退出、关闭句柄，私有凭据删除；具体数量和迭代问题见证据报告 |

矩阵各行以实测具体场景为范围。没有自动进程接管、真实进程对账、通用Job Object/进程树、主机总槽、跨Project、真实Solver或断电恢复验收。单槽只属于一个实验存储；所有权释放不释放不确定执行的业务槽。

R6-02补充：G `test_delayed_start_rechecks_permission_and_input_before_os_creation` 在claim之后、Popen之前改变输入或使Grant过期，证明最后启动门禁仍拒绝；`test_invalid_trusted_backend_configuration_does_not_leak_owner_lock` 验证可信配置错误也关闭已取得的owner锁，后续显式owner仍默认暂停。
