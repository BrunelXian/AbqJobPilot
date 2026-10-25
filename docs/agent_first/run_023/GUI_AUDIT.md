# Run023 · GUI 现状审查

审查日期：2026-10-25。范围是 Dev 源码、Dev 内保存的历史报告和截图，不连接历史服务，不打开历史 Project。本轮只新增本目录，不改现有 GUI。

## 实际基线

- 仓库 `D:\Projects\abqjobpilot_dev`，分支 `Develop`，HEAD `271c6f82fd6a4599dbae2df30d903dab2cef1f63`，无未解决冲突。
- 应用版本保持 `0.3.0.dev0`。开始时 25 个已跟踪文件有修改，`git diff --stat` 为 1073 行新增、155 行删除；未跟踪成果及逐文件摘要完整保存在 [BASELINE.json](BASELINE.json)。这不是本轮增量。
- 已读取实际根 AGENTS.md；适用上级 D:\ 与 D:\Projects 未发现 AGENTS.md。Dev 中只有根 AGENTS。未发现另一个通用 Run 协议文件；沿用历史 Run 的独立目录、原证据不覆盖、FINAL_SUMMARY 与验收记录方式。
- 读取 ENVIRONMENTS.md，使用登记 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，实际 Python 3.12.10 / Tk 8.6。生成设计资源仅用标准库。没有安装依赖。
- Run022 FINAL_SUMMARY 已明确完成并停止，状态 RC_PREFLIGHT_READY；其 664 项安全回归是**历史结果**，不是本轮重跑。

## 实际入口和源码接缝

以下行号基于本轮未改动源码；后续实现需按函数名定位。

| 路径 / 函数 | 当前实现事实 | 设计处理 |
|---|---|---|
| `Open_Dev_GUI.vbs:6–15` → `run_gui.py:1` | 固定登记 pythonw，启动 `gui_app.main`；不是浏览器应用 | 保留正常 Dev 入口，不引入第二套 UI 框架；通用部署另属 Run022 P1 |
| `abqjobpilot/gui_app.py:200` `AbqJobPilotApp.__init__` | Tk 根窗口；attachment 分支创建 ExecutionView 并立即返回；Classic 分支执行 `_load_legacy/init_storage/QueueRunner/ProjectManager` | 同一 Tk 根 + 工作区 Frame 的候选结构；不得以导航调用当前 Classic 根构造函数 |
| `gui_app.py:2492` `main` | 默认 attachment；`--legacy` 明确经典入口；monitor 退出后根据 legacy_requested 再启动一次 Classic mainloop | 当前不是双向页面路由。统一壳层应只切视图，不二次 mainloop、不重建执行所有者 |
| `execution_gui.py:376` `ExecutionView.legacy` | 设置 legacy_requested，销毁当前根窗口 | **已确认导航缺陷**：Classic 没有对应 return 标志/按钮，main 也没有回程分支 |
| `execution_gui.py:166–240` `ExecutionView.__init__` | New/选择 Project、连接材料、Start/Stop/Disconnect 和 Legacy 挤在同一行；三块纵向表/日志；混合中英文 | Projects 与 Service 分区；证据摘要提升为独立维度；无 Project 时只显示引导 |
| `execution_gui.py:56` `Reader._loop` | 后台线程；最新视图队列容量1，progress128/events64、分页32；选择版本/Project/owner 检查 | 复用读取与代际隔离；不把 HTML 原型变成新数据层 |
| `execution_gui.py:242/380/476` `_drain/_render/close` | Tk after80ms取队列；断线保留最后数据并标失效；关闭只结束 Reader、取消after；多次读取不是原子快照 | 页头保留连接/时效，证据带来源/时间；导航不可触发stop |
| `execution_gui.py:266/290` `new_project/attach_project` | 异步共享核心创建、明确目录；换 Project 清旧选择/缓存 | New/Open 向导包装相同核心，不建立另一种 Project |
| `product_project.py:43/83/94` `create/open/inspect_project` | 显式目录创建；产品manifest v1、store3；只读分类为产品/实验/Classic/未初始化/不可用 | 用户术语可统一，格式识别与拒绝码不改 |
| `service_discovery.py:56` `discover` | 显式实例、身份/协议/进程创建身份、原认证；无端口扫描 | Service卡显示已认证owner与失败原因，不以发现文件存在当已连接 |
| `service_lifecycle.py:59` `ServiceLifecycleManager` | inspect/start/connect/disconnect/stop；显式副作用、生命周期权限和精确停服条件 | 只重排管理动作；GUI缓存不能代替服务端准入 |
| `gui_app.py:342/715/745/869` | ttk.PanedWindow 横向 Queue/Results，纵向日志；Treeview、ScrolledText、Notebook 已可用 | 复用部件结构；保持左Queue右Results、STA/Console常驻和手动暂停跟随 |
| `gui_app.py:374–391` | `_table_split_fraction` 仅在内存；窗口初始92%×88%，上限1760×980，min1024×640 | 新设计建议用户级布局持久化，不能声称目前已经持久化 |
| `gui_app.py:252/2056/2273` | Classic初始en；切换en/zh；`_texts`内嵌字典，其他函数大量条件字符串 | 统一消息键；en默认、zh-CN规范化仅显示偏好层；法/德目前不存在 |
| `settings_store.py:12/23/29` | 当前为求解默认配置，`load_settings`会ensure_runtime_dirs；没有语言/布局键；显式runtime只读函数另有 | 不把新用户偏好写进工程Runtime；显示偏好模块未来独立、无Project初始化 |
| `gui_app.py:2022–2054` | AgentCommandConsole、旧API capability及旧自动化介绍；新服务能力不由这个窗口完整代表 | Agent Access同时标出Python服务与Classic MCP覆盖，不复用误导的全局“不能启动Solver”文案 |

## 当前视觉问题与证据

审阅保存的 [Run020实际截图](../run_020/windows_verified/product_gui.png)，未启动实际GUI。其大段身份、说明、按钮、原始字段表占据主层级；重要的Solver、验证、派发、范围收尾在长表中，缺少任务视角。当前呈现并未把 UNKNOWN 隐藏，但需要滚动才能理解各维度。

确认的问题：单向跳转；产品创建名称暴露架构术语；Service与Project操作混放；新视图汉英混杂；Classic只有两语言；空态缺少引导；多维证据缺乏可扫描层级。不是已确认执行安全缺陷，也不据此重写服务。

另外两条现有文案已经过时：ExecutionView初始service_status仍说“仅支持预配置 TEST_ONLY Project”；stop对话框仍说“空闲测试服务”。Run020/021B及当前产品接缝范围更宽。Run024只改准确显示语义，不据文案放宽后端能力。

## 历史材料的使用方式

- Run017产品矩阵/生命周期是当时快照，发现、创建、停服能力被Run018–021B增量扩展。不能把Run017“未实现”直接复制为当前现状。
- Run018：认证、32项分页、只读监控；Run019：显式生命周期；Run020：产品创建与DPAPI交接；Run021B：可信Grant与单Run派发、精确安全停服。
- Run021B [真实报告](../run_021b/real_001/FINAL_SUMMARY.md)保留PARTIAL与跨GUI Solver存活NOT_OBSERVED。Run022跨Run证据结论不改。设计中所有ID、时间、数值和资源采样是**合成示意数据**，不是新的实测。

## 最小可逆导航修复建议（本轮不实施）

若先修回程，只增加Classic的“Execution Monitor”动作和外层显式模式返回值；复用已有活动任务检查，先处理未保存界面操作，禁止调用Runner stop/Project恢复/服务启动。监控分支保持惰性加载。但该过渡仍是两次根窗口，不能作为最终统一窗口验收。

优选Run024直接做**单根壳层+视图适配**的小切片：把纯控件构建与Classic Runtime/Runner初始化拆开，未明确选Classic Project时只显示空态。不能简单在按钮回调里创建 `AbqJobPilotApp()`，也不能在换页时销毁仍由Classic控制器需要的状态。详细回归门槛见 IMPLEMENTATION_PLAN.md。
