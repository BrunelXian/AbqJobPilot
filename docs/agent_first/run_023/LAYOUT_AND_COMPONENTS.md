# 布局、组件与可视化设计索引

## 审阅入口

直接用浏览器打开 [design/index.html](design/index.html)。文件内嵌CSS、脚本、四语言消息，无网络字体、CDN或运行依赖；顶部深色条是**审阅工具栏，不属于产品UI**。Scene切换合成状态，Language切换设计语言，侧栏双向导航，Runs证据Tab、New向导和分隔条可交互。服务按钮仅演示提示，不能发出IPC、命令或创建Project。

合成数据名称/值用于设计；不是历史Run的证据。默认English。Create只把原型切到空Project场景；未实现目录浏览器、真实分页、多Run数据加载和持久偏好。浏览器原型不将作为产品运行时嵌入Tk。

| 设计组 | 快速看图 | 内容 |
|---|---|---|
| 首次空状态 | [01-empty](design/screenshots/01-empty.png) | New/Open、Recent空态、Project与工程输入区别；日志折叠，无三块空表 |
| 已连接Overview | [02-overview](design/screenshots/02-overview.png) | 当前Run/派发/槽位，Queue左Results右，持久日志与资源 |
| Runs | [03-runs](design/screenshots/03-runs.png) | 左任务列表、右多维证据、Identity/receipt、Events |
| Classic统一导航 | [04-classic](design/screenshots/04-classic.png) | 相同壳层，Classic来源明确；不混入新Store的DAT验证或事件 |
| New向导 | [English](design/screenshots/wizard-en.png) | 两步，目录/名称/Abaqus唯一类型、Review的无授权初始状态 |
| Service | [05-service](design/screenshots/05-service.png) | 身份/连接/显式生命周期，空闲准入与失败提示 |
| Agent Access | [06-agent](design/screenshots/06-agent.png) | Python服务与MCP Classic范围分开，无秘密/Grant生成 |
| Settings | [07-settings](design/screenshots/07-settings.png) | 用户显示语言、翻译状态、布局重置 |
| 断线/未知/完成 | [08](design/screenshots/08-disconnected.png)、[09](design/screenshots/09-unknown.png)、[11](design/screenshots/11-completed.png) | 缓存时效、槽保留与UNKNOWN、分维度完成 |
| 空Project | [10-empty-project](design/screenshots/10-empty-project.png) | 明确下一步Service/Agent，无自动启动 |
| 中/法/德布局 | [中文](design/screenshots/locale-zh-CN.png)、[Français](design/screenshots/locale-fr-FR.png)、[Deutsch](design/screenshots/locale-de-DE.png) | 相同Overview结构；非英语原始工程/日志内容不翻译 |
| 长文本/对话框 | [德语1100宽](design/screenshots/german-1100.png)、[法语向导](design/screenshots/wizard-fr-FR.png)、[德语向导](design/screenshots/wizard-de-DE.png) | 按钮换行、双列证据、内容独立滚动 |

## 尺寸与交互基线

所有尺寸为设计逻辑px，实际Tk按字体测量和Windows缩放适配，不能直接当物理像素硬编码。

| 部位 | 建议值/行为 |
|---|---|
| 默认窗口 | 1440×900工作区附近；不超过可用屏幕92%×90%；起始min1100×720，低于此范围允许内容滚动，不隐藏退出/Service诊断 |
| 顶栏/上下文 | 标题38、Project条66；名称两行，身份短摘要+详情可复制；不横向塞所有管理按钮 |
| 主导航 | 默认206宽，窄窗185，德语Classic允许两行；未来可调到240；不采用无文字仅图标作为默认 |
| 边距/间距 | 主内容22/24，组内12/16，紧凑4/8；1px边界、圆角4–5，避免夸张阴影/大营销卡片 |
| 字体 | Segoe UI 10pt正文、11–12pt组标题、18pt页标题；中文系统回退；原始ID/日志Consolas 9–10pt。原型用CSS近似，不声称Tk字号完全等价 |
| Queue/Results | 默认52:48，拖动35–65%；列内容最小宽度，不足出现表内横向滚动；保留用户选择及排序语义 |
| Runs | 列表260宽，可调220–360；详情至少500；六维摘要宽窗3列、窄窗2列；表格内横/纵滚动 |
| 日志 | 默认约184高，建议100–45%可调；STA/Text与Console/Events并排；无Run时折叠为提示行；切页不丢缓冲 |
| 对话框 | New宽650上下滚动，按钮最小88×34且按文本自然增长；错误不使用固定一行；显示目录可换行/完整复制 |
| 状态栏 | 30高，连接最后时间/owner/派发可见；独立本机CPU/RAM采样，GPU未知显示—；窄窗优先保留连接时效 |

表格主键用稳定Run/Job ID，不能按可翻译标题或行号定位。双击与Enter打开同一条详情；排序不得更改派发顺序。分页保留32项限制，日志保留现有有界读取。大段原始JSON放Details而非第一页主区域。

## 复用清单及所需适配

| 当前组件 | 可复用内容 | Run024所需局部适配 |
|---|---|---|
| `AbqJobPilotApp._configure_styles` | Segoe UI、ttk/clam、Treeview状态tag、边框 | 用设计token集中颜色/尺寸，不另换Qt/Web/Electron |
| `ttk.PanedWindow` / `_remember_table_split` | 横向与纵向可调分隔 | 从内存比例转用户偏好；恢复时clamp屏幕范围，绝不加载Runtime求解配置 |
| `_build_queue_area/_build_results_area` | 表格、选择恢复、滚动、搜索 | 提取纯Frame与显式数据适配器；旧动作留Classic，不复制成新服务写入口 |
| `_build_live_logs/_set_text` | 只读Text、原始行、Follow暂停 | 共用dock，来源随上下文切换；不能在Classic页显示服务事件却标Classic |
| `ExecutionView.Reader` | 公共读取、分页、代际检查、有界队列 | 与控件生命周期解耦；同Project换页不反复新建Reader；最后订阅结束才关GUI读取 |
| `_drain/_render` | Tk线程更新、断线标记、observer测试遥测 | 变成纯投影到新组件；保留未知/来源/时间，测试遥测仍来自实际控件 |
| `product_project` / discovery | 创建、只读分类、身份核验 | New/Open向导和分类错误UI，不改数据格式 |
| `ServiceLifecycleManager` | 已实现显式Start/Stop及权限 | Service页异步调用、保留原幂等操作键与同owner检查，不另造管理流程 |
| `ttk.Notebook` /现有详情窗 | 身份、文件引用、历史页结构 | 用于Runs内tabs或可选详情窗；一个主根窗口，不产生MCP专属主窗口 |

## 用户级持久化建议（尚未实现）

新 `ui_preferences` 设计仅含版本、locale、窗口几何、导航宽度、分隔比例、列宽/排序及明确选择的Recent引用。拟存用户级配置目录，由显式路径提供给测试；不复用 `settings_store.load_settings()` 的默认Runtime初始化。不得保存连接秘密、Grant、被复制owner端点或可自动执行的命令。

启动恢复只恢复显示。Recent可以列出，但不自动选Project或连接；选Project需用户明确动作。Classic会话和产品会话的UI缓存分键，语言切换不重开Project、不触发RPC。保存失败只提示显示偏好未保存，不影响Run；损坏偏好回退English与安全几何，不修工程库。

## 可访问性与缩放

Tab顺序：导航→Project上下文→当前页→日志；键盘焦点可见。Alt+1至Alt+8映射八个工作区的建议（原型只演示Alt+1/4）；菜单助记符按语言检验，避免Ctrl+S同时保存/停服。Service stop不可用时用邻近文字说明原因，服务端仍复核。

色觉要求文字/原始码并存；长ID支持复制，不只tooltip。对话框Escape取消、焦点圈/恢复调用点、屏幕阅读器标签在Tk实现时实测。原型没有完整Windows无障碍树或Tk的125%/150% DPI实测，不能凭浏览器截图声称已验收。Run024必须验证100/125/150%缩放、德语换行、用户字体增大、键盘导航和最小尺寸。
