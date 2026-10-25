# Run016 实际测试、迭代与清理

Windows 11 build26300；登记解释器 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python3.12.10、pytest9.1.0、SQLite3.49.1、Tk8.6。无依赖安装/升级。测试使用本轮7个显式Temp根，路径保存在各 TEMP.txt；Python以绝对路径、`-B`运行。后两轮明确禁用第三方pytest自动加载。没有跑全仓库旧GUI/Solver测试。

| 批次 | 实际结果 | 说明 |
|---|---|---|
| unit_001 | 37 PASS、1 FAIL，24.55秒 | 测试直接读event.body却期待公共投影的project_sequence；改测试取实际sequence列，不改业务事件含义 |
| windows_001 | 25 PASS、2 FAIL，39.92秒 | 新测试登记器在实际Python创建之后写float时间，不符合严格JSON；服务保守阻断。改登记器用整数纳秒，崩溃用例等待明确OBSERVING屏障 |
| windows_002 | 2 PASS，8.28秒 | 原生JOB_LIST/HANDLE_LIST、GUI重连、owner真实崩溃复验 |
| regression_001 | 304 PASS、1 FAIL，463.29秒 | 19个相关文件/305项。旧R7导出无后来添加的managed字段，被新投影拒绝；没有删除或弱化该断言 |
| final_affected | 58 PASS，67.50秒 | 为明确旧规则版本容许缺失的新可选字段，不补造证据；额外秘密字段仍拒绝。重跑相关Windows、Job、隔离与诊断组 |
| deadline_final | 182 PASS，113.27秒 | 在原生创建API紧前补最后时限检查；统一A回执与Run计时源。复跑Standard接缝、实际Windows/GUI、Job整组、原执行契约与诊断整组 |
| client_cleanup | 7 PASS，0.26秒 | 单元客户端的固定假connection/offer显式清理；兼容性/额外字段拒绝保留 |

按同一test classname/name合并各次**最新结果，共355项PASS、0跳过**，详见 FINAL_AUDIT.json。不是一次355全通过的宣称，也不拿前轮历史通过数作为本轮证据。原失败txt/xml均保留。旧R2提交/领取/存储/所有权、R3断线/认证、R5诊断、R7退出对账、R8公开客户端、R12实际GUI、R13原Standard、R14行政处置、R15范围管理均有针对性回归；未机械重跑全部历史组合。

## Windows实测证据

最终证据 `verified_deadline/test_managed_standard_pair_pub0.json`：

| 项 | A | B |
|---|---|---|
| Run | r_c12413e6dcae4a8dae16ea067a3da36d | r_269508c649c843f0bc910f5832fd4cf7 |
| 原生根PID / 创建时间100ns | 16884 / 134373060412706509 | 31092 / 134373060435813985 |
| 范围 | scope_baf74b372a5940148591c47e0f029ec5 | scope_8486921742b3471bb0b019fab2ab6ab0 |
| 持久顺序 | START_INTENT 2；MANAGED_COMPLETED 14；RESULT 15 | START_INTENT 17；MANAGED_COMPLETED 29；RESULT 30 |

A范围活动时公开提交B被拒绝；GUI及专属venv启动器WM_CLOSE退出后，owner和worker身份仍匹配存活；重开连接原A。两个结果都提交COMMITTED_EMPTY_SCOPE；scope直接查询active=0，Job和根句柄显式关闭。两个物理根各一次，重放未增加。记录里的Solver/DAT PASS来自**标记的历史文本替身**，不是真实Abaqus运行证据。

`test_public_pair_orchestrator_0.json`验证实际薄客户端run_pair经原IPC自行串联，仍两个实际Python根。`test_managed_standard_owner_cr0.json`在明确OBSERVING后真正结束本轮测试owner，worker继续；替换的测试owner保持PAUSED/RECONCILIATION_REQUIRED，B拒绝，没有领养或第二次创建。仅故障验收终止身份已核对的本轮owner，后代靠固定屏障释放/有限寿命自行退出。

所有scope/API查询、进程身份和退出码来自实际Win32对象；测试控制器的额外观察与服务数据库记录分开。未以固定sleep猜测关键启动窗口。等待轮询有界，worker具有原固定最长寿命。

## 隔离与清理

最终审计检查了4126份测试JSON、743个已登记Python身份（PID+创建时间+映像），没有身份匹配的存活者；不匹配/不可打开不补造历史退出码。实际退出证据来自各用例原保留句柄，当前状态仅为额外清理检查。所有最终正常用例显式关闭Job、原生根和观察句柄；早期登记器异常的未显式关闭句柄由本轮测试owner的OS退出回收，该失败记录保留。

真实连接私有文件由既有harness清理。审计另找到18份仅含固定字符串test-private的单元假连接，已核对本轮根/文件名/精确内容后逐文件删除，记录在DUMMY_CONNECTION_CLEANUP.json；后续单元测试自行清理。没有删目录、旧实验、历史输出、尝试文件或旧清理阻断。最终测试连接材料剩余0。

待审实例的private/bootstrap.json是将来可信准备所需材料，**有意保留在新实验根**，不导出秘密；它不是有效执行Grant。独立PREPARATION_CHECK证明plans=2，grants/runs/receipts/consumption/events/validation/reconciliation全0、supervisor_started=0、槽NULL。准备及check期间进程/网络创建哨兵未触发，检查前后实例文件摘要不变。非仓库CLI check实测输出见CLI_CHECK.txt。

517项历史保护摘要全部一致，包含历史真实execution.sqlite3字节摘要，未重新打开其可写Repository，未向旧owner发请求。未访问Stable、生产Project、共享环境或安装写入；Abaqus及额外信息/后处理调用均0。没有Git分支、恢复、提交或推送操作。
