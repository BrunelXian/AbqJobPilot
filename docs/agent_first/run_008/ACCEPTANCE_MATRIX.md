# Run 008 — R8-01～08实际验收

最终运行：**359 passed，0 failed/errors/skipped，421.60s**。原343项按classname/name逐一包含，16项新增。原测试源码未改。实际JUnit见[TEST_RESULTS.xml](TEST_RESULTS.xml)，逐测试名/耗时见[TEST_CASES.json](TEST_CASES.json)。以下“通过”仅指固定TEST_ONLY范围。

| ID | 结果 | 实际证据与测试映射 |
|---|---|---|
| R8-01 | PASS | [接口映射](PUBLIC_CLIENT_CONTRACT.md)逐项区分operator/client/internal；确认缺少Plan读取及显式validation RPC、批准依赖测试支架、包导入连带writer。新增仅两个RPC/包装及可信登记。test_plan_inspection_readonly_and_public_projection、test_trusted_process_issuance_exact_and_no_self_approval。 |
| R8-02 | PASS | test_standalone_operator_and_two_public_clients_from_nonrepo_cwd实际启动独立owner/A/B；A/B审计hook禁止tests/pytest、SQL、store/owner/issuer/backend、进程启动。显式--source，无共享安装；实际非仓库cwd/argv见EXAMPLE_INVOCATION。 |
| R8-03 | PASS | 同一测试的Project instance/Plan/Run交叉核对、显式临时所有路径、Recent不变、I/O guard。旧test_all_runtime_io_confined_and_default_navigation_untouched和全部process harness隔离检查重跑。 |
| R8-04 | PASS | A结构化GRANT_REQUIRED拒绝后才合法提交。test_new_ipc_operations_keep_auth_binding_and_strict_fields验证错误credential/Project/危险参数/approve未知操作；test_validation_refusal_before_artifact_read五分支、test_expired_and_stale_validation_permission_fail_before_read、trusted issuance测试。旧test_process_requires_exact_dedicated_test_grant_before_any_launch五分支保持Fake Grant不能启用process。 |
| R8-05 | PASS | 独立示例的四角色持久化exit=0、execution FINISHED、backend COMPLETED、artifact VALID、Solver NOT_RUN分离。explicit_validation_replay_concurrent_and_separate_state保留原receipt/attempt/退出/gate；explicit_validation_invalid_does_not_rewrite_process_success验证产物FAIL不会改写执行成功；pending_and_uncertain_are_ineligible拒绝未结束Run。 |
| R8-06 | PASS | A PID26744退出、owner PID2188继续、B PID1572重连。原receipt与Run保持，submit重放true；owner启动audit仅1次，与四个OS核验身份及退出证据交叉确认。test_standalone_operator_and_two_public_clients_from_nonrepo_cwd；旧R3/R6丢应答/并发/断线回归全部保持。 |
| R8-07 | PASS | 同一独立示例离线report_bytes验证、body摘要等于客户端原report摘要、view完全一致；两条历史validation仅一条explicit_client_validation，诊断未重新验证。导出不含凭据、Grant字段、原路径或Artifact字节，使用原限额。test_previous_v2_report_allowed_validation_source_remains_readable保留旧source枚举兼容；R5原50项、R7历史诊断契约重跑。 |
| R8-08 | PASS | 343旧+16新增全通过；原343测试名全部存在，旧断言文件哈希不变。test_validation_transaction_and_lost_response两窗口验证提交前回滚/提交后原receipt重放；[进程证据](PROCESS_EVIDENCE.json)、[最终清理核查](CLEANUP_AUDIT.json)、EXAMPLE_CLEANUP均完成。本轮仅Dev，Git HEAD/版本不变，无commit/push。 |

新增16项分布：test_public_workflow.py 14项（包含参数化），test_public_client_example.py 2项。Windows真实进程由原harness及独立示例创建；pytest只驱动独立程序，业务流程不调用测试内部函数。没有把异常注入当作全部进程验收，也没有为了编号重建R2～R7故障矩阵。

限定缺口：Plan与执行/验证许可依赖操作者预置；真实批准、通用任务准备、Abaqus、遗留观察/接管、主机/跨Project资源和GUI监督均未验收。独立示例展示新实例的正常工作流，不宣称可以恢复旧实例。
