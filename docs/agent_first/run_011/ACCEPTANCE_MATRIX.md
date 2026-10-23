# R11 验收矩阵

最终候选：`sha256:645389d8f25942e908f04dca25fbefed820d6f63b35fcfb6c308977b6c016824`。

Windows 11 10.0.26300，登记 LangChainEnv Python 3.12.10 / pytest 9.1.0。新增控制器测试最终 **56 passed / 0 failed / 0 skipped（5.40s）**；复用依赖另 **21 passed / 0 failed / 0 skipped（0.61s）**。最终相关集合共77项，未运行全部历史回归。真实 Abaqus 0次。

测试名相对于 `docs/agent_first/run_011/tests/test_candidate.py`；精确参数化用例与结果在 TEST_RESULTS_04.xml / VALIDATION.json。下表 PASS 只指候选及非 Solver 证据。

| ID | 结果 | 实际测试与证据 |
|---|---|---|
| R11-01 | PASS | `test_r11_01_public_readonly_entry_no_process_or_writes[default/help/check/report/import]` 独立普通 Python、非仓库 cwd；`material_failure_before_intent`；`unsafe_cli_parameter_is_not_supported`；`frozen_invocation_forwarded_exactly_without_os_create` 用捕获替身核对原命令字符串/executable/cwd/env/句柄参数。evidence_04/readonly_*.json、unsafe_parameter.json。 |
| R11-02 | PASS | `test_r11_02_query_failure_never_claims`、`job_or_unknown_never_claims`、`host_query_exception_is_before_write`：失败/未知/非布尔/有 Job 均无意图/调用。实际 check 查询成功但 in_any_job=true，返回 BLOCKED，无真实写入。真实无 Job 操作者宿主仍待验。 |
| R11-03 | PASS | `test_r11_03_four_process_concurrency_and_repeat`：确定屏障后4个独立控制器、不同候选标识抢同根，退出码0/2/2/2；再次调用2；物理 worker 身份登记仅1个。`any_existing_attempt_blocks_new_version` 覆盖空、半写、损坏、空对象意图。evidence_04/concurrency.json。 |
| R11-04 | PASS | `intent_fsync_failure_never_calls_and_preserves`、`creation_unknown_keeps_attempt_and_distinct_state`、`event_persistence_failure_prevents_creation`、`report_failure_is_unknown_not_success`。`real_controller_exit_preserves_claim[crash_intent/crash_created]` 在确定阶段真实 os._exit(91/92)，无 finally；重开仍阻断。crash_created 的独立 worker 登记只用于清理。 |
| R11-05 | PASS | `test_r11_05_06_controller_returns_worker_continues_then_exits[worker]`：测试内部预算0.6s，真实控制器返回0后，用核对过的 worker 引用确认仍存活，心跳文件继续增长，再放行夹具自行退出0。evidence_04/survival_worker.json。 |
| R11-06 | PASS | 同测试 `[launcher]`：实际 launcher 退出0已持久化，worker仍存活；控制器报告集合/整体退出UNKNOWN，未把 launcher 当worker。Toolhelp可能观察到 conhost，始终标候选，不伪造完整集合。survival_launcher.json。 |
| R11-07 | PASS | `exact_text_rules_and_signed_reference`、`outside_frozen_tolerance_is_failure`、`missing_conflicting_unsupported_text_never_passes`、`wrong_product_or_unrecognized_blocks_refused`、`old_output_and_living_member_do_not_validate`、`input_change_during_attempt_refuses_results`、`reference_matches_frozen_original`；`report_read_does_not_probe_or_change` 保持历史/只读。样例明确为 synthetic，不宣称真实 DAT 版式通过。 |
| R11-08 | PASS | `candidate_digest_and_parameter_changes_rejected`、`material_byte_change_rejected`；collect_validation.py 实际复核新21/原34材料、106项原文件不变、真实实验 observations/extracted为空、无Job输出。VALIDATION.json；候选 CLI 不执行真实 execute，测试审计哨兵限定普通 Python 入口并拒绝生产根写入/数据库/shell。 |

## 迭代与没有弱化的边界

1. TEST_RESULTS_01：35 passed、11 failed，1.08s。10项在 OS 创建前由测试哨兵拒绝：Windows subprocess audit 参数已经变成 command-line 字符串且 executable 可为 None，原测试误按 list 处理。修正为标准 Windows CommandLineToArgvW 解析后继续严格白名单；没有取消进程哨兵。另1项测试的10ms预算在文件fsync后已经用尽，改为测试用1秒以抵达要注入的创建失败阶段，真实300秒不变。
2. TEST_RESULTS_02：46 passed，5.31s；没有源码放宽来凑通过。
3. 增补产品/额外文本/事件故障/只读报告等边界，TEST_RESULTS_03：53 passed，5.43s。
4. 记录最后采样时间而非展示时刻；结果检查再次核对输入；关闭引用异常记录为缺口；增加精确调用捕获、冻结参考对照、输入变化和句柄关闭断言。最终 TEST_RESULTS_04：56 passed，5.40s。旧测试不删改。
5. 相关复用依赖 `tests/test_probe_preparation.py` 21项全部通过，覆盖原离线档案、输入/打印约束、执行拒绝、旧摘要及材料复核。正式核心未修改，未运行无关GUI/Solver/生产数据测试。

候选旧草稿保存在 CANDIDATE_DRAFT_01/02/03.json，仅保留迭代证据，**不是当前批准对象**。最终测试针对 CANDIDATE_MANIFEST.json。

## 真实进程与注入证据的区分

- 非 Solver 集成在当前受管工具环境实测。tests/fixture_driver.py 显式记录实际 Job 结果，再仅在内部 DI 替换准入布尔值。真实 probe.py 没有该参数或测试入口。
- 三轮通过的进程组共登记 **12个worker + 3个launcher = 15个固定Python夹具进程**，均关联到真实 PID/创建时间/映像与保留OS引用的退出码0；详见 VALIDATION.json。控制器/只读客户端另有逐个创建/退出与关闭记录；有意崩溃的控制器退出码为91/92，不伪装0。
- 每轮R11-03用实际物理启动身份登记核对“只启动一次”，不只依赖结果文件个数。
- 父测试harness核对自身 ProcessReference.handle=None、Popen Handle.closed 和标准文件关闭。夹具最长10秒，自行退出或收到固定测试release文件后正常退出；没有kill/terminate。Windows自动出现的conhost只按已取得的候选观察报告，不声称发现了任意完整进程树。
- 所有新临时测试根保留作证据；没有删除旧被拒绝清理目录。没有生成IPC私有凭据、正式Project、真实启动意图或后台安装。
- 真实操作者独立终端不属于Job的准入、300秒真实实验、包装器/完整Abaqus成员、实际DAT/ODB及Solver数值结果均未验证。
