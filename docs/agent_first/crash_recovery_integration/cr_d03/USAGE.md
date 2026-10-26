# CR-D03 — 本地 Python 接口

仅供独立批准后的可信管理程序；本轮没有批准任何历史真实实例 Apply。以下变量必须来自显式选定的受支持 Project 和已取得的批准，不从 Recent 推断。

登记环境：`D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python3.12.10。调用者可进程级设置 `PYTHONPATH=D:\Projects\abqjobpilot_dev`，不安装共享依赖。

```python
from abqjobpilot.product_project import open_project
from abqjobpilot.service_lifecycle import ServiceLifecycleManager
from abqjobpilot.execution.recovery import preview_interrupted_recovery, verify_interrupted_recovery

open_project(project_path)                 # 显式格式/身份检查，不迁移
context = ServiceLifecycleManager(project_path).context
preview = preview_interrupted_recovery(context, run_id)  # 只读，无 OS 查询
# 不从 preview 生成 approved=true，不自动进入下一步。
```

可信操作者管理程序的独立步骤：

```python
from abqjobpilot.recovery_management import open_product_recovery
from abqjobpilot.execution.models import now

with open_product_recovery(project_path, run_id) as session:
    current = session.preview()  # 必须锁内重新审阅；外部preview不能替代
    request = session.authorize(
        current, subject=approved_subject, source=approval_reference,
        reason=approved_reason, expires_at=now() + 300,
        operation_key=original_operation_key,
        residual_risk_accepted=explicit_residual_acceptance,
    )
    # 调用者应在Apply前保留原request/key以便丢应答后查询，勿记录任何连接秘密。
    result = session.apply(request)

verification = verify_interrupted_recovery(context, request)
```

这段示例不包含默认 Project/Run/批准值，不是普通 Agent 远程批准入口。管理会话会更新自己的 owner/gate，因此不属于只读诊断。锁冲突、当前活动进程、无法查询、旧预览、过期授权、错误Project、热journal均停止；没有 terminate、删锁或强制参数。

丢应答：先调用 Verify 原request；NOT_FOUND/STORE_UNAVAILABLE不能自动解释为无效果，不能新建key/grant。确认原事务结果后，原request只能通过现有幂等规则返回原回执。没有新的Retry/Resume接口。

本轮已执行的测试命令形式（每次报告名不同，避免覆盖）：

```powershell
Set-Location 'D:\Projects\abqjobpilot_dev'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs/agent_first/crash_recovery_integration/cr_d03/run_safe_tests.py new new_final
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs/agent_first/crash_recovery_integration/cr_d03/run_safe_tests.py windows windows_final
```

报告名参数是短文件名前缀，不是路径。实际全部命令和结果见 TEST_AND_ACCEPTANCE.md / TEST_RESULTS.json。禁止对历史真实实例用本示例做测试。
