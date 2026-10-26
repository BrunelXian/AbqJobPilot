# 更新后的 Develop 检查点方案

这是待批准白名单，**不是 Git 操作授权**。不使用 RC-G01 的 103 项草案作为新审批依据，不执行 add/rm/commit/push。

## 精确对象

`CANDIDATE_MANIFEST.json` 绑定三个逐文件集合的路径、Git 状态、字节数和 SHA-256：

1. `SOURCE_TEST_WHITELIST.json/.txt`：累计恢复核心/Cockpit/本地化及测试，新增合成 fixture、导出脱敏与 CLEANUP 修正。
2. `DOC_RESOURCE_WHITELIST.json/.txt`：既有 CR-D03/Run024/024R 审查文档、两份 README 最小入口修正。
3. `AUDIT_WHITELIST.json/.txt`：重新核对的 RC-G01 精选审计资料与本轮报告/机器摘要/重现脚本。原失败日志、截图、临时凭据/数据库不作为审计白名单自动全量纳入。

清单正文 canonical JSON：`json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')` 后 SHA-256。清单自身不自引用；另列文件原始字节摘要。所有新审计文件在正文固定后生成。摘要不是执行或提交授权。

## 建议提交顺序

**提交一：SOURCE_TEST + DOC_RESOURCE 的并集**。
推荐信息：`feat(dev): integrate authorised recovery and compact cockpit with reproducible fixtures`。
把累积核心/GUI/资源/对应测试保留一个可回归的完整整体，依赖当前 HEAD 已有 Run002–022 模块；不为形式拆出不能启动或缺资源的中间提交。包括已公开 CLEANUP 的当前副本脱敏、导出防泄漏修正；不声称清除了祖先。

**提交二：AUDIT + 候选清单及路径清单**。
推荐信息：`docs(rc): record credential exposure, fixture closure and checkpoint boundaries`。
依赖提交一。审计状态保持 PARTIAL，不在 commit 文案称 RC 已发布。将精确生成的清单及自描述 manifest 一起提交，不能通配 `rc_git_002/`；该目录内有必须排除的验证根。

19 项取消跟踪建议不进入本次增量，不在两次提交中执行。若以后批准，要逐路径另审 index-only 影响、保留本地文件与历史；不与凭据历史重写混为一谈。

## 本地 commit 前置条件

- 用户明确批准本轮最终清单正文摘要与白名单；分支仍 Develop、HEAD 仍 `9553755a24ff521dd2ac694ea39cab5a03f88466`。
- index 与本轮基线一致、无暂存内容/冲突；逐项重新计算 hash。任何外部修改停止相关暂存。
- 仅精确逐文件白名单暂存，不用 `git add .` / `git add -A`。审核 staged 文件集合、语法/资源/fixture 闭包，不混入新测试根。
- 审查 CLEANUP staged diff 时不得把被删除的秘密原文输出到聊天/日志；用字段级脱敏比较和内容身份核验。
- 本地保存修复不代表公开历史已安全；当前允许建议建立**受限本地检查点**，无需先批量取消跟踪 1,159 项。

## push 前置条件（独立批准）

历史公开认证材料的有效性/复制范围审查及风险接受，或精确撤销/轮换处理必须闭合。决定是否保留历史；若要重写，先专项批准分支/备份/协作影响，不能从普通 push 授权推导强推。然后重查远端 Develop、main、tags/PR/fork 的实际情况，明确只推经批准的新提交；不更新 main/Stable/Tag。

## Release Candidate 前置条件

完成上述安全处置，并落实独立安装包正向清单与部署验收。硬编码登记解释器及宿主配置仍限制为已验证的 Dev 主机；非该环境首次启动属于 P1，需要实现可审查配置或明确缩小 RC 支持范围。法德 Preview、固定 Standard 模型、Run021B `NOT_OBSERVED`、ODB `NOT_RUN`、域外 `UNKNOWN` 保持。正式版本号仍 0.3.0.dev0，不创建 Release。
