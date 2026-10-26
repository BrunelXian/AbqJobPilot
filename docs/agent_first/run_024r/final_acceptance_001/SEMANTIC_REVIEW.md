# Compact Cockpit 局部语义验收

日期：2026-10-26。本次继承用户已冻结的 Compact Engineering Cockpit 布局，不重做主窗口。

## 1. Results 的含义与最小修正

当前产品契约中 Results 是当前客户端命名空间内的 Run 证据概览，并非仅包含完成任务的结果文件列表。它与 Queue 复用同一有界 Project Run 查询，每页最多 32 条；筛选、排序只作用于本页。原布局没有显示 execution 列，START_INTENT / Solver NOT_RUN 因而容易被误解为已完成结果。

本次增加 Results 的 **Stage** 列，直接显示服务返回的原始 execution。保留未决、UNKNOWN 和正在启动的记录，便于人工关注；不按 Solver NOT_RUN 隐藏任务，不把文件存在当作结果已验证。结果与 Queue 使用完整 Run ID 作为内部行身份，显示短 ID 但完整 ID 仍可筛选，并在 Agent Command → Run Inspector 的 Identity 中查看。

实现：`abqjobpilot/cockpit_layout.py:55`、`desktop_workspace.py:134`。测试：`tests/test_cockpit_semantics.py`、`tests/test_cockpit_windows.py`。

## 2. START_INTENT 与 PROCESS_EXIT_OBSERVED 不矛盾

源码：`execution/process_backend.py:155–192` 对某个已记录成员取得退出码时，写入 PROCESS_EXIT_OBSERVED、EXIT_PARTIAL、exit_verification=PARTIAL，**不修改 execution**。尚有 worker 或受管后代时继续观察；后续完整受管范围为空且启动状态明确，才进入 PROCESS_COMPLETED / VALIDATING 和独立验证。GUI 没有权利将单条退出事件解释为完成。

此前截图来自固定 Python `result_wait` 场景：启动器先退出，worker 写入结果后等待测试释放。此次重新从实际隔离服务取得同样状态：Run `r_3c2471c21ed146bd9d6f18525a524aca`，execution=START_INTENT，exit_verification=PARTIAL，受管范围 active_processes=3，Solver=NOT_RUN，且日志仍有 WAITING。证据见 [SELECTION_EVIDENCE](evidence/SELECTION_EVIDENCE.json) 的 `partial_run_at_observation` 和 `active`。

因此没有查到需要修改 ExecutionService 的真实状态冲突。顶部新增“Recorded exits: N (not scope completion)”，并继续分别显示受管范围、Solver、DAT、Artifact。N 是服务的已持久化退出记录数量，不是全机进程数，也不是完整成员证明。

Reader 的 Run、events、progress 为连续的有界只读请求，不是跨请求原子快照；事件可能暂时比顶部快一轮。Identity 现在明确保留 GUI 完整观察时间、Run revision 和此一致性限制。界面继续标注 Recorded snapshot / not Solver liveness；失联保留缓存并标记最后成功读取时间。没有用事件反向修改 Run 状态。

## 3. 日志来源与显示

| 实际读取来源 | 新显示名称 | 证据边界 |
|---|---|---|
| `fixed_worker_self_report_not_exit_or_validation` | Worker Log · self-report | 固定 Python progress.jsonl 自报，非 STA、非 OS 退出证明 |
| `bounded_standard_text_latest` | STA / MSG / LOG · summaries | 既有 Standard 接口的有界摘要、字节数及已识别标记，不是完整文件、不是控制台 stdout |
| 未知或缺失 source | Progress · source unavailable | 不根据 Backend 名称或文件名猜测来源 |
| 公共 client.events 返回 | Events · execution service | 持久化服务事件，不伪称 Console stdout/stderr |

依据：`execution/progress_log.py`、`execution/standard_backend.py:201–222`。Reader 只透传既有响应 `source`，不增加文件读取或执行接口。原 JSON 内容、原始字段和事件顺序保留；没有清洗、替换或删去证据。

Classic 原有 STA/Console 保持原路径与语义。双日志常驻、Follow latest、横向滚动和可拖动分隔条保留。

## 4. 可读性与修改边界

- Run 显示为前 12 字符 + … + 后 8 字符；完整 ID 保存在内部身份与 Inspector。Run 列最小宽度 170，语言切换后仍保留。
- 刷新时间只在显示层去掉小数秒，保留日期及 UTC offset；原始时间不变。
- Results Stage、日志来源及退出记录说明有 en / zh-CN / fr-FR / de-DE 文本；法德仍为 Preview。
- 修改既有文件：`cockpit_layout.py`、`desktop_workspace.py`、`execution_gui.py`、四份 locales JSON、`tests/test_cockpit_windows.py`。
- 新增纯显示格式器 `cockpit_display.py`、针对性测试 `tests/test_cockpit_semantics.py`，以及本目录证据/报告工具。
- ExecutionService、Supervisor、Backend、授权、派发、恢复 Apply、数据格式和历史报告均未修改。见 [PRESERVATION.json](PRESERVATION.json)。

1600×900、1366×768、Agent Command 展开和实际 Run 联动截图见 [SCREENSHOT_MANIFEST.json](SCREENSHOT_MANIFEST.json)。1366×768 下短 ID 已完整显示；长原始文本可在 Inspector 与横向滚动查看。此次未改变系统 DPI，不扩展之前的 DPI 验收范围。
