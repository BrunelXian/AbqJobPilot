# Windows 工程师使用说明

本候选为源码目录 ZIP，不含 Python、Abaqus、许可证或执行授权。完整英文说明随包保存为 `DEPLOYMENT.md`。本轮只验证同一 Windows 11 用户下的两个现有 CPython 3.12.10 / Tk 8.6.15 环境，其他用户和主机尚未验收。

## 安装与启动

1. 将 candidate-004 ZIP 完整解压到新的可写目录；不要覆盖旧安装或 Project。
2. 准备已有的 64 位 CPython 3.12 和 Tk。在 `Open_Dev_GUI.vbs` 同目录的本地 `python-path.txt` 第一行填写绝对 `python.exe` 路径，不加引号。该文件是本机配置，不应随发布包分发。也可使用进程环境变量 `ABQJOBPILOT_PYTHON` 或应用专用 `.venv`，优先级和诊断详见包内说明。
3. 双击 `Open_Dev_GUI.vbs`。启动失败会显示诊断；不会自动安装依赖、启动 Supervisor、创建 Grant 或调用 Abaqus。

保留开发机 LangChainEnv 只是最后回退项，不是其他用户的部署要求。不要为运行本候选修改共享环境。

## Project、服务和监控

- New Project 指定独立新目录。创建后为空 Project、PAUSED，无 Grant 或 Run；外部 INP/CAE/ODB 不会被自动复制。
- Open Project 只打开明确选择的受支持格式，不迁移旧数据库。凭据与本机用户和 Project 绑定，不能把复制私有运行文件当成迁移。
- 在 Agent Command 的 Project & Service 区明确 Start Service，再连接。关闭 GUI 仅结束观察；后台执行独立存活。重开后重新选择相同 Project、认证连接并选择原 Run。
- Queue 在左、Results 在右。Current Run、日志和证据随选择更新；Results 不代表全部求解成功。进程退出、受管范围结束、Solver 与数值验证分别读取。断线缓存不代表实时状态。
- Stop Service 是单独操作，只有安全空闲、所有权和权限检查通过才允许。活跃、未知或待对账执行可能阻止停服；不要删除锁或强制结束进程。
- Classic Queue 和 Execution Workspace 可双向切换，保留各自格式、执行与授权边界。

## Agent 与恢复

独立 Python 客户端使用同一 Project 和公共服务。包内 `examples/agent_first/product_inspect.py --project <明确的产品Project路径>` 是只读检查示例，应由所选解释器运行。连接权限不等于真实执行授权。

CLI/MCP 的能力与 Python 执行服务并不完全等价：MCP 五个工具为既有格式的只读/预览能力；Legacy CLI 的显式入队不等于服务派发。不要把新执行存储交给不兼容的旧格式接口。MCP 需要额外的可选 SDK，缺失时不自动安装。

Crash Recovery 的 Interrupted (Unverified) 表示需要检查证据，不等于 Failed。诊断和 Preview 只读；Apply 需要精确可信授权，不会隐式 Retry、Requeue、Resume Solver 或打开派发。

## 能力和报错边界

真实支持仍限定于既有精确授权的 Abaqus 2024 Standard 固定模型及资源配置。本次不提供任意 Solver 授权或参数编辑，也没有在新宿主运行真实求解。English 默认，中文偏好保留，法德为 Preview。

启动、连接或所有权异常时，记录版本、错误代码及脱敏证据；保留原记录，不通过新 Project/新请求绕过未决启动。不要附认证文件、原始数据库或未审查日志。具体错误处理见包内 `DEPLOYMENT.md`。

不宣称支持任意分析模式、ODB 内容验证、跨机凭据迁移、注销/重启自动恢复、整机跨 Project 调度或自主 CAE 决策。Run 021B 的 NOT_OBSERVED、历史域外 UNKNOWN 及 ODB NOT_RUN 保持；历史凭据风险只是被限定接受，并未全局撤销。
