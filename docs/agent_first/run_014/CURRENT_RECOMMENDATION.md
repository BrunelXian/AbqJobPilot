# 当前真实实例：只读评估与待确认处置

对象：Run `r_609c9bbfd9c54b3ca2fce23bbd6059e4`，Project instance `pi_776faf62f2d64a4ab23e83c53b665788`。

记录owner：`owner_17886eb60d8349e880d61131a04be3b3` / PID17528 / creation100ns=134372377146539267；gate PAUSED v3。**本轮IPC健康查询超时，未取得身份匹配的当前owner引用。** 不以旧PID数字作停服目标，不把未发现匹配进程当作历史退出事实。

## 已成立与未成立

| 维度 | 当前持久事实及引用 |
|---|---|
| 接受/尝试 | 回执 `req_c17228560b40411585817099ed5ddbd3`；attempt `phase_5b46d6d7f0aa42bf82d3a353a4b1e359`；原执行消费1次 |
| 执行与观察 | revision20，BLOCKED / EVIDENCE_RECORDED，记录观察期限已结束 |
| 已观察退出 | 11个身份匹配成员有持久退出码0；source为direct_Popen_handle或retained_windows_handle；本轮只读，不重新生成退出记录 |
| 完整性 | member_completeness / overall_exit / exit_verification 仍UNKNOWN；不是全体Solver成员退出已证 |
| Solver | 历史COMPLETED_TEXT_EVIDENCE；没有重新运行 |
| DAT | 历史PRIMARY_THREE_PASS；验证 `val_67bc37128dcb48d7b4978095713a3174`，observation `obs_3805c9e40111420291557e6eabd12c6a`。本轮未重新读/验证产物 |
| ODB | NOT_RUN |
| 控制与隔离 | slot指向原Run，gate PAUSED；旧engineering及其scratch/输出仍须保留；没有资源租约已释放的事实 |
| owner当前状态 | 无响应且当前身份未确认，不能声明正常退出已验证 |

一致评估：`CURRENT_CLOSEOUT_PREVIEW.json`，policy `standard-closeout-v1`。

- preview_digest：`sha256:dd9f2e95913c180a42dcdf8f46055846f95930250afd977ea5a0daf1abe01b25`
- evidence_fingerprint：`sha256:303e4a04a12bb0c4a3efffb3f7d48cc1ac780e325a87273d244555a3656a989d`
- 当前拒绝原因：`CURRENT_QUIESCENT_OWNER_REQUIRED`。离线owner_id=null，两个动作目前都不能直接提交。

这份摘要用于审阅，取得管理owner后gate/owner必变，必须重评并签发精确新许可；不沿用旧评估摘要作为准入。

## 建议的具体后续动作（未执行）

1. 操作者确认接受本Run的**成员全集及整体退出仍未知、物理资源归还未证明**这一残余风险。
2. 只尝试既有OS排他锁的正常取得，建立**无执行工作线程、无StandardBackend的管理lease**。若原owner仍持锁、身份/存储状态不明或维护检查拒绝，就停止；不杀进程、删锁、改journal或启动替代Solver。不能把IPC超时当作接管许可。
3. 在这个持锁owner中重新读取评估；如果原已观察退出、原Plan/attempt/消费和观察结束证据仍满足政策，登记 `EXPLICIT_STANDARD_DISPOSITION` 的 `release_standard_logical_slot` 精确许可并提交一次幂等处置。记录真实授权来源及“接受完整成员集合仍未知”的理由。
4. **仅释放逻辑slot**。保留原Run和UNKNOWN、原回执、原执行消费、旧工程/scratch/输出隔离、输出意图、PAUSED。不Retry，不恢复派发，不运行验证器，不删除任何输出。
5. 取得管理回执后关闭这次管理lease，保持PAUSED。它没有启动任何子进程；不是“停止原Solver”。如果提交结果不确定，按原操作key查询，不换key重试。

独立恢复派发不在这个建议动作内，需以后针对新资源/计划和剩余不确定性单独审阅。旧输出解除隔离也不在本版能力中。

## 当前是否可以正常停止原owner

**尚不能给出针对当前旧owner的“可以直接停服”结论**。代码路径无主动终止后代，但本轮当前身份/连通性未确认，不能证明当前worker状态或收尾成功；外部宿主Job生命周期也不是简单关闭进程句柄可以证明的。

若后来确认原owner仍响应且静止，须单独核对其身份、未决记录已持久化和原停止入口的材料条件，再取得明确停服确认。原Run013包绑定旧源码，本版改动后旧stop的材料校验不能绕过。本轮既没有发stop请求，也没有为此更改候选包。

若正常排他锁已可取得，则不需要为了“停止旧owner”向旧PID发任何操作；管理交接仍会明确记录新owner，历史退出未知不会补写成成功。仅依靠获得锁不能证明未知Solver已结束，这正是行政政策必须显式接受的风险。

用户若不同意残余风险，应继续保留slot/PAUSED/路径隔离，等待未来独立、明确授权的观察或更严格证据流程；本轮没有force-close方案。
