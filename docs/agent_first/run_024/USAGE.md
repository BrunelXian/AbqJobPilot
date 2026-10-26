# Run024 — 使用说明

入口仍是 `D:\Projects\abqjobpilot_dev\Open_Dev_GUI.vbs`，使用登记的 LangChainEnv/pythonw，运行原 `run_gui.py`。本轮不更改安装环境，不创建新快捷方式。

1. 打开后默认 English，未选 Project。顶部 Project 菜单与 Projects 页提供 New Project / Open Project / Recent Projects / Project Settings。
2. New Project：输入名称、父目录和新文件夹；唯一类型 Abaqus。Review 检查目标后 Create。创建的是 AbqJobPilot Project，不是 `.cae`；不搬移 `.inp/.cae/.odb`。初始 PAUSED、无 Grant/Run、不启动服务。
3. Open Project 显式选择目录。产品 Store 与 Classic 格式分别识别；损坏/不兼容不迁移、不修复。Recent 只是用户显示索引，不自动选中/打开。
4. Service：Inspect/连接由选择 Project 的只读发现完成；无服务时明确 Start Service。Reconnect、Disconnect、Stop 分别沿用原生命周期接口；Stop 需确认且由服务安全空闲条件最终拒绝/接受。普通关窗不等于 Stop。
5. Runs 选择 Run，Newest runs/Older 分页。Identity 展示原状态/回执；Evidence 展示进程范围、退出及中断依据；Recovery assessment 仅展示候选决定、阻断原因及未知项。需要实际处置时使用已有可信本地 CR-D03 通道，本 GUI 无 Apply。
6. 下方日志/事件持续有界更新。手动滚动取消跟尾，可重新勾选。断线保留缓存，并标记中断与最后成功时间；重连不授权、不 Retry、不恢复 PAUSED。
7. 顶部 Classic Queue 进入兼容页；显式打开 Classic Project 后原 Queue 左/Results 右及 STA/Console 保留。Execution Workspace 返回产品 Runs，同一根窗口。Classic 与产品服务的 Project 来源始终分开，不对同一输出目录同时使用两个执行路径。
8. Settings/顶栏选择语言。新壳支持 en、zh-CN、fr-FR、de-DE；法德 Preview 尚待母语审校。Classic 工具保留 en/zh，法德明确回退英文。布局可拖动，Reset panel sizes 恢复比例。

显示偏好默认 `%USERPROFILE%\.abqjobpilot\display.json`，仅 language/geometry/dividers/recent；测试使用显式 ABQJOBPILOT_UI_PREFS。保存语言后下次启动保留。旧源码没有持久 locale 的读取契约（原 Classic 每次 lang=en），不从默认 Runtime/Recent 猜测语言。

Agent Access 展示公共 Python 接入、JSON CLI 的 Classic 范围及现有五个只读/预览 MCP 工具。它不是聊天窗口，不运行任意指令，也不公开凭据。知道 Project 路径/连接成功不等于获准执行。

## 边界

- 历史 owner 不会因新界面被升级、重启或替换。缺 readonly diagnostics capability 仅显示不可用；缺既有列表协议仍按原连接契约拒绝。
- 受管范围结束、Solver、DAT、Artifact、ODB、域外完整性分开，UNKNOWN 不转成成功/失败。PAUSED 不表示正在运行的 Solver 被暂停。
- 本轮 UI 验收仅固定 Python。没有真实 Abaqus、生产恢复 Apply、历史 owner 操作；无 Project Schema/授权/派发变化。
