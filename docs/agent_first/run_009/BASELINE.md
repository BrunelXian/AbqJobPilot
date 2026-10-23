# Run009 基线及修改范围

唯一工作区 `D:\Projects\abqjobpilot_dev`；实际根一致，分支Develop，HEAD `fb7912ec9e0107b18f65948b147c87579c87cded`，版本`0.3.0.dev0`。开始/实现中Git只读检查无冲突、无tracked修改。R2～R8是前置未跟踪成果；R8 SOURCE_HASHES中的44个文件全部匹配，已在本轮临时根保存副本和哈希。见[BASELINE_HASHES.json](BASELINE_HASHES.json)、[BASELINE_STATUS.txt](BASELINE_STATUS.txt)。未要求工作区干净。

先查D:\AGENTS.md、D:\Projects\AGENTS.md、Dev AGENTS.md，仅Dev文件存在。读取实际环境登记、R8 FINAL_SUMMARY/USAGE/ACCEPTANCE_MATRIX/PUBLIC_CLIENT_CONTRACT及历史Run协议。沿用独立目录、逐项矩阵、JUnit、进程清理/哈希证据；run_009创建前不存在，未覆盖历史。没有递归扫描其他项目或访问Stable。

登记环境 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，本轮执行前实测Python3.12.10、pytest9.1.0、SQLite3.49.1、Windows11 build26300。所有命令绝对解释器；无安装/升级或模型依赖。pyc、pytest自动插件、cacheprovider关闭。独立客户端通过显式--source设置本进程导入路径，不修改共享环境。

本轮只新增独立离线模块 `abqjobpilot/abaqus_preview/{__init__,inputs,preview}.py`、`examples/agent_first/abaqus_offline_preview.py`、测试helper及两组测试、run_009文档。已有执行包、旧产品代码、应用版本、API/Project/实验库Schema及原测试全部保持。最终逐文件比较见CHANGE_SCOPE.json。

隔离根见[TEMP_ROOT.txt](TEMP_ROOT.txt)。新增测试只创建该根下合成INP和显式JSON。旧Fake harness继续保持其禁止INP规则：IPC拒绝测试的工程输入放在另一个明确临时子目录，没有弱化旧断言。所有输入只供离线解析，没有交给任何真实Solver或旧Runner。

单一写入主体；无并行修改Agent。没有Git切换、恢复、同步、commit/push。没有Abaqus命令（包括帮助/环境/许可证）、生产队列、生产Project、Stable、共享环境、系统服务或无关进程操作。官方手册网络读取仅作静态依据；未查询本机安装/许可。
