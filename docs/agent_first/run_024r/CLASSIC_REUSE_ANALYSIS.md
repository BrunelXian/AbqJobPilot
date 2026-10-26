# Classic GUI 复用分析

仅审查 Dev 内的 Classic 源码及已有截图；没有访问 Stable，也没有启动 Classic Runner。

| 实际组件 / 文件与函数 | 应保留 | 应改进 / 安全边界 |
|---|---|---|
| `gui_app.py:350` `_build_widgets` | 纵向 workspace、横向 table PanedWindow；Queue 左 Results 右 | 统一边距和比例；不要复制 Runner 初始化副作用 |
| `_build_toolbar` / `_build_menus` | 快速操作、Project、Agent Command 的可见入口 | 主栏只放高频项；服务管理放抽屉，不混入 New/Open |
| `_build_status_area` / `_refresh_status` | 运行、队列、资源一眼可见 | Execution 模式取公共快照；Classic 模式取自己的原状态，不互相补值 |
| `_build_queue_area` / `_build_results_area` | ttk.Treeview、选择/排序/筛选、结果并排 | 行高约25px；窄宽度优先 Job/State，次要列转 Inspector；原执行命令不移植 |
| `_build_live_logs` / `_refresh_live_logs` | STA/Text 与 Console 同时出现，滚动查看 | 不因选择历史行就悄悄替换当前运行日志；明确来源和时间 |
| `_build_details_area` / `_show_details` | 按需显示 Overview/Files/Logs/History | Agent-first Inspector 显示相同信息层次，不能直接沿用 Classic DB 查询 |
| `_refresh_resource_usage` | 紧凑资源摘要 | 标注本机值，不宣称跨 Project 互斥；原型全部样例值 |
| `command_console.py:163` `AgentCommandConsole` | 目标 Project+ID、命令说明、可展开详情、输出与输入分区 | 原是1040×760 Toplevel；建议默认侧抽屉，长内容可扩宽。不另造主窗口体系 |
| `gui_app.py:2031` `open_agent_console` | 已有高级入口概念 | 不能在新版中变成任意 shell/Agent 自批权限 |
| `agent_session.py` `AgentCommandSession` | 明确目标、允许列表和结构化结果概念 | Session 包含 Classic Project/queue 的写操作；不可当纯显示组件原样接到产品 Store。本原型不实例化它 |
| `desktop_workspace.py` `open_classic` / `navigate` | 显式格式校验、惰性 Classic、返回 Execution、原控制器保留 | 后续只替换容器和样式，不重新创建 Runner/Reader来实现切页 |
| `execution_gui.py` `Reader` | 异步公共读取、分页/选择版本隔离、失联缓存 | 一个 Project 的读取权威保持不变，不把 mock 状态代码接进产品 |
| `ui_resources.py` `DisplayPreferences` / `translate` | 用户级语言、几何/分隔条偏好 | 后续增加布局偏好要版本化且可回退；不得写 Project 工程语义 |

原 Classic 实际截图参见 [Run024 已有 Classic 截图](../run_024/screenshots/classic_connected.png)，仅作历史视觉参考，不重新宣称已完成当前生命周期验证。

原型使用相同的 ttk.Treeview、PanedWindow、Menu、Combobox、Text、Scrollbar 和 Tk 事件循环；没有第二个 UI 框架。现阶段是独立构图验证，不声称已经将这些生产组件抽取或合并。建议复用组件形态和展示适配层，**保留原执行控制器及数据边界**。
