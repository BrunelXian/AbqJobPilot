# Run017 — 实际回归与发布门槛

## 环境和选择

已读 `D:\XianLab\envs\ENVIRONMENTS.md`，使用 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python3.12.10、pytest9.1.0、SQLite3.49.1、Tk8.6、Windows NT10.0.26300。未安装/升级依赖。设置PYTHONDONTWRITEBYTECODE、关闭pytest自动第三方插件和cacheprovider；TEMP/TMP、pytest basetemp、证据目录均显式指向本轮新临时根。

- 主测试根：`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run017_k6v6ayui`
- legacy/格式测试根：`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run017_legacy_smt5x6p_`
- 第二批在导入前为本进程显式替换Path.home及config runtime；ProjectManager每项明确recent_file。未把GUI当前Project或默认Recent当目标。

## 静态副作用审核

Fake组`execution_helpers.guard_environment`阻止外部启动/legacy导入/默认home访问；子进程组`supervisor_helpers.ProcessHarness`绑定新根、固定Python和身份句柄。真正故障终止只针对夹具新建且已核验的句柄，不按名称结束进程。测试结束等待退出、关闭句柄、移除自身private材料，保留业务证据。

Standard单元组替换`_launch`并阻止Popen；Windows组`tests/run013_process.py`使用固定普通Python worker，historical DAT是显式离线样本；`run016_process.py`替换`ManagedScope.create_standard`的目标为登记Python+固定脚本，保留真实JOB_LIST路径并用audit hook拒绝真实入口/无管理回退。没有调用Abaqus帮助、版本、许可、Datacheck、Solver、CAE、Viewer或Abaqus Python。历史样本从Dev已有 `ORIGINAL_DAT.bin` 读取，没有打开历史ODB。

GUI组仅对本轮创建、HWND归属和进程身份已核实的GUI发WM_CLOSE；验收真实GUI进程/venv退出、owner/worker继续与重连。现有Run016 owner和GUI不在测试目标/清理集合内。

legacy native evidence组使用FakeProcess及模拟读取/身份，不启动真实Runner子进程；retry preparation组是临时INP/被动监视模拟。它们与AF隔离测试同进程收集造成一次断言污染，见下文；不是实际启动了Solver。

## 结果与去重

| 批次 | 收集/执行 | 结果 | 证据 |
|---|---:|---|---|
| 主选择，显式28文件（含两个旧Run006命名测试） | 590/590 | 589 PASS、1 FAIL、0 SKIP；619.42秒 | initial.xml、INITIAL_TEST_LOG.txt、TEST_SELECTION.json |
| 干净进程重测execution_isolation | 9/9 | 9 PASS、0 SKIP；2.14秒 | isolated_recheck.xml、ISOLATION_RECHECK.txt |
| legacy API/MCP/Project + 新格式拒绝 | 57/57 | 57 PASS、0 SKIP；26.38秒 | legacy.xml、LEGACY_TEST_LOG.txt、run_legacy_audit_tests.py |

总执行656个case，其中重测9个。按`classname::name`去重、保留每个case最后实测结果：**647个唯一case均PASS，0最终FAIL/ERROR/SKIP**；首次1个失败保留，不能声称首轮一次全绿。完整ID、批次及结果见 [TEST_RESULTS.json](TEST_RESULTS.json)。R16的355和更早阶段数字使用不同选集，不能与本次总数直接相减判退化。

失败原因：`tests/test_run006_native_evidence.py:11/19`在pytest收集时导入legacy config/runner；`test_execution_isolation.py:84`要求本进程无legacy模块。静态依赖图和所有其它行为断言仍通过；新进程独立执行原9项全部通过。没有删/改旧断言，没有修改应用源码。后续按导入隔离性质分进程运行，禁止把legacy收集混入AF“未导入legacy”的测试进程。

新加2项是有实际文件比较的格式边界测试：legacy读取AF拒绝、AF读取legacy拒绝，前后文件摘要不变且不生成对方数据库。不是重复比较实现生成字段。

## 实际覆盖与未执行

- 受影响核心：接受/提交幂等、原子领取、TEST_ONLY与真实能力类别隔离、Plan失效、同owner/跨owner、只读失败/分页/超限、诊断白名单/导出、Fake与记录退出对账、事务故障/丢应答、closeout与PAUSED/隔离、托管Job自动收尾、固定A→B窗口、IPC响应、GUI退出重连/owner真实崩溃均有本轮结果。
- legacy侧：本轮MCP11、Project模型10、DB9、所有权8、queue-only7、PythonAPI10，以及新格式2。API/CLI全部命令未完整重跑；MCP含有界stdioSDK及缺失SDK子进程测试。capability标记不能将这一子集扩大为全GUI旧流程已产品化。
- 未运行文件：test_a4_project_automation、test_agent_command_console_ui、test_agent_project_session、test_automation_surface、test_command_parser、test_g2_5_project_multiselect、test_g2_task_workspace、test_gui_table_state、test_parsers、test_probe_preparation、test_process_identity、test_project_data_defaults、test_project_gui、test_queue_store、test_recent_projects、test_recovery_workflow、test_runner_core、test_runtime_coordination；以及TestPublicCli类和历史docs内控制器测试。它们不在本次主要变更范围；部分旧测试涉及默认Runtime/GUI，需要另做完整隔离证明，未将其失败/跳过隐去。
- 不执行真实Solver/真实任务、ODB内容、生产迁移、Stable、关机/注销/终端关闭/服务安装测试。历史实机报告仅作为历史证据。

## Windows进程与清理

[TEST_CLEANUP.json](TEST_CLEANUP.json)包含132份harness清理inventory、181条生命周期记录及9份native cleanup：对应退出/凭据核验均通过（其中6条独立示例采用`exit_source=retained_windows_handle + handle_closed`格式，其余采用`actual_process_handle_signaled/exited`；汇总脚本按两种已有格式读取，不修改原证据）。私有目录剩余文件0，inventory验证凭据不出现在剩余文件。

对本轮新测试JSON中记录的687个唯一PID+创建时间+映像再次进行只读核验：682个无法打开原对象、5个PID已不匹配原身份，**未发现身份匹配的存活进程**。这些事后结果不反向补写历史退出；历史退出证据来自测试当时持有的OS句柄。audit不终止任何进程、不删除文件。范围只到本轮登记对象，不进行全机Python扫描。

本轮Windows证据保留在 [windows_evidence](windows_evidence)：managed_scope顺序/多级/瞬时后代、owner崩溃、替身Standard序列、closeout停服/重启、实际GUI等。测试故障注入有明确标记，不冒充真实Abaqus。临时业务DB/输出保留用于核验，未递归清理；旧被拒绝删除目录保持不动。

## 可复现命令

以下为本轮实际入口。不要再次指定同一basetemp或证据文件覆盖本轮材料；复测先创建新临时根和输出编号。实际主选文件清单在TEST_SELECTION.json。

```powershell
# 当时：TEMP/TMP/RUN012_EVIDENCE_DIR至RUN016_EVIDENCE_DIR均已设置到本轮新根。
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider --basetemp '<新临时根>\cases' --junitxml '<新临时根>\regression.xml' <TEST_SELECTION.json中的显式文件>
# 隔离断言必须单独干净进程（不要与legacy模块一起收集）。
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B -m pytest tests/test_execution_isolation.py -q -p no:cacheprovider --basetemp '<新临时根>\isolation'
# 此入口内部使用mkdtemp，每次生成新根：
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs/agent_first/run_017/run_legacy_audit_tests.py
```

带尖括号的是明确参数说明，不声称可直接粘贴。日志保存的实际根与完整选集才是本次执行证据；没有给用户一个默认会提交真实实验的复现脚本。

## Dev检查点与0.3.0门槛

当前可以进入**审查后的Dev检查点准备**，不能直接发布/晋升。检查点的拆分与资产风险见基线文档；本轮无commit/push。

| 门槛 | 当前结论 |
|---|---|
| 执行核心基线 | 本轮相关回归通过；一次选集污染已解释并独立复核；未确认P0 |
| 默认产品启动/发现 | 未实现，Run018优先；不应把VBS示例当最终产品 |
| Project生产兼容/迁移 | 新旧分离；未做生产迁移、复制后权限处理产品化 |
| 真实批准与配置 | 固定可信入口，不是完整人类审批；硬编码单机Runtime需后续审查 |
| 主机资源/跨Project/legacy冲突 | 尚无全局协调；新旧执行权威混用需严格限制 |
| Abaqus支持矩阵 | 仅已记录固定2024 Standard轴向杆、CPU1/GPU0、2048MB；不推广其它模式 |
| 进程域与系统生命周期 | 当前Job范围已测；外部服务/注销/重启/遗留监控接管未验收 |
| 结果验证 | 三项DAT有历史实测和离线回归；ODB内容仍NOT_RUN |
| 发布质量 | 完整用户入口、依赖/安装可复现、敏感材料筛选、文档一致性、干净发布候选及最终测试还需单独完成 |
| Stable晋升 | 单独授权、单独验证；本轮完全未访问 |

因本轮只改文档和测试，不重跑真实分析，不改变权限/状态机来提高表面PASS率。下一阶段任何核心改动必须保持这里列出的原始证据、失败与恢复边界。
