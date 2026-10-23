# Run 003 — 进程、故障窗口与隔离证据

实际环境：Windows-11-10.0.26300-SP0；绝对登记解释器 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python3.12.10。该venv启动器的实际Python映像为 `D:\Program Files\Python312\python.exe`；这是Windows虚拟环境的转发行为，未更换选定环境。PID与映像路径均来自Windows进程API，不按名称猜测。

机器可读记录：[PROCESS_EVIDENCE.json](PROCESS_EVIDENCE.json)，含27个多进程case、39个实际Python身份、各启动器PID、退出码、终止方式、阶段屏障、IO trap摘要及凭据清理清单。完整测试断言见[验收矩阵](ACCEPTANCE_MATRIX.md)。

## 明确创建、明确结束

[supervisor_helpers.py](../../../tests/supervisor_helpers.py)仅允许固定的当前绝对Python解释器、固定的[run003_process.py](../../../tests/run003_process.py)、显式临时根/配置参数，`CREATE_NO_WINDOW`后台启动，无任意命令选择。初始身份文件后子进程等待identity-bound屏障；父harness验证父子关系、创建时间和实际映像后保留内核句柄，才允许继续运行。

实际终止使用这个已核验并持续持有的Windows进程句柄，绝不按PID字符串重新查找后直接kill，更没有按名称批量结束进程。终止返回后WaitForSingleObject确认实际进程退出，再wait启动器。正常结束通过仅测试harness可用的stop文件/事件通知，owner等工作线程退出后释放锁。普通IPC没有shutdown/cancel/approve能力。

最终39个实际Python句柄均signaled、39个启动器均有退出码。4次显式故障终止：接受后等待客户端、丢应答客户端、post-artifact owner、陈旧端点测试owner；其余正常退出或明确拒绝后退出。句柄全部关闭，没有本轮常驻服务或残留测试进程。

机器记录中的exit_code取自Popen启动器的wait结果；实际Python进程的退出确认字段是actual_process_handle_signaled，不把启动器PID冒充实际owner PID。

## 关键真实进程窗口

| 场景 | 最终实测身份 / 阶段 | 结果 |
| --- | --- | --- |
| 客户端结束 | owner26636 / client14120 / reconnect28608；dispatch:after_claim | Run已持久START_INTENT，客户端被结束；owner完成并验证；新客户端查询原Run |
| 应答丢失 | owner22308 / client13668；submit:before_response | 接受事务已提交，首socket响应未发送；Fake不依赖handler屏障并已完成；原key重放同receipt |
| owner崩溃 | owner2964，创建时间134370688657582829（Windows100ns）；dispatch:after_artifact | 固定JSON已写入并fsync，终态事务未开始；按句柄结束后启动新owner29920；保留不确定、PENDING、原文件，不执行第二次 |

阶段由测试检查点写出reached标记并等待显式release，故障时机不靠sleep估算；短轮询仅用于等待已经定义的标记/状态条件。测试检查点不可从RPC设置，不向Fake传命令/callable，也没有动态Backend。

崩溃前已提交START_INTENT与槽占用是持久禁止重跑的依据。没有把文件存在等同于Artifact有效；重启时原Run没有ValidationRecord，solver仍NOT_RUN。PENDING既未领取也没有模拟副作用，与不确定在途Run分开显示。

## 文件边界与清理

临时根：`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run003_6fcc0e2aa14c45dc97a3e68b980a3104`。run1/run2/run3/final分别使用新的子目录，未清空历史basetemp。

- 每个Project、runtime、TXT输入、Recent哨兵、SQLite、JSON产物和所有测试进程控制文件均在相应case根内。
- Run002原有默认路径/启动/旧模块trap保留；每个实际测试子进程再次安装。子进程Path IO经过confined检查，完成进程保存路径清单；被真实终止的进程不能执行finally，因此其清理依靠父harness句柄记录，而不伪造完整IO日志。
- 独立SQL连接仍通过context/manifest/root/inode/format/sidecar校验；C层SQLite IO不受Path.open monkeypatch拦截，隔离依据是显式URI及这些检查，不夸称Python IO trap覆盖所有C层IO。
- 每case结束确认Recent摘要/mtime未变；没有INP/CAE/JNL/ODB、旧queue/live_status/project.db。业务只读测试比较完整Project文件摘要/mtime，不仅比较行数。
- 最终case清理bootstrap及所有私有进程配置，逐文件确认剩余内容不含连接token；前三轮共166个私有配置也在本轮临时根内按明确文件名清理。
- 非秘密临时数据库、输入、产物、原始测试输出、阶段记录与inventory保留作为审计证据，未冒称它们已删除。保留不意味着继续运行；所有测试进程均结束，端点/owner文件只是陈旧诊断记录。

未接触用户其他进程、真实Project/Runtime/Recent、生产数据库、共享环境或Stable。没有系统服务/启动项安装。未清理恢复备份或Git保护引用。
