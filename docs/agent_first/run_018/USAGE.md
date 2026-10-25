# Run018 — 正常 Dev GUI 查看已有服务

## 操作

1. 双击 Dev 根目录 **`D:\Projects\abqjobpilot_dev\Open_Dev_GUI.vbs`**。使用已登记的`D:\XianLab\envs\LangChainEnv\Scripts\pythonw.exe`；不需要保留PowerShell窗口。它只打开GUI，**不会启动服务**。
2. 点击“选择 Agent-first Project…”，选择操作者明确交接的隔离实例`project`目录（含`experiment.json`）。不要选择生产Project或历史真实实验来测试。
3. 默认使用该实例根下`private\connection.json`。若可信操作者使用其他文件名，用“指定连接材料…”选择**同实例根内、Project目录外**的已有私有文件。不要复制其中的秘密到日志或聊天。
4. 连接成功后点击Run列表中的任务。无需手工填写request key。显示原始接收回执、Job/Plan、owner、各维度状态和有界日志；“更早一页”每次最多32项。
5. 关闭整个GUI不会停止执行。再次双击上述入口，重新选择原Project和原Run。也可在同一窗口点“重新连接”；该操作保留同Project选择、重新认证，不重提任务或恢复PAUSED。

原队列工作流保留在“Legacy 队列界面”按钮中，或显式`run_gui.py --legacy`。它有原有Runtime/Recent与执行行为，不与Agent-first状态混合；本轮正常连接流程不触发它。

## 已有 TEST 服务

已有可信操作者入口仍为`examples\agent_first\dev_gui_demo.py`（固定TEST_ONLY准备/授权/启动与提交分离）；`R15_01_Start_TEST_Service.vbs`、`R15_02_Submit_Two_Tests.vbs`是旧演示支架，**不在新GUI里自动调用**。它们保留已有实例时会拒绝替换，不能通过删除旧pointer或锁来绕过。需要新演示时由操作者明确选择新的隔离根，通过已有入口准备；不是生产服务管理。

本轮实际自动化使用同一Supervisor与公共客户端，但测试控制根每次新建。客户端提交在GUI之前，GUI只做选择和读查询。实际GUI截图和各进程身份见`windows_evidence/normal_gui_lifecycle.*`；测试不要求运行任何真实Abaqus入口。

## 原因与处理

| 界面原因 | 含义及下一步 |
|---|---|
| DISCOVERY_UNAVAILABLE / NOT_FOUND | 无可用连接材料／服务；请让可信操作者检查既有服务，GUI不代建 |
| UNSUPPORTED_FORMAT / DISCOVERY_LAYOUT_UNSUPPORTED | 非格式3或不在支持的直接子目录布局；不迁移 |
| PROJECT_IDENTITY_MISMATCH / ENDPOINT_IDENTITY_MISMATCH | Project、连接文件或owner不一致；核对来源，不删除锁 |
| PROCESS_IDENTITY_MISMATCH / UNKNOWN | 无法确认记录进程身份；不是进程已安全结束的证明 |
| AUTHENTICATION_FAILED / PROTOCOL_MISMATCH | 凭据或协议不兼容；重新交接正确材料 |
| CAPABILITY_UNAVAILABLE | 已在运行的旧owner没有列表接口；本轮不自动停服/重启它 |
| COMMUNICATION_UNKNOWN | 超时或断线；显示最后成功观察，不能据此重跑或认定失败 |
| STORE_REQUIRES_MAINTENANCE / LIMIT_EXCEEDED | 存储要求显式维护／查询超限；只读入口不修复或静默截断 |

GUI不提供批准、恢复派发、重试、收尾或停止服务按钮。PAUSED／UNKNOWN持续显示为原状态。

## 实际入口与复现

普通GUI的等价命令（版本和环境未改变）：

```powershell
& 'D:\XianLab\envs\LangChainEnv\Scripts\pythonw.exe' -B 'D:\Projects\abqjobpilot_dev\run_gui.py'
```

正常入口的Windows验收由`tests/run018_gui.py`调用**同一个无参数`run_gui.main()`**，仅附加UI动作和观测钩子；固定worker由独立公共客户端提交。测试进程从非仓库临时cwd运行，用WM_CLOSE关闭实际GUI和专属venv启动器。没有使用测试专用GUI构造分支代替正常入口。VBS内容经静态路径/命令核对；主程序生命周期由实际python/pythonw进程验收，不将脚本文件存在等同于生命周期证明。

准确选集、临时根及执行记录见TEST_RESULTS.md。复测必须使用新basetemp和证据目录；不要覆盖本轮材料，也不要复用Run016保留实例。
