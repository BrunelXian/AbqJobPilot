# Run021 — 只读 Git 候选范围审查

审查时Develop@271c6f82fd6a4599dbae2df30d903dab2cef1f63，无冲突；未暂存/恢复/提交/推送。`BASELINE.json`保留开始状态和已有文件摘要，`GIT_ASSET_AUDIT.json`记录逐文件分类、大小、风险标签、忽略路径及核对结果。审查不停止历史owner、不读取临时Project数据库。

本次扫描时非忽略候选1315文件、27,851,159字节，忽略项123；含后续尚会追加的本轮文档前快照，不是最终Git提交数量。无候选数据库/SQLite/ODB、无private/runtime目录候选。26个二进制/图片候选需逐项人工决定。最大单项是历史 `docs/agent_first/run_013/real_001/PUBLIC_OBSERVATIONS.jsonl`（4,982,433字节），建议不直接纳入普通源码检查点，先确认长期证据保存和脱敏策略。

554个候选含本机路径引用（D:\XianLab、用户Temp、固定安装等）。报告中的实验身份和历史路径为证据，不能为“干净”而篡改；产品硬编码解释器/安装路径则是明确单机限制，发布前需独立配置设计。扫描没有导出任何候选秘密值。唯一“credential长字符串”命中为Run003协议文档的 `<private-local-token>` 占位说明，复核非真实令牌。此词法检查不等于通用秘密扫描或截图匿名化保证。

## 建议分组（只建议，不提交）

1. R2–8共享执行核心、Store/owner/IPC、TEST_ONLY、诊断/对账、受限进程与公共客户端：结合原阶段矩阵与最新相关回归评审；保持原子接受和授权消费，避免按文件随机拆断依赖。
2. R9–11离线输入与历史控制器：离线产品模块与历史实验研究资产分开；旧控制器不当当前产品入口。真实原始DAT离线夹具需明确用途和许可来源。
3. R12–16 GUI连接、受限Standard、受管Job、自动收尾及序列：源码+对应测试；实机报告单独证据提交，不能带临时工程库/连接材料。
4. R17–20产品GUI发现、生命周期、Project创建和本机凭据：按模块依赖组织一个或少量有意义提交；DPAPI/private目录排除必须有最终检查。
5. Run021本轮仅文档、无Solver准备脚本和两个负向缺口测试；**没有已验收的新产品Standard接入代码**。不可写提交说明称此真实产品链已完成。

建议说明可分别为“Add unified owned execution service and bounded client contracts”“Integrate managed fixed Standard evidence and GUI monitoring”“Add explicit product project lifecycle and protected local credentials”“Record product Standard readiness gaps and isolated regression evidence”。实际拆分需审核依赖，不能由本轮自动创建检查点。

## 明确排除和发布门槛

- 不提交候选Temp Project、execution.sqlite3、private/、owner/start/stop活动元数据、密文凭据、Grant对象、真实工程输出及运行scratch。DPAPI密文也不是可发布内容。
- `.gitignore`已排除多数Abaqus扩展和runtime部分，但**没有全局DB或private规则**；不能只依赖ignore。建议下一次获准提交前逐路径审核暂存清单，非本轮修改ignore或清理文件。
- 运行截图、JSONL及带用户名路径的实验报告需范围审阅；已存历史报告不覆盖、不删除。
- 超大二进制、临时日志、测试basetemp应留在显式外部证据位置；需要Git保存时提供有界汇总与来源摘要。
- 提交前重新核对分支/HEAD、冲突、候选路径、秘密检查、必要回归，以及实际差异是否包含未完成产品Standard补丁。不得用旧历史测试数代替新结果。
- 0.3.0、Stable晋升、生产格式迁移、通用真实批准、真实产品宿主实测与安全停服均未由本轮获得通过。
