# 实施风险与 Run024 开发任务

本轮没有修改任何应用实现。以下为设计确认后的受限计划，不自动执行。

## 建议冻结的决策

1. 一套Tk/ttk主壳、一个Tk根与mainloop、持续左导航；不引入Web/Qt，不嵌入本HTML。
2. 统一用户Project命名；保留两种格式/控制器的真实区别；Abaqus是唯一向导类型，不新写schema字段。
3. 产品Queue、Runs、Results是公共读取投影。普通GUI不新增Solver提交、批准、Resume、Retry、对账apply或MCP写权限。
4. Service低频区复用既有管理器；显示偏好与工程配置分离。
5. 新用户English，四语言资源架构和显式翻译覆盖；不修改证据/API原码。

## Run024 最小指令草案

**目标**：在已确认的Run023设计基础上，以正常 `Open_Dev_GUI.vbs` 入口实现统一Tk主壳、双向导航与Project/Service分区。先完成安全壳层，不把整套求解功能重做一遍。

**先读**：AGENTS、环境登记、Run022范围限制、Run023全部契约与实际源码；核验Develop/HEAD/冲突，保存已有修改。只在Dev，真实Abaqus预算0；不操作历史owner/Project，不改变执行核心、Backend、授权/派发/Schema、不提交推送。

**实施顺序与可独立回滚单元**：

| 单元 | 最小改动 | 进入下一步的条件 |
|---|---|---|
| 1. 纯壳与路由 | 从root抽出导航/上下文/工作区容器；用空Frame占位；Classic与monitor能双向切换 | 每次导航业务RPC写入计数0、进程创建0、默认Runtime初始化0，只有一个Tk根/mainloop |
| 2. 读取视图适配 | 将ExecutionView的Reader与Frame展示解耦；Overview/Queue/Runs/Results复用单一会话，分页与日志原边界不变 | 慢IPC不卡UI；跨Project迟到回包被丢弃；缓存时效不丢；不复制状态机 |
| 3. Classic适配 | 纯布局与Runtime/Runner创建分离；必须显式选择Classic Project；保留旧Queue左Results右、原动作及准入 | 进入空Classic不导入/初始化旧Runtime；活动任务切页不销毁其控制器；新旧日志与身份不串 |
| 4. Projects与Service | 同一产品核心New/Open/分类向导，Service中显式管理；Recent仅用户显示索引 | 空Project0Grant/0Run/PAUSED、创建不启动；Stop复用原owner/操作键，确认不增加权限 |
| 5. 消息与偏好 | 提取壳层/监控/向导字符串，默认en；四资源目录与覆盖清单；用户级locale/几何 | 语言切换不调用业务接口；无Runtime默认写；法德若未完成显示Preview，不能标全产品完成 |
| 6. 视觉与收尾 | 证据摘要、dock/分隔比例、键盘/缩放；旧样式部件逐个迁入 | 设计审阅差异表+实际Tk截图，不以HTML截图冒充完成 |

如果Classic安全拆分超出可评审范围，先交付统一壳空Classic入口与明确阻断，不直接实例化旧根窗口冒充完成；不得标双向功能全部验收。本轮设计并不授权绕过现有活动任务限制。

## 主要风险与失败处理

| 风险 | 具体依据 | 控制 |
|---|---|---|
| 导航触发默认Runtime | Classic构造中的init_storage/QueueRunner/ProjectManager | 控件构建惰性且无业务初始化；显式格式上下文才能启用旧操作 |
| 多窗口/线程泄漏 | 当前destroy+第二mainloop；每次Reconnect创建Reader | 单根；会话有订阅者计数/有界关闭；换页不重连；Tk任务/线程清理测试 |
| 翻译导致状态错误 | 当前很多按self.lang分支及raw字符串 | 所有逻辑仍按API原码，IID不翻译，显示独立 |
| 来源混淆 | 新旧都有Queue、Results、Console命名 | 上下文条/每个日志来源/不同模型类型；禁止跨历史库双写 |
| 过期/跨Project数据泄漏 | Reader多次读、迟到生命周期结果 | 复用generation；失联顶条+时间；不把缓存当实时 |
| 停服按钮误用 | 活跃/UNKNOWN/保留路径不能由UI推定空闲 | 仅Service，显式确认，同owner原事务拒绝；不加Force |
| 语言/布局污染工程 | settings_store.load_settings有默认Runtime写 | 新用户级显示偏好，显式测试路径，无工程语义字段 |
| 未实现能力被视觉承诺 | 通用计划编辑、GUI批准、MCP写未实现 | 不显示可用执行动作；文案准确；后续能力另轮评审 |
| 隐藏资源竞争 | Classic与服务无跨引擎全局租约 | 明确不同时针对同一输出路径操作；不在本轮新增并行执行快捷键 |

## 必要回归与验收条件

先检查测试副作用，用新临时Project/Runtime/Recent和固定Python夹具，真实Abaqus创建失败哨兵。不得动历史实例。

- 静态依赖/无副作用：导入壳、空导航、语言切换、窗口打开关闭不创建Project/Grant/Run/进程，不写执行DB；core摘要不变。
- UI：所有导航互达；Classic→Runs→Classic不丢选中项、布局或任务；每种格式明确显示；无服务/无Project/空列表不空白三表。
- 公共读取：`test_attachment_gui.py`（明确Project、分页、断线/重连）、`test_execution_gui.py`（活worker跨GUI关闭、慢IPC、owner异常）作为实际回归来源。
- Legacy：`test_gui_table_state.py`、`test_project_gui.py`、`test_g2_5_project_multiselect.py`；原排序、多选、日志与活动任务限制保持。不要直接全量运行可能访问默认Runtime的旧测试，先隔离审查。
- 生命周期/身份：`test_service_lifecycle.py`、`test_product_project.py`、`test_lifecycle_boundaries.py`、Project view与credential边界相关用例；不放宽旧owner兼容拒绝。
- 状态语义：范围结束≠Solver完成≠DAT通过≠ODB验证；PAUSED不代表已运行Solver暂停；UNKNOWN/行政释放保留原码和路径隔离；GUI动作不能Resume。
- 四语言：缺键/参数负测，错误码映射不泄密；长德语按钮/表列/对话框100/125/150%缩放；滚动、焦点、键盘路径；母语审校另标。
- Windows闭环：新固定Python任务执行中完整关闭正常GUI及专属启动器；原owner/worker身份保持、日志增长；重开同Project/Run/回执，启动次数不增。HTML测试不替代此项。

完成后提交实际源码差异、屏幕证据、唯一测试计数与失败迭代；未完成页面/翻译必须明示。停止，不真实求解、不升级版本、不发布、不开下一轮。

## Run023本身不扩大的工作

Run022的通用部署、缺Tk诊断、Git提交筛选、真实实验NOT_OBSERVED、域外UNKNOWN/ODB NOT_RUN仍各自保留。UI设计不是发布门槛已消失的证明。本轮没有发现需要为了视觉设计修改执行核心的新理由。
