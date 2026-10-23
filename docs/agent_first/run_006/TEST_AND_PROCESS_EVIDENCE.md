# Run 006 — Windows进程、故障与清理证据

最终 **293 passed、0 failed、0 errors、0 skipped，175.29秒**（JUnit 175.228秒）：原R2～R5的239项全部重新通过，新增34项进程契约测试和20项Windows集成测试。逐项场景见[验收矩阵](ACCEPTANCE_MATRIX.md)。本轮不是纯Fake或异常模拟：真实启动登记解释器、固定launcher/worker及Windows虚拟环境转发器；owner故障使用已核验且保留的实际Python进程句柄TerminateProcess。

目标系统实测Windows 11 build26300、Python3.12.10 64位；详情见[环境记录](ENVIRONMENT.json)。最终52个多进程case记录82个owner/client实际Python进程，以及21次固定Backend物理启动对应的84个fixture角色进程。另有owner/client外层venv启动器，均已Popen.wait完成，不把启动器PID误当实际Python PID。全部82个owner/client句柄确认信号退出，84个fixture角色取得退出码并关闭句柄；18次owner/client故障终止与16次fixture清理终止均限已核验的本轮句柄。最终私有凭据文件残留为0。

## 证据分层

- **服务持久事实**：原Run/phase_attempt_id、START_INTENT、process_records、逐个process_exits、状态revision、ArtifactObservation/Validation与派发门。before_create和after_create均可能无进程身份；这不说明从未启动。before_exit_record可能已经物理退出而库内仍无退出记录。
- **控制器额外观察**：每次允许的真实Popen返回后独立OpenProcess登记启动转发器PID/创建时间/映像；从受限握手候选核对并持有四个角色句柄；分别观察owner已退出、worker是否仍存活及真实退出码。该数据没有提供给新owner来补全缺失记录。
- **清理事实**：只操作本轮登记且通过OS核验的保留句柄；等待退出、记录码并关闭句柄。用户其他Python进程不参与。控制器清理不产生ReconciliationRecord，也不把未知Run标成功。

最终[PROCESS_EVIDENCE.json](PROCESS_EVIDENCE.json)保存这些层次的白名单汇总，七个真实owner崩溃窗口分别列出服务前后状态及控制器额外观察。原始各case的lifecycle.json、fixture-lifecycle.json、physical-launches.json、crash-evidence.json、inventory.json与io.json留在[TEMP_ROOT.txt](TEMP_ROOT.txt)指定的独立临时根。

启动次数不靠result.json数量推断：物理启动登记与实际launcher_transport身份对应，每个已启动Run仅一条登记；固定脚本只产生一个worker，四个角色的实际身份/创建时间/退出互相核对。before_create有0次物理启动，after_create与各后续崩溃窗口各1次，重连和重启不增加。

## 迭代记录（保留失败，不覆盖）

| 执行位置 | 实际结果 | 处理 |
| --- | --- | --- |
| smoke | 1 failed，1.74s | 真实正常生命周期已完成；新增测试把events列表误当字典，修正测试读取方式 |
| run1 | 10 passed、2 failed、2 teardown errors，25.40s | harness轮询endpoint与Windows原子替换竞争；改为明确owner-ready握手。清理观察与进程自然退出竞态改为等待保留句柄确认。终态事务内屏障阻塞后续submit，改为事务外明确的before_terminal窗口；事务故障仍单独保留测试 |
| run2 | 47 passed、2 failed，54.88s | 第二Run的launcher已退出后无法新取得映像查询证据，测试不放宽身份断言；新增可重复身份屏障，让控制器在退出前持有每个句柄 |
| run3 | 50 passed，37.52s | 新进程/授权组及原9项隔离组通过 |
| full1 | 283 passed，179.91s | R2～R5原239项及当时44项新增全部重跑通过 |
| final | 290 passed，200.33s | 增补未持久退出、实际启动登记、缺历史诊断、严格产物类型/重复键与退出码读取失败 |
| verified | 291 passed，195.20s | 补充无效受信任配置关闭owner锁，以及审计读取路径正确区分临时数据与允许的只读解释器/夹具文件；36个源码/测试哈希在本次执行期间保持一致 |
| release_check（最终交付） | 293 passed，175.29s | 补充领取后、实际创建OS进程前的Plan/Grant/输入/解释器再次核验；启动延迟期间Grant过期或输入改变均在有效Popen trap下拒绝。最终源码哈希和交付JUnit绑定本轮 |

run1有一条未走完自动teardown的owner由补充控制器按原identity.json重新核验并终止；补充结果保存在run1/supplemental-cleanup.json。run2补查没有仍存活且身份匹配的目标，也无私有凭据残留。早期缺保留句柄的已结束进程不补造退出码：补查明确标PROCESS_IDENTITY_UNKNOWN/无法重新确认。各轮最终只读补查见[ITERATION_CLEANUP.json](ITERATION_CLEANUP.json)，不存在匹配的存活目标或私有凭据文件；其中候选身份包含负面测试故意构造的创建时间，不可当作物理启动计数。最终验收重新执行所有场景并在退出前持有完整句柄，不能用早期补查冒充完整退出证明。

## 路径和秘密边界

实验输入/输出、manifest/SQLite、故障屏障和控制器登记均在每case显式临时根；固定解释器和Dev夹具源码是允许的只读执行对象，不把它们误标为临时数据。io.json分别列出临时数据访问与trusted_read_only_execution_objects；所有写入数据都限临时根。默认Runtime/Recent/旧模块导入陷阱继续有效。

独立测试入口保留原Popen/os启动trap，仅对ProcessFixtureConfig存在时启用精确白名单：绝对登记解释器、固定脚本、固定flags/角色/Run目录、shell=False、close_fds=True、精确环境键。原Fake路径不能经过这条能力。环境秘密哨兵不会传入launcher/worker；连接秘密不写fixture manifest或诊断导出。退出后删除本轮private-bootstrap.json/private-process.json，临时非秘密证据保留。

没有修改系统Job Object或外部进程约束。目标Windows实测worker能够在owner退出后继续存活，新owner随后取得原锁而仍暂停；不将这些结论推广到其他宿主、文件系统、任意进程树或真实Solver。

## 可复现命令

从Dev根执行，每次创建新临时根，不复用已有basetemp。先按AGENTS重新核对环境登记。

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$r6TestRoot = Join-Path ([IO.Path]::GetTempPath()) ('AbqJobPilot_Run006_repro_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $r6TestRoot | Out-Null
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B -m pytest -p no:cacheprovider tests/test_execution_contract.py tests/test_execution_store.py tests/test_execution_isolation.py tests/test_execution_ownership.py tests/test_fake_supervisor.py tests/test_fake_reconciliation.py tests/test_reconciliation_supervisor.py tests/test_run_diagnostics.py tests/test_diagnostic_supervisor.py tests/test_process_contract.py tests/test_process_fixture.py --basetemp="$r6TestRoot\cases" --junitxml="$r6TestRoot\results.xml" -q
```

仅复现无GUI真实进程演示，可将测试列表替换为 `tests/test_process_fixture.py`。正常完成和owner崩溃各参数case自动生成原始独立观察、清理记录和exports/*.json；不是可供任意命令调用的通用启动器。

交付示例：[正常完成](examples/normal.json)、[owner崩溃后阻断](examples/owner_crash_blocked.json)。它们是历史数据库快照，未复制原产物字节、未重新探测进程或验证文件、不包含可执行授权；白名单投影摘要不是可信签名。正常例可同时查看进程退出和Artifact PASS；崩溃例保持UNKNOWN及PAUSED，不借控制器掌握的额外证据宣称业务完成。
