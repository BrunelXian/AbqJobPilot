# Run 004 — 进程、故障窗口与隔离证据

环境为Windows-11-10.0.26300-SP0，登记解释器 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python3.12.10（MSC1943 AMD64），SQLite3.49.1，pytest9.1.0。全部新数据位于本轮新建根 `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run004_e0d90d97a657421899e4df6616b561fb`，最终189项运行位于其final子目录。

结构化汇总[PROCESS_EVIDENCE.json](PROCESS_EVIDENCE.json)包含每个case路径、实际进程身份、创建时间、启动器PID、退出码、屏障、隔离检查、凭据清理与两个完整演示的业务记录。原始lifecycle/inventory/io/barrier/demonstration文件留在相应临时case内。没有复制IPC秘密到报告。

## 实际进程及清理

最终测试共30个多进程case、49个实际Python进程；其中Run004新增3个case、10个实际进程，前置回归27个case、39个。8次故障终止（本轮新增场景4次，原回归4次）均使用已核验并持续持有的Windows进程句柄。所有49个实际句柄均已signaled，启动器也退出；句柄已关闭。

Windows venv python.exe会作为redirector启动实际Python映像。本轮仍以登记venv绝对路径调用，实际映像 `D:\Program Files\Python312\python.exe` 来自该venv，不是切换解释器。harness核对父子关系、creation_time_100ns和映像后保留HANDLE；故障终止不重新按PID查找，不按进程名称批量终止。

| 最终case/角色 | 实际PID | 启动器PID | creation_time_100ns | 退出证据 |
| --- | ---: | ---: | ---: | --- |
| test_windows_crash_reconcile_e0 / 原owner | 33572 | 14648 | 134370730180133670 | dispatch:after_artifact后通过持有HANDLE终止，77 |
| 同case / 对账owner | 3376 | 27480 | 134370730185336762 | 完成对账与独立恢复，测试stop后0 |
| 同case / 再次重启owner | 33656 | 32464 | 134370730195707410 | 重放旧resume仍PAUSED，测试stop后0 |
| test_windows_crash_reconcile_e1 / 丢应答客户端 | 19928 | 3276 | 134370730216264052 | management:before_response已到达，持有HANDLE终止，77 |

以上表只列关键样本，完整49条以JSON为准。41个正常退出的进程写出完整io.json并通过路径/launch/legacy检查；8个被终止进程不可能运行finally，因此没有伪造其完整IO日志。它们仍有预先绑定身份与确定屏障，其隔离trap已在入口安装；最终文件inventory与测试断言同时验证允许范围。

所有多进程case的private-bootstrap.json及private-process.json已在持有进程全部退出后删除；清理项逐条在inventory登记，剩余文件经扫描不包含原连接秘密。三次测试运行根中均无这两种私有文件残留。测试管理request/reply属于精确owner/动作的TEST_ONLY夹具记录，不能在新owner复用；它们不是连接凭据。

临时实验数据库、产物、不可变证据快照和日志保留作为本轮证据，没有宣称整个临时根已删除。所有case的Recent哨兵内容不变，未生成CAE/INP/JNL/ODB、旧queue/live_status/project.db。测试不访问默认Runtime/Recent或生产Project；子进程入口对执行包路径施加临时根检查，并禁止真实启动与旧模块导入。

## 确定故障窗口与业务证明

端到端入口为[真实多进程测试](../../../tests/test_reconciliation_supervisor.py)。测试等待命名屏障文件到达才执行故障，不用固定sleep推测阶段；短轮询只等待确定条件并有超时界限。

1. 原owner在 `dispatch:after_artifact` 停住：原Run的START_INTENT已提交，Fake结果已写，终态事务尚未开始。接受另一个PENDING后终止原owner。
2. 新owner取得OS锁后PAUSED；纯预览重复读取完全一致且inventory不变。只有IPC连接资格但缺管理Grant的申请被拒绝。
3. owner内测试控制器登记精确管理权限；apply采纳原结果。原Run唯一START_INTENT和原result的bytes/mtime保持；新增快照及RECONCILIATION_APPLIED，没有伪造FAKE_COMPLETED。
4. 对账回执的门是PAUSED/version3，第二个Run仍PENDING。另一个管理权限执行resume，回执OPEN/version4；原派发验证通过后第二个Run才产生自己的结果。
5. 再次启动第三owner，门PAUSED/version5；原resume重放只返回历史回执，当前门仍PAUSED。
6. 丢应答变体在 `management:before_response` 屏障结束测试客户端，owner继续。其他连接先查原管理回执，再同key重放；只有一次对账记录/消费和原副作用。

正常应答演示的原Run为 `r_34e44b7ea674478ea4dc60232b2eb0e1`；原提交回执req_d73b339804d44ec58cfaa4e4535c4903、对账op_ae54c96acbb043158a8e7346a5bc816c保持独立。原结果与快照摘要/421字节、原Plan与验证引用均在JSON演示记录中。solver_conclusion始终NOT_RUN，validation_scope为simulation。

## 保存/提交故障

[本地故障测试](../../../tests/test_fake_reconciliation.py)还验证before_snapshot、after_snapshot、before_commit、after_commit；这些是确定异常注入，与上面的真实进程退出证据分别报告。

快照写出后事务回滚时，原回执/事件/Run仍保持；孤立快照可由operation文件名识别，普通查询不清理。commit已经成功但确认异常的测试让SQLite真正commit后抛错，服务返回ACCEPTANCE_UNKNOWN，再按原key查询/重放取得唯一回执，不把数据库回滚当成撤销文件副作用。

## 明确边界

本轮没有模拟断电、内核崩溃或磁盘硬件损坏。已有journal/WAL维护门禁仍拒绝，不隐式恢复数据库。限定fake-v1的确定字节与历史接受/领取证据足以支持本次采纳，不能推广成真实Solver结论、进程退出验证或对抗同一OS用户任意篡改。证据不足的Run继续阻断，未实现强制关闭、自动Retry、万能解锁或完整恢复控制台。

复现命令见[验收矩阵](ACCEPTANCE_MATRIX.md)。本轮没有长期后台安装、系统服务或启动项，所有创建进程已退出。
