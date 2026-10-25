# Dev 恢复能力与差异矩阵

根路径统一为 D:\Projects\abqjobpilot_dev。下面代码路径和函数均经本轮静态核实。IMPLEMENTED_TESTED = 当前实现存在，且有实际测试源码及历史执行报告；**不表示本轮重跑**。IMPLEMENTED_UNVERIFIED = 代码存在而无对应验收依据；PARTIAL = 只有明确子集；MISSING = 新执行路径没有所需能力；LEGACY_ONLY = 仅旧格式，不可用于 Agent-first Store。

历史证据索引：R3/R4/R5/R6/R7/R8 = docs/agent_first/run_003～008/FINAL_SUMMARY.md 与各 ACCEPTANCE_MATRIX.md；R14=run_014/ACCEPTANCE_MATRIX.md（后续真实处置另见 disposition_001/FINAL_SUMMARY.md）；R15=run_015/ACCEPTANCE_MATRIX.md；R16=run_016/real_001/FINAL_SUMMARY.md；R18/19/20=对应 FINAL_SUMMARY.md；R21B=run_021b/CONTROL_CONTRACT.md、TESTS_AND_ACCEPTANCE.md、real_001/FINAL_SUMMARY.md；R22=run_022/TEST_RESULTS.json。历史结果不合成为一次实验。

| 能力 | 状态 | 源码/实际权威与测试 | 边界／建议 |
|---|---|---|---|
| 独立 owner、同一 OS 排他锁 | IMPLEMENTED_TESTED | execution/ownership.py: LocalOwnerLock；store.acquire_supervisor_store；tests/test_execution_ownership.py；test_lifecycle_boundaries.test_two_os_clients_race_same_original_owner_lock；R3/R19 | owner metadata 不是锁；不得另造管理锁绕开它 |
| owner 退出后 worker 继续 | IMPLEMENTED_TESTED | managed_process.close 不终止；tests/test_managed_scope.test_managed_owner_crash_leaves_worker_alive_and_restart_blocked；R6/R15 | 限实测宿主；不是外层 Job、注销或关机保证 |
| 原锁重新获取后的 PAUSED/未决保持 | IMPLEMENTED_TESTED | store.acquire_supervisor_store；ReadOnlyStore.query_run；同上 crash 测试；R3/R4 | 可信底层重新取得所有权是写操作；产品自动重启仍拒绝 |
| 产品正常重启与未知启动阻断 | IMPLEMENTED_TESTED | service_lifecycle.inspect/start/_stopped；execution/lifecycle.require_idle；tests/test_lifecycle_boundaries.test_real_owner_crash_not_automatically_replaced；R19/R21B | 缺 clean stop/有未决 Run 不允许普通 start，不能宣称全面恢复 |
| Windows 受管范围和正常收尾 | IMPLEMENTED_TESTED | managed_process.ManagedScope/check_completion；standard_backend.persist_result；test_managed_scope/test_standard_managed_windows；R15/R16 | 仅 ROOT_AND_INHERITING_CREATEPROCESS_DESCENDANTS，不包含域外服务 |
| owner 崩溃后重挂接原 Job/worker | MISSING | ManagedScope 未命名、无 reopen/adoption API；test_managed_true_crash_after_empty_before_commit_does_not_release | 保持明确不支持；不在本计划偷偷实现 |
| Plan/Grant/Run/Attempt/Receipt/Event | IMPLEMENTED_TESTED | store._SCHEMA；service.submit/_execute_pending；test_product_standard_control；R3/R21B | Attempt 是 runs.attempt_no/phase_attempt_id/owner_epoch，不是独立表；消费在接受事务，不等于已经 OS 创建 |
| 接受/领取/管理原子性、幂等 | IMPLEMENTED_TESTED | service.submit；reconciliation.manage/_prior；product_standard.ProductStandardControl；test_recorded_exit_reconciliation.test_unknown_sql_commit_queries_original_key；R4/R7/R21B | 外部进程创建与 SQL 不可能同一事务；START_INTENT 后未知不重跑 |
| 诊断一致只读、白名单导出 | IMPLEMENTED_TESTED | ReadOnlyStore.diagnose；diagnostics.build_report/report_bytes；audit_export；test_run_diagnostics 的 snapshot/read-only/whitelist/export 测试；R5/R22 | 历史数据库视图，不做当前 OS/产物验证；达到限额拒绝，不假装完整 |
| Fake 固定产物采纳 | IMPLEMENTED_TESTED | reconciliation._inspect/manage ADOPT；test_fake_reconciliation；R4 | Fake 专用会读取固定产物；不能移用于真实 Solver。不能笼统说“所有既有 preview 都不读文件” |
| 四角色已记录退出对账 | IMPLEMENTED_TESTED | process_reconciliation.inspect/apply_recorded；test_recorded_exit_reconciliation；R7 | 要求固定角色依据+四个持久 OS exit；显式拒绝 managed_scope |
| Standard 只读处置预览/保留/行政释放 | IMPLEMENTED_TESTED | closeout.snapshot/assess/preview_store/issue/apply_recorded；test_standard_closeout；R14 | 释放需 observation ended + observed exits 完整；不是完整进程全集验证 |
| 原锁内离线管理入口 | IMPLEMENTED_TESTED | examples/agent_first/standard_closeout_operator.main；test_trusted_operator_entry_refuses_active_owner_and_has_no_backend；R14 disposition | 已存在，不能重复开发第二锁；仍是实验 bootstrap 入口，非产品凭据桥接 |
| PAUSED、槽位、路径隔离独立 | IMPLEMENTED_TESTED | closeout.administratively_released/blocks_dispatch/check_retained_paths/issue_resume；test_separate_resume_quarantine_and_pending_prerequisites；R14 | 行政标志必须有回执/消费/决定；每 Store 路径保护，不是整机排他 |
| 精确真实 Grant、单次派发 | IMPLEMENTED_TESTED | execution/product_standard.py: invoke/claim 等；test_product_standard_control；R21B | 独立 operator capability；全局 PAUSED；不能作为恢复权限复用 |
| 安全空闲停服 | IMPLEMENTED_TESTED | execution/lifecycle.stop/require_idle；supervisor.serve finally；test_lifecycle_boundaries/test_product_standard_control；R19/R21B | UNKNOWN、行政释放、占槽仍会拒绝产品停服；停服不是 Solver exit |
| Windows 重启证据及中断分类 | MISSING | execution/ownership.current_process_identity 无 boot provenance；execution/diagnostics 无 boot/session 分类；全 abqjobpilot 搜索未发现 probe_windows_boot/boot_time | 需新增结构化来源/不确定性；当前 PID 消失不能补历史exit |
| managed proof 已落盘但终态未提交的显式补提交流程 | MISSING | test_managed_true_crash_after_empty_before_commit_does_not_release；process_reconciliation 禁止 managed_scope；closeout只行政策略 | 独立后续证据策略，不能与缺证据行政政策合并 |
| 重启且退出遥测缺失时有限行政处置 | PARTIAL | closeout现有事务/隔离已具备；assess: valid_exits/ended 限制；test_insufficient_evidence_cannot_release | 保持旧策略；新风险接受政策另审，不新增无条件force-close |
| 产品 Project 的可信 recovery 管理会话 | PARTIAL | service_lifecycle.start 的 require_idle；现有 operator 示例；product_project/local_credentials | 复用所有权，需产品 DPAPI 最小适配；不启动 dispatcher，不采用连接token作批准 |
| 原排队请求保持，不自动重派 | IMPLEMENTED_TESTED | store.needs_reconciliation/pending_for_owner；restart PAUSED；test_managed_owner_crash_leaves_worker_alive_and_restart_blocked 的第二 Run PENDING 断言 | Agent-first 叫 PENDING/PLANNED，不误套 Classic QUEUED |
| retry_of 有限新 Run 关系 | PARTIAL | service.submit: terminal同Job+新Plan/Grant；Standard明确INVALID_RETRY；tests/test_execution_contract.py:test_true_retry_creates_new_run_and_preserves_old_evidence、tests/test_execution_store.py:test_retry_of_uncertain_run_is_rejected | 现有不是 Standard 中断后重跑能力；CR-D05另审 |
| Abaqus 原生 restart/resume | MISSING | standard_contract 固定 analysis；service Standard retry拒绝；R16/R21B范围 | 无重启动数据校验和许可，不作为默认恢复 |
| GUI 未决/历史退出/行政/PAUSED 展示 | IMPLEMENTED_TESTED | execution_gui.Reader._loop/ExecutionView._render/close；test_execution_gui/test_attachment_gui；R14/R18–20 | 分次公共读非原子；无恢复批准UI。缺中断原因到证据的完整导航 |
| GUI Interrupted (Unverified) 及来源详情 | PARTIAL | execution_gui 无该分类；gui_presentation.status_presentation raw UNKNOWN_INTERRUPTED→Failed；status_codes→UNKNOWN | Agent-first新增诊断投影；Classic映射单独修复并保留格式 |
| Python 已有诊断/处置接口 | IMPLEMENTED_TESTED | execution/client.py: diagnose/preview_closeout/apply_closeout/management_receipt/preview_process_reconciliation 等；supervisor白名单；R7/R8/R14 | 有效连接不是 mint 权限；新增中断查询只需薄包装，不再造 SDK |
| CLI/MCP crash recovery | LEGACY_ONLY | api/cli.py 为旧 API 命令；mcp/tools.ReadOnlyTools 五个只读/预览工具；test_mcp_readonly；R22 | 五工具不是 Agent-first恢复；没有 recovery Apply。只读扩展也要兼容性审查 |
| Classic recovery | LEGACY_ONLY | recovery_assessment/recovery_workflow/recovery_dialog/runtime_coordination；docs/ABQJOBPILOT_RECOVERY_AND_RECONCILIATION.md | JSON/历史DB不同权威，进程名tasklist只能辅助；Dev未含交接所述boot hotfix；不可拿来写新Store |
| Project 格式和本机凭据隔离 | IMPLEMENTED_TESTED | product_project.open_project/validate_product；local_credentials.seal/unseal；test_product_project/test_service_attachment；R20 | manifest v1 + execution schema3；复制路径/主机凭据不可携带有效权限；不隐式迁移 |

补充：store._check_sidecars/_connection会对SQLite sidecar和非DELETE模式报STORE_REQUIRES_MAINTENANCE。拒绝隐式修复已被test_run_diagnostics的honest read failures覆盖；安全存储修复为MISSING。D02只增加此失败的可解释诊断，不通过绕开检查取得业务快照。

## 不重复开发清单

不新建 Runner、执行数据库、重复管理锁、审批文件层、GUI 独立恢复状态机、普通客户端批准器或后台观察会话。优先复用 snapshot/white-list、management receipt、精确 grant checker 和原 owner transaction。已有功能的不足应表述为适用范围而非“完全缺失”。

所有 IMPLEMENTED_TESTED 条目的新版本实施都须重跑受影响回归；历史 PASS 不是当前修改后的自动通行证。

