# Run 005 — 测试、Windows进程与三阶段导出

最终实际运行：**239 passed，0 failed，0 errors，0 skipped，118.04s**。原始[JUnit](TEST_RESULTS.xml)、[控制台输出](TEST_OUTPUT.txt)、[29文件源码哈希](SOURCE_HASHES.json)与[结构化进程证据](PROCESS_EVIDENCE.json)共同绑定本轮结果。

## 回归和迭代

| 测试模块 | 本次通过数 |
| --- | ---: |
| test_execution_contract | 56 |
| test_execution_store | 30 |
| test_execution_isolation | 9 |
| test_execution_ownership | 2 |
| test_fake_supervisor | 28 |
| test_fake_reconciliation | 61 |
| test_reconciliation_supervisor | 3 |
| test_run_diagnostics | 48 |
| test_diagnostic_supervisor | 2 |

Run004全部189个case身份逐项包含于本次239个PASS，保留此前断线、幂等、锁、领取、对账及恢复断言。新增50项不是预设数量；R5-01～12分别见[矩阵](ACCEPTANCE_MATRIX.md)。未运行旧GUI/Solver或生产数据测试。

| 迭代 | 实际结果 | 原因和修正 |
| --- | --- | --- |
| run1（新增组） | 32 passed，1 failed，10.80s | 诊断调用通过产物读取陷阱，但测试后独立inventory自身也被陷阱拦截。只在诊断结束后恢复Path.open以核验文件清单，未放宽诊断断言 |
| run2（全部相关组） | 228 passed，103.45s | 原189回归加新增39项，包括记录上限、快照和导出故障 |
| final（收尾前复验） | 235 passed，106.86s | 补5种持久记录错绑拒绝、真实PLAN_EXPIRED投影和导出清理失败；SQL读取截止也覆盖连接元数据检查 |
| verified（最终代码） | 239 passed，118.04s | 将manifest/meta/门也纳入诊断专用读取限额，新增4项超限拒绝测试；所有相关回归重新通过 |

四次各用新的basetemp，原始XML/文本保留在本轮临时根的run1/run2/final/verified对应文件中，没有清空前一轮或旧Run证据。本目录最终证据取自verified。

## 实测环境与进程清理

Windows-11-10.0.26300-SP0；登记解释器 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`；Python3.12.10（MSC1943 AMD64）、SQLite3.49.1、pytest9.1.0。无安装/共享环境修改。

最终32个多进程case共53个实际Python进程：前置回归49个，本轮新增两个case共4个。9次故障终止均持有预先核验的Windows进程HANDLE；全部实际进程handle signaled、启动器wait完成、句柄关闭。四次迭代共163条实际进程退出记录全部检查通过。

venv入口是注册解释器；它在Windows上通过redirector承载实际映像 `D:\Program Files\Python312\python.exe`。harness验证父子PID、creation_time_100ns和映像，再持有句柄；不凭PID数值重新查找并终止，不批量结束Python进程。关键新增流程：

| 角色 | 实际PID / 启动器PID | 创建时间100ns | 结果 |
| --- | --- | ---: | --- |
| 原owner | 12972 / 35672 | 134370770120579898 | dispatch:after_artifact屏障后通过持有句柄终止，退出77 |
| 重启owner | 13788 / 25004 | 134370770145873867 | 完成诊断/对账/恢复，测试stop后退出0 |
| 独立诊断客户端 | 1192 / 24212 | 134370770170006084 | 等待被屏障延迟的旧视图应答，完成后退出0 |

44个正常退出进程完成io.json路径/launch/default/legacy陷阱检查；9个真实故障终止进程不能运行finally，没有伪造完整IO日志。它们有绑定身份、到达屏障与文件清单检查。原launch/default Runtime/Recent陷阱均保留。

全部private-bootstrap.json/private-process.json在自有进程退出后删除；四次测试根均无这些文件残留。剩余多进程case文件经harness扫描不含真实连接credential，Recent哨兵保持不变，没有工程CAE/INP/JNL/ODB或旧project.db/queue/live_status。

临时数据库、日志、演示报告及故障测试中有意保留的audit_<uuid>.partial仍留作证据，不宣称整个临时目录被删除。该partial来自写入/清理双故障用例，没有发布目标，也没有成功回执；普通查询不清理它。

## 三阶段真实报告

原Run为 `r_d2a0f5ae8b544fb3991f41343449ca63`，三个文件均逐字节复制自客户端在临时独立audit_exports目录产生的最终导出，不重新生成或改写内容。

| 样例 | Run revision | 门 | 内容 |
| --- | ---: | --- | --- |
| [01_uncertain.json](examples/01_uncertain.json) | 2 | PAUSED/version3 | 已接受、START_INTENT、执行不确定、持久验证证据不足；没有当前文件检查 |
| [02_reconciled_paused.json](examples/02_reconciled_paused.json) | 3 | PAUSED/version3 | 显式对账与历史simulation PASS，门仍暂停 |
| [03_resumed.json](examples/03_resumed.json) | 3 | OPEN/version4 | 同Run/原回执/原对账事实，独立恢复后的门；没有再次执行原Run |

文件分别10,096 / 14,133 / 13,065字节。content_digest覆盖public body；完整文件SHA-256另见PROCESS_EVIDENCE的examples项。历史Plan/Artifact摘要保留为引用，并非重新验证。read_at是秒级，本次三个报告同秒读取，靠Run revision和门版本区分，不能只按时间判断先后。

流程使用dispatch:after_artifact与diagnostic:before_response确定屏障。第一次诊断完成读取后停在传输前，此时另一客户端成功显式对账，随后第一个客户端仍得到原不确定报告；不是混合新Run状态与旧事件。所有导出在随后状态已经改变后进行，仍与各自最初报告字节相等。

本地SQL并发测试还把读事务停在第一次Run读取后，让另一个实际连接更新Run/事件/门并进入待提交状态。读报告只有完整旧组合；关闭只读连接立即允许writer提交，下一报告才出现完整新组合。该测试不以假对象替代SQLite并发。

此实现审计文件保留必要的本机测试路径/进程身份，区别于三个面向调用方的诊断样例：样例没有绝对路径、环境、连接秘密或授权ID。这不是通用匿名化承诺。

## 可复现命令

在Dev根目录运行，始终选新目录，不复用已有basetemp：

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$r5TestRoot = Join-Path ([IO.Path]::GetTempPath()) ('AbqJobPilot_Run005_repro_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $r5TestRoot | Out-Null
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B -m pytest -p no:cacheprovider tests/test_execution_contract.py tests/test_execution_store.py tests/test_execution_isolation.py tests/test_execution_ownership.py tests/test_fake_supervisor.py tests/test_fake_reconciliation.py tests/test_reconciliation_supervisor.py tests/test_run_diagnostics.py tests/test_diagnostic_supervisor.py --basetemp="$r5TestRoot\cases" --junitxml="$r5TestRoot\results.xml" -q
```

只复现三阶段无GUI演示，把测试列表替换为 `tests/test_diagnostic_supervisor.py::test_windows_three_stage_diagnostic_export_and_detached_response`，使用另一个新根。case生成audit_exports三份JSON、diagnostic-demonstration.json、lifecycle.json和inventory.json，结束时清理自己的进程与连接凭据。此测试明确创建Fake实验和管理权限，不可拿生产Project路径替换。

本轮实际最终命令使用相同解释器/测试列表，basetemp为 `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run005_d82227bef89642dd8a467f514192cc74\verified`，JUnit为同根verified.xml；控制台保存verified.txt。未执行真实Abaqus、断电/内核崩溃或网络文件系统验收。
