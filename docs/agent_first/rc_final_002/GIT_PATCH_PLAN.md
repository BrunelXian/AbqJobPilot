# 精确Git补丁方案（本轮不暂存、commit或push）

预期父提交为 `6e44387b7a35bea57e99e7e8711e799c2e089b2b`，Develop。以本轮最终 `COMMIT_CANDIDATE.json` 的逐路径工作树SHA、Git规范化blob身份、状态和分组为审批依据；不能仅按本说明或旧清单暂存。

## 建议提交顺序

1. `fix(deploy): qualify explicit Python startup and reproducible source packaging`
   将RC-F01启动器、application_runtime、Project/service宿主选择、README/DEPLOYMENT、测试入口修复与构建器/资源清单/新测试作为一个原子提交。执行核心、授权、自动收尾与Schema没有本轮新补丁。保留并纳入已审查的tests/run003_process.py部署测试导入修正，不能因它早于RC-F01便漏掉依赖。
2. `ci: add isolated no-solver checks and deployment qualification gates`
   CI workflow、安全测试入口与选定发布文档。依赖第1提交及当前HEAD中已有测试/合成fixtures；没有push触发器，PR或人工workflow_dispatch才运行。单独审批后才可推送/启用GitHub设置。

两组均不得使用git add .或-A。以后获批执行时，先核对HEAD/index/所有文件hash，再逐路径暂存和diff-check，核对实际blob与组别，commit后验证父提交/路径范围。工作树CRLF与规范化Git blob身份分别记录，不能混用字节摘要。

## 白名单边界

Git候选包括必要源码、测试、语言资源依赖的既有HEAD引用、可移植构建脚本及明确选定的文档。114项运行资源清单包含精确路径和内容摘要；未变更的现有模块无需重新提交。图标不在清单且不是必需资源，不更改ignore、不取消跟踪任何文件。

部署ZIP、测试支持ZIP、原始日志、截图、数据库、凭据、进程证据、隔离测试根、机器python-path.txt/venv以及本地审计快照不纳入新commit。既有历史文件保持原样；发布排除不等于git rm。精确排除规则见EXCLUSIONS.json。

## 放行区分

- 本地检查点：需用户对最终精确清单及提交信息授权；可记录PARTIAL验收，不把提交等同RC。
- Develop push：需独立授权并重新检查实时远端基线、祖先范围、hooks、分支保护和CI行为；不因RC-P01授权过旧提交而自动覆盖本补丁。
- 正式RC：仍需干净Win11验收、提交后受审输入重建和发布批准。版本保持0.3.0.dev0；无Tag/Release/Stable晋升授权。

历史凭据风险按此前接受的未知测试副本残余风险记录；没有证明全球撤销或清除公开副本。本次扫描只检查明确新候选内容的已知泄露值匹配，不使用其认证或解密，不把0匹配解释为全仓库无秘密。
