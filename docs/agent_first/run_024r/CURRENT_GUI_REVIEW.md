# Run024R 当前 GUI 产品复核

本轮是产品方向重置与独立原型评审。Run024 的功能测试记录保留，但不能替代用户视觉验收；用户已明确拒绝九入口日常导航。正式 RC 发布操作暂停，本轮不发布、不替换生产窗口。

## 实际基线

- Develop，HEAD `9553755a24ff521dd2ac694ea39cab5a03f88466`，版本 `0.3.0.dev0`。
- 启动入口仍为仓库根 `Open_Dev_GUI.vbs`；本轮未改动。
- 原生技术栈：Python / tkinter / ttk；不是浏览器 UI。
- `abqjobpilot/desktop_workspace.py:19` 的 `PAGES` 为 overview、projects、queue、runs、results、agent、classic、service、settings；构造函数逐项建立侧栏。
- `DesktopWorkspace._build_pages()` 分别创建 Overview 摘要、Run 列表与证据、独立 Queue/Results/Service 页面。`_render()` 将公共 Reader 快照投影到这些控件。
- `navigate()` 及 Classic 惰性嵌入已实现双向导航，不能重复把“无返回入口”当作当前缺陷。现在的主要缺陷是日常信息分散、层级和密度不合用户需要。
- [Run024 原总结](../run_024/FINAL_SUMMARY.md) 的764项为历史测试口径，本轮没有重跑，也不引用为本轮原型用例数。

## 问题与修订决定

| 当前设计 / 实际源码依据 | 产品影响 | Run024R 决定 |
|---|---|---|
| 九个侧栏入口占据常驻空间 | 用户需要先判断在哪一页，而非直接看任务 | 日常只有紧凑主控制台；高级功能进入 Agent Command |
| Overview 两块较大文字区域，Queue、Results 的完整信息另处展示 | 同屏比较任务和结果成本高 | 恢复 Queue 左、Results 右，当前 Run 摘要放在其上方 |
| 多层标题、Project/状态/时间上下堆叠 | 有效表格高度减少 | 压缩为工具栏、单行状态栏、两行当前 Run |
| 原始 JSON 是多个详情的主要呈现形式 | 诊断准确但不适合持续扫视 | 默认看维度摘要，结构化原因与原始 JSON 在 Inspector 展开；不删证据 |
| 底部日志已持续存在，但默认高度较小 | 用户需要同时追踪 STA 和 Console | 保留并提高日志初始占比，支持拖动及横向滚动 |
| Service 已有独立页面 | 权限边界正确，但多出顶级入口 | 收入 Agent Command → Project & Service，仍然独立于 New/Open |
| 多语言资源已存在 | 不能用视觉重置丢失语言基础 | English 默认；中英主控件、法德 Preview；技术事实保持原代码 |

不是要删除已有功能。Project 创建、认证连接、分页、只读恢复诊断、服务生命周期等必须在后续适配时全部保留。尤其不得为了模拟紧凑界面，把真实 Grant、Apply 或 Resume 加入普通 GUI。

## 本轮取证方式

`capture_current.py` 使用当前 `AbqJobPilotApp(attachment_mode=True, native_workspace=True)` 的真实窗口，注入纯显示快照。Reader 为 None，资源值为明确模拟值。audit hook 阻止进程创建、IPC和数据库访问；显示偏好仅写本轮 `_isolated`。未打开用户 Project、默认 Recent 或历史实验。

A 图是当前实际控件，不是重新绘制的仿制图。B 图由独立 Tk 原型生成。A 的快照提供12个 Run，Overview 本身只显示当前 Run 摘要；B 展示12条队列和12条结果。两者不是同一数据库的逐行性能比较，不能据此宣称吞吐或运行能力提升。

保留当前生产代码、Run024 与 CR-D03 全部历史材料。源码保护结果见 [FINAL_CHECKS.json](FINAL_CHECKS.json)。
