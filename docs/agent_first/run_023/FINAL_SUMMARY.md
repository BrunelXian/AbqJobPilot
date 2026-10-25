# Run023 · GUI/UX 设计审阅基线

**PASS_ABQJOBPILOT_RUN023_GUI_UX_DESIGN_READY**

已完成现有Tkinter/ttk界面审查与统一主窗口的设计基线v1。**本状态只表示可以评审；实际GUI未修改，尚未进入Run024。**

## 先看设计

- [打开可浏览设计稿](design/index.html)：八个工作区与独立Service区域；顶部审阅工具可切空态、运行、完成、UNKNOWN、断线，以及English/中文/法语/德语。
- [Overview](design/screenshots/02-overview.png) · [Runs](design/screenshots/03-runs.png) · [Classic](design/screenshots/04-classic.png) · [首次空态](design/screenshots/01-empty.png)。
- [完整图稿与组件索引](LAYOUT_AND_COMPONENTS.md)，含New向导、Service、Agent Access、Settings与四语言布局。

设计保留左Queue右Results、常驻STA/Console、当前Project/Run及系统资源。将New/Open/Recent/Project Settings与Service动作分区。空项目给出下一步，不再默认显示三块空白表。Queue仅展示已接受任务，不增加普通用户的批准或Solver提交能力。

## 核心判断

当前单向导航由 `ExecutionView.legacy()` 销毁根窗口后，`gui_app.main()`再创建Classic根窗口造成；Classic无返回分支。Classic构造还会初始化旧存储，因此不能只给两个构造函数互相加按钮。拟采用**一个Tk根窗口、持续导航、隔离的数据适配器与显式Classic上下文**；最小可逆方案与分步实现已有记录，本轮没有改动它。

“Agent-first”保留为架构术语，用户创建入口使用New Project，唯一类型Abaqus。Classic Project和新执行存储继续按真实格式分别打开，不迁移、不合并状态。MCP在Agent Access中明确标注当前五个Classic只读/预览工具，不宣称与Python执行接口等价，不另建主窗口。

运行阶段、受管范围、Solver、DAT、ODB和域外UNKNOWN分别显示。PAUSED不等于当前Solver暂停；行政释放不等于完整退出；断线缓存有显著时效标记。原型全部使用合成数据，不是新的运行证据。

## 验证和保护

- 实际基线 `Develop@271c6f82fd6a4599dbae2df30d903dab2cef1f63`，版本0.3.0.dev0，无冲突。25项原跟踪修改及未跟踪成果保持；1462个既有非忽略文件摘要无变化。本轮新增仅在run_023。
- 10个设计文件测试通过；78个浏览器命名断言通过，包括四语言向导/按钮、导航、证据Tab、德语窄窗、Classic来源隔离。不是应用回归数量；未重跑历史664项。
- 四语言各110个设计消息键，参数集合一致。全产品翻译尚未实现，法德需母语审校；浏览器渲染不替代Tk高DPI和无障碍验收。
- 渲染初次缺工具包浏览器后改用本机已有Chrome，无安装；记录了视觉修正迭代，独立无头浏览器关闭，自己创建的临时profile清理完成。
- Abaqus调用 **0**。没有运行GUI/服务/Backend、修改Project、操作历史owner、访问Stable、修改共享依赖、Git切分支/清理/提交/推送。原Run022和Run021B真实报告及其限制保持。

## 交付与下一步

| 材料 | 内容 |
|---|---|
| [GUI_AUDIT](GUI_AUDIT.md) | 当前入口、源码函数、导航缺陷、语言/布局现状 |
| [NAVIGATION_AND_CONTRACT](NAVIGATION_AND_CONTRACT.md) | 导航图、页面职责、只读边界、Project命名与格式、关键流程 |
| [LOCALIZATION_SPEC](LOCALIZATION_SPEC.md) | 四语言资源、默认/回退、错误/参数、覆盖状态与审校门槛 |
| [LAYOUT_AND_COMPONENTS](LAYOUT_AND_COMPONENTS.md) | 设计图、尺寸/滚动/布局偏好、组件复用 |
| [IMPLEMENTATION_PLAN](IMPLEMENTATION_PLAN.md) | 风险、最小导航修复、Run024开发切片与回归门槛 |
| [REVIEW_AND_VALIDATION](REVIEW_AND_VALIDATION.md) | 实测结果、迭代、复现命令、验收矩阵及未验收项 |

建议设计确认后，Run024先实现单根壳层与安全双向导航，再适配现有读取视图、Project/Service分区和用户显示偏好。不得在该切片顺便增加Solver授权UI、MCP写工具、通用计划编辑或修改执行核心。

**本轮到此停止，等待设计确认。** 未自动进入实现、发布或新实验。
