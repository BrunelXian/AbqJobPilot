# Run 004 — 基线与前置修改

日期：2026-10-22（Asia/Shanghai）。唯一工作区 `D:\Projects\abqjobpilot_dev`，分支Develop，HEAD `fb7912ec9e0107b18f65948b147c87579c87cded`，应用版本0.3.0.dev0。

起始已跟踪文件无修改、无冲突；37个未跟踪文件均为Run002/003前置成果。Run003 SOURCE_HASHES.json中21个源码/测试全部与本地匹配，无无法解释的变化。本轮保留全部历史报告及前置成果，仅增量修改实验包和相关隔离测试。

已检查适用指令：D:\AGENTS.md、D:\Projects\AGENTS.md不存在，Dev根AGENTS.md存在并已读。已读Run001R ADR、Run002/003总结与验收矩阵、Run003协议和实现/测试，继续按独立Run目录保存证据。本目录起始不存在。

环境登记 `D:\XianLab\envs\ENVIRONMENTS.md`；实际验证绝对解释器 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python3.12.10、Windows-11-10.0.26300-SP0、SQLite3.49.1、pytest9.1.0。没有安装或修改依赖。

Stable完全排除；不读取真实Project、Runtime、Recent或数据库，不启动Solver/Datacheck/旧Runner，不执行Git写操作。仅本轮新建临时实验及可核验身份的Python测试进程。旧GUI、Runner、Project格式、MCP行为与应用版本不改；实验格式的新版本不迁移现存数据。

## 结束检查

分支/完整HEAD仍与起始一致，版本仍0.3.0.dev0。没有冲突、没有已跟踪文件diff，git diff --check通过。50个未跟踪文件由原37个前置文件加本轮4个新源码/测试、9个文档/证据组成；另对前置8个实验模块和2个测试支持文件作增量修改，没有清理或覆盖历史报告。

25个当前源码/测试哈希与最终测试快照一致；原125个case身份完整包含于189个最终PASS。15行R4验收、31处测试名引用、23个本地文档链接已检查，源码/文档行尾和代码围栏检查通过。Run002/003的JUnit与源码哈希文件保持原SHA-256：

| 前置文件 | SHA-256 |
| --- | --- |
| run_002/TEST_RESULTS.xml | 05319DDB3B4269096D61099F11FC87EAE703D788F702D4FD559C647FA4FC4EDA |
| run_002/SOURCE_HASHES.json | 097DF3F64D8564FB057E71BC6AE60610E0D23C7EFBB740ACFF8A395C9920B724 |
| run_003/TEST_RESULTS.xml | 783A74E169C267125ED4F4B4ACDA5745E58A3603BD6FF0C1B8EFAB3C1D8C4AEF |
| run_003/SOURCE_HASHES.json | F43E694277C849C641951A19E279BE6E84BF55213199FD5EB9B35E1E07C7CABA |

三次迭代共147条实际进程记录全部确认退出，最终一轮49条详细记录已导出；临时根内无private-bootstrap/private-process凭据文件残留。其余实验文件保留供审计。没有共享环境改动、后台残留或Git写操作。
