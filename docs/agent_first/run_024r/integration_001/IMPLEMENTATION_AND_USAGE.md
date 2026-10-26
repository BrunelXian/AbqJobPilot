# 实现与操作契约

## 实际修改

|文件|职责和边界|
|---|---|
|`abqjobpilot/cockpit_layout.py`（新增）|纯原生 ttk 容器：顶部、摘要、左右表格、双日志、五区抽屉、Classic 宿主。无服务/数据库/Backend 依赖，无模拟记录。|
|`abqjobpilot/desktop_workspace.py`|复用 Run024 Project 创建/打开、ServiceLifecycleManager、ClassicPane、只读恢复投影；替换九页导航，增加表格排序筛选、同步选择和紧凑摘要。|
|`abqjobpilot/execution_gui.py`|现有 Reader 成功/错误快照携带 selection_version；Tk 消费时二次检查。无执行服务接口或权限变化。|
|`abqjobpilot/locales/{en,zh-CN,fr-FR,de-DE}.json`|新增紧凑界面资源，保持用户语言偏好及法德 Preview。|
|`tests/test_native_workspace*.py`, `test_native_visual.py`, `run024_gui.py`|适配已批准布局，保留原安全断言、实际正常 run_gui.main、公共查询和保留句柄证明。|
|`tests/test_cockpit_widgets.py`, `test_cockpit_windows.py`, `cockpit_capture.py`（新增）|独立控件/真实服务联动测试，以及只捕获自己 HWND 的 Win32 客户区截图。|

正常入口及 gui_app.py 本轮没有更换。原入口原本就创建 DesktopWorkspace，现在该组件构建 Cockpit。没有引用 docs 下的原型作为产品代码。未引入 Web、Electron、浏览器或第二 GUI 框架。

## 数据与动作分离

`run_gui.main → AbqJobPilotApp → DesktopWorkspace → Reader → Public Client → Supervisor`。

布局组件仅呈现数据；Project/Service 按钮继续调用原有显式可信产品入口，工作在线程中，结果按 Project generation 接收。默认打开、选择 Run、切换 Classic、展开抽屉、刷新和退出，不创建 Grant、不改变派发、不执行恢复。

Agent Command：Project & Service；Run Inspector & Evidence；Crash Recovery；Agent Integration；Advanced Settings。Recovery 直接展示核心只读诊断/预览，只有证据入口，无 Apply、恢复授权、Retry 或真实 Grant 按钮。MCP 只列已有五个读取/预览工具。Agent 仍可不依赖 GUI 使用公共 API。

## 主界面与数据联动

- Queue：已接受请求的阶段；Results：同页 Runs 的 Solver 与 Artifact 验证摘要，未验证显示 NOT_RUN/UNKNOWN，不仅列成功记录。
- 点击任一表格选择同一 Run，更新 Current Run、STA/Text、Console/Events 与 Evidence。原始执行阶段、受管范围、Solver、DAT、Artifact、ODB 仍分维度，不重新解释 START_INTENT 为成功。
- 标题排序，文本筛选；都是本页最多 32 条。Newest/Older 使用既有 keyset 查询，不一次加载全库。
- 读取在后台线程执行。progress 最多128条、events最多64条、validation最多8条。事件严格按 Run ID 归属；日志失败不能覆盖独立 Run 证据。
- 快速选择立即清空前一 Run 的详情/日志；Reader 和 Tk 两处版本检查拒绝迟到选择。旧 Run 快照不会因语言切换重新出现。
- Project 切换清除选择、缓存和日志；失联保留最后成功数据并显示 stale/最后成功时间。即便连接正常，显示也标明记录快照，不把它作为 Solver OS 存活证明。
- Follow latest 默认开启，手动竖向滚动暂停追随；可重新勾选；两个日志都有横向滚动。主上下、表格左右、日志左右分隔条可调，沿用用户级显示偏好，不写 Project。

## Classic

保留原 ClassicPane 实例、Runner、选择、过滤及布局；同进程视图切换，不重建 Runner。顶部 Classic Queue 常驻；Classic 内 Execution Workspace 返回。Classic 中打开顶部 Agent Command 时先切回 Execution Workspace，避免其标题与产品服务目标混淆；不触发服务操作。Classic 显式打开独立旧格式 Project，不自动迁移；在 Classic 中隐藏产品 Current Run 摘要，明确数据来源。Classic 任务活跃时关闭整窗仍执行原有阻止规则，不终止其任务。已有 UNKNOWN_INTERRUPTED/Failed 分离测试保持。

## 正常操作

双击根目录 Open_Dev_GUI.vbs → New/Open Project → Agent Command → Project & Service → Reconnect 或明确 Start Service。选择列表记录观察。Close 仅收起抽屉；关闭主 GUI 仅断开监控（Classic 活跃任务的既有限制仍在）。显式 Stop Service 沿用原有空闲/所有权/PAUSED检查；没有 GUI 快捷绕过。

产品无需保留测试 PowerShell 窗口。测试实际从同一 run_gui.main 启动，仪器化部分仅捕获身份、发送测试交互与截图；未替换 Client 或 Backend。正常 VBS 启动器本轮保持原样，未把测试驱动加入产品启动链。
