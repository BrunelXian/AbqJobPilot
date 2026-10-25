# Run014：已授权的单次有限行政处置

**APPLIED_VERIFIED — 仅逻辑执行槽释放完成。新增 Abaqus 调用 0。**

2026-10-24 15:25:32（UTC+08:00），对 `r_609c9bbfd9c54b3ca2fce23bbd6059e4` 完成已授权处置，随后在持锁期间及释放本次管理 lease 后重新读取持久化状态，两次一致。没有恢复派发、启动任务、停止/重启/接管旧 owner 或终止进程。

## 精确对象与回执

| 项目 | 实际结果 |
|---|---|
| Project instance | `pi_776faf62f2d64a4ab23e83c53b665788` |
| Run | `r_609c9bbfd9c54b3ca2fce23bbd6059e4` |
| revision | **20 → 21**；锁内评估绑定当时的 revision20 |
| 动作 | `release_standard_logical_slot` |
| 处置记录 | `disposition_c225b0582c664a4d939821575e6f6549` |
| 管理操作回执 | `op_ef7048a01b854129a1d32dac7e9f6417` |
| 幂等键 | `closeout-request_f26673ed6feb466d911748d5cd5533e0` |
| 逻辑槽 | 原 Run → `NULL` |
| 派发 | **PAUSED**；gate v3 → 取得管理 lease 后 v4 → 处置后 v5 |
| 旧路径 | **RETAINED_NO_REUSE**；engineering、scratch、输出身份仍保留 |
| 原始接收回执 | `req_c17228560b40411585817099ed5ddbd3`，内容未变 |

原请求在提交前保存为 [EXACT_REQUEST.json](EXACT_REQUEST.json)，回执随后通过既有 `management_receipt(namespace, action, key)` 按同一键只读取得，见 [DURABLE_RECEIPT.json](DURABLE_RECEIPT.json)。没有第二次 apply、换键、重发执行或退款原授权。

## 排他性与实际调用路径

原 Run013 清单绑定的 `ownership.py` 与 `store.py` 均与当前实际文件逐字节摘要一致。原 Supervisor 和本次管理入口都调用 `acquire_supervisor_store`，最终使用相同的：

- 文件：`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run013_e52135d71d2c43d2a45301c586cbfb7e\project\owner.lock`；
- Windows `msvcrt.LK_NBLCK` 排他字节锁：offset 4096、length 1；
- 不可继承的文件句柄，正常取得成功，未删除/改写锁文件，未强占；每次管理事务仍检查持有 lease 和锁文件身份。

这不是新建的独立管理锁，也不以 IPC 超时、旧 PID 未找到或文件残留推定排他权。持有的就是旧 owner 遵守的存储锁。锁内重读确认原 Run、Plan、slot、原回执、20条历史事件、观察、验证及原消费与处置前一致，没有新增执行证据；服务重算评估允许本次动作。

复用调用链：`load_bootstrap`（只读）→ `acquire_supervisor_store` → `ExecutionService`（不配置真实或进程 Backend，不创建执行线程）→ `preview_closeout` → `closeout.issue` → `apply_closeout` → 既有管理事务及只读回执查询。

本次实际授权来源见 [AUTHORIZATION_SOURCE.md](AUTHORIZATION_SOURCE.md)，是用户当前消息，不是新的执行授权协议。精确管理 grant 仅批准当前 Run、owner、revision、评估摘要、证据指纹及释放动作，单次使用。处置、管理消费、回执、Run投影、事件及控制记录按既有事务一起提交。

临时管理 owner 为 `owner_fdadb9803c7a48f4b5428025509b052b`。现有入口取得管理 lease 时会更新数据库管理 owner/gate；这一变化已记录，不隐瞒为“所有 owner 元数据不变”。**未创建替代 Supervisor、监听器或监控任务；没有接管旧进程或旧端点。** 原 Run 记录的 owner 仍为 `owner_17886eb60d8349e880d61131a04be3b3`，旧 owner.json 和 connection.json 未变化。本次仅关闭自己的临时管理锁，数据库保留最后管理 owner ID；该 ID 不表示现在有一个活动服务。

具体锁身份、当前管理进程身份及原材料摘要见 [EXCLUSIVE_MANAGEMENT.json](EXCLUSIVE_MANAGEMENT.json)；锁内评估见 [LOCKED_ASSESSMENT.json](LOCKED_ASSESSMENT.json)。没有重新探测未知 Solver 或倒填历史退出事实。

## 保留的证据和限制

| 维度 | 提交后事实 |
|---|---|
| execution / phase | `BLOCKED / EVIDENCE_RECORDED`，原字段不变 |
| 原 reconciliation 字段 | `RECONCILIATION_REQUIRED`，未伪装为证据已完整 |
| 独立行政投影 | `LOGICAL_SLOT_RELEASED_WITH_RESIDUAL_UNCERTAINTY` |
| member_completeness / overall_exit / exit_verification | **UNKNOWN / UNKNOWN / UNKNOWN**，原样保留 |
| 已记录进程及退出记录 | 原内容完全一致；行政决定不是新的 OS 退出证据 |
| Solver | 原 `COMPLETED_TEXT_EVIDENCE` |
| DAT | 原 `PRIMARY_THREE_PASS`；原 ValidationRecord 不变 |
| Artifact / ODB | 原 `VALID / NOT_RUN`；本次没有重新验证或打开 ODB |
| 原执行消费 | 仍1次，grant及消费内容不变 |
| 事件/验证/观察 | 事件20→21，仅追加处置事件；原1条验证和1条观察未变 |
| 管理记录 | 精确 grant、消费、回执、处置和控制事件各新增1条 |

旧工程及 scratch 路径：

`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run013_e52135d71d2c43d2a45301c586cbfb7e\engineering`

`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run013_e52135d71d2c43d2a45301c586cbfb7e\engineering\scratch`

保留输出键：`sha256:564c957021567b457c4b78009b133d80740d053539891d8ec66a6b70b8b2b03f`。

路径保留使用既有同实验存储的准入政策及原输出意图，**不宣称整机/跨 Project 物理资源租约，也不宣称所有物理资源已归还**。不复用旧路径，不 Retry，不恢复派发。行政决定只能解除已授权的逻辑槽占用，不能倒推完整成员集合已退出。

## 实际核验和保留范围

- 工作区 `Develop@271c6f82fd6a4599dbae2df30d903dab2cef1f63`，无冲突；版本0.3.0.dev0。保留原工作区修改；未改变实现代码。
- 已读环境登记，实际使用 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python3.12.10 / SQLite3.49.1 / Windows。
- 本次不是重新运行历史测试组；执行的是已验收管理 API 的实际单次处置。13项提交后检查全部通过，见 [VERIFICATION.json](VERIFICATION.json)。
- 原受保护295项历史材料、已有 Run014 报告和已审阅实现摘要保持；工程输入、输出、原意图及私有连接材料保持。工程文件摘要前后比较；ODB仅核对文件元数据，没有打开内容。
- 不重新启动或改变真实 owner，不读写生产 Project，不访问 Stable，不修改共享环境/安装，不提交或推送。
- 调用脚本仅是本次已有 API 的审计编排，不新增业务入口或 SQL 写入；`INVOCATION_STARTED.json` 已存在，禁止把脚本当作重试入口。原代码与历史报告未覆盖。

本次已完成所授权的有限行政处置，停止在此。后续恢复派发、旧路径复用或 owner 生命周期操作均未获得本次授权。
