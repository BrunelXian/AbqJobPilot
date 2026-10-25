# Run021 — 验收与未完成项

**整体PARTIAL，不使用候选READY状态。** 351个现有/新增边界回归通过不能替代未实施的组合链。

| 范围 | 本轮实际结果 | 证据/用例 |
|---|---|---|
| 基线/历史保护 | PASS | BASELINE、FINAL_INTEGRITY；原文件未改、无缺失，无Git写操作 |
| 新产品Project | PASS | 公开create_project实际创建，PREPARATION_FACTS/CANDIDATE_FINAL_CHECK；GUI New测试、test_product_project |
| 固定输入与公开预览 | PASS，仅不可执行预览 | OFFLINE_PREVIEW；420字节新副本、固定摘要，0数据库计划 |
| 单项受管Standard Plan | NOT_IMPLEMENTED | test_managed_single_cannot_be_mislabeled_ready，当前managed仅接受pair |
| 产品Standard服务启动 | NOT_IMPLEMENTED，拒绝有效 | test_product_rejects_real_plan_before_start_reservation；无启动预约/进程副作用 |
| 活跃owner精确真实批准及单次派发 | BLOCKED_IMPLEMENTATION_REVIEW | 自动审批拒绝补丁；现有PAUSED接受/OPEN政策不足；没有改用直接SQL |
| 产品GUI/独立Python认证与生命周期 | PASS，固定ProcessFixture | test_product_windows全部9项、windows_product；真实GUI与venv exit0后owner/worker仍活、游标3→4，同Run重连 |
| 受管Standard接缝、历史DAT | PASS，独立旧路径替身回归 | test_standard_managed/windows/backend/admission；windows_standard_substitute；原生JOB_LIST+固定Python+历史样本，不是真实分析 |
| 产品Standard停服/重启PAUSED | NOT_IMPLEMENTED | require_idle当前拒绝真实计划/记录；不能用TEST_ONLY Stop通过替代 |
| 凭据/身份/复制边界 | PASS，现有产品机制 | product_project/windows、service_attachment；无新认证协议，候选私有材料未导出 |
| 既有授权/幂等/UNKNOWN/PAUSED/所有权 | PASS，相关回归 | regression_001.xml 336PASS；无修改核心断言 |
| Legacy GUI/格式 | PASS | legacy.xml 15PASS，单独隔离进程 |
| 清理 | PASS | CLEANUP：323登记身份事后核验无匹配存活，31份测试私有材料删除；事后消失不补造退出 |
| Git检查点建议 | 完成只读审查 | GIT_ASSET_AUDIT/GIT_REVIEW，未暂存/提交 |
| 实机验收清单冻结与授权请求 | 尚不具备 | PREPARATION_MANIFEST明确PARTIAL、plan_id=null；无真实执行命令，不申请当前不完整对象的实机批准 |

主回归336PASS（336.64秒），Legacy15PASS（5.11秒）；唯一ID按classname+参数化name去重，共351PASS，0FAIL/0SKIP。没有测试失败迭代；准备脚本一次Path类型错误在离线预览前置检查拒绝，修正后仍使用原新空Project，详见TEST_SCOPE。

正常GUI截图位于windows_product/product_gui.png，实测Run `r_e133b154928144eb9eb4a58a9cf6ec40`。GUI/venv通过保留句柄exit0；owner/worker继续存活，重放同回执且单个START_INTENT。最终COMMITTED_EMPTY_SCOPE、Artifact VALID、Solver NOT_RUN。这是本轮新测试，未连接历史Run016。

本轮没有真实Grant/Run写入候选Project，没有打开其派发门；Abaqus调用0、ODB读取0。替身测试中的模拟Standard许可仅属于强制替换实际创建接缝、无法调用真实程序的隔离数据，不可作为候选授权。
