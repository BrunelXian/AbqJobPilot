# Agent-first Run 002 — 实测验收矩阵

日期：2026-10-21。最终代码结果：**95 passed，0 failed，0 errors，0 skipped**。仅覆盖 Run 002 的单进程隔离 Fake 契约。R2-01～16 均有下表中的实际测试证据；完整模拟服务 MVP 与真实 Abaqus 验收未运行。

原始证据：[TEST_RESULTS.xml](TEST_RESULTS.xml)（含95个完整参数化 case 名称及结果）、[TEST_OUTPUT.txt](TEST_OUTPUT.txt)、[SOURCE_HASHES.json](SOURCE_HASHES.json)（本次测试对应的13个源码/测试文件 SHA-256）。

下面 C/S/I 是文件缩写，`文件::函数名` 与 JUnit testcase 名称对应；参数化函数的全部实例均通过。不同 R2 要求可共用同一测试，行数和引用次数不能相加当测试数。

- C：[test_execution_contract.py](../../../tests/test_execution_contract.py)，56个 case。
- S：[test_execution_store.py](../../../tests/test_execution_store.py)，30个 case。
- I：[test_execution_isolation.py](../../../tests/test_execution_isolation.py)，9个 case。
- 测试支持：[execution_helpers.py](../../../tests/execution_helpers.py)，包含隔离 fixture、运行时 trap、测试授权签发器；不是生产授权入口。

## R2-01～16 逐项结果

| 要求 | 实际测试名称 | 观察证据 / 结果 |
| --- | --- | --- |
| R2-01 无 GUI 提交/查询，先持久 Run | C::test_headless_submit_and_validation_run_persisted_before_effect | PASS；Fake 调用前用独立只读连接查到 receipt、START_INTENT Run 和事件；完成后查到 observation/validation；Solver NOT_RUN |
| R2-02 提交和执行重复不再产生副作用 | C::test_idempotent_submit_and_execution_replay；C::test_simultaneous_claim_same_run_only_one_effect | PASS；同 receipt/Run，Fake 调用一次，START_INTENT 和消费记录各一次 |
| R2-03 同键异内容 | C::test_same_key_different_content_conflict | PASS；分别改变 plan_id、plan_digest、grant_id、retry_of，结构化 IDEMPOTENCY_CONFLICT；旧计数不变 |
| R2-04 多客户端/多服务对象与单槽 | C::test_concurrent_submit_across_service_and_store_objects；C::test_atomic_execution_claim_and_store_single_slot；C::test_simultaneous_claim_same_run_only_one_effect；C::test_single_slot_scope_is_per_experiment_store | PASS；8个独立 facade 同时 submit 仅一个新接受；同时领取同 Run 一次副作用；另一 Run 遇 SLOT_BUSY 仍保持 ACCEPTED/PENDING；不同存储可并行，明确非主机全局槽 |
| R2-05 错 Project/实例/root/manifest | C::test_wrong_context_rejected；C::test_real_other_project_retry_and_request_scope_rejected；S::test_malformed_manifest_is_structured_error_without_repair | PASS；context 四种不一致和实际其他 Project 的请求拒绝；畸形 manifest 不修复 |
| R2-06 输入/配置/计划失效 | C::test_changed_input_or_configuration_invalidates_plan；C::test_plan_expiry_after_prepare_blocks_execution | PASS；接受前与 dispatch 前分别改变同大小输入、配置 revision/values、计划有效期；接受前无 Run，接受后 BLOCKED 且保留 receipt；无 Fake 输出 |
| R2-07 授权与资源拒绝 | C::test_grant_conditions_reject；C::test_missing_or_unregistered_grant；C::test_self_approval_and_execution_options_rejected；C::test_resource_budget_rejected；C::test_grant_expiry_after_accept_blocks_dispatch_but_keeps_receipt | PASS；缺失/未知/过期、错误 Project/Plan/Job/revision/authority/output/max_runs、REAL grant、自报 approved/allow_solver、任意执行参数、资源越界均拒绝 |
| R2-08 新任务不能借用旧授权；复制不继承 | C::test_new_work_cannot_reuse_old_plan_or_grant；S::test_copied_project_does_not_inherit_execution_permission | PASS；新 Job/revision/Plan 和已消费 grant 不能借用；复制库没有当前 owner session，拒绝写入且复制数据不变 |
| R2-09 旧请求在到期/输入变化后重放 | C::test_replay_survives_expired_grant_and_changed_input；C::test_grant_expiry_after_accept_blocks_dispatch_but_keeps_receipt | PASS；原 receipt 可查询/重放，无重新批准、消费或 dispatch |
| R2-10 关闭后重新只读打开 | S::test_reopen_readonly_retains_receipt_run_events_validation_without_writes | PASS；receipt/Run/events/observation/validation 保留；三轮查询 inventory 不变；关闭后拒绝新的 writer |
| R2-11 Fake 完成与结果验证分离 | S::test_fake_completion_and_artifact_validation_are_separate；S::test_existing_old_output_is_not_overwritten_or_adopted | PASS；缺失、坏 JSON、旧成功文本、错误 Run/phase/Plan、digest 改变得到 INVALID/UNKNOWN；Fake 可 COMPLETED，但 Solver 始终 NOT_RUN；已有输出不覆盖 |
| R2-12 事务/文件/应答故障窗口 | S::test_accept_transaction_failure_rolls_back_all_acceptance_records；S::test_lost_acceptance_response_replays_committed_receipt；S::test_commit_acknowledgement_failure_queries_existing_acceptance；S::test_claim_transaction_failure_has_no_effect_or_partial_claim；S::test_post_claim_failures_preserve_uncertainty_and_never_repeat_effect；S::test_response_failure_after_terminal_commit_does_not_repeat | PASS；接受原子性、已提交但应答不明、领取前后、文件已写/观察失败/终态失败/不确定记录也失败、终态后响应失败均有注入；未假称文件可被 DB rollback 撤销；未知槽保持占用，不重复副作用 |
| R2-13 查询零初始化/迁移/修复 | S::test_query_failures_never_initialize_migrate_or_repair；S::test_readonly_connection_enforces_query_only_and_foreign_keys；S::test_reopen_readonly_retains_receipt_run_events_validation_without_writes | PASS；缺库、损坏库、未来 schema、WAL/SHM/journal 拒绝且 inventory 不变；SQL query_only 拒绝 DELETE；外键约束有效 |
| R2-14 临时根隔离、真实启动不可达 | I::test_dependency_graph_excludes_all_legacy_and_launch_modules；I::test_all_runtime_io_confined_and_default_navigation_untouched；I::test_path_escape_rejected_before_candidate_filesystem_access；I::test_real_junction_or_symlink_is_rejected；I::test_creation_never_adopts_existing_directory | PASS；AST 依赖/调用白名单、进程启动/默认路径 trap、临时文件清单；越界/.. /UNC/相对路径/ADS 在候选文件系统访问前拒绝；实际 Windows junction 被拒绝；未创建旧 queue/project.db 或工程作业 |
| R2-15 真 Retry 与非法引用 | C::test_true_retry_creates_new_run_and_preserves_old_evidence；C::test_invalid_retry_rejected；C::test_real_other_project_retry_and_request_scope_rejected；S::test_retry_of_uncertain_run_is_rejected | PASS；新 Run、attempt+1、retry_of 保留；旧验证不变；不存在、PENDING、其他 Job、实际其他 Project、待对账 Run 拒绝 |
| R2-16 canonical 摘要、类型和事件序列 | C::test_canonical_values_and_event_pagination；C::test_plan_is_detached_from_mutable_inputs_and_expiry_checked；C::test_self_approval_and_execution_options_rejected | PASS；排序 key/Unicode 稳定，bool/int 与列表顺序有区别，浮点/NaN/Infinity/未知字段拒绝；Plan 不受外部字典修改；事件分页序列连续、ID 唯一且可定位 accepted_sequence |

## 实际执行命令与迭代

使用 PowerShell，仅当前进程设置环境变量；未修改共享环境：

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B -m pytest -p no:cacheprovider tests/test_execution_contract.py tests/test_execution_store.py tests/test_execution_isolation.py --basetemp='C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run002_253758f6191e4eb4a05bc1c31b099c77\final' --junitxml='C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run002_253758f6191e4eb4a05bc1c31b099c77\final.junit.xml' -q
```

这是实际最终测试命令记录；重跑时必须使用新的显式临时目录，不照抄已存在的 basetemp 以清空旧证据。终端输出同时通过 Tee-Object 保存为临时根的 final.txt，再复制到本目录 TEST_OUTPUT.txt。

| 次数 | 原因 | 实际结果 |
| --- | --- | --- |
| run1 | 初始实现与核心验收 | 85 passed，15.31s；无失败/跳过 |
| run2 | 源码复核后补充提交确认不明、manifest、到期、存储槽作用域等边界 | 95 passed，18.33s；无失败/跳过 |
| final | 修正 SLOT_BUSY 错误回执语义并加入断言后复验 | 95 passed，17.13s；无失败/跳过；JUnit suite time=17.097s |

最终结论只对应 final 的95个 case，不将三次计数相加。run1/run2 原始 XML/文本仍在本轮显式临时根中；交付保留最终 XML/输出及精确源码哈希。

## 明确未验收

- 没有运行已有全量测试或旧命令构造测试；旧模块未变，避免旧测试读取默认 Runtime。没有把历史测试结果充当本轮结果。
- 故障为单进程逻辑注入和 commit acknowledgement 模拟；未 kill 用户/测试进程，未验证断电、OS 崩溃或跨进程重启恢复。
- WAL/journal 用测试 sidecar 触发保守拒绝，未执行 SQLite 恢复或生产 WAL 审计。
- 没有独立 Supervisor、IPC、客户端断线后的持续监督、跨 Project 输出锁、主机全局槽、真实批准域或真实 Backend；这些属于后续矩阵 B/C，状态 NOT_RUN。
- 没有 Abaqus Solver/Datacheck、真实 ODB 结果验证、生产 Project/数据库迁移；95项 PASS 不表示真实结果有效或正式0.3.0可发布。
