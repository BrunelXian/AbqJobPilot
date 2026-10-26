# Git 跟踪与安装包排除分离

对 RC-G01 的 1,159 项逐文件重新计算身份并分类，见 `TRACKED_EXCLUSION_REVIEW.json`。这不是 `git rm --cached` 清单的批准。

| 类别 | 数量 | 处理 |
|---|---:|---|
| A：拟不再跟踪 | 19 | 瞬态 ready 标志、旧测试工作目录、stdout/stderr、批量进程观测 JSONL。精确路径及原因见 `PROPOSED_UNTRACK.json`。保持本地文件和历史；仅提案，index 未改 |
| B：Git 可保留、安装包排除 | 1,136 | 历史设计、测试源码、报告、审计资料等。绝不因“不是安装时依赖”就大批移出 Git。CLEANUP 当前副本脱敏后可保留，祖先风险另议 |
| C：待独立审查 | 4 | 原始 DAT、旧工程截图、两个不能作为完整 JSON 解析的历史资料；不自动删除、不纳入新提交增量 |

C 精确路径：`docs/agent_first/run_011/result_review_001/ORIGINAL_DAT.bin`、`sample.png`、`docs/agent_first/run_016/real_001/gui_A_reconnected/view.json`、`docs/agent_first/run_019/windows_product_lifecycle.json`。读取异常只表明无法按完整 JSON 审查，不推断数据损坏，更不修改历史资料。

本轮新提交白名单是**增量**，不表示祖先中 B/C/A 文件已经移除。源码回归副本是经过筛选的独立包，也不等同于完整 Git clone；两者用途明确分开。

安装包采用正向运行依赖清单：应用模块/语言资源、正常入口及必要许可/使用说明。tests、examples、docs 下实验、真实输出、凭据、数据库和临时目录全部排除。保留 Git 的历史报告可以引用本地证据；不能据此把这些证据打进安装包。

此前 45 个测试根及 RC-G01 的四个源码验证根完整保留，不再尝试删除。45 根的准确路径来自 Final Acceptance 既有审计，均不在仓库下；本轮只复核排除关系和报告 hash，不再次访问其凭据或进程。RC-G02 新验证目录在 `rc_git_002/local_verification/`，同样排除 Git 和发布包。不修改现有忽略规则；后续如需忽略，单独批准精确规则，不能忽略整个 JSON/docs 树。
