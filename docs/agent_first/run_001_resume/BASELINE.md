# Run 001R — Dev 基线与范围

日期：2026-10-21，Asia/Shanghai。性质：本地静态审查与设计交付。以当前 Develop 为唯一源码依据；不延续旧 main 基线、双版本审计或 Git 恢复工作。

## 起始核验

| 项目 | 实际结果 |
| --- | --- |
| 工作目录 | `D:\Projects\abqjobpilot_dev` |
| 分支 | `Develop` |
| 完整 HEAD | `af3fd79667ef70693d616f7f8cfba9c5a7f5b21b` |
| 起始未提交修改 / 未跟踪文件 | `git status --short --untracked-files=all` 无输出 |
| 未解决冲突 | `git ls-files -u` 无输出 |
| 应用版本 | `abqjobpilot/__init__.py`：`__version__ = "0.3.0.dev0"` |
| 正式目标版本 | `0.3.0`；不是本轮发布结果 |

上述 Git 读取使用 `GIT_OPTIONAL_LOCKS=0`。不查询远端，不操作分支或恢复备份。结束时的本轮 diff 检查用于确认变更范围，不开展第二次基线审计。

Stable 完全排除在本轮范围之外，未读取、扫描、比较、修改或启动其软件或数据；未审计 Stable 不是本轮缺口或阻塞。也未读取用户的现有 Project、Runtime、Recent、数据库、启动器或快捷方式。本轮关于路径的结论来自 Dev 源码，不代表某个现存安装或 Project 的运行配置已核实。

## 指引、Run 约定与既有成果

- 开始时逐一检查 `D:\AGENTS.md`、`D:\Projects\AGENTS.md`、Dev 根 `AGENTS.md`，均不存在；没有递归扫描其他项目。用户提供的 Python Environment Policy 适用，本轮新增 Dev 根 [AGENTS.md](../../../AGENTS.md)。
- 已读取 `D:\XianLab\envs\ENVIRONMENTS.md`；本轮未运行 Python、导入应用包或检查共享环境依赖，因此不宣称重新验证了任何解释器。后续 Python 测试应按登记和项目要求重新核验绝对解释器路径；历史 Run 中旧 `envs/conda/LangChainEnv` 路径不能直接照抄。
- Dev 文档中已有 Run 使用 `docs/mcp/run_NNN` 分轮保存 BASELINE、专项证据、FINAL_SUMMARY 等。已读取 [Run 001 协议与安全证据](../../mcp/run_001/PROTOCOL_AND_SAFETY_EVIDENCE.md)、[Run 006 总结](../../mcp/run_006/FINAL_SUMMARY.md)及[本地 publication handoff](../../mcp/run_006/FINAL_CLEAN_PUBLICATION_HANDOFF.md)。它们是历史证据，不是本轮 Git 操作授权，也不是当前测试结果。
- Agent-first 已有文件仅 [原 ADR_AND_CONTRACTS.md](../run_001/ADR_AND_CONTRACTS.md)。已完整读取；其旧 main 基线及正文保留不动。该目录没有 BASELINE、ARCHITECTURE_REVIEW、MVP_ACCEPTANCE_MATRIX 或 FINAL_SUMMARY；旧草案指向这些不存在文件的链接作为历史缺口记录，不补写或改造旧证据。
- 原 ADR SHA-256：`7254F40818A9957AAF92D953FAD3AFFA65B34EB0814AC1AC6DE9ACA0804DA124`。
- `docs/agent_first/run_001_resume` 起始不存在，采用用户指定续审目录，不覆盖旧 Run。

## 版本与当前 Dev 能力边界

| 入口 / 声明 | 静态证据与判断 |
| --- | --- |
| 版本唯一来源 | [__init__.py](../../../abqjobpilot/__init__.py)，当前已是 `0.3.0.dev0`，本轮不改源码 |
| GUI About | [gui_app.py](../../../abqjobpilot/gui_app.py) 导入 `__version__`；About 标签及 `.dev` 开发版本标识引用它 |
| CLI capabilities | [api/cli.py](../../../abqjobpilot/api/cli.py) 调用 `client.capabilities()`；[api/client.py](../../../abqjobpilot/api/client.py) 返回 `application_version=__version__` |
| MCP Server | [mcp/server.py](../../../abqjobpilot/mcp/server.py)::`build_server` 使用 `version=__version__` |
| 版本断言 | [test_a4_project_automation.py](../../../tests/test_a4_project_automation.py)::`test_version_capabilities_and_json_errors` 已断言 `0.3.0.dev0`；本轮未执行 |
| README 当前 Develop 文案 | 英中各两处由 `0.2.2.dev0` 更新为 `0.3.0.dev0`，增加设计尚未实现/真实验收未完成说明 |
| Schema | `config.SCHEMA_VERSION="1.0"`、Project manifest `PROJECT_SCHEMA_VERSION="1.0"`、history DB `migrations.SCHEMA_VERSION=1` 均不改；新实验协议只在设计中命名 |

入口一致性是源码连线检查，不是 GUI、CLI 或 MCP 运行验收。历史记录旧版本号保留。向正式 `0.3.0` 晋升须有后续明确发布范围、相应实施与回归证据、完整模拟服务验收及计划支持的真实 Abaqus 能力验收，另行授权发布/Stable 晋升；只完成 Run 002 不足以晋升。

## 证据等级与检查方法

本轮事实为本地文件、函数、调用点和测试源码静态证据。功能实现、限制、目标设计、未来实机验证在 [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md) 分列。未将旧测试计数（包括历史 250 passed / 1 skipped）记作本轮通过结果。

实际执行仅 PowerShell 文件读取、`rg` 搜索、只读 Git 状态/差异、哈希及文档检查；新增/修改 Markdown。未运行 pytest、GUI、CLI capabilities、MCP server、Runner 或 Abaqus，未打开数据库。不存在本轮 SQL 查询、WAL 处置、数据库初始化或迁移。

交付导航：[架构复核](ARCHITECTURE_REVIEW.md) · [ADR 与冻结契约](ADR_AND_CONTRACTS.md) · [分层验收矩阵](MVP_ACCEPTANCE_MATRIX.md) · [总结与 Run 002 指令](FINAL_SUMMARY.md)。
