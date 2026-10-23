# Run 012 最终报告

**固定 Python 进程的公共客户端、独立执行服务与现有 GUI 闭环通过。**

本轮真实 Abaqus 调用 **0**。没有重放 Run 010/011、读取其外部实验输出、修改候选或重置尝试保护；没有访问 Stable、生产 Project、共享环境，没有 Git 切换、提交或推送。

## 可直接使用

从资源管理器依次双击：

1. `D:\Projects\abqjobpilot_dev\examples\agent_first\01_Start_TEST_Service.vbs`
2. `D:\Projects\abqjobpilot_dev\examples\agent_first\02_Submit_Fixed_Test.vbs`
3. `D:\Projects\abqjobpilot_dev\examples\agent_first\03_Open_Dev_GUI.vbs`

在约45秒的固定 worker 等待期间关闭整个 GUI，再次打开第3个入口即可查看同一 Run。完成后使用同目录 `04_Stop_TEST_Service.vbs` 正常结束演示服务。无需保持 PowerShell 窗口；GUI 本身不启动或停止 owner。

完整条件、明确的数据位置及错误处理见 [USAGE.md](USAGE.md)。TEST_ONLY Plan/Grant 由可信演示准备步骤预置，普通客户端不能批准任意任务。首次点击才创建新的隔离临时实例，本轮没有留下一个需要用户接管的活动测试进程。

## 实现

- 复用既有 ExecutionService、独立 FakeSupervisor、OS 所有权锁、ProjectContext、精确 TEST_ONLY 授权、幂等提交、每存储单槽、固定 ProcessFixture 四成员集合、OS 退出记录和独立 validator。
- 在原 `AbqJobPilotApp` 添加显式连接模式；复用原布局组件、状态灯、表格和日志区。旧依赖延迟加载到 gui_legacy，隔离模式不访问旧 Runtime/Recent/Runner/历史库。
- 新 `ExecutionView/Reader` 只使用公共客户端读取，后台线程轮询、Tk显示。关闭等待当前有界读取收尾；无控制操作、数据库写入或授权消费。失联明确展示缓存及最后更新时间。
- 增加固定 worker 的有界进度文件与唯一新公共只读 `progress` 查询，沿用认证、Project/owner 绑定和帧限额。进度自报不等于退出或验证。
- 新增可信开发演示入口和5项针对性验收。没有新建长期 Runner、Supervisor 框架、系统服务、计划任务或生产 Schema。

既有文件改动仅：gui_app.py、execution/client.py、execution/supervisor.py、execution/process_fixture.py、test_execution_isolation.py。新增文件与函数见 IMPLEMENTATION.md。版本仍为统一来源 `0.3.0.dev0`。

## Windows 真实进程证据

实际系统 `Microsoft Windows NT 10.0.26300.0`；登记解释器 Python3.12.10 / Tk8.6。

完整新增组的主闭环 Run：`r_77ce2ebb576f4a3cab905a4be6291621`（evidence_003）。

- GUI 尚不存在时，独立公共客户端提交、取得回执并正常退出。
- owner PID31628；GUI A实际进程17392及venv启动器13724均经具体OS句柄观察到exit0；不是仅隐藏窗口或mainloop返回。
- 此后原worker17748仍存活，OS身份核验使用PID、创建时间、映像和保留句柄；日志序号从4继续到5。owner身份不变。
- GUI B实际进程21132显示同一Run和原request_id。可信测试启动陷阱和OS对象确认固定执行物理启动1次；公开同键重放没有再启动。
- 四个固定成员取得服务持久化exit0；FINISHED、Backend COMPLETED、Artifact VALID、Solver NOT_RUN分别显示。没有把进度文件当成OS退出证明。
- owner正常退出时GUI显示连接中断。明确重启owner后为PAUSED，GUI重新连接不恢复派发。另一测试真正终止启动前屏障处owner，重启后的不确定Run继续阻断；GUI只读显示待对账。

独立产品入口测试另有Run `r_8d8b568ec8dd4714b483b9bc26a8cb8a`：start命令进程退出后owner11448继续运行；GUI退出后产品计时控制释放固定屏障，worker自行完成；owner正常退出后private_remaining=0。

所有数字是此次测试中的PID简写，不用于之后按PID猜测归属或清理。完整身份、OS退出来源、Tk已渲染字段、清理记录、窗口实拍见 evidence_003。最后统一版本标题和保留表格滚动位置后，又以真实闭环单测复核通过，补充证据在 evidence_004。

## 测试与保留

最终有效测试组合：**369 passed，0 skipped**。

- R2～R8相关实验回归：359 passed，214.47s。
- 旧GUI与表格状态回归：5 passed。
- 新Windows GUI/公共进度/产品入口/owner崩溃/慢IPC组：5 passed，61.84s。
- 最后展示细节修改后的主闭环重复验证：1 passed，未重复计入369。

失败迭代与修复详见 ACCEPTANCE_MATRIX.md；没有降低旧断言。通过来源是本轮实际运行的JUnit和OS证据，不是历史交接的测试数字。

345个先前文件摘要已核对，221个Run010/011本地材料全部保持。5个预期既有文件差异已列明；其余基线文件不变。原真实实验根及此前清理受阻目录未访问/删除。每次新增测试私有交接按本轮归属清除，正常GUI及owner退出经句柄确认；故障用例只终止已明确创建和核实身份的测试owner。没有按名称批量结束进程。临时业务证据保留，未做递归清理。

## 尚未覆盖

结论只适用于本轮Windows承载环境中的固定Python进程及GUI正常关闭/重开。未宣称桌面VBS宿主政策、终端关闭、注销、重启、任意进程树、真实Abaqus后台生命周期或跨Project资源保护已验收。演示会话为有界开发工具，不是长期安装的系统服务；owner停止后不自动重建或恢复。

GUI当前仅为只读服务查看；真实执行批准、人类监督写操作和真实Backend接入仍须单独设计和授权。本轮到此停止，不自动开展下一阶段。
