# Run021 — PARTIAL：产品 Standard 接入待评审

**PARTIAL — 尚未形成可批准执行的产品 Standard 验收包。**

本轮完成源码接缝审查、新产品Project与固定输入/离线预览、Windows产品及受管Standard替身回归、Git资产审查。新增精确真实批准/单次派发控制补丁被自动审批拒绝，未写入；现有应用、核心状态机、历史文档与测试文件均未修改。不能把两条分别通过的路径描述成产品Standard全链已通过。

## 已固定的准备材料

| 字段 | 实际值 |
|---|---|
| 实验 | run021_42b9754ee29b457d8c86b2e97a26ec4b |
| Project | p_fa698230f3e6499caf08517e3e82dbc2 |
| instance | pi_88118c5738214496aa2757ef5265df50 |
| 名称 | Run021 Standard product candidate |
| 根 | C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run021_42b9754ee29b457d8c86b2e97a26ec4b |
| 格式 | product manifest v1 / execution store v3 |
| 执行存储 | 根下 project\execution.sqlite3 |
| 输入 | 根下 engineering\axial_bar.inp，420字节 |
| 输入SHA-256 | e2f91730b68f3af72b8054bc168d31b72a3f21ae186e899d64ab4b6b761523a3 |
| Job候选 | r021_bar_42b9754e |
| cwd / 输出 | 根下 engineering |
| scratch | 根下 engineering\scratch |
| 目标入口 | D:\ABAQUS2024\Commands\abq2024.bat，仅静态读取摘要，未调用 |
| 资源意图 | CPU1 / GPU0 / 2048MB，最多一次analysis，额外调用0 |
| 观察意图 | 300秒仅停止观察，不终止、不重试、不删除 |
| ExecutionPlan ID | **未创建**；没有伪造ID或把离线preview当Plan |
| 当前状态 | PAUSED；0 Plan、0 Grant、0 Run、0消费、0事件；Supervisor未启动 |
| 准备清单 | PREPARATION_MANIFEST.json，明确PARTIAL_NOT_AN_EXECUTION_ACCEPTANCE_PACKAGE |
| 规范化body SHA-256 | c5b2ab1edd4d4c3c7d8ccc8803409b02bdde583a60ba8c7d6179fc887334736c |

摘要使用现有canonical_json(body)的UTF-8字节再SHA-256，不是整个JSON文件摘要，也不是执行许可。由于没有ExecutionPlan及产品Standard执行路径，这只是**不完整准备记录**，不能沿用此摘要批准真实执行。完整补丁通过后须另行形成绑定实际代码、Plan与材料的最终清单。

候选通过既有create_project创建，未复制数据库；离线prepare/inspect使用轴向打印支持档案。首次脚本把Path传给只接受str的目录参数，公开前置检查拒绝；修正脚本后复用同一已创建空Project，输入字节未改变。普通只读Python示例已在候选根（非仓库cwd）执行，返回NOT_RUNNING，见CANDIDATE_PUBLIC_INSPECT.json。最终再次只读核验同一摘要、输入和空库状态，见CANDIDATE_FINAL_CHECK.json。私有DPAPI材料保留在候选private内，未输出秘密。

## 具体未完成接缝

1. 产品ServiceLifecycleManager/service_owner只配置TEST_ONLY；require_idle和Supervisor拒绝Standard计划/配置。
2. 当前受管Standard只定义原A→B pair计划，没有本轮单项产品Plan。
3. 原真实issuer必须持有Store所有权，无法由外部脚本绕过活跃owner登记。本轮需要精确受控的owner内登记接缝，不能用连接或Stop能力代替。
4. 原PAUSED拒绝新接受，原resume打开整个gate；成功Standard保持OPEN。没有“精确接受一项→独立单次派发→持久归PAUSED”的产品政策。
5. 产品正常停服仍拒绝真实记录；需定义仅对充分受管结束、无未决状态且保留旧输出的安全停止，不得用TEST_ONLY测试结论替代。

源文件/函数、未实施补丁和竞争/故障回归要求见 [INTEGRATION_AND_PATCH_REVIEW.md](INTEGRATION_AND_PATCH_REVIEW.md)。这不是重建执行核心的理由；建议沿用原Store、owner、management receipts、Grant和Job范围，新增一个固定单项产品接缝。

## 实测与清理

- **351个唯一用例PASS，0FAIL/0SKIP**：主选集336（336.64秒）+独立Legacy15（5.11秒），ID和批次在TEST_RESULTS.json；完整XML/console保留。
- 正常Windows产品GUI新建/启动/独立客户端/关闭重连/空闲停服重启通过。固定Run `r_e133b154928144eb9eb4a58a9cf6ec40`：GUI及venv保留句柄exit0，原owner/worker仍活，游标3→4；重开原Run/回执，唯一启动；最终COMMITTED_EMPTY_SCOPE、Artifact VALID、Solver NOT_RUN。
- 原Standard managed链在另外的新隔离实例以固定Python替身、原生JOB_LIST、历史DAT样本通过；不是候选Project已经运行，也不证明真实Standard产品宿主兼容。
- 323份登记进程身份事后只读核验无匹配存活；31份残留测试私有材料删除。候选根与历史根完全排除清理。测试自身保留句柄记录的退出与事后身份未发现分别表达；审计没有terminate或递归删目录。
- 既有文件摘要全部保持，无缺失、无应用版本改变；Develop完整HEAD仍为271c6f82fd6a4599dbae2df30d903dab2cef1f63，无冲突。仅本轮新目录为新增成果。

见[验收矩阵](ACCEPTANCE_MATRIX.md)、[测试范围](TEST_SCOPE.md)、CLEANUP.json、FINAL_INTEGRITY.json。真实Abaqus调用 **0**，ODB读取 **0**；候选真实Grant/提交/开门 **0**；无Stable、生产数据、历史owner操作、共享环境/安装修改、Git切换/恢复/提交/推送。

## Git与下一步

[GIT_REVIEW.md](GIT_REVIEW.md)及逐文件审查列出源码、测试、研究资产的建议分组；一份4.98MB历史JSONL、26个二进制候选及本机路径需提交前审阅。未发现候选DB/ODB/private目录；词法秘密扫描命中文档占位符，不宣称通用匿名化。不得把本轮未实现的接缝写成已验收功能提交。

现在不申请真实实验授权，也不提供真实执行命令。下一步先明确评审允许的开发范围：**实现和隔离测试固定单项产品Standard配置、精确owner内授权登记、单次派发与安全停服；仍禁止在待审Project创建可消费真实Grant、打开派发或提交真实Run，Abaqus预算保持0。** 完成后才冻结实际Plan和清单，一次性申请真实Grant+一次analysis及约定收尾操作。

自动审批对新增控制补丁的原始拒绝理由为：“该补丁新增可签发真实 Grant 并打开派发门的持久化控制能力，超出 Run021 明确要求的‘不得创建真实 Grant、打开派发门或提交 Run’及复用既有授权机制的范围。”补丁没有落盘，没有更换工具或方案绕过。此范围冲突阻止本轮完成接入，不代表真实实验已经失败或执行过。本轮停止，等待该开发范围得到明确确认；不进入下一轮或实机执行。
