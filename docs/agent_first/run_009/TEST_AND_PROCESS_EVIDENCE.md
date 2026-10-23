# Run009 实际测试与隔离

环境见[ENVIRONMENT.json](ENVIRONMENT.json)。最终命令在Dev运行，使用绝对解释器；PYTHONDONTWRITEBYTECODE=1、PYTEST_DISABLE_PLUGIN_AUTOLOAD=1，禁用cacheprovider：

```powershell
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B -m pytest `
 tests/test_execution_contract.py tests/test_execution_store.py tests/test_execution_isolation.py `
 tests/test_execution_ownership.py tests/test_fake_supervisor.py tests/test_fake_reconciliation.py `
 tests/test_reconciliation_supervisor.py tests/test_run_diagnostics.py tests/test_diagnostic_supervisor.py `
 tests/test_process_contract.py tests/test_process_fixture.py tests/test_recorded_exit_reconciliation.py `
 tests/test_public_workflow.py tests/test_public_client_example.py tests/test_abaqus_preview.py `
 tests/test_abaqus_preview_integration.py -q -p no:cacheprovider `
 --basetemp='C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run009_ecc0fb67b272432d8364f6267923dca6\full1' `
 --junitxml='C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run009_ecc0fb67b272432d8364f6267923dca6\full1.xml'
```

stdout/stderr写入同临时根full1-output.txt，并原样保存为[TEST_OUTPUT.txt](TEST_OUTPUT.txt)。实际 **452通过，252.75秒**，359旧+93新，无失败/错误/跳过。没有预设数量或删改旧测试。源码hash确认原44文件未变。

## 失败迭代没有覆盖

| 试跑 | 实际结果 | 原因与修正 |
|---|---|---|
| target1 | 73通过、14失败 | Windows3.12 path.stat与fd.fstat的ctime在部分新文件不同，误报INPUT_UNSTABLE；另一个新身份注入测试同时改了比较两端，未能触发预期失败。 |
| target2 | 72通过、15失败 | 加入安全原因码显示并修正注入测试后，复现并定位ctime实际差异。不是输入变化。 |
| target3 | 87通过 | 去除不具内容身份意义的ctime比较；保留dev/inode/size/mtime、OS写删除排他、最终路径核对和二次字节摘要。 |
| target4 | 91通过、2失败、1teardown错误 | 新测试把Fake.emit误写成execute、把events列表当字典；工程INP放入旧Fake harness目录触发其原禁止INP断言。owner已退出且凭据已删除，但最终inventory断言未完成。 |
| target5 | 93通过 | 按实际API修正新测试，工程输入移到独立临时子目录；旧harness和断言完全不动。 |
| full1 | 452通过 | 全部前轮组及新增组运行。 |

原始target1～5的JUnit/输出均在iterations。不是因预期Abaqus结果不符而修改执行行为；没有任何Abaqus启动。独立离线示例没有失败迭代：target4、target5、full1每次成功/拒绝均按0/2正常返回。

## 副作用和进程

新单元组通过既有guard_environment禁止Popen/系统启动、默认home及旧Runtime模块；新增prepare/inspect还设置数据库、Backend和validator陷阱。实际Windows文件测试使用只读CreateFile引用，不启动任何程序。真实junction/硬链接仅在本轮临时根创建；未跟随到外部工程。INP路径读取哨兵验证危险引用在打开前拒绝。

公开示例客户端通过标准Python命令独立运行。完整argv、cwd、Popen和实际客户端PID、退出码在EXAMPLE_INVOCATIONS；其输入和配置读路径明确，输出仅一个显式exports/preview.json。拒绝分支无新文件。EXAMPLE_FILE_INTEGRITY保留调用前后文件摘要/mtime，导出内容与原prepare对象相等，不重新读取已变输入。

原R2～R8涉及的owner/client/launcher/worker仍通过原harness登记身份、保留句柄、确定性屏障、真实进程终止及清理。新离线路径没有动态启动能力；回归中的Python固定Backend不是Abaqus执行。

[PROCESS_AND_CLEANUP_EVIDENCE.json](PROCESS_AND_CLEANUP_EVIDENCE.json)聚合所有本轮试跑：162条lifecycle记录、328条fixture角色记录、490个唯一OS身份；另6次普通离线客户端调用均正常等待退出、关闭Popen句柄及管道。控制器仅按已有身份/保留句柄操作自己创建的进程，没有按名称批量结束进程。

所有角色记录的退出/句柄关闭均满足原断言；R8独立示例的all_children_waited/all_handles_closed=true，私有材料清理完成。对490个已登记PID+创建时间额外执行只读OS核验：匹配存活0、探针不可用0。PID已复用时不认为仍是旧进程，也不对其做终止。当前未找到进程不是服务退出证据；清理结论主要依据已保留的真实句柄退出记录。测试控制器额外观察没有写进被测业务库。

private-bootstrap/private-process及operator_private剩余文件0。target4虽在最后INP目录规则处失败，其进程退出/句柄关闭记录已写出、凭据已删除，最终聚合复核完成。临时合成输入、输出及审计证据保留，未执行自动全目录清理。

没有修改或迁移实验/生产Schema；没有读取Stable、生产Recent/Runtime/Project或真实工程；没有运行旧Runner、Abaqus任何子命令或许可证查询。版本保持0.3.0.dev0，未安装依赖、Git切换/恢复/commit/push。文件审计/启动陷阱是本轮可复现证据，不宣称完成全系统访问监控或OS级隔离。
