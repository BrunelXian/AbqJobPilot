# Run019 使用

正常入口：[Open_Dev_GUI.vbs](../../../Open_Dev_GUI.vbs)。实际为本机登记的 `D:\XianLab\envs\LangChainEnv\Scripts\pythonw.exe` 启动现有 `run_gui.py`，版本 0.3.0.dev0。

1. 明确选择一个 Agent-first Project。发现/选择/刷新仍只读，没有服务时生命周期行显示 NOT_RUNNING（不是任务失败）。
2. 对已由可信设置预配置的空闲 TEST_ONLY Project，明确点击 **Start Service**。后台线程进行检查；成功后自动认证连接。不会自动创建 Project、批准、提交或恢复任务。
3. 从已有 Run 列表选择任务；状态、范围收尾、Solver、验证和日志分开显示。断线保留缓存并标记过期。
4. **Disconnect** 或关闭窗口只断开 GUI。重开后选择同一 Project、重新连接，读取同一 Run。
5. **Stop Service** 显示明确确认说明，使用该实例单独的生命周期操作者能力。仅空闲受支持服务允许正常停止；活动、PENDING、UNKNOWN、槽占用或行政路径保留拒绝。重启是另一次显式 Start，仍 PAUSED；此界面没有恢复派发入口。

Start/Stop 需要 `<instance>\private\operator.json`；连接材料仍为 `private\connection.json`。不要把这些文件写入日志、提交 Git 或提供给无权操作者。旧服务不支持生命周期/Run 列表时报告能力缺失，不自动替换。读取真实历史 owner 不构成停止/重启许可。

## 独立 Python API

```python
from abqjobpilot.service_lifecycle import ServiceLifecycleManager
m = ServiceLifecycleManager(explicit_project_root)
print(m.inspect())                         # 只读
started = m.start()                         # 明确授权的生命周期操作
client, context, health = m.connect()       # 原认证公共客户端
# client.submit(exact_pre_authorized_request) 是独立操作，不由 start 执行
m.disconnect()                             # 仅客户端
m.stop(owner_id=health['owner_id'], operation_key=explicit_stable_key)
```

准确 owner ID 应从 `client.endpoint['owner_id']` 取得（health 同样提供 owner_id）。停服失去应答后保留原 owner 和键，再查询原回执；不换键、不杀进程。start 返回 STARTING/START_UNCONFIRMED 时只 inspect/connect；再次调用也不会获得新创建预算。

## 可复现的可信 TEST_ONLY 设置

新增例子 `examples\agent_first\lifecycle_demo.py` 与测试内部模块无关。prepare 创建**全新的**显式隔离实例、固定 normal ProcessFixture 计划、一次 TEST_ONLY Grant 和生命周期操作者能力；它不启动服务、不提交。submit 只用原公共客户端和预置精确请求。该 short normal 示例可能很快结束；GUI 关闭时 worker 持续运行的证据来自有界 result_wait 集成测试，不宣称短示例必然给人工留下关闭时机。

以下命令已在非仓库 cwd 验证（实际根和输出见 PUBLIC_EXAMPLE.json）。示例根已有记录，**不要重用**它做新 prepare；为新的演示选择新的明确临时目录：

```powershell
$python = 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe'
$example = 'D:\Projects\abqjobpilot_dev\examples\agent_first\lifecycle_demo.py'
$root = 'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run019_4uyet2rj\public_example'
& $python -B $example prepare --root $root
& $python -B $example inspect --root $root
& $python -B $example start --root $root
& $python -B $example submit --root $root
# GUI：双击正常入口，选择 $root\project；无需手工启动/保留 PowerShell 来维持 owner。
# stop 的 --owner 使用 inspect 返回的准确 owner_id；不自动取任意当前 owner：
& $python -B $example stop --root $root --owner '<实际 owner_id>'
```

`check_example.py` 是本轮实际执行与证据保存脚本，记录了上述命令的非仓库运行、同键 submit 重放、退出证据与私有材料清理。它使用的新测试实例已经停服并移除凭据，不能当作留给用户的活服务。

GUI 的明确 Start 可替代例子中 start 命令；无需手工拼装 Supervisor 命令。本轮未增加 VBS 调度渠道、系统服务或新的 GUI。可信设置、生命周期能力和任务执行批准分别交接；通用工程 Project 产品化配置仍属后续发布门槛。

## 证据位置

- `<instance>\private\start_<id>\intent.json / claimed.json / created.json / ready.json / host.json / stopped.json`
- 同目录 stdout.log、stderr.log：服务自己的独立磁盘输出，不是 GUI 管道。
- Project 执行库：原 Run/Event/Validation，以及一次停服 management_receipt/control_event。无需也不应由用户直接修改数据库。
- 本轮报告目录：测试 XML/日志、Windows GUI 生命周期与清理证据。启动预约、历史记录和输出不由产品自动清理。
