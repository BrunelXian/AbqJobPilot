# Run014 实际测试与故障记录

Windows、本机登记LangChainEnv绝对解释器；Python3.12.10。未使用Abaqus程序作为测试替身。Standard创建接缝用固定Python替换并设置其余创建调用失败哨兵；原Fake隔离AST/导入/无启动断言未弱化。

## 执行批次

| 证据 | 实际结果 | 范围/备注 |
|---|---|---|
| unit_final.txt / unit_final.xml | 65 passed，32.56秒 | 新处置单元26项、Standard Backend/准入和既有无执行/默认目录隔离 |
| regression_final.txt / regression_final.xml | 302 passed；1个测试setup失败并产生teardown错误（终端显示2 errors），394.43秒 | R2 store/契约/ownership、R3 IPC、R4事务对账、R5诊断、R7退出对账、公共workflow、实际GUI、Standard及新Windows闭环 |
| snapshot_final.txt / snapshot_final.xml | 1 passed，0.77秒 | 新增SQLite实际并发写入/读取一致视图屏障 |
| verified_final.txt / verified_final.xml | 83 passed，160.29秒 | 最终全部30项新测试、整组50项R7退出对账、3项R3进程所有权/断线/崩溃关键回归；修复旧支架身份发布竞态后执行 |

按 `(classname,testname)` 取最新实际结果去重，共**369项全部通过：新增30项、既有相关339项**，无跳过。不是“某一次全量369 passed”，也不替代矩阵。逐项及对应批次见 TEST_CASE_INDEX.json。

上述执行均为 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe -B -m pytest`，参数包含 `-q --tb=short --disable-warnings --maxfail=... --basetemp=<新UUID目录> --junitxml=<本轮新文件>`；工作目录为Dev。实际basetemp分别保存在 UNIT_TEMP_FINAL.txt、REGRESSION_TEMP.txt、SNAPSHOT_TEMP.txt、VERIFIED_TEMP.txt，不复用旧目录。Windows证据环境变量RUN014_EVIDENCE_DIR仅指向本轮新子目录。

未运行旧Runner、真实Solver、旧GUI生产Project全量测试，也未机械重跑全部历史项目测试。没有改旧业务断言来凑通过。

## 失败迭代（保留，不抹去）

1. 最初新单元测试命令漏带显式basetemp，pytest在默认 `pytest-of-wuxia` 创建fixture前遇到访问拒绝，3个setup errors，尚未开始业务/进程测试。随后所有运行改为新UUID显式临时根；未清理或改变该默认目录权限。这是执行方式失误，不将它写成测试通过。
2. unit_iteration_01：4 failed /6 passed；新增代码误用了原 `document` 的受限表查询，management_grants不在其白名单。修正为内部固定SQL，不扩大原辅助函数白名单。
3. unit_iteration_02：21 passed/1 failed；测试预期在check_plan拒绝，但实际更早在prepare就拒绝旧资源复用，改成验证这一更强拒绝点。
4. unit_regression_01：63 passed/2 failed；新增负面fixture缺少必填runs列；另新增import样式未符合既有AST依赖隔离。补齐fixture，改为明确模块导入；**旧隔离断言保持原样**。unit_final随后65通过。
5. 大回归中的1个R7用例 `test_incomplete_or_conflicting_required_set_rejected[projection]`：旧 `run003_process.py` 直接write_text身份文件，父进程见到文件但读取空串。失败发生在握手阶段，未获得owner、未启动Backend。子进程报12秒身份绑定截止异常；teardown拒绝没有身份句柄的强制结束。唯一修复为完整写入identity.partial再replace发布identity.json，不改断言或等待条件。整组R7和关键R3随后全部重验通过。

## Windows进程及清理

最终新增场景证据在 `windows_verified/`：

- `test_normal_owner_stop_leaves_0.json`：owner/venv真实退出后worker身份仍匹配，STA字节增长；重启slot/Run保留PAUSED。持有的7份OS引用最终均退出码0并关闭，包含已观察到的worker启动器及控制台辅助进程。
- `test_public_disposition_lost_r0.json`：真实IPC丢应答、幂等重放、实际现有GUI展示/关闭、owner重启；物理固定Python启动1次。持有的7份OS引用最终均退出码0；GUI/专属启动器也有WM_CLOSE退出证据。
- `test_true_owner_crash_during_d0.json`：真实提交前崩溃，核实后终止测试owner；owner与专属启动器退出77，固定worker相关引用退出0。正常读取拒绝维护条件。没有修复日志或再次执行。

测试控制器的独立句柄记录用于测试观察和安全清理，未补入被测服务的进程退出证据。不存在按进程名批量终止；故障/旧回归清理只作用于本轮测试登记并核实的句柄。新功能对真实进程没有终止入口。

聚合 `CLEANUP_SUMMARY.json`：两批旧支架共195条harness生命周期记录及440条fixture引用记录（可重复引用同一进程，不当作唯一进程数），记录的退出及句柄关闭条件全部满足；149份inventory报告记录其私有凭据清理、剩余文件无凭据。新Windows三例另列。

**首次身份发布竞态的限制单独保留**：该失败支架进程没有取得保留OS退出码；当前按其PID/创建时间/映像未找到匹配引用，stderr显示握手截止异常，owner-ready和physical-launches均不存在。不能倒填退出码0。只移除了本轮该fixture的2份私有文件，保留日志，未终止任何进程，见FIXTURE_RACE_CLEANUP.json。最终重验的正常清理证据不替换这段失败历史。

临时数据库、日志及故障journal作为审计材料保留在本轮显式根；没有删除旧Run010/011实验、被拒清理目录或真实Run013输出/意图。当前真实owner及其窗口未被操作。

## 当前真实实例与保护复核

当前旧endpoint健康请求超时；未取得记录owner身份匹配。严格只读数据库评估成功，数据库字节读前后相同、原Run及业务计数/slot/gate与初读相同。没有OS进程扫描或Abaqus探测。新operator `preview` 命令已从非仓库cwd实际调用；`review-and-decide`仅在隔离fixture测试，从未对真实实例调用。

最终历史材料摘要、Git及当前库复核见FINAL_AUDIT.json。命令行0退出不是完整Solver成员退出的代替结论；本轮仅完成收尾实现及相应隔离验证。
