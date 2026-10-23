# Run 008 — 已验证的Windows公开客户端示例

范围是新建隔离实例、操作者预置的固定result_wait测试Plan。通用Job/Plan编辑、真实审批、真实Backend不在示例内。没有模型参与，不能称为真实AI Agent自主执行。

入口：[`operator_demo.py`](../../../examples/agent_first/operator_demo.py) 和 [`client_workflow.py`](../../../examples/agent_first/client_workflow.py)。两者都不依赖pytest、tests模块或手工SQL；共享环境无需安装项目。显式`--source`只对本进程设置Dev导入路径。

## 一次运行

操作者命令在非仓库cwd执行。以下模式已由独立进程集成验收执行；每次必须选择全新目录，已有目录拒绝覆盖：

```powershell
$pythonExe = 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe'
$sourceRoot = 'D:\Projects\abqjobpilot_dev'
$runRoot = Join-Path $env:TEMP ('AbqJobPilot_Run008_demo_' + [guid]::NewGuid().ToString('N'))
Set-Location $env:TEMP
& $pythonExe -B "$sourceRoot\examples\agent_first\operator_demo.py" --source $sourceRoot --root $runRoot
```

原始实际argv、cwd、返回码保存在本轮临时根full3对应测试的`example-invocation.json`，交付副本为[EXAMPLE_INVOCATION.json](EXAMPLE_INVOCATION.json)。例程内部的A/B也均使用该根下non_repository_cwd，不从仓库当前目录偶然导入。具体复现的JUnit入口：

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B -m pytest tests/test_public_client_example.py -q -p no:cacheprovider --basetemp='<全新显式临时目录>'
```

第二条是验收驱动模板，不能把占位符当作实际记录；业务示例不需要pytest。全量已执行命令及结果见[测试证据](TEST_AND_PROCESS_EVIDENCE.md)。

## 可观察的角色步骤

1. **可信操作者**建立新临时Project、TXT输入、Recent哨兵、固定解释器/fixture配置、Plan及一次专用执行Grant。close本地owner后显式启动Supervisor，交接私有bootstrap和连接材料。没有提前创建Run。
2. **客户端A**读取私有connection/offer，health→inspect_plan。先演示未登记Grant的GRANT_REQUIRED拒绝，再用已批准请求submit；保存session.json及原receipt/Run ID，退出。
3. **owner执行线程**启动固定四角色测试进程，与A连接/存活无关。result_wait让worker保持在有界等待中；操作者在A已退出后从公开Run取得身份并用OS引用额外证明worker未退出，仅用于验收/清理。普通客户端不依赖这些额外事实。
4. **操作者**释放固定夹具等待。服务自己通过保留OS句柄确认四角色退出并正常独立验证。操作者针对已完成Run的精确revision、Plan、当前owner签发一次独立验证ticket。该本地测试控制线程不是approve RPC。
5. **客户端B**读取原session/offer，取原receipt并重放submit；仅按公开Run判断FINISHED及退出已验证，分页读取事件；validate_run→同key再调用检查幂等→diagnose一次→export_diagnostic同对象。保存complete.json与diagnostic.json。
6. **操作者**请求自身owner停止，等待本轮进程、关闭持有句柄，删除私有bootstrap/setup/connection/offer/approval/ticket。保留非秘密审计文件，记录cleanup.json。客户端从不启动或结束owner。

两客户端实际命令结构如下，私有文件由操作者在有效阶段提供，完成后已清理，不能拿会话JSON当执行许可再次提交：

```powershell
& $pythonExe -B "$sourceRoot\examples\agent_first\client_workflow.py" --source $sourceRoot --connection "$runRoot\operator_private\connection.json" --offer "$runRoot\operator_private\offer.json" --session "$runRoot\client_session" --phase submit
& $pythonExe -B "$sourceRoot\examples\agent_first\client_workflow.py" --source $sourceRoot --connection "$runRoot\operator_private\connection.json" --offer "$runRoot\operator_private\offer.json" --session "$runRoot\client_session" --phase complete --validation-ticket "$runRoot\operator_private\validation-ticket.json" --export-root "$runRoot\exports"
```

## 输出与错误解释

client_session包含capabilities、Plan白名单、结构化rejection、原session/accepted/complete；exports仅diagnostic.json。客户端审计hook拒绝tests/pytest、store/service/owner/issuer/Backend、旧模块导入及SQL、进程启动，约束数据I/O临时根。连接/授权材料不得写会话或导出。

accepted.request_status与replayed只说明请求接受/重放；Run.execution、process_observation、exit_verification、backend_outcome、artifact_validation、solver_conclusion分开显示。测试结果COMPLETED和验证VALID不等于Abaqus求解成功；Solver始终NOT_RUN。观察是历史记录，不是客户端新探测。gate显示读取时持久化状态。

事件cursor是在显式验证之前取得；诊断随后包含新验证事件，两个读取时点分别标识，不伪装为同一事务。只有诊断对象与其导出是同一快照。导出可以离线审阅；不含原始Artifact、授权或整个Runtime，不是当前健康证明或可导入许可。

客户端错误仅输出稳定code、原key/Run和query-first建议。超时/EOF/连接故障不表示任务失败、取消或可换key重试。管理提交不确定时通过`management_receipt('validate_process_artifact', original_key)`确认，再按原请求重放；普通客户端没有自动Retry/对账/恢复逻辑。

示例只接受新建实例。重启暂停、不确定Run阻断等仍沿用R3～R7；不能用重跑本演示来恢复旧实例。owner的本地控制、启动审计和清理记录是操作者证据，不能被普通客户端当作服务退出证据。
