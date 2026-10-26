# 精确提交方案（待阻断处理及明确授权）

本方案不是暂存命令，也不是对 commit/push 的授权。当前暂存区为空。

## 文件范围和顺序

1. **功能整体：40 个精确路径**，见 [GROUP_1_PATHS.txt](GROUP_1_PATHS.txt)。
   建议信息：`feat(dev): integrate authorised recovery and compact native cockpit`。
   包含 CR-D03 核心扩展/本地管理桥、IPC 只读诊断接入、Cockpit/Classic 适配、语言资源及直接相关测试。核心和 GUI 共同引用当前接口，不以模块数量强拆成不能通过回归的中间提交。依赖当前 HEAD 已有 Run002–022/CR-D02 源码。
2. **功能文档：31 个精确路径**，见 [GROUP_2_PATHS.txt](GROUP_2_PATHS.txt)。
   建议信息：`docs(dev): record recovery and cockpit acceptance boundaries`。依赖第一组；保持旧报告原文，Raw evidence 链接标为本地资料，不将历史报告升级为新的执行许可。
3. **本轮审计材料**：最终 `AUDIT_ARTIFACT_WHITELIST.json` 指定的路径。
   建议信息：`docs(rc): record checkpoint audit and publication blockers`。本轮报告写明 PARTIAL，不能将提交文案改成“RC 已发布”。本地源码验证副本、数据库、BASELINE 原始库存与敏感资料原件不纳入。

本轮审计白名单为 31 项有 hash 的材料，加上清单自身，共 32 个新路径。因此当前三组审阅范围合计 **103 项（19 MODIFY + 84 ADD）**，不含 1,159 项待审索引排除，不含尚未实现的 fixture/文档修正。此数值是当前草案规模，不是已获准的 Git 操作。

现有 71 项 delta：19 tracked 修改（114+/45−），52 新文件（4,166 行）。上述不含后续 fixture 修正与新审计报告。精确工作树 hash 与分组见 [COMMIT_GROUPS.json](COMMIT_GROUPS.json)、[CHANGE_ESTIMATE.json](CHANGE_ESTIMATE.json)。

## 必须先处理的文件处置

完整源快照白名单是 449 项，不是仅 71 项修改。当前 HEAD 仍跟踪的 1,159 个排除候选逐项列于 [TRACKED_EXCLUSION_PROPOSAL.txt](TRACKED_EXCLUSION_PROPOSAL.txt)。此清单是审阅提案，**不能直接批量移出索引**：先解决两个必要 fixture 和旧截图决定，再形成最终白名单。未来获批仅移出 Git 索引时，也必须保留本地原文件和证据。

历史凭据处理是另外一个需要评审的 Git 历史问题。普通 index-only 移除不能使未来 push 不携带这些祖先对象。本轮不提供可误执行的 reset、filter-repo、force-push 或删除命令。

临时测试目录 45 项与本轮四个源码验证根均不在提交/发布范围；禁止 `git add .`、`git add -A` 或靠 Git clean 排除。每个获批路径必须核对本报告 hash 后单独暂存，随后再审 `git diff --cached`；任何新用户修改、HEAD/index 变化都使审批范围需重核。

## 后续准确授权请求

现在不建议批准 push。需先独立批准最小测试 fixture 脱敏及引用修正、README 入口文案修正，并决定凭据历史/旧截图的处置范围；这些不是本轮擅自实施的工作。

阻断解决、白名单重核后，所需 Git 授权应明确写为：

> 允许在 Develop 上，仅按经重新冻结的 GROUP_1、GROUP_2 和 AUDIT_ARTIFACT 白名单及逐项批准的索引排除清单建立本地检查点；保留全部本地历史证据和未获批准文件，不切换分支、不清理。凭据历史和远端风险确认已处理后，另行允许将这些确定的提交推送到 origin/Develop；不创建 Tag、不发布 Release、不修改 Stable。

当前远端目标（仅本地配置核验）：`https://github.com/BrunelXian/AbqJobPilot.git` 的 `Develop`。没有 fetch/push 或服务端确认。授权不得包含未明确审阅的 force push、main 同步或 Stable 晋升。
