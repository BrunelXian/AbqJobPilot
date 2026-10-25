# Run020 — GUI 与 Python 用法

本轮新增产品Project创建和本机凭据交接，仍仅支持本地受限测试服务生命周期。没有自动Grant、任务提交、恢复派发或真实Solver启用。

## 正常 Dev 操作

1. 双击 `D:\Projects\abqjobpilot_dev\Open_Dev_GUI.vbs`。
2. 点击 **New Agent-first Project…**，在现有父目录内输入一个**不存在的新目录名**，再输入显示名称。取消不会创建；已有目录拒绝覆盖。
3. GUI显示Project名称/身份，Service **NOT_RUNNING**。此时无Grant、Run或Supervisor，初始派发PAUSED。
4. 点击 **Start Service**；认证成功后显示CONNECTED，空Run列表正常。
5. 关闭窗口，重新打开同一Dev入口；用“选择 Agent-first Project…”选刚创建的根目录，连接原owner。不会自动创建第二owner。
6. Disconnect只断开GUI；Reconnect重新核对身份。空闲时显式 **Stop Service**，确认后按原服务安全条件停服。之后显式Start保持PAUSED。

运行任务、Unknown、未决启动或资源保留时Stop会拒绝，不存在强制杀进程替代。发现旧owner不兼容、旧凭据、拷贝目录或格式不支持时明确BLOCKED；不要删除锁/凭据/意图来绕过。

Legacy按钮保持原队列界面；Legacy Project不会被自动升级。不要将新Project的内部SQLite交给Legacy打开。当前新Project不提供普通用户任务批准UI；固定Python的可信测试设置是开发验收步骤，不是New操作的默认行为。

## 公开 Python API

使用登记的 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`。本进程显式加入Dev源码路径，不安装或修改共享环境。以下是API用法，`chosen_new_directory`必须由调用者明确提供：

```python
import sys
sys.path.insert(0, r'D:\Projects\abqjobpilot_dev')
from abqjobpilot.product_project import create_project, open_project, inspect_project
from abqjobpilot.service_lifecycle import ServiceLifecycleManager

# 只有显式Create会新建目录；此时不启动服务。
manifest = create_project(chosen_new_directory, 'My Project')
manifest = open_project(chosen_new_directory)  # 只读完整身份/格式检查
manager = ServiceLifecycleManager(chosen_new_directory)
state = manager.inspect()                    # NOT_RUNNING
started = manager.start()                    # 调用者明确的生命周期操作
client, context, health = manager.connect()  # 同用户本机密文交接；不要打印内部凭据
page = client.project_view()                 # 空列表或最多32项
manager.disconnect()                        # 不停服务

# 只有操作者明确要求时：精确owner、稳定操作幂等键。
receipt = manager.stop(owner_id=client.endpoint['owner_id'], operation_key='my-explicit-idle-stop')
```

Start/Stop的operator capability与连接credential独立；文件由同用户Windows保护，原ExecutionGrant仍另行核验。代码摘要或已连接状态均不等于任务执行批准。

## 独立只读示例

`examples/agent_first/product_inspect.py`只使用公开Project/API和manager，默认/帮助/检查均无启动。可以从任意工作目录运行：

```powershell
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B 'D:\Projects\abqjobpilot_dev\examples\agent_first\product_inspect.py' --project '<自己明确创建的Project根>'
```

尖括号项是用户选择值，不是已验证的具体目录。实际验收使用的完整命令、临时目录与stdout由本目录测试证据记录；独立client在非仓库cwd认证、查询、断开及显式start复用已有owner已经Windows实测。未新增CLI/MCP写工具。

## 凭据、复制与错误

不要分享/归档 `private/`，即使文件是DPAPI密文。普通日志、GUI、公开状态和诊断导出均不包含其解密值。不要手工修改host_binding或原context。复制/移动/new host/new user需要未来显式重新配置；当前实现保守拒绝，不会关联源Project的owner。

| 原因码 | 处理含义 |
|---|---|
| PROJECT_EXISTS | 已有目标不覆盖；选择尚不存在的目录 |
| PROJECT_INCOMPLETE | 未完成创建保留供检查；打开不会修复 |
| LEGACY_PROJECT | 使用独立Legacy入口，不迁移 |
| NOT_AN_AGENT_FIRST_PROJECT | 普通文件夹，Open不初始化 |
| UNSUPPORTED_FORMAT / STORE_REQUIRES_MAINTENANCE | 不兼容/需维护，不隐式修复 |
| PROJECT_IDENTITY_MISMATCH | 目录、存储或实例不一致，拒绝连接 |
| LOCAL_CREDENTIAL_UNAVAILABLE | 主机/用户/密文保护不匹配，无明文fallback |
| START_UNCONFIRMED / START_BLOCKED | 启动结果或现有owner不确定，不重试创建 |
| SERVICE_NOT_IDLE | 当前不能正常停服，不通过杀进程补偿 |

测试数据位于本轮专属临时根。测试结束移除了测试私有连接材料；不要把保留的测试证据目录当可继续运行的演示Project。普通用户通过New新建自己的空Project即可使用上述入口。
