# Run022 — Develop Git安全检查点计划（未提交）

## 实际基线

`Develop@271c6f82fd6a4599dbae2df30d903dab2cef1f63`，0.3.0.dev0，无unmerged项。开始时25个tracked修改，`git diff --numstat`合计1035新增/149删除；676个tracked路径。初次清单741个untracked包括本轮刚创建的2个审计脚本，因此**原有untracked739项**。没有删除/恢复/暂存此前成果。

[BASELINE.json](BASELINE.json)逐路径保存现有文件的sha256/大小、完整porcelain/numstat、ignored列表。排除本轮自身目录后的既有可候选文件1415项、34,372,086字节。最终新增和改动以 FINAL_INVENTORY.json 为准；本轮仅允许README双语与run_022交付变化。

## 分组及建议

| 资产 | 处理建议 | 必须一起检查 |
|---|---|---|
| `abqjobpilot/execution/*`累计Run002–021B统一核心与新管理模块 | 属已审查功能源码，显式选取提交，不能仅因未跟踪排除 | service/store/supervisor与closeout/managed/product_standard的完整依赖；不要拆出不可运行的半个状态机 |
| `product_project.py/local_credentials.py/service_*`、`execution_gui.py/gui_app.py` | 产品Project/认证/生命周期/GUI源码，连同对应测试 | 不将注册路径误当通用可移植配置；不要把测试profile写入产品默认 |
| `tests/test_*`及固定`runNNN_*.py`harness | 提交源码与固定、无真实Abaqus的测试驱动 | 子进程trap、身份清理、隔离home/runtime/recent；历史DAT素材依赖要保留明确来源 |
| `examples/agent_first/*`和VBS | 分别标明通用薄客户端、可信TEST支架、历史真实验收入口 | R16等真实按钮绑定旧实例，不应作为普通用户快捷入口发布；不删除历史文件，发布包显式排除 |
| README/AGENTS/架构契约/各Run总结与验收矩阵 | 审阅后提交必要开发文档 | 历史事实保持，真实路径是证据来源不是有效授权；对外版本做独立脱敏导出 |
| 历史原始JSONL、截图、初始失败日志、清理inventory、冻结清单 | 本地保留；Git逐文件决定摘要/精选证据/受控归档，默认不做全量公开 | 活动PID/用户名/本机路径、误导性可点击旧执行入口、大量重复快照 |
| 实际Project DB、private、输出、scratch、连接材料、审计原件 | **不进入源码发布包**；按Project所有权保留原位 | 本轮不访问外部历史实例以核对，也不删除它们；没有通用“清空实验”命令 |

## 实际发现

- 现有`.gitignore`覆盖pycache、部分`runtime/*`、/projects、backups、ODB/DAT/STA/MSG/LOG等扩展；不普遍覆盖SQLite、任意位置private/connection、`.bin`或观察JSONL。
- Git候选扫描未发现`.db/.sqlite/.sqlite3/.odb`；未发现匹配敏感字段规则的实际凭据文件。扫描只报告路径/字段行号，不输出秘密值；不能保证对任意编码秘密的绝对检出。
- 扩展扫描见 [CANDIDATE_CONTENT_REVIEW.json](CANDIDATE_CONTENT_REVIEW.json)：SQLite魔数和私钥/常见token特征未命中。7处审阅项中，2处是空`.gitkeep`目录占位；Run003协议文档为尖括号连接秘密占位；GUI及closeout测试3处、Run015备份1处为隔离测试/错误凭据的固定字面值。它们不是当前服务的可用凭据，保留测试语义，不需要删除。候选分组：应用91、tests79、examples35、历史Run文档1166、其他44项。
- 大文件：已tracked `docs/agent_first/run_013/real_001/PUBLIC_OBSERVATIONS.jsonl` 4,982,433字节；untracked `run_021b/real_001/OBSERVATIONS.jsonl` 4,110,669字节。建议保留原始本地证据，发布/检查点选择摘要和必要片段；移除已经tracked内容需要未来明确操作，ignore不会自动移除tracked文件。
- `.bin`候选5项：Run011宿主证据stdout/stderr、`result_review_001/ORIGINAL_DAT.bin`及旧测试目录两份观察stdout/stderr。`ORIGINAL_DAT.bin`是10334字节、有来源的固定回归样本，被Standard测试直接引用；不能机械删除或用`*.bin`规则让安全回归缺素材。其余原始捕获逐项审阅，不作为应用runtime资源。
- `run_011/result_review_001/old_tests_tmp_001`旧测试临时路径仍有候选；按用户要求保留，不清理。建议从新发布包排除，未来审批后以精确路径规则处理。
- 开始有130个ignored路径，多数pycache；另有旧DAT、Run018日志和图标。ignored不等于适合删除，本轮未清理。
- 大量报告含Windows用户/安装/临时根路径，属于实验定位和核对信息。源码硬编码解释器/安装路径属于支持边界P1；报告路径属于披露审阅，不自动定性为凭据泄漏。
- 本轮run_022同样有BASELINE/FINAL_INVENTORY、初轮错误trace及约1.4MB CLEANUP原始记录；不能因由本轮生成就全量入Git。建议提交六份结论文档、可复现审计源码、选集/结果摘要和必要Windows小证据，原始清理与失败日志本地保留并建立摘要索引，公开前审阅路径信息。

## 建议忽略规则（仅提案，本轮未修改）

采用精确实例/私有数据目录规则排除 `**/private/`、真实Project的`execution.sqlite3*`、`project.db*`、scratch与原始输出；应用前先列出将匹配的tracked和untracked路径，不误排源码fixture。历史原始日志和旧测试临时目录使用精确路径排除。不要一刀切忽略所有JSON、BIN或docs，否则会隐藏固定Plan、审计摘要和DAT回归样本。

如果要公开历史报告，另生成脱敏副本与源摘要索引；原冻结文件不可就地改写。报告目录内本次产生的原始失败trace也按审计资料保留，不因含机器路径直接删除。

## 建议原子提交顺序

1. `feat(execution): add managed scope completion and explicit closeout`：Run014–016核心与对应测试/契约；已在HEAD内的Run002–013不重复提交。检查依赖完整性。
2. `feat(product): add scoped service discovery and safe lifecycle`：Run018–019服务/GUI适配及测试。
3. `feat(project): add protected local project and credential handoff`：Run020Project与DPAPI、相关GUI测试。
4. `feat(execution): bind fixed Standard approval and one-shot dispatch`：Run021B控制接缝及替身/Windows测试。
5. `docs(dev): freeze MVP scope and RC preflight evidence`：精选Run017–022契约/报告与本轮README修正；原始实验大日志另作审阅归档决定。

这不是可盲目按文件切割的命令表：跨阶段同一service/store/gui文件累积修改需要逐hunk核对，或保留一个可通过回归的功能整体提交，不能为了提交数量拆坏依赖。

## 在授权commit/push之前执行的检查

1. 人工确认精确路径/片段清单，先排除有效凭据、数据库、真实结果及一次性按钮；不要`git add .`。
2. 核对HEAD/Develop/无冲突及外部并发修改；以本轮摘要确认保护材料。
3. 另行授权后才stage；审查`git diff --cached --stat`、逐文件diff、秘密/大文件/忽略匹配和跨平台行尾；LF→CRLF提示不是本轮已改文件证据。
4. 检查测试素材、入口及文档链接在将要提交的集合中完整；在独立新目录/明确环境复现安全选集，禁止绑定历史活动Project。
5. 新的真实执行不属于提交检查。所有未解决风险、NOT_OBSERVED、UNKNOWN、ODB NOT_RUN继续保留。
6. commit、push、Release Tag、版本改号、Stable晋升分别等待明确授权。本轮没有执行任何一步。

**建议：可以建立经过筛选的Develop检查点；尚不适合把整个工作区直接提交或当作正式发布包。**
