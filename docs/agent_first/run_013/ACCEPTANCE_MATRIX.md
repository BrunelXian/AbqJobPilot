# Run 013 验收证据

结论仅为候选接入和准备就绪。真实 Abaqus 调用0；新验收 Project 的 plans=1，grants/runs/receipts/consumption/observations/validations 均为0（DELIVERY_AUDIT.json）。没有将离线样本写入该实例。

| 要求 | 结果与实际用例/证据 |
|---|---|
| TEST_ONLY 不升级真实能力 | `test_real_requires_separate_grant_and_opt_in`：无许可、Fake Grant、ProcessFixture 工厂及未启用 Standard 的服务拒绝；Run/消费均0。原 R9 public preview 拒绝组保持。 |
| 固定计划、上下文、输入/输出/资源 | `test_changed_or_unapproved_request_never_launches` 六种拒绝；`test_one_grant_budget_and_dispatch_rechecks`；`test_command_is_frozen_windows_template_with_only_new_identity` 将实际命令与旧冻结引号模板比对，仅替换新 cwd/Job；不执行命令。 |
| 一次预算与幂等 | `test_durable_receipt_single_launch_separate_partial_dimensions`；`test_concurrent_service_claim_single_effect`；`test_cross_project_same_output_identity_cannot_restart`。保留原回执，同键不再启动；不同存储同输出键也遇到已有输出意图。 |
| 启动与持久化故障 | `test_creation_commit_crash_windows_remain_blocked` 四个确定注入点（意图后、创建前、创建后、结果提交前）；`test_intent_fsync_failure_and_uncertain_creation_preserve_claim`、`test_creation_error_never_means_safe_to_repeat`。记录不清理，不释放槽，不重跑。原 R3～R7 真实 owner 崩溃回归仍通过；本组不把异常注入写成真实 Abaqus 崩溃验收。 |
| 宿主与准备入口 | `test_host_policy_requires_queries_identity_and_regular_outputs` 五种组合；`test_host_failure_before_external_attempt`；`test_initial_preparation_lease_cannot_bypass_started_owner`、`test_approval_provision_does_not_start_or_resume_owner`。测试明确区分注入与真实 Windows owner 的观测。 |
| IPC、独立执行与 GUI | `test_windows_public_standard_path_gui_reconnect_substitute`：非仓库 cwd 的独立普通客户端、实际 Supervisor、固定 Python 替身和真实 Tk GUI。运行时查询<2秒；GUI/venv退出后 worker 身份仍匹配、STA长度继续增加；重开同Run，物理替身启动1次。原 Run012 5项 GUI 生命周期/慢通信/owner崩溃回归另见 gui_regression_002。 |
| 分维度结论 | 同一 Windows 替身测试中：文本完成、DAT主三项通过，但成员完整性/整体退出/退出验证 UNKNOWN、ODB NOT_RUN、派发 PAUSED、Run RECONCILIATION_REQUIRED。没有把替身结果称为真实 Abaqus 结果。 |
| 已有退出/对账边界 | `test_standard_has_no_existing_test_reconciliation_escape`：两种原预览均给出 `candidate_action=null`、`UNSUPPORTED_EVIDENCE_POLICY`。原管理事务和重放、暂停/恢复组通过。 |
| 解析、旧文件、未结束进程和日志 | `test_historical_cp936_sample_and_malformed_data`、`test_live_and_old_text_cannot_be_promoted`、`test_parser_failure_does_not_erase_os_evidence`。独立 validator 不覆盖启动/退出记录；GUI 保留其他状态并显示日志错误。R5白名单、限额、只读和导出组通过。 |
| 原材料、版本、工作区 | 开始和结束均 Develop、同HEAD、版本0.3.0.dev0。220个纳入本轮基线的 Run010/011 文件不变；原清单34个实际引用材料全部匹配。已有源码仅7个预期修改，见 DELIVERY_AUDIT.json；gui_app.py 的前轮改动未再修改。 |

## 实际测试结果

最终有效、按测试身份去重：**514项通过**。

- `REGRESSION_02.xml/txt`：501 passed，298.85s。含执行/存储/所有权、Fake/ProcessFixture、恢复/对账、诊断、公共工作流、Run009预览、Run010离线准备、Run012 GUI、Run013 Backend与Windows替身集成。
- `ADMISSION_02.xml`：8 passed，1.31s。
- `LEGACY_GUI.xml`：4 passed，1 skipped（第二次 Tk 初始化找不到 init.tcl；不是业务断言跳过）。该唯一项在独立进程 `LEGACY_GUI_RETRY.xml` 中 1 passed。最终该项已取得实际通过证据，没有修改或弱化旧断言。

所有测试使用登记解释器，`PYTHONDONTWRITEBYTECODE=1`、`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`、`-p no:cacheprovider` 和显式新 basetemp。没有机械运行无关旧 Solver 测试。

### 保留的失败迭代

- TEST_ITERATION_01：14通过、2失败。新测试误以为旧 ProcessGrant 工厂返回 UNSUPPORTED_EVIDENCE_POLICY，实际为 TEST_GRANT_ONLY；另一个测试比较数值文本尾零，而不是冻结数值和容差。修正测试预期后 TEST_ITERATION_02 的25项（含隔离组）通过。
- TEST_ITERATION_03：22项新增 Backend 用例通过。
- WINDOWS_ITERATION_01：实际 Windows IPC/GUI 替身闭环1项通过；最终状态展示调整后再次随主回归通过，证据以 evidence_003 为准。
- REGRESSION_01：505通过、1失败。将旧 GUI 与实验隔离组放入同一 pytest 进程，使旧 GUI 的收集导入触发隔离组的“旧 config 不在 sys.modules”断言；按原隔离要求拆成独立进程，没有删除断言。
- ADMISSION_01：7通过、1失败。新测试期待 preview 抛异常，实际契约返回结构化不可候选原因；修正为检查 null candidate 和稳定拒绝码后8项通过。

## Windows 事实及清理

新替身最终 Run `r_6b7288ba66954919bbe35309b530fd8a`（**测试实例**，不是待批准实例）。实际 owner13024，worker27596；GUI A 22040及venv25336、GUI B36604及venv23160分别取得保留句柄exit0。数字只作该次证据索引，不能拿它们作后续按PID清理依据。

完整PID/创建时间/映像/退出来源、已渲染GUI行、原回执和最终持久状态在 `evidence_003/windows_substitute_gui.json`。这次实际owner的Job查询成功且 in_any_job=true，输出为文件，限定政策eligible=true；未宣称完整Job层级或Abaqus宿主已验收。GUI用真实WM_CLOSE结束，不是隐藏窗口。

受控创建 seam 只调用固定普通Python测试脚本；其他Popen接口设为拒绝。原 TEST_ONLY/旧Runner/默认目录陷阱保持，新增模块的AST允许范围仅限固定启动及只读Win32观察。真实Abaqus入口没有被执行。

替身owner、客户端、两套GUI及已登记worker正常退出并关闭测试句柄，private bootstrap/connection/offer 已移除。故障回归只终止本轮创建并已核实身份的测试进程。新测试目录和业务证据保留，没有递归清理旧目录；新待批准实例 private/bootstrap 是有意保留的连接准备材料，不含已授予的真实执行许可，不应导出。

尚未验证：桌面VBS启动的真实服务链、实际Abaqus跨GUI关闭的生存、完整成员集合及冲突资源释放、owner崩溃后的真实进程状态、终端/注销/重启、ODB内容、跨Project/主机资源协调。下一次实验若运行太快，必须诚实标注运行期间GUI关闭场景未捕获，不能为补证自动再运行。
