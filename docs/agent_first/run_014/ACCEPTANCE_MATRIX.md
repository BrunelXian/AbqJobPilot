# Run014 逐项验收

全部新场景在显式临时Project/Runtime/存储中完成；真实Run只读。测试名称是实际pytest节点，结果及所有参数实例见 TEST_CASE_INDEX.json。

| ID | 要求 | 实际测试/证据 | 结果 |
|---|---|---|---|
| R14-01 | 一致只读预览、不写业务/不探进程/不读产物 | `test_preview_consistent_read_only_and_no_external_probes`、`test_preview_cannot_mix_concurrent_sqlite_views`；DB写入并发屏障，读到完整旧视图，随后新revision/gate可见；读前后文件与业务表相同 | PASS |
| R14-02 | 同键重放无重复效果 | `test_replay_conflict_concurrent_effect_once_and_new_owner_replay`、Windows `test_public_disposition_lost_response_gui_and_restart`：提交后实际EOF，原key重放相同回执；owner重启后也不重复消费或开门 | PASS |
| R14-03 | 冲突和并发拒绝错误放行 | `test_competing_dispositions_cannot_both_change_same_revision`、上述并发测试；两个服务对象同评估仅1次转换；异内容IDEMPOTENCY_CONFLICT | PASS |
| R14-04 | 新证据/状态使旧评估失效 | `test_stale_assessment_rejected[revision/event/gate/owner]`；STALE_PREVIEW/STALE_OWNER，无新决定或解锁 | PASS |
| R14-05 | 失败/崩溃/丢响应无无记录解锁 | `test_transaction_and_lost_response_no_unrecorded_release`；Windows `test_true_owner_crash_during_disposition_no_unrecorded_unlock`：真实owner在management:before_commit屏障被核实句柄终止，读拒绝STORE_REQUIRES_MAINTENANCE；未修复journal、未再次启动 | PASS，崩溃实例保留维护限制 |
| R14-06 | UNKNOWN与原证据完整保留 | `test_explicit_release_preserves_evidence_receipt_gate_and_intent`；逐字段比较原Run、原receipt/consumption/observations/validations；诊断仅增加ADMINISTRATIVE_DISPOSITION，仍EXECUTION_UNCERTAIN | PASS |
| R14-07 | 槽、路径隔离、派发互相独立 | `test_retain_is_independent_and_does_not_release`、`test_separate_resume_quarantine_and_pending_prerequisites`、`test_remaining_uncertainty_blocks_independent_resumption`、`test_test_only_resume_cannot_approve_real_residual_risk`；新Job旧目录在prepare拒绝RESOURCE_RETAINED，独立恢复不执行旧Run | PASS |
| R14-08 | 停服/重启保留未决/隔离 | Windows `test_normal_owner_stop_leaves_worker_alive_and_restart_blocked`：owner及venv transport退出、同身份worker继续存活并写日志；新ownerPAUSED、原Run/slot不变。最终自行退出且句柄关闭；仅固定Python替身范围 | PASS |
| R14-09 | 原TEST_ONLY、真实执行Grant、一次意图不扩权 | `test_disposition_requires_independent_exact_operator_permission`、`test_insufficient_evidence_cannot_release`、既有 `test_real_requires_separate_grant_and_opt_in`、Standard准入/故障/重放与R2/R4/R7回归；旧intent仍在，创建次数不增 | PASS |
| R14-10 | 公共客户端和真实Dev GUI展示 | Windows `test_public_disposition_lost_response_gui_and_restart`；实际Tk表格读取了原Run、slot、行政处置、PAUSED，GUI WM_CLOSE和启动器退出均有证据；没有GUI写库或批准 | PASS |
| R14-11 | 可达可信入口与旧版本兼容 | `test_trusted_operator_entry_refuses_active_owner_and_has_no_backend`、`test_preview_limit_busy_and_legacy_diagnostic_compatibility`；活跃owner拒绝、本地持锁operator调用同service、无Backend；老v3/rules-v1报告可离线校验 | PASS |
| R14-12 | 当前真实实例保持只读 | CURRENT_READONLY、CURRENT_CLOSEOUT_PREVIEW、OPERATOR_READONLY_OUTPUT、FINAL_AUDIT；Run/slot/gate/事件/授权消费不变，295历史材料未改，Abaqus0 | 完成；当前处置待明确确认 |

本轮未宣称：真实Abaqus在owner退出后的存活/退出验收、正常自动收尾的完整成员容器、主机或跨Project资源排他、ODB内容验证、终端关闭/注销/重启、历史未决进程自动接管。
