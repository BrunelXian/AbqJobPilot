# 本次实机逐项验收

所有结果仅针对获批固定批次；无第三次调用、重跑或模型调整。

| 项目 | 结果 | 实际证据 |
|---|---|---|
| 批准body、引用材料、输入、零尝试状态 | PASS | PREFLIGHT.json：49+20匹配；2 Plan、0 Grant/Run；目录无冲突 |
| 可信两项授权、普通客户端提交 | PASS | AUTHORIZATION_SOURCE.md；POST_RUN_AUDIT.json精确许可白名单与2条consumption；原session回执 |
| 每项一次受管启动，无非受管回退 | PASS | 每项唯一START意图/CREATE_ENTERING/CREATED及cmd根OS身份；CREATE_PROCESS_JOB_LIST证明 |
| A正常收尾后才允许B | PASS | FINAL_EVENTS.json：36/37 A闭合及结果→38 B接受→43/44 B创建；无行政/管理处置 |
| 时间与资源约束 | PASS | 两项Plan匹配；A17:25:10、B17:25:31均在冻结deadline前；300秒均未触发 |
| 原Job范围结束，正常释放逻辑槽 | PASS | A/B各total12、active0、pending=false、limit_terminated=0；COMMITTED_EMPTY_SCOPE；最终slotNULL |
| Solver证据与DAT独立验证 | PASS | 两项DAT/STA/MSG完成证据组合；原验证记录三项主数值全PASS，哈希/文件身份复核相同 |
| A真实GUI及专属启动器全退出后继续 | PASS | AFTER_GUI_CLOSE.json：两GUI链进程retained handle exit0；owner与standard.exe仍活 |
| A GUI重连同Run和回执、无二次启动 | PASS | GUI_RECONNECTED.json、FINAL_EVENTS.json、原receipt复核；随后MSG字节增长 |
| B GUI展示 | PASS | gui_B_FINAL_VIEW.json、gui_B.png与公共Run一致 |
| B单独关闭/重连 | NOT_EXERCISED | 本批要求的关闭与重连已在A求解期间取得；不另作补充启动 |
| 全局成员集合、域外服务全集退出 | UNKNOWN / OUT_OF_SCOPE | 原member_completeness/overall_exit仍UNKNOWN；受管范围证明未扩展到整机 |
| ODB内容 | NOT_RUN | 未调用Abaqus Python/Viewer或读取ODB内容 |
| 历史保护与当前服务保留 | PASS | POST_RUN_AUDIT.json：517项保护摘要不变；REMAINING_STATE.json；未停owner/恢复旧派发 |

`audit_results.py`仅只读复核并向本目录新文件写报告；`observe_gui.py`仅作公共读取和本次GUI生命周期测量，不是另一个执行控制器。完整限制见FINAL_SUMMARY.md。
