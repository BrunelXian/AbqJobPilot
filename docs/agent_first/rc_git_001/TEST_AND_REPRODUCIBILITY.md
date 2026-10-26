# RC-G01 验证结果

环境先读取登记并核验：`D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python 3.12.10 / Tk 8.6 / pytest 9.1.0。没有安装、升级或修改共享依赖。

## 本轮新结果

- 412 个既有 `.py` 经 AST 解析：PASS；不导入执行历史脚本。
- `git diff --check`：无输出，退出码 0。LF→CRLF 警告没有被当作实际源码改写。
- 四语言各 168 keys，key/参数检查通过；法德保持 Preview。
- 从精确白名单复制出的独立源码快照：**15 个唯一 pytest 用例 PASS，0 最终 FAIL/SKIP**。9 个执行依赖/路径隔离 + 6 个 Cockpit 来源/显示/语言语义。两组选集独立 interpreter，不复用被 GUI 导入污染的进程。
- 原始结果：[isolation_TEST.xml](isolation_TEST.xml)、[semantics_TEST.xml](semantics_TEST.xml)、[TEST_RESULTS.json](TEST_RESULTS.json)。

首次两次 runner 均在 collection 前发生 pytest configure INTERNALERROR（exit=3）：本轮写入审计钩子拒绝了 pytest 默认 NUL 日志目标。改为明确位于隔离根的 `--log-file` 后复测通过，没有放宽目录写入规则或改产品断言。两个首次失败 RESULT.json 与成功记录都保留，未把它们计算为产品测试失败或被跳过用例。

`verify_snapshot.py` 仅复制审阅后的应用/测试源码与资源，逐文件核对 SHA；所有可写路径位于 Dev 本轮 `local_verification/<uuid>`，HOME/TEMP/Recent/preferences 显式隔离。audit hook 拒绝所有外部进程启动，真实 Abaqus 路径不可达。两个 GUI/测试进程均正常返回；Tk 夹具销毁窗口并断言 reader/lifecycle thread 结束。未创建后台 owner 或 worker，无用户进程清理；四个验证根全部保留并排除 Git。

## 没有重新执行的范围

Final Acceptance 的 225、Integration 的 768、CR-D03 的 548 是历史验收数字，本轮不累计。本轮源码与这些交接后基线在审计期间未变，但没有据此声称完整筛选快照通过全部回归。

Standard/Recovery 完整回归需要目前排除的原始 DAT/诊断素材，待测试数据替代后再运行；未为让测试通过而临时复制禁止材料进候选。实际 Windows GUI 后台存活闭环沿用上轮证据，不重复创建服务。没有 Abaqus、真实恢复、系统重启、DPI 切换、历史 owner 或远端 Git 操作。

## 独立复现

本目录 `audit_checkpoint.py`、`classify_candidate.py`、`verify_snapshot.py`、`finalize_audit.py` 是审计/验证源码，不是产品入口。它们不包含 Git 暂存或提交操作。再次执行应放到新审计批次以保留本轮材料，不能覆盖本轮 BASELINE。verify_snapshot 已拒绝复用已有 JUnit 输出名。

完整 Git 候选尚未冻结为可执行提交，因为存在已入历史的凭据和两项必要测试数据缺口。本轮的通过仅覆盖上述明确选集。
