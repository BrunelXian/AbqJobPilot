# Run024 / CR-D04 — 恢复显示交接（未实施 GUI）

仍为原生 Windows Tk/ttk 工作区；Run023 HTML 仅设计稿。顶部 `Scene` 左侧常驻 `Classic Queue`；Classic 提供 `Execution Workspace` 返回入口。导航不得重新启动服务/任务、初始化Project、批准或恢复派发。默认 English；en/zh-CN/fr-FR/de-DE 按实际覆盖声明，不将下列建议词条称作全产品翻译完成。

## 单一权威与分层显示

1. Runs 的徽标读取 CR-D02 `diagnosis.display_projection/message_key`，不要在 Tk 内重新猜测 PID/boot/崩溃。`UNKNOWN_INTERRUPTED` → `Interrupted (Unverified)`，不等于 Failed。
2. Details 同时展示原 execution/reconciliation、受管范围及 managed_completion、原进程退出、Solver、DAT/Artifact、ODB、PAUSED/槽和路径隔离。点击徽标打开同报告的 reason_evidence、JSON pointers、快照摘要和观察时间。
3. 当前 `preview_interrupted_recovery` 仅本地 Python 核心入口，无新 IPC。CR-D04 要先做能力协商与只读桥接；旧 owner 缺能力时明确不支持，不自动重启/接管，不让 GUI 偷读/写执行DB。
4. Preview 页显示“候选处置，需要独立授权”；`apply_allowed=false` 不因已有连接凭据改为true。服务在线时不通过新会话抢锁。
5. `RECOVERY_APPLIED` 显示“处置已记录”，与“执行已验证”分开。行政释放继续 UNKNOWN、PAUSED、旧路径保留；不能显示“计算成功”或“可重试”。原受管证据对账显示 `recovery_scope_completion`，不能冒充 `COMMITTED_EMPTY_SCOPE`，不能因此启用A→B、Stop、Resume。
6. 读取失败后保留缓存但标明过期；当前 verify NOT_CONFIRMED 与历史原回执同时可见。不能将读失败当作事务未执行，不能换key重做。
7. History保留原记录，Results只按原验证结论。OS后查和历史退出分组，PID不存在不能显示所有后代已退出。

## 恢复操作 UI 边界

本轮没有新增公开恢复 mint/Apply RPC。GUI 不得直接导入可信 `open_product_recovery(...).authorize(...)` 用点击或自报主体代替独立批准。若下一阶段需要交互式 Apply，必须单独审查可信操作者通道，绑定实际批准范围/版本/期限/风险，不把 Start/Stop 或 Solver token复用成恢复授权。

“结束观察”“证据对账”“行政释放逻辑槽”“恢复派发”“Retry”不得合成一个 Complete 按钮。后两项不属于本接口。所有动作应先显示其具体影响与未改变项。

## Classic P1 必修

Classic Queue 将异常中断误显示为 Failed，仍是 Run024 必修 P1。修复 presentation 的 Interrupted/UNKNOWN_INTERRUPTED 映射及过滤，同时保留真实 FAILED；不能写回旧DB、更改失败事实或用新Store模型解释Classic格式。新增测试应覆盖确实失败、结果未验证中断、旧记录无新字段和新旧来源切换。

## 建议消息资源（设计词条，尚无产品翻译实施）

| key | en | zh-CN | fr-FR | de-DE |
|---|---|---|---|---|
| interruption.unknown_interrupted | Interrupted (Unverified) | 异常中断（结果未验证） | Interrompu (non vérifié) | Unterbrochen (nicht verifiziert) |
| recovery.preview.title | Recovery assessment | 恢复处置评估 | Évaluation de récupération | Wiederherstellungsbewertung |
| recovery.status.applied | Disposition recorded | 处置已记录 | Décision enregistrée | Entscheidung protokolliert |
| recovery.status.not_confirmed | Current verification unavailable | 当前核验未确认 | Vérification actuelle indisponible | Aktuelle Prüfung nicht bestätigt |
| recovery.admin.residual | Residual uncertainty accepted | 已接受列明残余不确定性 | Incertitude résiduelle acceptée | Verbleibende Unsicherheit akzeptiert |
| recovery.requires_authority | Separate operator approval required | 需要单独操作者批准 | Approbation distincte requise | Gesonderte Freigabe erforderlich |
| recovery.blocked.active | A recorded process is active or cannot be checked | 记录进程仍活动或无法核查 | Processus actif ou impossible à vérifier | Prozess aktiv oder nicht überprüfbar |
| recovery.retention | Previous output remains isolated | 旧输出仍隔离保留 | Ancienne sortie toujours isolée | Frühere Ausgabe bleibt isoliert |

动态项使用 `{run_id}`、`{revision}`、`{reason_code}` 等命名参数，机器code/摘要/路径/原证据不翻译、不动态eval。法德长文允许换行与可滚动详情；按钮宽度按文本和DPI测试，不截去否定条件。语言偏好不写工程语义或授权。

最小 UI 验收：同一核心报告的多语言显示一致、0业务写RPC、旧owner兼容拒绝、迟到跨Project结果丢弃、缓存过期、原生双向导航、正常失败不被改标 Interrupted；没有实际恢复授权时Apply不可达。
