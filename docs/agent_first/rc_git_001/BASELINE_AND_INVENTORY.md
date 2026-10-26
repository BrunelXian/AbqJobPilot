# RC-G01 — Develop 检查点资产审计

日期：2026-10-26。仅审计和隔离验证；没有暂存、提交、推送、版本变更或历史文件清理。

## 实际基线

- 仓库：`D:\Projects\abqjobpilot_dev`；分支 Develop。
- 完整 HEAD：`9553755a24ff521dd2ac694ea39cab5a03f88466`。
- 版本：`abqjobpilot/__init__.py` 的 `0.3.0.dev0`。
- 1,556 个 tracked 文件；本轮开始前 498 个 untracked 文件；共 2,054 个既有文件，63,310,270 字节。
- 19 个 tracked 修改，114 行新增 / 45 行删除；没有 tracked 删除、未解决冲突或 staged 内容。
- [BASELINE.json](BASELINE.json) 保存完整 porcelain、逐文件 SHA-256/大小、numstat、133 个 ignored 路径列表及 index 摘要。ignored 项只列名称，没有打开默认 Runtime、缓存或其他数据。
- HEAD 已经包含 Run002–022、Run023 和 CR-D02 等既有资产；Run022 原计划的 HEAD `271c6f82...` 已过时。不能再次将已提交核心误报成未跟踪，也不能只提交最后的 GUI 文件。

## 逐文件分类

[FILE_CLASSIFICATION.json](FILE_CLASSIFICATION.json) 是全部 2,054 个既有文件的精确分类表，含实际路径、tracked 属性、工作树内容摘要、大小、分类理由及 KEEP_HEAD / MODIFY / ADD 建议。

| 类别 | 数量 | 处理 |
|---|---:|---|
| INCLUDE | 449 | 审阅后的候选完整快照，包含既有 HEAD 中必须保留的依赖 |
| LOCAL_ONLY | 1,585 | 原始测试/运行证据、截图、一次性工具等；保留本地，不自动装入提交/发布包 |
| REVIEW_REQUIRED | 3 | 原始 DAT 回归副本、历史诊断 fixture、含工程信息的旧 sample.png |
| PROHIBITED | 17 | 凭据容器副本、原始输出/过程记录/标记等，禁止进入当前提交候选 |

449 项候选共 3,507,941 字节，包含 104 个应用文件、93 个测试/fixture 文件、12 个 Python 示例、231 个文档/静态设计或契约素材、9 个根目录文件。产品运行源码与资源没有相对导入缺件。**这不等于完整测试依赖已闭合**，见依赖报告。

候选中的实际 Git delta 为 **71 个路径：19 MODIFY + 52 ADD**，新增文件共 4,166 行；尚未计算本轮审计材料和未来替代 fixture。准确白名单：[ADD_MODIFY_WHITELIST.txt](ADD_MODIFY_WHITELIST.txt)。完整快照：[CANDIDATE_SNAPSHOT_WHITELIST.json](CANDIDATE_SNAPSHOT_WHITELIST.json)。

排除候选中 **1,159 个文件已经在 HEAD 被跟踪**。仅不 add 它们不会使它们从下一次 Git 快照消失。精确路径见 [TRACKED_EXCLUSION_PROPOSAL.txt](TRACKED_EXCLUSION_PROPOSAL.txt)，仅为待审“保留本地、移出未来索引”的提案，绝非已执行命令，也不能一次盲目处理：必须先替换两个被测试引用的原始 fixture。其余 untracked 排除见 [LOCAL_UNTRACKED_EXCLUSIONS.txt](LOCAL_UNTRACKED_EXCLUSIONS.txt)。历史仓库内容不会因为下一次移出索引而从祖先提交消失。

## 本轮新增数据

审计只写 `docs/agent_first/rc_git_001`。为验证白名单独立性，在其 `local_verification/` 中建立四个明确的私有验证根（两次 runner 配置失败、两次成功），共 846 个源副本/临时测试文件，逐项记录在 [AUDIT_LOCAL_EXCLUSIONS.json](AUDIT_LOCAL_EXCLUSIONS.json)。它们全部排除，不允许 `git add .`。未递归删除任何目录。

[PRESERVATION.json](PRESERVATION.json) 确认 2,054 个既有文件内容及原 Git index hash 未变；原 HEAD、分支、历史报告、核心和 GUI 没有被此次审计改写。新增审计候选与本地审计输出单独列在最终审批范围文件中，避免递归自引用。
