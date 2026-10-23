# Run 010 — 实际基线与范围

- 实际仓库根：`D:\Projects\abqjobpilot_dev`；分支 `Develop`；HEAD `fb7912ec9e0107b18f65948b147c87579c87cded`。开始及收口均只读检查；无未解决冲突，无 tracked diff。
- `abqjobpilot/__init__.py:__version__` 仍为 `0.3.0.dev0`，未修改。
- 读取实际存在的 Dev AGENTS.md；适用上级 D:\AGENTS.md、D:\Projects\AGENTS.md 不存在，没有递归扫描其他项目。读取登记环境、Run协议及Run009实际交接/用法/矩阵/静态契约、对应源码与测试。
- 复用现有每Run独立目录、原始测试证据及最终报告惯例；本次 run_010 原本不存在。没有覆盖旧Run证据。
- Run002～009的 execution、abaqus_preview、examples、tests、各Run文档原先均为未跟踪前置成果。`BASELINE_STATUS.txt` 记录状态；Run009交付的51项源码/测试摘要全部匹配，见 `BASELINE_HASHES.json`。其中48项本轮仍逐字节不变。
- 本轮改3个既有未跟踪文件：`abaqus_preview/inputs.py`、`preview.py`、`examples/agent_first/abaqus_offline_preview.py`；新增 `examples/agent_first/abaqus_probe_review.py`、`tests/test_probe_preparation.py` 和 run_010交付/隔离实验材料。`CHANGE_SCOPE.json` 给出前后摘要。
- 现有执行核心、授权、Supervisor、进程Backend、旧GUI/Runner/Project/MCP、数据库schema和版本源均未修改。没有为预览注册真实Backend或签发Grant。
- 实际解释器：`D:\XianLab\envs\LangChainEnv\Scripts\python.exe`；Python3.12.10；pytest9.1.0；Windows11 10.0.26300。读取 `D:\XianLab\envs\ENVIRONMENTS.md` 后按绝对路径运行，不安装依赖。测试关闭第三方插件自动加载、pytest缓存与字节码写入，显式basetemp。

没有访问Stable、生产Project/Runtime/Recent/队列/数据库或用户工程；没有Abaqus任何形式调用（含信息/许可/帮助）；没有旧Runner、Git恢复/分支操作/提交/推送或全局配置修改。只读安装取证从Dev明确配置路径和可见引用链进入。

隔离实验根（保留到审批后）：

`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a`

该根沿用既有Run的显式TEMP隔离约定，但本次待批准输入/清单不能随测试目录一起删除。输入、材料、空scratch、观察目录、提取目录及隔离home/tmp保留。证据收集后的临时测试目录清理被自动审批策略拒绝；包括改用三个明确绝对LiteralPath的较窄调用也未执行。三个测试子目录及本轮中间控制脚本因此保留，不绕过策略；进程退出与IPC私有材料清理已由测试harness完成。最终路径存在性/清理记录见 `TEMP_CLEANUP.json`。

PREVIEW的Project身份仅为声明；未创建正式或实验Project数据库。没有真实执行Run、SubmissionReceipt、授权消耗、业务事件、Solver结果或Artifact验证记录。本轮的JSON记录属于准备材料/控制器离线证据。
