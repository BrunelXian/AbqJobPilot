# 原生视觉对照与评审证据

两组对照都来自实际Windows Tk窗口。A：当前Run024控件；B：推荐的独立Compact Cockpit原型。拼图仅将捕获PNG缩小一半并排，不用HTML重绘界面。请打开原尺寸图检查文字。

## 对照一：1600×900客户区

![A Run024 Overview / B Compact Cockpit](screenshots/COMPARE_1600.png)

[A原图](screenshots/A_overview_1600.png) · [B原图](screenshots/B_live_1600_final.png)

B默认隐藏高级抽屉；当前Run摘要、12条Queue、12条Results及两路日志同屏。A是当前Overview的实际设计，不是将列表故意删除；其完整Run表位于另一页。

## 对照二：1366×768客户区

![A Run024 Runs / B Compact Cockpit](screenshots/COMPARE_1366.png)

[A原图](screenshots/A_runs_1366.png) · [B原图](screenshots/B_live_1366.png)

B通过垂直滚动查看剩余行；日志保持可见。A展示当前Runs列表、证据Tab和日志。两者使用不同但明确标记的模拟集合，比较信息架构，不是同一数据库的语义或性能基准。

## 原型场景索引

| 场景 | 原生截图 | 检查目的 |
|---|---|---|
| 默认1600 | [live](screenshots/B_live_1600_final.png) | 完整同屏密度 |
| 默认1366 | [live](screenshots/B_live_1366.png) | 常用小尺寸滚动与布局 |
| 未选Project | [empty](screenshots/B_empty_1366.png) | 不展示空白大表格，没有伪造服务时间 |
| Classic模式 | [classic](screenshots/B_classic_1366.png) | 同布局、不同数据来源/身份/证据语义 |
| Agent Command | [Project & Service](screenshots/B_command_1600.png) | 服务按钮移入高级区，原型禁用 |
| Inspector | [evidence](screenshots/B_evidence_1366.png) | 按需展开详情、主日志仍可见 |
| Recovery | [recovery](screenshots/B_recovery_1366.png) | Interrupted与Failed区别，无Apply |
| Agent Integration | [integration](screenshots/B_integration_1600.png) | 程序化接口独立工作，不执行样例代码 |
| 中文125% | [zh](screenshots/B_zh_125.png) | 主控件翻译与放大 |
| 法语125% | [fr Preview](screenshots/B_fr_125.png) | 长文字、Preview标识 |
| 德语150% | [de Preview](screenshots/B_de_150.png) | 工具栏可达、优先列 |
| 德语150%+抽屉 | [recovery](screenshots/B_de_150_recovery.png) | 最窄可读区、滚动详情、Close可达 |
| 连接中断 | [disconnected](screenshots/B_disconnected_1366.png) | STALE/DISCONNECTED、保留最后样例观察 |

## 实际检查与限制

13个唯一原型场景全部正常返回，FAIL/SKIP=0。`PROTOTYPE_CHECKS.json`列出命令参数和返回码，每张截图对应JSON记录几何、语言、模式、缩放和模块加载断言。9个场景另执行模式往返、选择保留、5子区/4语言切换；其余4个只捕获指定视图并核查边界。

程序断言检查Agent/模式/语言按钮及抽屉Close不超出客户区。人工检查对照图、主视图、Classic、空状态和德语抽屉。**这不是所有文字无截断、可访问性或生产GUI功能验收。**

初版150%德语抽屉暴露六列过窄、返回长按钮被挤压的问题。已改成紧凑Close、优先列和日志水平滚动。改前截图`B_de_150_drawer.png`、`B_de_150_drawer_v2.png`保留为迭代，不作为最终稿。后续原型审查还修正Classic日志串用Execution样例标识、空状态显示模拟观察时间的问题，最终13场景再次运行通过。

125/150%为该进程`tk scaling`及原型行高调整，不是修改Windows系统DPI，也未完成真实跨屏Per-Monitor DPI验证。标题栏仍由本机Windows绘制。长德语行在窄列可截断，详情区完整可滚动；未来应补键盘访问/tooltip，不能声称本轮完全解决所有DPI问题。

四语言局部词典各58键且一致；高级技术详情仍有英文。法德Preview待母语审校。现有产品翻译未改动。

## 副作用与保护

- 原型只用标准库Tk/ttk和模拟数据，未导入产品execution模块；六类执行/网络/DB audit事件直接拒绝，负向检查仅调用guard本身，不尝试启动Solver。
- A参考捕获没有Reader；audit阻止IPC/DB/进程；用户偏好隔离在本目录。没有启动正常服务或打开真实Project。
- 截图仅用本轮窗口HWND，沿用`tests/run012_capture.py`的Win32绘制捕获方式，并在`finally`释放GDI资源；未捕获用户其他窗口。
- 所有捕获程序正常destroy窗口并返回0；没有后台观察者、worker、Supervisor或私有凭据。`_isolated`仅保留本轮显示偏好，无需删除历史任何东西。
- [FINAL_CHECKS](FINAL_CHECKS.json)：1741个基线文件SHA-256保持，目录外新增0，Develop/HEAD/版本未变，无冲突。
- 不重跑历史764项核心测试：本轮未改生产代码/状态机。原型检查不能替代下一阶段实际GUI连接与生命周期回归。
