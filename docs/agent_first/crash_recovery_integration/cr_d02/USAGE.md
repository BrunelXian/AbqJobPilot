# CR-D02 — 内部与Python只读接口

解释器：`D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，本轮核验Python3.12.10、pytest9.1.0。无需安装依赖。不要使用默认Recent或GUI选中Project推断目标。

```python
from abqjobpilot.service_discovery import project_identity
from abqjobpilot.execution.interruption import inspect_interrupted_execution

context = project_identity(explicit_project_directory)
report = inspect_interrupted_execution(context, explicit_run_id)
# 单独、明确的可选当前OS查询；无启动、接管或控制。
observed = inspect_interrupted_execution(context, explicit_run_id, observe_os=True)
```

上面的变量由调用者明确指定，是接口示例，不是本轮对历史真实Project执行过的命令。`project_identity`读取显式manifest/物理身份；不调用 `discover` 或 `ServiceLifecycleManager.start`。产品根和实验Project根均沿用原格式识别；Classic Project、不兼容格式、移位/损坏身份安全拒绝。

已有内部调用者也可以使用：

```python
from abqjobpilot.execution.store import open_existing_read_only
reader = open_existing_read_only(context)
report = reader.inspect_interrupted_execution(context, explicit_run_id)
```

两个入口调用同一分类器。纯函数 `build_interruption_report` 是内部测试接缝；生产调用不接受自报owner死亡、boot变化、scope完整或approved字段。当前接口无需活跃owner；它读取现有执行Store，不启动一个owner来解释历史。

## 输出与保存

返回普通JSON结构；见 DIAGNOSTIC_CONTRACT.md。诊断不写报告文件。调用者若需保留，应将这一个已生成报告写到**显式、隔离、no-overwrite的审计目标**，不重新查询后冒称同一快照。示例：

```python
from abqjobpilot.execution.models import canonical_json
with explicit_new_audit_json.open('x', encoding='utf-8') as stream:
    stream.write(canonical_json(report))
```

写文件是调用方显式导出行为，不是Inspect副作用。新报告不冒充旧 `af-run-diagnostic-v1/v2/v3`；不要传入原 `client.export_diagnostic`，该旧白名单仍应拒绝新版本。现有diagnose及其导出功能不变；CR-D04如需统一导出，应新增明确版本支持及白名单测试，不打包原数据库/Runtime/凭据。

## 本轮实际验证命令

以下命令在Dev工作目录运行，驱动自动建立新隔离根，写入报告目录；已有报告不能覆盖，复现须指定新报告名。

```powershell
Set-Location -LiteralPath 'D:\Projects\abqjobpilot_dev'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs/agent_first/crash_recovery_integration/cr_d02/run_safe_tests.py new new_final
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs/agent_first/crash_recovery_integration/cr_d02/run_safe_tests.py isolation isolation_current
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs/agent_first/crash_recovery_integration/cr_d02/run_safe_tests.py regression regression_iteration_02
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs/agent_first/crash_recovery_integration/cr_d02/run_safe_tests.py product product_final
```

后续实际批次以 TEST_RESULTS.json 和 TEST_AND_ACCEPTANCE.md 为准。驱动不是产品CLI，不接受真实工程命令；Windows子进程只走固定测试夹具，Standard创建接缝替换为固定普通Python。新增接口未接入IPC/CLI/MCP/GUI；这是CR-D01规定的D02边界，不表示现有Python IPC客户端已经有同名RPC。
