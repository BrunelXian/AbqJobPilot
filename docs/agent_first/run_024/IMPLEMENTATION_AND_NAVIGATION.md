# Run024 — 原生统一工作区与修改范围

本轮依据 Run023 与 CR-D02/03，改造展示层；一个 Tk 根窗口、一个 mainloop，HTML 仍仅为设计资料。

## 实际接入

| 文件 | 修改与复用 |
|---|---|
| `abqjobpilot/gui_app.py` | 正常 `main()` 进入原生 DesktopWorkspace；抽出原 Classic 初始化；移除导航销毁窗口后另开根窗口的路径；Classic 中断标签与筛选独立。旧内部构造方式保留兼容测试。 |
| `abqjobpilot/desktop_workspace.py` | 单根持久页面、Project/Run 显式上下文、分页/异步读取、Service、New Project 向导、用户显示偏好及恢复只读详情。复用 ExecutionView 生命周期动作和 Reader。 |
| `abqjobpilot/classic_workspace.py` | 显式有效 Classic Project 后才嵌入原布局和控制器；不创建第二 Tk；切页保留 Runner、选中项/搜索、原 STA/Console；活动 Classic Runner 阻止关闭整个应用。 |
| `abqjobpilot/ui_resources.py`、`locales/*.json` | 四语言、English 回退、参数化文本、用户级有界偏好。与 Runtime/Store 无依赖。 |
| `abqjobpilot/execution_gui.py` | 可选 diagnostics，能力协商后读取两项核心投影；老服务缺能力显示不可用；原异步、分页、日志和 stale 机制复用。 |
| `abqjobpilot/execution/client.py`、`supervisor.py` | 仅两个只读 IPC 路由。参数精确为 run_id；无新高权限写入口，无 OS 探测参数。 |
| `abqjobpilot/gui_presentation.py` | 仅 raw `UNKNOWN_INTERRUPTED` 映射 Interrupted (Unverified)，真实 FAILED 仍 Failed；无持久状态修改。 |
| `tests/run018_gui.py`、`run019_gui.py`、`run020_gui.py` 与相应 GUI 断言 | 原正常入口改为本轮原生页面；白名单加入只读操作；New 测试实际填写向导。业务、生命周期与权限断言保留。 |
| `tests/test_native_workspace*.py`、`test_native_visual.py`、`run024_gui.py` | 原生控件、四语言、单根导航、只读一致性、实际 Windows 完整退出/重开及截图。 |

当前已有 CR-D03 的 interruption_probe、process_handles、reconciliation、store、recovery/recovery_management 及其测试修改，全部视为前轮资产；不归为本轮变更、不覆盖。最终摘要核验见 FINAL_CHECKS.json。

## 导航和数据权威

`Open_Dev_GUI.vbs → run_gui.main → AbqJobPilotApp(native_workspace=True) → DesktopWorkspace`

- 九个工作区持久 Frame：Overview / Projects / Queue / Runs / Results / Agent Access / Classic Queue / Service / Settings。
- 顶部常驻 Classic Queue，先于 Project/语言区；Classic 内 Execution Workspace 一键返回。无 Scene 模拟器，无第二进程/根窗口。
- 产品页面共享一个公共 Reader；选择 Project/Run 后经客户端认证读取 Supervisor。切页不重连、不授权、不派发。切 Project 清空旧选择/缓存，迟到生命周期应答按 generation 丢弃。
- Classic 与产品上下文分别保留，当前页顶栏明确来源；不双写历史、不把 Classic Runner 视为 Supervisor。Classic 只在显式有效格式/已有 runtime 文件后初始化原控制器。导航到空 Classic 不初始化默认 Runtime。
- 原 Classic 的任务编辑、队列控制、文件定位和历史行为继续在显式 Classic 范围内。切页不销毁编辑控件/对话框。旧界面语言保持原 en/zh；不声称全产品四语翻译完成。
- GUI 关闭停止自己的 Reader/after 回调并保存显示偏好；不调用 owner stop。产品任务可后台继续。Classic 活动任务另有关闭保护，不能把其 Runner 说成独立服务。

## 设计到原生的差异

保留深蓝顶栏、常驻双向导航、稳定侧栏、Queue 左 Results 右、可拖动分隔栏、底部日志/事件、身份与 freshness、独立 Service 区域。空态引导取代默认空三表。

未移植 HTML Scene/合成运行数据、浏览器布局引擎、装饰性卡片。采用 ttk Treeview/Notebook/PanedWindow/ScrolledText；Evidence/Recovery 显示核心原始 JSON 和可读维度摘要，保留原码，避免 UI 另推导恢复决定。新 Queue 是已接受 Run 的只读视图，不开放提交/批准按钮；Results 不打开 ODB。

系统 CPU/RAM 仅表示本机采样，非单 Run 配额/消耗。嵌入 Classic 的 GPU 外部 nvidia-smi 自动查询禁用，显示不可用，防止进入页面创建外部程序。没有修改 Backend 或执行资源策略。

阶段 A 先统一壳和 Classic，阶段 B 增加页面/资源/向导，阶段 C 增加只读 IPC/恢复投影并跑 Windows/产品回归。没有独立执行核心、Web Server 或新 UI 依赖。
