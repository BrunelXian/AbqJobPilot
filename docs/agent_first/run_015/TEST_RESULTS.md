# Run015 实际验证记录

环境：Windows，登记解释器 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python3.12.10、pytest9.1.0、SQLite3.49.1、Tk8.6。没有安装或升级依赖。Python全部使用绝对路径和`-B`；测试禁用第三方pytest插件自动加载。所有实验数据使用本轮新建Temp根，记录于各`*TEMP*.txt`。

## 执行与迭代

| 批次 | 结果 | 说明 |
|---|---|---|
| iteration_001 | 失败1 | 首次测试取证错误：请求事件页1000，超过已有IPC上限64；改为按原接口分页，没有放宽上限 |
| iteration_002 | 失败1 | 取证脚本误用`sequence`，实际字段为`project_sequence`；修正测试读取，没有改API |
| iteration_003 | 2 passed | 两任务、延迟后代真实Windows通过 |
| iteration_004 | 15 passed，37.97秒 | 新Windows范围、GUI、真实owner崩溃、故障注入整组 |
| regression | 382 passed，1 failed，512.38秒 | 15个相关测试文件、383项，唯一失败为旧静态依赖白名单未列新managed模块；原日志保留 |
| isolation_final | 9 passed，9.32秒 | 增加仅新模块所需ctypes/sys及list2cmdline白名单和严格原生创建断言；原Fake、客户端、诊断禁启动断言保留 |
| final_affected | 50 passed，98.93秒 | 最终证据发现本机快速场景含venv链累计24进程，修正新计划声明12→32后，重跑managed整组、原process_contract整组及managed产品入口；不声称这是OS硬限制 |

`FINAL_AUDIT_002.json`按测试classname/name合并后续重跑结果，保留每项来源，不将整批历史失败覆盖或说成一次383全通过。没有跳过关键场景，没有运行无关旧GUI/Solver测试或为了凑数重跑全仓库。

最终383个不同测试的最新结果全部PASS，跳过0。合并不是新的一次执行：完整回归382通过/1失败，相关修正后9项和50项分别全通过。`FINAL_AUDIT.json`是最终数量修正前的审计，保留为中间记录；`FINAL_AUDIT_002.json`是最终审计。

## 可复现命令

首次相关回归的命令内容如下（每次必须用新的`--basetemp`，不可复用已有证据目录）：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$taskTemp = Join-Path $env:TEMP ('AbqJobPilot_R15_regression_' + [guid]::NewGuid().ToString('N'))
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B -m pytest tests/test_execution_contract.py tests/test_execution_store.py tests/test_execution_ownership.py tests/test_execution_isolation.py tests/test_process_contract.py tests/test_process_fixture.py tests/test_recorded_exit_reconciliation.py tests/test_run_diagnostics.py tests/test_diagnostic_supervisor.py tests/test_execution_gui.py tests/test_standard_closeout.py tests/test_standard_backend.py tests/test_standard_supervisor.py tests/test_fake_reconciliation.py tests/test_managed_scope.py --basetemp $taskTemp -q
```

按文件数计量不构成覆盖结论。完整收集列表在`COLLECTED.txt`，每项结果在XML，风险映射在`ACCEPTANCE_MATRIX.md`。如需要保存新证据，给`RUN015_EVIDENCE_DIR`、`RUN012_EVIDENCE_DIR`和`--junitxml`提供新的明确目录/文件，不覆盖本轮文件。

## 证据与清理

- `verified_final/*.json`：服务原持久Run/事件、物理根创建记录及身份、直接Job计数、GUI状态、测试控制器持有的退出引用。测试控制器额外观察未回填服务证据。
- `gui_final/product_entries_managed.json`：实际独立产品入口、启动器退出、两项请求、原服务owner、公共事件和正常清理结果；非仓库cwd下运行。
- `FINAL_AUDIT_002.json`：新测试根的inventory/lifecycle、私有凭据删除、Job和根创建句柄关闭记录、只针对已登记PID+创建时间+镜像的最终只读检查。事后找不到身份不补成历史退出码。
- 故障用例仅对测试创建且身份已核实的owner作真实终止；worker通过固定屏障/期限自行退出。生产代码没有terminate路径，未按进程名操作其他Python。
- 正常运行的原生Job与根创建句柄由Backend关闭；owner崩溃的句柄由OS在进程退出时回收，未据此推断范围已空。实例重启仍阻断。
- 临时业务证据和日志保留，私有连接/bootstrap材料仅由原测试清理逻辑删除。没有删除历史Run010/011目录、尝试或输出。
- `BASELINE.json`中394份历史冻结文件/报告及原真实执行库的摘要复核均保持；没有管理旧owner，也未接触Stable。

本轮Abaqus调用0；原生创建审计哨兵只允许固定Python夹具命令、明确cwd与最小环境，保留默认Runtime/Recent/旧Runner访问陷阱。
