# 隔离验证与 Windows 验收

本次使用已登记的 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe -B`，Python 3.12.10、Tk 8.6、pytest 9.1.0。未修改环境。每批次设置独立 TEMP/TMP、HOME/USERPROFILE、Runtime/Recent，并关闭 pycache、pytest 插件自动加载及缓存。Runner 限制写入本轮临时根和报告目录，禁止真实 Abaqus 启动入口。

## 结果与失败迭代

**225 个唯一测试最终 PASS；最终 FAIL=0、SKIP=0。** 以 JUnit `classname::name` 去重，参数化项分别计数，同项复测不叠加。各批次、完整用例名、首次失败见 [TEST_RESULTS.json](TEST_RESULTS.json)；实际 XML 和每批次 `*_ROOT.json` 原样保留。

首次 `regression_01` 是 125 PASS / 1 FAIL 后停止。`test_dependency_graph_excludes_all_legacy_and_launch_modules` 断言进程 `sys.modules` 不含 `abqjobpilot.config`；同一批次先运行的 GUI 用例已经合法导入该模块。失败是选集混用造成的导入隔离冲突，不是执行核心新增依赖。原失败 XML 保留。独立 interpreter 的 `isolation_01` 9/9 通过，后续未执行的 MCP 部分以 `api_01` 11/11 通过；没有放宽断言或修改核心。Runner 现在明确将 import-isolation 与 GUI 分批。

覆盖：显示语义、真实双 Run 选择、GUI/公共 IPC、Project 身份与分页、只读诊断及 Recovery Preview、受管范围与正常收尾、TEST_ONLY/执行依赖隔离、MCP 只读边界、Classic 主要流程、四语言与原生导航、分隔条、Follow latest、横向滚动、断线缓存和旧选择丢弃。未重新运行整个历史 768 项选集；未执行 Abaqus、真实恢复、系统 DPI/注销/重启或历史 owner 操作。

## 实际 Windows 进程证据

最终生命周期证据：[NATIVE_EVIDENCE.json](evidence/NATIVE_EVIDENCE.json)。

| 项目 | 实测 |
|---|---|
| Run | `r_f8f9585b56c449b2a84b0aacbc4557ce` |
| 回执 | `req_77d66cb609714847bf3885185c0d37e6` |
| 原 owner | PID 18856；creation_time_100ns 134374689755492220 |
| worker | PID 26504；creation_time_100ns 134374689760761156 |
| 第一次 GUI / venv 启动器 | PID 18532 / 28000；均通过保留 Windows 句柄取得 exit=0 |
| GUI 退出后 | 原 owner 身份一致，原 worker 句柄仍存活，progress sequence 增长 |
| GUI 重开 | 同一 Run、回执、owner；物理任务启动一次 |
| 只读观测 | GUI 打开/导航/重连期间 Store hash 与 Run/回执/门/事件/验证保持一致 |
| 最终 | FINISHED；COMMITTED_EMPTY_SCOPE；Artifact VALID；Solver NOT_RUN |

这些证据来自正常产品 `run_gui.main` 与原生 Tk 窗口，使用测试专属控制通道操作真实窗口；不是原型数据、隐藏窗口或仅函数返回。GUI 按 WM_CLOSE 正常退出；固定 Python worker 经自身释放条件完成。另一个隔离实例验证两条真实 Run 的 Results/Queue 选择、Current Run、双日志、Evidence 联动，见 [SELECTION_EVIDENCE.json](evidence/SELECTION_EVIDENCE.json)。

这次 Python 测试不验证 Abaqus、ODB 或所有域外进程。历史完成记录不会因为被选中而表示为正在运行；界面明确显示记录快照，连接状态与 Run 阶段分别呈现。

## 测试收尾与复现

本轮共 21 个独立测试根保留，未做递归删除。`CURRENT_TEST_CLEANUP.json` 列出准确路径、184 个已记录身份的只读观察，以及 28 份夹具收尾 inventory：全部报告自身进程退出、临时凭据移除且余留文件不含其连接秘密；未发现遗留 `gui-private-connection.json`、`private-process.json`、`bootstrap.json`。GUI/venv 实际退出句柄证据另在 NATIVE_EVIDENCE。当前进程查询没有匹配存活身份；PID 不存在不被当作历史完整退出证明。

故障测试仅操作自己创建并持有身份句柄的替身。旧 45 个目录与历史 owner 均不是这些清理操作的对象。

从 Dev 根运行下面入口，使用新的报告批次名以保留本轮结果：

```powershell
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs/agent_first/run_024r/final_acceptance_001/run_safe_tests.py semantics review_semantics
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs/agent_first/run_024r/final_acceptance_001/run_safe_tests.py native_windows review_windows
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs/agent_first/run_024r/final_acceptance_001/run_safe_tests.py isolation review_isolation
```

这些是复现说明，不安排自动后续运行。全体截图均来自此次实际窗口、原始像素尺寸，摘要与来源已保存。
