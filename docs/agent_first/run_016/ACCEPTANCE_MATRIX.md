# Run016 候选验收矩阵

真实 Abaqus 调用预算/实际均为 0。表中 Windows 进程是真实固定 Python 替身，不是 Abaqus。历史 DAT 来源为 `docs/agent_first/run_011/result_review_001/ORIGINAL_DAT.bin`；测试将该只读样本复制进明确标记的替身用例，绝不导入待审 Project。实际批次结果及失败迭代见 TEST_RESULTS.md。

| 项 | 风险及验收 | 实际用例 / 证据 |
|---|---|---|
| R16-01 | Standard 经过 Run015 原 Job 创建接缝，无无管理回退；文件输出不依赖管道 | `test_managed_standard_pair_public_gui_and_real_scope`、`test_no_unmanaged_fallback_and_test_grant_stays_separate`、`test_execution_isolation.py`；windows_final 的物理根身份、Job 查询及句柄关闭 |
| R16-02 | A 范围仍活动，B 不可接受/启动 | Windows pair 用例在 active_processes>0/worker 存活时公开提交 B 被 PREDECESSOR_NOT_QUALIFIED 拒绝；实际创建次数仍 1 |
| R16-03 | 范围结束但 Solver/DAT/退出失败不允许 B | `test_empty_scope_does_not_qualify_failed_a[solver/numerical/exit]`；范围结束与失败/PAUSED 分开；即便负向夹具人为打开门仍拒绝 |
| R16-04 | 行政释放不能替代正常收尾；管理策略不能临时变更 | `test_b_rechecks_current_preconditions[administrative/scope_missing]`、`test_changed_management_is_not_a_new_runtime_choice`；原 R14 行政处置回归 |
| R16-05 | A 收尾提交在先，B 启动在后，两个各一次 | `test_pair_server_guards_and_success_order`、`test_public_pair_orchestrator_uses_existing_server`；公开薄客户端 A→B；实际两个 OS 根身份；全局事件序号顺序 |
| R16-06 | PAUSED、过期授权/窗口、输入变化/输出冲突阻断 B | `test_b_rechecks_current_preconditions` 七种负向；`test_paused_during_a_completion_does_not_open_gate`；`test_deadline_never_releases_slot_or_enables_late_b` 活跃/晚到空范围两种 |
| R16-07 | 重放、丢应答、失联不增加创建；不确定 B 只查原请求 | `test_ack_loss_replay_and_expiry_between_b_accept_and_create`；`test_public_sequencer_stops_on_loss_and_never_resubmits` 六种；Windows pair 重放仍两次 |
| R16-08 | Job 查询、收尾前/事务中故障，不无记录释放；域外候选不放行 | `test_scope_or_transaction_failure_holds_slot` 三个屏障；`test_known_off_scope_execution_is_not_automatically_closed`；未决保槽、PAUSED |
| R16-09 | 实际 GUI 关闭/重连、owner 崩溃保持原契约 | Windows pair 通过 WM_CLOSE 关闭整个 GUI/venv，再重连原 Run；`test_managed_standard_owner_crash_does_not_adopt_or_start_b` 真正终止本轮 owner，worker 继续，重启 PAUSED/B 拒绝；原 GUI/Job/Supervisor 回归 |
| R16-10 | 待审实例仅两个计划；无 Grant/Run/消费/尝试/输出；旧成果未变 | PREPARATION_CHECK.json、FINAL_AUDIT.json、单份 ACCEPTANCE_MANIFEST.json；原保护摘要逐项检查 |

故障注入与直接 Windows 观察分开：unit tests 的 scope/退出/文本结果有显式替身；`run016_process.py` 在 Standard Backend 的唯一原生创建接缝替换为固定 Python，仍实际执行 JOB_LIST/HANDLE_LIST、OS 观察、IPC、GUI 和事务。OS 的 Job 查询是事实；样本里的 Solver/DAT 结论仅说明解析及政策连通，不能作新真实 Run 的结果。

没有修改旧断言来放行。静态隔离测试把原来“完全不继承句柄”的约束精化为“仅三项显式文件句柄白名单”，同时保留无 breakaway、无 Terminate、无无管理回退、Fake/客户端禁启动。旧固定 Python 路径依旧 bInheritHandles=False。

真实验收待批准：A/B 新包装器的嵌套 Job 兼容、关键求解和输出写入是否在管理范围、两项实际 Solver/DAT、真实 A 求解期间 GUI 退出后的 OS 持续运行。任何一项未观察到均单独保留，不用替身或历史 11 个进程列表补证。
