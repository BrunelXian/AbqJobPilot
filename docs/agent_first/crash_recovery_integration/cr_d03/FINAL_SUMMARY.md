# CR-D03 — Authorised Recovery

**PASS_ABQJOBPILOT_CR_D03_AUTHORISED_RECOVERY_READY**

已实现执行核心的统一只读恢复预览、可信本地精确登记、原 owner.lock 排他管理、原事务中的幂等 Apply，以及提交后独立核验。**仅对本轮隔离实例执行。Abaqus调用0；历史/生产恢复Apply0。**

## 实际能力

- `preview_interrupted_recovery` 复用CR-D02诊断及原证据，保持只读；KEEP_BLOCKED、可考虑的证据对账和行政处置明确分开。
- Run007四角色退出对账、Run014行政释放直接委托原实现；没有第二套恢复数据库、Runner或调度器。
- 新增原受管Job空查询已经持久化、终态提交缺失的窄对账策略。创建结果、Plan/Run/Attempt/owner/scope、历史事件和当前身份均检查；不重开Job、不推定域外全集退出。
- 产品本地管理桥取得原owner同一排他锁，再持久PAUSED、锁内预览/许可/Apply；活owner/worker、身份查询失败、旧revision、过期或错scope均阻断。
- 精确许可绑定动作、版本、摘要、主体/来源/理由、一次使用、幂等身份及残余风险。复用Run014可信同用户本地Python边界；**没有新增普通IPC/GUI/CLI/MCP批准权限，也不声称实现人类审批或同OS用户恶意代码隔离。**
- 原 UNKNOWN、Solver/数值、执行Grant消费、历史事件、旧输出和其他队列保留。范围对账不补写自动完成标记，不恢复派发/Stop，不创建Run/Attempt/Retry。`RECOVERY_APPLIED` 与执行验证分开。

当前进程查询也收紧了：权限/身份读取失败返回QUERY_FAILED，只有明确的PID不存在来源才PROCESS_UNAVAILABLE；两者均不提供历史完整退出证据。真实Windows测试证实已退出对象仍被独立观察句柄保留时可能无法重新读映像，Apply保守拒绝；不能强行把这一观察改成可恢复。

## 验收

**548个唯一用例，全部PASS，0最终FAIL/ERROR/SKIP**。其中新入口39项、新Windows4项；其余为CR-D02、R7/R14–16、原管理/所有权/Store、R18–21B产品/凭据/生命周期和隔离回归。计数按最终XML去重，不冒用历史数字。

真实Windows固定Python验证：原Job空证据后owner崩溃并显式对账、活worker拒绝释放、原R7对账、原R14行政处置；第二项PENDING保持、物理启动不重复、跨管理owner查原回执。产品桥的Standard路径使用受控替身与显式注入OS事实，不冒充真实Abaqus恢复验收。

首次失败均保留：registry回调死锁、内部表帮助器使用错误、SQL写窗口热journal拒绝、测试握手遗漏、已退出对象映像查询不完整及相应旧断言调整。详见 TEST_AND_ACCEPTANCE.md，不以末次PASS隐去原失败。

清理：667个本轮登记身份后查匹配存活0；最后纯注入批次无新增真实身份。报告已知秘密命中0，合计187份本轮临时私有文件移除；原测试退出/句柄关闭证据保留，业务DB/输出/审计未删除。没有按名称终止进程，没有操作历史owner。

## 保持的限制

1. 缺exit、单独boot时间估计、丢失Job证据、身份未知或热journal仍KEEP_BLOCKED；没有通用系统崩溃后行政放行政策。
2. 原受管证据对账使用 `recovery_scope_completion`，不伪造自动 `COMMITTED_EMPTY_SCOPE`。现有A→B与严格停服条件未放宽；Solver/Artifact缺失仍缺失。
3. 原锁只约束遵守同一协议的写者；OS观察与SQL不是跨系统原子快照。原owner身份缺失/替换时可能无法管理，必须拒绝。
4. 本轮核心/本地Python入口已实现；远程操作者授权、GUI完整恢复交互及CLI/MCP集成留CR-D04独立审查。Classic中断误显示Failed仍是Run024必修P1。
5. 新尝试、Retry、Abaqus Restart、实际关机/重启、生产迁移、真实Solver恢复未验收。历史 NOT_OBSERVED / UNKNOWN / ODB NOT_RUN 保持。

没有新增Schema、全局Run状态或版本变更。既有4个运行源码文件和3个测试文件修改，新增2个运行模块、2个测试模块；旧文档/冻结包/GUI/Backend/授权执行语义保持。Develop HEAD `9553755a24ff521dd2ac694ea39cab5a03f88466`，0.3.0.dev0；1556个基线文件的保留核验见FINAL_CHECKS.json。

未确认新的P0执行安全缺陷；Run022受限RC结论不扩展为通用自动恢复已完成。没有访问Stable、共享环境改动、历史实例操作、Git恢复/暂存/提交/推送。

## 交付

- [最小改动及复用](IMPLEMENTATION_AND_SCOPE.md)
- [权限、排他、事务、幂等及兼容契约](RECOVERY_CONTRACT.md)
- [Python接口使用](USAGE.md)
- [22项/26项矩阵、失败及未覆盖范围](TEST_AND_ACCEPTANCE.md)
- [逐用例结果](TEST_RESULTS.json)、[实际Windows证据](WINDOWS_RECOVERY_EVIDENCE.json)
- [首次清理](CLEANUP.json)、[最终新增批次清理](CLEANUP_FINAL.json)、[最终保护核验](FINAL_CHECKS.json)
- [Run024显示与导航](RUN024_GUI_HANDOFF.md)、[剩余边界与下一阶段](REMAINING_AND_NEXT_STEPS.md)

完成后停止，等待后续授权；本报告不授权任何历史实例处置或新的Solver调用。
