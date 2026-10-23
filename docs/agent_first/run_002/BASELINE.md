# Agent-first Run 002 — 实际基线

日期：2026-10-21，Asia/Shanghai。范围：Dev 内的单进程 Fake 内部服务、隔离测试及报告。指导文件为根 [AGENTS.md](../../../AGENTS.md) 与 [Run 001R 五份设计](../run_001_resume/FINAL_SUMMARY.md)，本次用户澄清优先于其中旧的开工条件。

## 开工事实与前置工作

| 项目 | 实际结果 |
| --- | --- |
| 目录 | `D:\Projects\abqjobpilot_dev` |
| 分支 / HEAD | `Develop@fb7912ec9e0107b18f65948b147c87579c87cded` |
| 已知设计源码基线 | `af3fd79667ef70693d616f7f8cfba9c5a7f5b21b` |
| 两提交差异 | 仅 Run 001R 的8个文档文件：AGENTS、英中 README、五份续审交付；`abqjobpilot/` 和 `tests/` 无差异 |
| 起始状态 | `git status --short --untracked-files=all` 与 `git ls-files -u` 均无输出 |
| 应用版本 | `abqjobpilot/__init__.py`：`0.3.0.dev0`，本轮不改 |

用户预期上一轮交付尚未提交；实际已进入 `fb7912ec...`。只读 `git log -3`、`git diff --name-status/stat af3fd796... HEAD` 和源码/测试差异确认这是前置文档提交，不是关键源码基线变化。因此依照本次“仅关键基线变化才停止”的澄清继续，并已向用户说明。该提交不是本轮创建的；本轮没有 Git 写入操作。前置8个文件保持不变。

开始时明确检查 `D:\AGENTS.md`、`D:\Projects\AGENTS.md`（不存在）及 Dev 根 AGENTS（存在并读取）；未递归扫描其他项目。读取 Run 001R 的 BASELINE、ARCHITECTURE_REVIEW、ADR_AND_CONTRACTS、MVP_ACCEPTANCE_MATRIX、FINAL_SUMMARY 全部内容及指定环境登记。`docs/agent_first/run_002` 起始不存在，故新建；历史目录不覆盖。

Stable 完全排除，未访问、扫描、比较、修改或启动。没有读取现有 Project、默认 Runtime/Recent、生产数据库或快捷方式；新代码也没有 legacy 模块依赖。

## 环境与命令边界

已读取 `D:\XianLab\envs\ENVIRONMENTS.md`。现有 requirements 声明普通应用使用标准库；MCP 为可选依赖，本切片不使用。沿用已登记 LangChainEnv，无安装或依赖变更。

| 实际检查 | 结果 |
| --- | --- |
| 绝对解释器 | `D:\XianLab\envs\LangChainEnv\Scripts\python.exe` |
| `sys.version` | Python 3.12.10，64 bit / MSC v.1943 |
| stdlib SQLite | 3.49.1 |
| pytest / iniconfig | 9.1.0 / 2.3.0 |

环境核验使用绝对解释器 `-I -B -c`，导入标准库并查询包元数据。测试使用绝对解释器 `-B -m pytest`、`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`、`PYTHONDONTWRITEBYTECODE=1`、`-p no:cacheprovider`。未运行旧测试集合或应用 GUI/CLI/MCP/Runner。

显式测试根：`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run002_253758f6191e4eb4a05bc1c31b099c77`，由本轮新建。三次运行分别使用新子目录 `run1`、`run2`、`final`，不复用/清空用户目录。测试输入只有 TXT，Fake 产物只有 JSON；Project、Runtime、Recent 哨兵及 DB/journal 均在对应 pytest 临时根内。

## 本轮变更边界

仅新增 `abqjobpilot/execution/` 9个模块、4个测试/测试支持文件、此 Run 报告与证据。旧 Settings、Datacheck、Runner、GUI、API/MCP、Project/history schema 均未修改；未增加执行入口到旧产品界面。

最终实现的精确文件哈希见 [SOURCE_HASHES.json](SOURCE_HASHES.json)。实测结果见 [ACCEPTANCE_MATRIX.md](ACCEPTANCE_MATRIX.md)，行为和限制见 [IMPLEMENTATION.md](IMPLEMENTATION.md)。
