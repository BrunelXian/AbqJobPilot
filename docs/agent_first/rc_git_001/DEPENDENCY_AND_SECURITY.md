# 依赖、敏感数据与可复现性

## 凭据发现：阻断无条件 push

**`docs/agent_first/run_022/CLEANUP.json` 已跟踪，并在 HEAD 中包含凭据副本。**

- JSON 中有 44 个 `ciphertext` 字段，以及 1 个 `credential` 明文字段（64 字符）。
- 明文字段位于 `$.lifecycle_records[881].record.credential`，来源是 Run022 的 `test_windows_dpapi_binding_tamper_and_plaintext_downgrade` 隔离测试。该测试专门写入明文 profile，验证产品拒绝降级；它不启动服务，不赋予 Solver Grant。
- 已对比 `git show HEAD:<path>` 与工作树 JSON，两者解析内容完全一致。原字节不同仅为 Git LF / 工作树 CRLF。不是本轮新产生的泄漏，也没有修改历史报告来掩盖发现。
- 只记录路径、字段位置、类型和数量，**不复制秘密或密文值**。证据：[SENSITIVE_FINDING.json](SENSITIVE_FINDING.json)、[CONTENT_SCAN.json](CONTENT_SCAN.json)。

这是提交/发布材料的 P0 门禁，不是已证实的未授权 Solver 执行漏洞。没有使用凭据、查询其端点或操作任何历史 owner，不能凭审计宣称其当前有效或无效。已有测试来源缩小了风险，但不能取消“凭据不进入 Git/发布包”的要求。

本地缓存的 `origin/Develop` 与 HEAD 都指向 `9553755...`，remote 配置为 `https://github.com/BrunelXian/AbqJobPilot.git`。**未进行网络查询**，不据此宣称已公开泄漏或远端当前状态。普通下一次提交移出文件只影响新树，不清除祖先对象。后续须单独审阅敏感历史处理及远端影响，不能擅自 force-push、改写分支或删除本地记录。

源码 AST 扫描发现的两处 `secret` 常量仅位于 `tests/test_run_diagnostics.py` 的明确防导出 canary 用例；应用源码未发现类似硬编码凭据常量。没有 SQLite 魔数或私钥/已知 token 形状命中。启发式扫描并不证明不存在任意编码的秘密。

## 固定 fixture 逐项决定

完整大小/摘要/理由：[FIXTURE_REVIEW.json](FIXTURE_REVIEW.json)。

| 文件 | 大小 | 本轮建议 |
|---|---:|---|
| `tests/fixtures/Job_test.inp` | 76 B | 纳入；注明 fake 的 Queue 文本测试，不是实际结果 |
| `docs/agent_first/run_010/axial_bar.inp` | 420 B | 纳入；本仓库生成的自包含解析轴向杆输入，无 INCLUDE/外部工程；固定 Standard 契约和测试直接依赖 |
| `run_010/EXPERIMENT_MANIFEST.json` | 18,266 B | 纳入为旧的 prepare-only 调用模板测试素材；execution_authorized=false，不是当前授权；材料路径不能自动执行 |
| `run_010/RUNTIME_STATIC_IDENTITIES.json` | 4,457 B | 纳入为显式历史准备示例的静态身份元数据；不是本机动态认证秘密，不能当成跨机配置 |
| `run_011/result_review_001/ORIGINAL_DAT.bin` | 10,334 B | **待决定/默认排除**；真实 DAT 原字节副本，不能因 `.bin` 扩展名绕过禁入规则 |
| `run_007/examples/historical_invalid_after.json` | 29,955 B | **待决定/默认排除**；真实历史诊断/进程记录被兼容测试直接读取，需要明确标记的合成 fixture |

轴向杆输入 SHA-256：`e2f91730b68f3af72b8054bc168d31b72a3f21ae186e899d64ab4b6b761523a3`。DAT 原副本 SHA-256：`23ac0cdd7714ef956f481fdf1ec97530cd0cf44a160ae286cd689400efc3f045`。来源是 Run011 独立复核，后续 Standard/受管/产品/恢复测试复用其编码、版式和数值。**本轮不修改冻结副本，不复制进白名单快照。**

最小下一步：保留原样本本地；另建立声明为人工合成的 CP936/2024 版式 fixture，保留目标表、步/实体/组件与拒绝边界，并修改测试引用。历史诊断 fixture 同样生成合成身份并按原 envelope 算法绑定摘要。仅改测试/素材，不改 Parser 以迁就新样本；需分别通过相关回归。不能把生成后的素材冒充真实验收证据。若用户希望为原始素材作明确归档例外，需要另行授权，当前白名单没有这种例外。

`sample.png` 为旧 UI 截图，已目视发现工程目录、Job 名、运行统计；没有认证秘密，但应另行批准公开或换用脱敏展示副本。它不是运行依赖，README 链接需要同步处理，原图不删除。

## 产品及测试依赖

- 104 个应用源码/资源全部纳入。AST 解析了 412 个既有 Python 文件，无语法错误；产品相对导入闭包无缺项，包括 CR-D02 `interruption`、CR-D03 `recovery/recovery_management`、原 Store/IPC/ownership、Cockpit/Classic 与四语言 JSON。
- recovery 的 Apply 仍为可信本地管理路径；新增公共 client/Supervisor 方法只提供诊断及 Preview，没有新增 MCP/GUI 的直接批准权。`UNKNOWN_INTERRUPTED` 仍是诊断投影。此次未改变运行语义。
- `tests/test_standard_backend.py`、`run013_process.py`、`test_product_standard_control.py` 及间接复用者依赖上述 DAT；两份 public compatibility 测试依赖旧诊断 JSON。因此**当前筛选集不满足完整离线测试可复现性**，不能直接宣称整个安全回归已通过候选快照。
- 旧准备/验收示例可能读取 historical manifest 和被排除的 VBS/资料；不作为普通产品入口发布。当前只保证正常产品模块闭包，不能把这些示例全部描述为迁移后可一键重放。
- 304 条 Markdown 链接未落入候选文件集：300 条为明确本地证据，3 条 Run001 文档缺失，1 条指向现有目录。详见 [DEPENDENCY_AUDIT.json](DEPENDENCY_AUDIT.json)。不篡改旧报告；发布文档需显式说明本地证据索引并修正真正缺失的引用。

## 部署与语言

正常入口 `Open_Dev_GUI.vbs → run_gui.py → gui_app.main`，原生 Tk Cockpit 不依赖 HTML/Web Server。`__version__` 0.3.0.dev0；产品 manifest version=1、执行存储 schema=3、契约 af-experiment-v1 保持。

`Open_Dev_GUI.vbs`、`service_lifecycle.PYTHON`、`standard_contract.PYTHON` 硬绑定 `D:\XianLab\envs\LangChainEnv`；Standard ENTRY 为 `D:\ABAQUS2024\Commands\abq2024.bat`，Windows 路径和资源配置固定。VBS 缺解释器有 MsgBox，缺 Tk/损坏依赖的完整用户诊断仍未验收。根 requirements 使用标准库；MCP 是可选 `mcp>=2,<3`。不能将登记单机支持等同于任意 Windows 用户的可移植部署。

en/zh-CN/fr-FR/de-DE 各 168 keys，参数占位符一致；默认 en，既有中文偏好保留，法德仍 Preview。[LANGUAGE_REVIEW.json](LANGUAGE_REVIEW.json)。README 中的 New Agent-first Project / Legacy queue 名称及旧连接视图说明尚未跟上正式 New Project / Classic Queue / Agent Command Cockpit；属于首次使用文档 P1，需要局部修正文案，不重新设计 GUI。

## 45 个旧目录与忽略规则

[RETAINED_45_EXCLUSION.json](RETAINED_45_EXCLUSION.json) 重核原清单 45 个精确路径：全部仓库外，Git/发布候选数量均为 0。本轮没有重新打开其凭据或连接 owner，也没有再次尝试删除；内容/进程结论仍引用上一轮的有时间边界审计，不冒称本轮新 OS 检测。

当前 `.gitignore` 缺少任意位置 SQLite/private/原始报告的完整覆盖。先以白名单控制，不追加宽泛 `*.json`/`*.bin` 规则。可审阅精确实例和 `rc_git_001/local_verification/` 排除规则；**本轮没有修改 ignore**，更没有用 Git clean 清理。ignore 无法消除已经 tracked 的凭据历史。
