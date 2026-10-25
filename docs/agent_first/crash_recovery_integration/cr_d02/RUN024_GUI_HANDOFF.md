# Run024 — 中断诊断显示接入要求

本文件是接口交接，不是已实现GUI。Run023 HTML仍只是设计稿；Run024必须使用当前原生Windows Tk GUI实现，不能把HTML作为产品运行界面。

## 必修导航与P1

- 新版顶部栏在 **Scene左侧**设置常驻 **Classic Queue** 快捷按钮；不限于侧栏或兼容性设置页。
- Classic Queue提供对应 **Execution Workspace** 返回入口。单Tk根/主循环，切换不重启Supervisor、不初始化Project、不改变派发或执行状态。
- **必修P1**：`abqjobpilot/gui_presentation.py:23` 当前把 `raw == UNKNOWN_INTERRUPTED` 与真正 `canonical == FAILED` 合并显示Failed。Run024须先单独处理该raw值，显示Interrupted (Unverified)，保留原持久raw和canonical UNKNOWN；真正FAILED仍显示Failed。补标签、颜色、过滤/搜索与历史兼容断言，不能只测试“不是success”。

## Agent-first读取适配

D02提供内部/离线Python入口，尚无新的IPC operation。CR-D04与Run024应协调一个只读协议扩展：能力协商成功后调用统一服务端分类器，不在Reader/Tk/CLI/MCP复制规则。旧owner没有能力时显示诊断不可用，不替换、重启或接管owner。若使用离线入口，必须标明离线读取，不能伪称认证连接成功。

Run列表只展示当前选定Run的有界诊断投影；大量Runs先分页，按需查询，避免为每行做OS查询。默认仅历史快照。当前OS观察是明确操作，放在后台工作线程，2秒只是合作查询预算；不阻塞Tk。Project切换的generation检查丢弃旧回包；断线保留缓存但标STALE与最后成功时间。

Run Details同时显示：原execution/phase、诊断投影、reason_codes和reason_evidence pointers、Project/Run/Attempt、历史owner、当前观察来源/时间、范围proof、原Solver/DAT/Artifact/ODB、PAUSED/slot、路径隔离与行政处置。点击Interrupted徽标打开这些依据，不只换颜色。`known_member_active=false`不表示全部退出；查询不可用、未观察、域外未知须可见。

`COMPLETION_RECORDED`是历史范围/完成记录；不替代Solver与验证。Results没有验证则显示未验证；不能因诊断Interrupted改写为Failed。已有行政释放单列“逻辑槽已行政释放；不确定性保留”，不能隐藏UNKNOWN。Legacy Queue与新Store保持独立格式/证据来源，不迁移、不双写。

## 四语言资源（拟议显示文本，尚未集成或完成母语审校）

机器字段和reason code不翻译；资源键覆盖以下显示。新用户默认en，与Run023统一资源机制。

| key | en | zh-CN | fr-FR（待审） | de-DE（待审） |
|---|---|---|---|---|
| interruption.unknown_interrupted | Interrupted (Unverified) | 异常中断（结果未验证） | Interrompu (non vérifié) | Unterbrochen (nicht verifiziert) |
| interruption.execution_state_unknown | Execution state unknown | 执行状态未知 | État d’exécution inconnu | Ausführungszustand unbekannt |
| interruption.execution_activity_observed | Recorded process still active | 已记录进程仍活动 | Processus enregistré toujours actif | Erfasster Prozess noch aktiv |
| interruption.completion_recorded | Completion evidence recorded | 已记录完成证据 | Preuve de fin enregistrée | Abschlussnachweis gespeichert |
| interruption.administrative_disposition_recorded | Administrative decision recorded | 已记录行政处置 | Décision administrative enregistrée | Administrative Entscheidung gespeichert |
| interruption.never_started_recorded | No recorded start | 未记录启动 | Aucun démarrage enregistré | Kein Start dokumentiert |
| interruption.evidence_conflict | Inconsistent evidence | 证据不一致 | Preuves incohérentes | Widersprüchliche Nachweise |
| interruption.observed_at | Observed at {time} | 观察时间：{time} | Observé à {time} | Beobachtet um {time} |
| interruption.preview_only | Review only; no recovery permission | 仅供预览；没有恢复权限 | Examen seul ; aucune autorisation de reprise | Nur Prüfung; keine Wiederherstellungsberechtigung |
| interruption.stale | Cached evidence · last read {time} | 缓存证据 · 上次读取 {time} | Preuves en cache · dernière lecture {time} | Zwischengespeicherte Nachweise · zuletzt gelesen {time} |
| interruption.reason_fallback | Evidence reason: {code} | 证据原因：{code} | Motif : {code} | Nachweisgrund: {code} |

reason资源可按 `interruption.reason.<lowercase_reason_code>` 增量加入，未知键使用有界、转义后的code fallback，禁止显示异常原载荷。参数键须四语言一致；时间格式只影响展示。英文/中文为已确定术语，法德为设计建议，不能显示“全产品翻译完成”。德语需可换行详情、可调整列宽及滚动；按钮不硬截断。

## 恢复界面权限边界

`recovery_preview.may_request_readonly_review`仅允许请求评估，不是Apply按钮的启用条件。D02永远 `apply_allowed=false`。CR-D03未来受控管理入口必须重新取同一owner排他锁、重评估、精确批准和事务提交；GUI不得把旧报告摘要或OS观察当批准。D02/Run024不提供Requeue、Retry、Restart、force close、恢复PAUSED或Kill。

验收：导航零业务写/零服务启动；GUI与Python相同reason/摘要；缺能力/断线/跨Project不串数据；实际Failed与Interrupted区分；四语言占位符和德语布局；原生Windows完整退出/重连；保留旧Grant、状态、隔离和History。
