# Run 010 验收矩阵

结论：实验材料已具备审查条件，但本轮整体保守记为 **PARTIAL**，因为R10-07中的临时文件清理被自动审批策略阻止。任何真实执行仍未授权、未进行。各项均为准备范围验收，非Runtime/真实Backend验收。

| ID | 结果 | 实际证据 |
|---|---|---|
| R10-01 | PASS | BASELINE/BASELINE_STATUS/BASELINE_HASHES、CHANGE_SCOPE；Develop完整HEAD复核，无冲突；51项前置源码初始匹配，48项保持，只有3项有意最小修改。Run009公开接口/授权隔离审查见RUNTIME_AND_CONTRACT表。 |
| R10-02 | PASS（静态） | 19份明确来源文件身份、安装2024登记、PE版本、BAT→Intel→SMALauncher链、本地memory说明、参数表；INDIRECT_CONFIG_PATHS明确VS默认路径缺失。未执行包装器/环境/信息命令。2024关键词手册未取得、动态未知有明确标记。 |
| R10-03 | PASS（离线） | 唯一axial_bar.inp、PREVIEW、PUBLIC_CLIENT_RESULT及ANALYTICAL_REFERENCE。实际公开接口在非仓库cwd成功；解析F L/(E A)=0.01、F/A=1、RF=-1。新输出档案21项测试覆盖固定语法、只读、变更拒绝，不声明Solver模型已验证。 |
| R10-04 | PASS | EXPERIMENT_MANIFEST固定ID/34项材料/完整目录/job/单阶段/CPU1/GPU0/2048MB/analysis1次/额外Abaqus0次；PACKAGE_RECHECK实际复核成功，未有同名输出；未预留资源和输出。 |
| R10-05 | PASS（方案审查） | OBSERVATION_AND_ACCEPTANCE_PLAN：绝对cmd/BAT、参数引号/cwd/显式环境/独占日志、创建时间+映像+持有引用的观察；300秒只停止等待，引用本机Python wait与run的不同超时行为。未知真实成员集合不照搬夹具。 |
| R10-06 | PASS | `test_new_preview_refused_before_execution_mutations`：新档案直接公开service提交拒绝且DB/消费/事件不变。原R9 `test_existing_public_ipc_rejects_preview_and_never_downgrades`、`test_recomputed_execution_plan_backend_still_rejected_before_consumption`实跑；56项execution_contract和34项process_contract回归。未新增Backend/Grant能力。 |
| R10-07 | PARTIAL（文件清理阻断） | 最终204 passed、0failed/0skipped，28.38s；TEST_RESULTS/TEST_OUTPUT/TEST_CASES逐名。第一轮5失败及后来静态材料复核拒绝均保留在ITERATIONS。进程已退出、私有凭据已清理；递归删除本轮临时测试目录两次均被自动策略拒绝，文件仍保留，见PROCESS_AND_CLEANUP_EVIDENCE/TEMP_CLEANUP。 |
| R10-08 | PASS（停在批准前） | 清单摘要04ed0538…ee4af2b6、固定输入/预览、冻结容差、独立DAT读取方案、风险/停止边界和FINAL_SUMMARY中的精确批准请求。实际Abaqus调用0，没有真实Grant/Run。 |

## 实测选择与解释

最终组：test_abaqus_preview=91、test_abaqus_preview_integration=2、test_execution_contract=56、test_process_contract=34、test_probe_preparation=21，共204。

新增/修改接缝是两个离线解析模块、既有离线示例的一个参数和只读包复核示例，因此运行全R9公开prepare/读写边界/IPC拒绝组，以及执行和固定进程授权契约回归。没有修改监督/对账/恢复核心，按本轮指令没有机械重跑历史452项、所有进程崩溃矩阵或无关GUI/Solver测试。历史452不计作本轮结果。

新测试具体包括 `test_default_profile_remains_identical_and_rejects_new_keywords`、`test_probe_profile_is_bounded_readonly_and_not_an_execution_plan`、9种 `test_only_exact_print_subset_is_supported`、3种 `test_print_request_presence_and_placement`、新预览提交拒绝、5种材料/输入/输出变更检测、`test_static_metadata_hardlinks_do_not_relax_input_policy`。默认启动陷阱与旧Runtime导入陷阱有效；原有测试断言未改。

第一次测试198通过5失败：4项新增测试误匹配错误描述而非code；1项旧文件固定引用测试的回调只接收位置参数，新代码默认路径传入关键字造成兼容失败。修正新断言和默认内部调用后203通过。真实包复核又拒绝了cmd.exe合法硬链接；只改只读安装材料检查，新增保持INP硬链接拒绝测试，最终204通过。初版清单保留为MANIFEST_REVISION_01，不再用于批准；当前清单已重新摘要并实际复核。

没有用缺少错误推定求解成功；没有任何实际数值结果。本轮唯一结果验证交付是冻结的解析值、容差和缺失/歧义/失败分类方案。
