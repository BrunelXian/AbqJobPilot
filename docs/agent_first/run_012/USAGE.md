# Dev 固定 Python 执行演示

真实 Abaqus 调用 **0**。这是隔离的 TEST_ONLY ProcessFixture，不是 Abaqus 求解，也不是 Run 011 实验重放。

## 直接使用

在资源管理器打开：

`D:\Projects\abqjobpilot_dev\examples\agent_first`

按以下顺序双击现有入口：

1. **01_Start_TEST_Service.vbs**：创建新的临时演示 Project，预置固定计划/测试授权，并独立启动服务。确认提示后可关闭提示；无需保持 PowerShell。
2. **02_Submit_Fixed_Test.vbs**：普通 Python 客户端向服务提交唯一固定请求。此时不用打开 GUI。返回 ACCEPTED、Run ID、原始回执；再次点击只重放同一请求，不增加一次物理执行。
3. **03_Open_Dev_GUI.vbs**：打开现有 Dev GUI 的独立服务查看模式。确认 Project instance、Run ID 和原回执一致，看左侧 WAITING 日志继续增长。
4. worker 等待期间用窗口 **× 正常关闭整个 GUI**。随后再次双击 **03_Open_Dev_GUI.vbs**。它重新连接原 owner 和 Run，不重新提交。提交后约 45 秒，固定 worker 自行完成；GUI 分别显示 FINISHED、OS exit VERIFIED、Artifact VALID、Solver NOT_RUN。
5. 查看完成后双击 **04_Stop_TEST_Service.vbs**，显式请求演示 owner 正常退出。关闭 GUI 本身不停止服务。服务退出后私有连接文件被移除；再开 GUI 会诚实显示连接中断。

关闭再重开应在约 45 秒的等待窗口内完成。独立服务和演示授权的会话预算为 15 分钟；到期后不自动重启或恢复。打开 GUI 本身不创建新演示。重复点击 Start 在已有 LOCAL_DEMO.json 时拒绝替换，不删除旧实例；这是单实例演示入口，不是通用 Project 管理器。

入口使用固定已登记 Python；VBS 只通过正常 Windows Script Host 隐藏启动普通 Python，不改 Job 或系统策略。实际验收覆盖该 Python 入口和真实 Tk 进程；桌面 VBS 的宿主管理策略若被系统禁用，应报告限制，不绕过策略。没有要求用户保持 PowerShell，但不承诺注销、关机或终端/宿主 Job 被销毁后仍继续运行。

## 明确数据位置

第一次 Start 后：

- `D:\Projects\abqjobpilot_dev\docs\agent_first\run_012\LOCAL_DEMO.json`：公开指针，仅保存实验根、实例和请求键，无连接凭据。
- 实例根：`%TEMP%\AbqJobPilot_Run012_<随机标识>`，Start 提示给出完整路径。
- `<root>\project`：实验执行存储；`<root>\project\runtime`：固定测试进程输出。
- `<root>\private`：连接材料和可信测试交接，不能作为公开报告分享；owner 正常停止后清除这四份材料。
- `<root>\session\accepted.json`：公共接收回执。
- `<root>\logs`：owner 普通 stdout/stderr 文件。
- `<root>\control`：owner/启动器身份和正常清理报告。
- `<root>\project\runtime\process_runs\<Run ID>\progress.jsonl`：有界固定进度；result.json 是独立验证的模拟产物。

输入、Runtime 和 Project 全部属于新建的临时演示根；不读取默认 Recent、不引用生产 Project。不要把 private 文件粘到聊天或日志。stop 不删除数据库、结果、事件或证据。

## 已验证的程序化入口

入口文件：`D:\Projects\abqjobpilot_dev\examples\agent_first\dev_gui_demo.py`。

下列是实际入口的参数形式。自动验收从明确的非仓库临时 cwd 执行了 start、submit；GUI 验收驱动调用同一个 AbqJobPilotApp，正常关闭真实 HWND；停止使用相同的 control/stop.json 契约。没有将桌面 VBS 双击标为操作者已验收。`<root>` 是每次测试创建的新目录，不能复用已有数据：

```powershell
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B 'D:\Projects\abqjobpilot_dev\examples\agent_first\dev_gui_demo.py' start --root '<root>'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B 'D:\Projects\abqjobpilot_dev\examples\agent_first\dev_gui_demo.py' submit --root '<root>'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B 'D:\Projects\abqjobpilot_dev\examples\agent_first\dev_gui_demo.py' gui --root '<root>'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B 'D:\Projects\abqjobpilot_dev\examples\agent_first\dev_gui_demo.py' stop --root '<root>'
```

上述 `<root>` 表示参数模板；实际测试绝对路径在 evidence_003/product_entries.json。测试的正常 stop 使用同一个专属 control/stop.json 契约，GUI 使用实际 AbqJobPilotApp 和公开客户端。独立 client_workflow.py 的 submit 阶段也在 GUI 未创建时真实运行。

原 `run_gui.py` 另支持两个必须一起提供的参数 `--execution-connection <绝对私有连接文件>` 和 `--request-key <原请求键>`。没有这两个参数时仍进入原 Dev 队列工作区；本演示请使用 03 入口，避免选择已有工程。

## 失联或阻断

- 显示连接中断时，缓存状态及最后读取时间不代表当前运行状况。重新打开只查询，不重试业务。
- owner 崩溃后的新 owner 仍为 PAUSED；未完成 Run 仍需原明确对账机制。本入口没有自动重启、批准或恢复按钮。
- 当前仅展示固定 Python Backend，不支持任意命令、真实 Abaqus、生产 Runtime、Run 011 外部实验或跨 Project 调度。

窗口实拍和关闭/重连证据见 `evidence_003`；具体验收见 ACCEPTANCE_MATRIX.md。
