# Run 004 — 逐项验收与真实结果

最终结果：**189 passed，0 failed，0 errors，0 skipped，89.13s**。实际Windows运行，JUnit见[TEST_RESULTS.xml](TEST_RESULTS.xml)，控制台原文见[TEST_OUTPUT.txt](TEST_OUTPUT.txt)，对应源码见[SOURCE_HASHES.json](SOURCE_HASHES.json)。所有下列引用均指本次最终运行中通过的测试；参数化名称以JUnit为准。

L指[tests/test_fake_reconciliation.py](../../../tests/test_fake_reconciliation.py)，P指[tests/test_reconciliation_supervisor.py](../../../tests/test_reconciliation_supervisor.py)。下列完整函数名省略L/P模块前缀；同一测试可支持多个验收项，不能将矩阵行数视为测试数。

| ID | 结果 | 实际测试名称 | 观察与证据 |
| --- | --- | --- | --- |
| R4-01 | PASS | P `test_windows_crash_reconcile_explicit_resume_end_to_end`（False/True） | owner在dispatch:after_artifact屏障被真实句柄终止；重启PAUSED、Run需对账、原结果仅一份。进程创建时间/映像/退出与屏障见PROCESS_EVIDENCE |
| R4-02 | PASS | L `test_preview_is_readonly_deterministic_and_adoption_appends_bound_evidence`；P `test_windows_crash_reconcile_explicit_resume_end_to_end` | 同事实预览完全一致；数据库、文件内容/mtime、证据目录inventory无变动；返回原计划、修订、指纹、候选与依据 |
| R4-03 | PASS | L `test_preview_is_readonly_deterministic_and_adoption_appends_bound_evidence`；L `test_historical_plan_is_used_without_reading_new_input_or_configuration`；P端到端 | 原Run/attempt/提交回执与执行消费保留；只新增本次observation/validation/reconciliation/event；源结果bytes/mtime不变，快照摘要绑定；不再次Fake、不伪造历史完成事件 |
| R4-04 | PASS | L `test_bad_artifact_cannot_be_adopted_or_recreated`（9种）；L `test_missing_historical_evidence_never_infers_completion`（4种） | 缺失/损坏/错Run/Plan/phase/config/input/格式/超限均无候选或拒绝；缺接受、领取、消费或历史输入清单同样拒绝，保留阻断，无补写或重跑 |
| R4-05 | PASS | L `test_unsupported_plan_rejected_before_artifact_read`（5种）；L `test_real_junction_artifact_is_refused_before_read`；L `test_hardlinked_artifact_is_not_accepted`；L `test_format_two_readonly_compatible_but_management_rejected` | 越界输出、未知Backend/版本/政策/canonicalization在artifact打开前拒绝；真实Windows junction拒绝、硬链接在读内容前拒绝；旧格式只读兼容且管理拒绝，无迁移 |
| R4-06 | PASS | L `test_preview_change_invalidates_submission`（artifact/revision/gate/owner）；P `test_owner_restart_invalidates_old_preview_and_management_permission` | 摘要或前置条件变化拒绝；真实owner再次启动后旧预览/权限STALE_OWNER；无错误终态、无业务写入 |
| R4-07 | PASS | L `test_management_grant_exact_scope_and_expiry_required`（8种）；L `test_self_attested_management_fields_rejected`（3种）；L `test_execution_grant_cannot_replace_management_permission`（2种）；L `test_resume_requires_distinct_exact_management_permission`（6种）；P端到端 | 缺管理许可、过期、越权、错owner/Project/action/authority等拒绝；approved/role/target_state拒绝；真实IPC凭据只允许连接，原执行Grant不能批准管理 |
| R4-08 | PASS | P `test_windows_crash_reconcile_explicit_resume_end_to_end[True]`；L `test_management_commit_ack_unknown_is_resolved_by_original_key`；L `test_snapshot_and_commit_failures_preserve_truth_and_receipt[management:after_commit]` | 对账已提交、应答未送时真实结束等待客户端；重连同键取原回执，仅一条对账记录；commit实际完成后确认报错也用原key查询恢复结论 |
| R4-09 | PASS | L `test_concurrent_apply_idempotency_conflict_and_consumption`；L `test_concurrent_distinct_keys_cannot_adopt_same_revision_twice`；L `test_resume_atomic_idempotency_conflict_and_receipt_is_not_gate_view` | 六线程同key只一操作/一次消费；同key异内容冲突；不同key竞争同revision只一次状态转换；resume同样事务幂等 |
| R4-10 | PASS | L `test_snapshot_and_commit_failures_preserve_truth_and_receipt`（before/after snapshot、before/after commit）；L `test_management_commit_ack_unknown_is_resolved_by_original_key` | 快照保存或提交故障不假报成功；回滚不撤销文件，允许可识别的孤立快照；已提交结果未知须查原key；原事件/回执保持且Fake不增加 |
| R4-11 | PASS | L `test_resume_separate_from_adoption_pending_revalidated_and_replay_no_reopen`；P端到端 | 采纳后PAUSED，另一个PENDING未运行；重连无派发；再次重启并重放旧resume回执仍PAUSED |
| R4-12 | PASS | L `test_resume_separate_from_adoption_pending_revalidated_and_replay_no_reopen`；L `test_resume_requires_distinct_exact_management_permission`；L `test_query_and_management_refuse_maintenance_without_repair` | 有未解Run/占用槽拒绝恢复；精确owner/门版本许可、无不确定性时OPEN；维护错误不隐式修复；回执与当前门分开查询 |
| R4-13 | PASS | L `test_pending_does_not_revive_stale_plan_or_grant_after_resume`（input/configuration/grant_expired/plan_expired/authority） | 恢复门不复活失效任务；原领取校验继续拒绝并BLOCKED，未Fake；原执行消费关系保留 |
| R4-14 | PASS | P `test_windows_crash_reconcile_explicit_resume_end_to_end`（2个真实进程case） | 原Run只有一次START_INTENT和原副作用；授权采纳后另一个任务仍PENDING；独立恢复才完成第二个任务。demonstration保留原回执、门、事件、快照引用 |
| R4-15 | PASS | 原R2/R3全部125项；L/P新增64项；原 `test_execution_isolation.py` 9项 | 125个前置JUnit case身份全部包含于最终189个PASS；原launch/legacy/default路径trap保留；30个多进程case全部清理句柄/凭据，临时数据范围和Recent哨兵验证通过 |

## 覆盖数量与回归边界

| 模块 | 本次通过数 |
| --- | ---: |
| test_execution_contract | 56 |
| test_execution_store | 30 |
| test_execution_isolation | 9 |
| test_execution_ownership | 2 |
| test_fake_supervisor | 28 |
| test_fake_reconciliation | 61 |
| test_reconciliation_supervisor | 3 |

原125项中包含Run002的95项。没有降低原断言；仅对静态隔离测试加入新模块所需fsync/fstat精确白名单，原真实启动与旧模块导入trap仍在。没有运行无关GUI/Solver全量组，没有真实Abaqus验收。

## 迭代记录

本轮独立临时根为 `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run004_e0d90d97a657421899e4df6616b561fb`。每次采用全新basetemp，保留旧结果。

| 次数/证据 | 实际结果 | 修正/新增依据 |
| --- | --- | --- |
| run1.xml / run1.txt / run1 | 169 passed，2 failed，79.88s | 两项授权负面用例在测试fixture调用时action/scope同名参数冲突；将fixture形参改为issued_action/issued_scope，允许构造被拒绝的越权对象；未放宽产品校验或断言 |
| run2.xml / run2.txt / run2 | 186 passed，84.15s | 补齐恢复权限、维护拒绝、Windows路径和格式兼容等覆盖 |
| final.xml / final.txt / final | 189 passed，89.13s | 再补硬链接与commit确认丢失覆盖，严格历史契约类型检查，清除已解决Run当前error但保留历史事件；最终源码哈希绑定此轮 |

最终零失败、零跳过，R4无待覆盖项。Windows进程终止不代表断电/操作系统崩溃，TEST_ONLY管理许可不代表生产人类批准；限定证据充分的fake-v1采纳不代表证据不足Run可强制关闭。详见[进程与故障证据](PROCESS_AND_FAILURE_EVIDENCE.md)。

## 可复现命令

在Dev根目录使用登记解释器，每次生成新的测试根；不将basetemp指向已有目录：

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$r4TestRoot = Join-Path ([IO.Path]::GetTempPath()) ('AbqJobPilot_Run004_repro_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $r4TestRoot | Out-Null
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B -m pytest -p no:cacheprovider tests/test_execution_contract.py tests/test_execution_store.py tests/test_execution_isolation.py tests/test_execution_ownership.py tests/test_fake_supervisor.py tests/test_fake_reconciliation.py tests/test_reconciliation_supervisor.py --basetemp="$r4TestRoot\cases" --junitxml="$r4TestRoot\results.xml" -q
```

仅复现无GUI多进程端到端演示时，使用同一新根与选定解释器，把测试列表替换为 `tests/test_reconciliation_supervisor.py::test_windows_crash_reconcile_explicit_resume_end_to_end`。两个参数case分别验证正常对账应答和提交后丢应答；各case输出demonstration.json、lifecycle.json、inventory.json，退出时清理自有进程与连接凭据。测试入口不启动旧Runner或Solver。
