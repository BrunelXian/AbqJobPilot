# Run009 公开离线客户端

开发实验接口，不连接Supervisor，不启动Abaqus，不需要批准或连接凭据，也不能产生真实执行许可。操作者提供明确Project关联和受限Runtime Profile；普通客户端可独立准备及检查支持子集内的候选计划。通用任务编辑/任意INP/真实Runtime验证仍未实现。

公开入口：[`prepare/inspect/export_preview`](../../../abqjobpilot/abaqus_preview/preview.py)。独立示例：[`abaqus_offline_preview.py`](../../../examples/agent_first/abaqus_offline_preview.py)。示例的业务流程只导入产品模块与标准库，不依赖pytest、SQL、测试helper、GUI、owner或授权工厂。

## Python调用

```python
from abqjobpilot.abaqus_preview import prepare, inspect, export_preview

# project/profile来自操作者的显式小型JSON；工程目录及输出目录均由调用者指定。
preview = prepare(project=project, runtime_profile=profile,
                  engineering_root=engineering_root, submission_cwd=engineering_root,
                  main_input="source.inp", job_name="candidate")
report = inspect(preview)             # 仅检查这个对象，不再读取输入
result = export_preview(preview, export_root=export_root, target="preview.json")
```

Project对象只含project_id、project_instance_id，属于公开关联声明；离线工具不打开已有Project或认证DB中的身份。Profile见[实际样例](examples/profile.json)，精确字段及INP表见[契约](CONTRACT_AND_BACKEND_GAPS.md)。未知字段不忽略。调用者不能提供命令、插件、环境字典、approve、任意Backend或脚本。

## 实际Windows独立运行

[EXAMPLE_INVOCATIONS.json](EXAMPLE_INVOCATIONS.json)保存本轮成功与拒绝两次**实际argv、非仓库cwd、实际客户端PID及正常退出结果**。使用登记解释器 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`；`--source D:\Projects\abqjobpilot_dev`只设置该Python进程的导入路径。没有共享安装、PYTHONPATH全局修改或运行Abaqus命令。

实际执行的参数结构如下；下列变量指向本轮隔离实例，精确绝对路径以上述JSON为准。目标已经存在时拒绝覆盖，再次演示须选择新的显式导出根或文件名。

```powershell
$pythonExe = 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe'
$sourceRoot = 'D:\Projects\abqjobpilot_dev'
# $caseRoot 取 EXAMPLE_INVOCATIONS.json 第一条cwd的父目录。
Set-Location "$caseRoot\non_repository_cwd"
& $pythonExe -B "$sourceRoot\examples\agent_first\abaqus_offline_preview.py" `
  --source $sourceRoot --project "$caseRoot\project.json" --profile "$caseRoot\profile.json" `
  --engineering-root "$caseRoot\engineering" --submission-cwd "$caseRoot\engineering" `
  --main-input source.inp --job candidate --export-root "$caseRoot\exports"
# 已执行的拒绝分支：相同命令把 source.inp 改为 rejected.inp。
```

输入为本轮临时根中由验收驱动生成的合成truss语法文本。客户端不生成或修改输入。可将以下小型数据说明用于手工建立**新的临时根**，不需要pytest：Project/Profile内容采用交付JSON；source.inp为NODE/T3D2/MATERIAL/ELASTIC/SOLID SECTION、单STEP/STATIC/BOUNDARY/CLOAD/END STEP的限制组合，具体文本见[合成输入说明](examples/SYNTHETIC_INPUT.md)。INP本体只保存在临时根，不复制成仓库内工程作业；拒绝输入为`*NODE, INPUT=external.inp`，返回UNSUPPORTED_PARAMETER，而不会寻找external.inp。

成功stdout结构为status=PREVIEW_PREPARED、preview、client_pid及可选export回执；失败为status=PREVIEW_REJECTED、稳定code、run_created=false及纠正输入的建议。失败退出码2，成功0。不把离线失败表述为运行失败/已取消，不提供可执行求解命令。

输出含明确未验证项：目标声明2024，但可访问参考手册2025；Runtime未验证、Solver语义未验证、资源/输出未占有、无真实执行能力。静态依赖完整结论仅限支持子集。源文件后续改变不更新已经取得/导出的预览；以后真实执行必须另行核验并批准新的精确计划。

导出只包含body中的声明、内容摘要和观察信息；不含输入字节、数据库、Runtime包、Grant/IPC秘密或结果证据。不提供通用匿名化（显式工程路径保留）。没有Artifact或Run。文件可离线审阅，但既不能作为当前文件状态证明，也不能当执行许可导入。

独立示例安装审计hook拒绝进程创建、SQL、网络连接及执行/旧模块导入。它是开发防误用检查，不是同OS用户任意shell条件下的安全沙箱。新增离线路径的单元测试也设置有效进程启动/默认路径陷阱；既有R2～R8固定测试进程按原授权正常运行，未撤掉旧启动陷阱。
