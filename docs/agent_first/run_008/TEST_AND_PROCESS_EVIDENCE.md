# Run 008 — 测试、实际进程与清理

## 当前实际结果

最终full3：**359 passed，0 failed/errors/skipped，421.60秒**。重新运行原343项，加新增16项。[原始输出](TEST_OUTPUT.txt)、[JUnit](TEST_RESULTS.xml)、[逐项数据](TEST_CASES.json)、[环境](ENVIRONMENT.json)均来自本轮。本机Windows11 build26300、Python3.12.10、pytest9.1.0。未运行无关GUI/Solver或生产数据测试。

执行参数：登记绝对Python加`-B -m pytest`，设置PYTEST_DISABLE_PLUGIN_AUTOLOAD=1，关闭pyc和cacheprovider；`--basetemp`为本轮临时根下全新目录；`--junitxml`保存到本轮根。测试文件为test_execution_contract/store/isolation/ownership、test_fake_supervisor/reconciliation、test_reconciliation_supervisor、test_run_diagnostics/diagnostic_supervisor、test_process_contract/fixture、test_recorded_exit_reconciliation、test_public_workflow/client_example（均在tests/，完整真实名称见JUnit）。

## 独立工作流

[实际命令](EXAMPLE_INVOCATION.json)从非仓库目录执行，returncode0、stdout/stderr为空。ordinary客户端不导入tests、pytest、store、service、supervisor、authority或backend；不执行SQL或启动程序。实际A PID26744、B PID1572、owner PID2188，Project instance为`pi_d53fea6f100d4052b00effe6a098258e`，Run为`r_fc6237e0cc394d4db066be8059c8a356`。

服务持久化事实：接受事务/原回执；一次START_INTENT；四个OS核实成员；四条保留句柄退出观察；PROCESS_COMPLETED；原正常验证与新的显式验证记录。四成员均exit0；Solver NOT_RUN。B重放提交与管理验证不产生第二次对应副作用。

操作者额外观察：A已经退出而worker精确OS引用未signaled，owner仍运行；owner的CPython subprocess审计仅一次固定启动尝试。这是启动前audit，并非单独的创建成功证明；与服务四角色实际OS身份/退出记录结合才证明本次一次物理启动。操作者释放固定result_wait的屏障，普通客户端不读取控制器文件或PID判断业务成功。

公开脱敏样例：[Plan](examples/plan.json)、[接受](examples/accepted.json)、[拒绝](examples/rejection.json)、[重连完成](examples/complete.json)、[离线诊断](examples/diagnostic.json)。客户端事件cursor来自验证之前；诊断view来自验证之后，分开记录。诊断与导出是同一快照、同body摘要。源Artifact字节、连接秘密、可用授权和原始日志不在导出中。

## 进程与清理证据

最终harness部分记录153个owner/client实际进程、82次Backend物理启动、328个fixture角色；独立示例另有1个owner、2个client、1次Backend启动/4个fixture角色。它们不是通用任意进程树统计，也不把venv transport与实际Python角色混为同一PID。详见[PROCESS_EVIDENCE](PROCESS_EVIDENCE.json)、[示例生命周期](EXAMPLE_LIFECYCLE.json)、[示例公开证据](EXAMPLE_WORKFLOW_EVIDENCE.json)。

harness持有的owner/client句柄均signaled，fixture引用均有退出证据并关闭；独立示例等待所有自身子进程并关闭清理引用，服务正常释放自己的OS引用和锁。launcher可能在控制器查询时已结束，因此控制器不事后强求重新打开它；服务已保留并记录其退出。示例删除6份私有handoff/control JSON，remaining_private_files=0；[EXAMPLE_CLEANUP](EXAMPLE_CLEANUP.json)无错误。执行/管理授权消费的历史记录保留在实验数据库，未因清理退还授权。

跨本轮所有试运行/pytest迭代累计核查1698个已登记OS身份，未发现匹配存活；2个旧PID当前查询被拒绝，但均以精确身份的既有句柄退出记录确认历史清理，当前PID所属保持未知；仅对这些PID/创建时间进行只读核验，没有按名称枚举/终止。PID不存在/复用不伪造成历史exit0。详见[CLEANUP_AUDIT](CLEANUP_AUDIT.json)。所有迭代私有bootstrap/process/示例handoff文件残留0；[ITERATION_CLEANUP](ITERATION_CLEANUP.json)保留当时失败记录。

## 修正过的失败迭代

demo1：最小子进程环境没有TEMP/TMP，owner自身临时根不一致，路径检查拒绝；补明确临时根，未启动Backend。demo2：Windows审计事件给出quoted commandline而非list，示例启动防线拒绝；服务保守标记不确定，没有实际Backend创建。demo3：控制器尝试在launcher退出后取得完整image身份而失败，随后owner清理有退出竞态；保留该错误，不把本次标为通过。修改为只保留仍等待的worker清理引用，launcher退出依赖服务既有句柄证据；所有本次登记身份最终核查无匹配存活，未补造服务退出事实。demo4工作流通过。

target1为新增测试适配错误（fixture登记、gate方法名、原因码）及发现底层异常文本可能泄漏；修正测试到真实接口，并对新入口错误使用固定文本。target2仅有秘密字段检查误把披露列表中的credentials_and_grants文字当作秘密，修正为检查实际字段；原有测试未改。target3新增15项全通过。full1 358项全通过。最终diff复核补回旧诊断格式原有source枚举，并增加兼容性断言；full2为358 passed、1 failed：旧控制器读取已发布授权回复时遇到Windows PermissionError，尚未到达恢复拒绝断言；没有将该轮标为全通过。原代码不变，独立复测7个崩溃窗口全部通过；最终full3 359项全通过。失败证据留在本轮临时根，未覆盖旧Run材料，也没有重试同一不确定Run来凑成功。

## 未改变的语义

R2接受/消费事务、幂等与单槽；R3断线不取消owner及重启暂停；R4Fake采纳限制；R6固定角色OS身份/退出、崩溃阻断；R7已持久化退出对账；R5只读一致诊断与客户端导出全部保留。没有新的自动Retry、接管、对账、resume或进程控制。新增独立验证有明确业务写入和授权，绝不隐藏在inspect_plan/diagnose/export中。
