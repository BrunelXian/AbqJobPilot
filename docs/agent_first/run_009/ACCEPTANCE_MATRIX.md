# Run009 逐项验收

最终一次完整相关实验回归：**452 passed，0 failed/errors/skipped，252.75秒**。359项前轮测试名全部包含，原源码/断言未变；新增93项。原始[JUnit](TEST_RESULTS.xml)、[输出](TEST_OUTPUT.txt)、[逐测试名](TEST_CASES.json)、[失败迭代](ITERATIONS.json)、[副作用](EXAMPLE_FILE_INTEGRITY.json)、[清理](PROCESS_AND_CLEANUP_EVIDENCE.json)。PASS仅指受限离线档案，不是Abaqus2024语义/安装/执行验收。

| ID | 结果 | 实际测试、文件及证据 |
|---|---|---|
| R9-01 | PASS | BASELINE.md/BASELINE_HASHES/CHANGE_SCOPE；44个前轮文件初末匹配，Develop/完整HEAD/版本和冲突检查；CONTRACT_AND_BACKEND_GAPS.md接口表逐函数标明权限。 |
| R9-02 | PASS | `test_nonrepo_standalone_client_success_rejection_and_same_export`：两次独立Python从非仓库cwd调用prepare/inspect/export，退出0/2，普通脚本无pytest/tests/SQL/GUI依赖；EXAMPLE_INVOCATIONS、examples/success/rejection。 |
| R9-03 | PASS | `test_stable_body_and_distinct_observation_no_filesystem_writes`、`test_semantic_changes_change_digest`十二分支：主文件/依赖字节、配置/资源/scratch/job/Project/instance/输入名/根变更；观察时间独立。原359测试和44文件摘要未变。 |
| R9-04 | PASS | `test_include_is_submission_root_not_including_parent_and_case_rules`实际建立同名但不同位置文件；无根文件时拒绝，不读include父目录。`test_unsupported_grammar_never_claims_coverage`20分支、encoding五分支；支持表与2025参考/2024缺口明确。 |
| R9-05 | PASS | `test_unsafe_references_refused_before_read`13分支验证危险候选未打开；missing/cycles/limits八分支；真实硬链接、真实Windows junction拒绝；持有文件时实际写入获PermissionError，第二次身份检查的变化被拒绝。 |
| R9-06 | PASS | stable-body测试检查完整分维状态；profile白名单14分支；`test_inspection_is_offline_bounded_and_not_an_execution_attestation`拒绝重算摘要后的AVAILABLE升级。无Run/求解/结果验证状态伪装。 |
| R9-07 | PASS | `test_no_storage_or_validation_access_even_with_existing_store`设置SQLite、Backend、validator、transaction陷阱；新增单元组沿用启动/默认路径/旧模块陷阱；standalone审计hook；输入/Project文件哈希和时间不变，仅显式导出新增JSON。 |
| R9-08 | PASS | `test_direct_service_and_trusted_issuer_cannot_accept_preview`拒绝preview类型、请求封套和未知Plan；`test_recomputed_execution_plan_backend_still_rejected_before_consumption`使用真实登记Fake/Process Grant仍拒绝伪造Backend；真实IPC的`test_existing_public_ipc_rejects_preview_and_never_downgrades`拒绝标志修改/摘要替换/未知prepare、convert、approve、register操作。前后DB文件、Run/receipt/events/consumption及门保持；无降级执行。 |
| R9-09 | PASS | `test_output_scope_is_physical_directory_and_job_not_project`不同Project指向同根/job键相同、未预留；同basename输入冲突拒绝；旧同名log不当运行证据。scope边界和scratch/cwd分别在契约与样例显示。 |
| R9-10 | PASS | 静态契约表覆盖启动、成员完整性、退出证据、Solver、Artifact、批准、输入变化、输出/资源和全部崩溃窗口；对应当前process_backend/service/authorization/process_reconciliation代码路径；不将固定Python验收当Abaqus验收。 |
| R9-11 | PASS | 359项R2～R8逐名重跑，无删改旧断言，含公开A/B重连、真实Windows崩溃、授权/幂等/恢复。没有运行无关GUI/Solver组。 |
| R9-12 | PASS | Windows实际客户端PID9076/24688、Popen PID33732/5632，分别0/2退出；全量及本轮试跑清理聚合490个已登记OS身份、6次离线客户端调用，所有已记录句柄等待/关闭，无匹配存活、无不可查询探针、无私有材料残留。DELIVERY_CHECKS/GIT_FINAL和前置哈希确认无Stable/生产数据/Abaqus/Git写操作范围扩大。 |

额外导出边界：`test_export_uses_original_snapshot_nooverwrite_and_failure_cleanup`改变源文件后仍导出原对象，fsync失败不误报成功且清理own partial；`test_export_race_does_not_overwrite_or_cleanup_someone_elses_file`目标竞争不会覆盖；六个path分支、junction、32KiB检查无静默截断。`test_offline_dependency_graph_has_no_execution_authority_or_legacy_imports`核对新增包依赖，原执行包依赖检查保持。

支持子集内的完整依赖处理是本轮可验收结论；不支持语法直接失败，不产生“部分但完整”的预览。2024具体手册/安装行为未核验是明确未解决项，已获2025参考规则并作版本区分，未将其隐藏成实机证明。
