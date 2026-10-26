# Compact Engineering Cockpit

## 日常信息架构

```text
AbqJobPilot | Project ▼                  Agent Command | Classic/Execution | Language
Running / Queue / Dispatch / Supervisor                    CPU / RAM
CURRENT RUN: Job / Run ID                     Inspect / Evidence
Managed scope · Solver · DAT · ODB
┌ Queue + filter ─────────────┬ Results + filter ──────────┐
│ priorities, state, CPU…    │ Solver, DAT, ODB, elapsed │
├ STA / Text ────────────────┼ Console / Events ─────────┤
│ current Run source        │ current Run source       │
└───────────────────────────┴───────────────────────────┘
Source / freshness                                       status
```

高级功能是主控制台右侧 Agent Command 抽屉，不是九个顶级工作区。主界面一直可见；Esc 或 Close 返回，F2 切换。双击表格行 / Inspect 可展开证据。当前活动 Run 与“选中检查的历史行”分开：选历史行不能把活动任务标题或持续日志伪装成该历史任务。

未选择 Project 时隐藏无来源的表格和日志，显示紧凑 New Project / Open Project 引导。原型另有 Load sample Project；它只加载内存样例，不是产品功能。空状态不伪造 Project/服务身份或最后成功观察时间。

## Agent Command 五个子工作区

| 子区 | 内容与入口 | 权限/返回规则 |
|---|---|---|
| Project & Service | New/Open/Recent/Settings、Project身份/格式；Service身份、Start/Reconnect/Disconnect/Stop | Project与Service分组；普通打开不启动。复用既有生命周期前置条件 |
| Run Inspector & Evidence | 选中Run/Attempt/Receipt、原始状态、范围证据、Solver、DAT、ODB、事件、原始JSON | 只读；保留来源/版本/时间/缺失证据；失败与UNKNOWN不混淆 |
| Crash Recovery | Interrupted (Unverified)、诊断原因、只读Preview、KEEP_BLOCKED、PAUSED/槽位/隔离 | 本GUI不签发恢复许可。行政处置不等于验证完成；没有普通Apply/Retry/Resume按钮 |
| Agent Integration | Python/CLI/MCP能力、既有Classic命令说明及结果/详情概念 | Agent独立通过公共API工作；MCP不是执行核心。命令能力按数据格式分别绑定 |
| Settings & Diagnostics | 语言、密度/比例、诊断来源、脱敏导出设计 | 用户显示偏好；不更改状态机、Project格式和原始证据 |

抽屉是选中项的深入视图，不能变成默认整页导航。服务四按钮在原型为**禁用的视觉占位**，没有真实实现绑定。New/Open只演示抽屉位置；恢复和命令文本均不能执行。

## 视觉和尺寸

- ttk clam，Segoe UI 10，标题10–13，Consolas日志；没有大尺寸营销标题。
- 常用间距4/6/10px；表格100%行高25px。选中蓝、未知/未验证琥珀、明确失败红；颜色不替代文字。
- Queue/Results初始1:1，上表格/下日志约61:39；Agent抽屉初始约440px，用户可拖宽。
- 表格、日志左右两组独立分隔；外层抽屉也可拖动。最小原型客户区1100×680。
- 窄表格优先 Queue Job/State/CPU、Results Job/Solver/DAT；其他字段进入Inspector。长状态不缩成含糊Success/Failed，详情完整显示。原型的长德语行可截断，完整标题/详情保留；后续增加hover全文。
- 1600×900与1366×768为本轮Tk客户区尺寸，外框截图包含Windows非客户区边框，**不是证明1366×768物理屏在任意任务栏/DPI下都适配**。后续要按work-area钳制初始窗口并实测真实DPI。
- 底部两个日志不切换成同一个Tab；需能关闭Follow而不被刷新拉回。原型是固定文本，Follow仅视觉位置，未模拟持续流。

## 数据与状态

Execution：公共Reader → 持久Store投影。Classic：原Runner/Classic历史，明确标注来源。切换只切展示/缓存，不创建、提交、恢复、停止或迁移。

继续分开：原始执行阶段、受管范围、Solver、DAT、ODB、域外UNKNOWN。Interrupted是诊断投影，不覆盖真实FAILED。当前诊断/Preview最终以CR-D02/03公共接口为准，本原型只用模拟字符串展示位置。

本轮原型不导入产品客户端，不连接服务；两模式各有模拟选择缓存与不同身份前缀。Classic日志不冒用Execution的回执或范围事件。

## 多语言

English默认；现有产品149键资源保持不动。原型`EXTRA`为局部显示文案集合，四语言具有一致的键；FR/DE明确Preview。中文主控件已译，技术详情仍有English示例；法德未完成母语审校，也未承诺所有详情翻译完成。

后续将确认的文案纳入现有`ui_resources.translate`，不要另建翻译框架。状态代码、Plan/Run/Receipt、证据JSON保持原值，展示消息可参数替换。新建议key：`cockpit.currentRun`、`cockpit.source`、`cockpit.stale`、`agentWorkspace.*`、`scope.summary`；复用已有中断/恢复key，不新增持久状态。
