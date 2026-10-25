# Run015 使用说明：两项固定 Python 任务

使用现有Dev GUI、公共客户端及Supervisor。所有入口都是TEST_ONLY，不接入原Run013实例，不自动为真实Abaqus准备或授予权限。

## 直接使用

依次双击Dev的以下已有技术栈薄入口（调用同一个 `dev_gui_demo.py`）：

1. [R15_01_Start_TEST_Service.vbs](../../../examples/agent_first/R15_01_Start_TEST_Service.vbs)：创建新的Temp隔离Project，可信设置预置两个精确Plan及TEST_ONLY Grant，然后启动原Supervisor。不提交任务。
2. [R15_02_Submit_Two_Tests.vbs](../../../examples/agent_first/R15_02_Submit_Two_Tests.vbs)：普通公共客户端提交两个固定请求。重复点击沿原幂等键返回原回执，不增加执行。
3. [R15_03_Open_Dev_GUI.vbs](../../../examples/agent_first/R15_03_Open_Dev_GUI.vbs)：现有GUI连接第一项，显示范围标识、最后OS活动计数、范围收尾、关键进程退出、Artifact和派发状态。
4. 第一项固定worker写结果后等约45秒，由可信演示设置解除固定屏障。此期间可正常关闭整个GUI，再打开同一入口；owner及Job不由GUI拥有。**关闭GUI不停止测试服务**。
5. 第一项收尾事务成功后第二项自动派发；[R15_05_View_Second_Task.vbs](../../../examples/agent_first/R15_05_View_Second_Task.vbs)只读显示第二个请求。两个窗口分别连接原Run，不重新批准/提交。
6. 完成后可显式点击 [R15_04_Stop_TEST_Service.vbs](../../../examples/agent_first/R15_04_Stop_TEST_Service.vbs)。沿原演示有界停服契约，不杀worker；固定演示服务最多存活900秒。

没有系统服务、计划任务、全局安装或breakaway。无需保留PowerShell窗口，但Windows会话保持存活。真实Abaqus、关闭终端/注销/重启的兼容性不在此演示保证中。

入口保存 `docs/agent_first/run_015/LOCAL_DEMO.json`，指向首次明确创建的 `Temp\AbqJobPilot_Run015_<uuid>`。已有指针时再次Start明确拒绝，不自动替换、清理或复用旧数据。连接材料位于新根private，正常演示停服会删除自己创建的私有材料；业务结果保留。没有访问Run010/011/013的工程根。

## 供程序调用的同一公开接口

可信准备使用 `ProcessFixtureConfig.current(managed_scope=True)`，其余仍是既有 `ExecutionService.prepare` 和 `issue_process_execution`，必须在明确新建的隔离实例及有效owner下执行。普通客户端拿到实际offer/connection后：

```python
client.inspect_plan(request['plan_id'], request['plan_digest'])
accepted = client.submit(request)
run = client.run(accepted['receipt']['run_id'])
progress = client.progress(run['run_id'])
report = client.diagnose(run['run_id'])
```

新固定计划可见managed_scope政策和实现摘要；普通客户端不能提供任意脚本、命令或额外Job操作。Job或依赖变化使原Plan失效，不能通过重新计算客户端字段放行。

原schema3读取仍适用；诊断报告v2在新managed记录上使用rules-v4，加入白名单范围历史字段。旧记录继续原rules-v3，不补造Job证据。

## 对应的明确命令

入口本质为以下命令；自动化验收使用等价的显式 `--root <全新临时目录>` 从非仓库cwd运行，不依赖工作目录推断：

```powershell
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B 'D:\Projects\abqjobpilot_dev\examples\agent_first\dev_gui_demo.py' start --managed-scope --notice
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B 'D:\Projects\abqjobpilot_dev\examples\agent_first\dev_gui_demo.py' submit --managed-scope --notice
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B 'D:\Projects\abqjobpilot_dev\examples\agent_first\dev_gui_demo.py' gui --managed-scope
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B 'D:\Projects\abqjobpilot_dev\examples\agent_first\dev_gui_demo.py' gui --managed-scope --task 2
```

VBS只是Windows隐藏启动窗口的薄包装；具体实测、未验证的双击交互范围及清理结果以FINAL_SUMMARY和验收矩阵为准。不要将本轮已测试替身作为真实Backend许可。
