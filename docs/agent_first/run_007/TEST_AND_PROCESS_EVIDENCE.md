# Run 007 — 实际测试、进程与清理

最终 **343 passed，0 failed、0 errors、0 skipped，241.96秒**。原R2～R6全部293个case身份完整包含于最终通过集合；新增50项。没有修改任何旧测试文件，没有删除或弱化原断言。见[JUnit](TEST_RESULTS.xml)、[原始输出](TEST_OUTPUT.txt)、[逐项验收](ACCEPTANCE_MATRIX.md)。38个源码/测试哈希与最终测试快照一致，见[SOURCE_HASHES](SOURCE_HASHES.json)。

| 组 | 本轮实际通过 |
| --- | ---: |
| execution_contract / store / isolation / ownership | 56 / 30 / 9 / 2 |
| fake_supervisor / fake_reconciliation / reconciliation_supervisor | 28 / 61 / 3 |
| run_diagnostics / diagnostic_supervisor | 48 / 2 |
| process_contract / process_fixture | 34 / 20 |
| recorded_exit_reconciliation（本轮） | 50 |

使用登记绝对解释器与Windows11 build26300；[环境](ENVIRONMENT.json)记录Python3.12.10、pytest9.1.0、SQLite3.49.1。原始命令选取上述十二个测试文件，`-B -m pytest -p no:cacheprovider -q`，设置PYTEST_DISABLE_PLUGIN_AUTOLOAD=1及PYTHONDONTWRITEBYTECODE=1；basetemp为[TEMP_ROOT](TEMP_ROOT.txt)下新建full1，JUnit为full1.xml。没有运行无关GUI、真实Solver或生产数据测试。

## 迭代与失败记录

| 轮次 | 结果 | 说明 |
| --- | --- | --- |
| smoke | 39 passed，64.19s | 首批新测试，包含真实owner退出及重启 |
| run1 | 58 passed、1 failed，82.25s | 新增边界与9项隔离回归。失败来自测试夹具向不存在的Job插入另一Run，外键约束正确拒绝；修正为先真实接受第二个Run，再通过持锁owner注入其不确定状态，未放松约束 |
| full1 | 343 passed，241.96s | 修正夹具并完整重跑293项回归与50项新增；最终源码未再改变 |

另一次基线快照辅助脚本误把前轮哈希JSON列表项当路径，TypeError后没有产生源码修改；改为读取path字段，36个前置哈希全部匹配。不是测试失败或环境修改。全部迭代文本/XML及原始测试数据保留在本轮临时根，没有覆盖旧轮证据。

## Windows进程事实

最终102个多进程case登记141个实际owner/client Python进程，以及71次Backend物理启动、284个固定角色进程。每次物理启动使用受控Popen登记的实际launcher_transport身份，与控制器持有句柄的PID/创建时间核对；不使用产物文件数代替启动次数。原测试Python转发器亦全部wait退出。

最终70次owner/client故障终止，以及20次fixture角色清理终止，均只使用本轮已核验身份的保留Windows句柄。所有登记进程完成退出观察，句柄关闭；私有连接凭据文件残留0，Recent哨兵不变，数据访问限临时根或明确的只读解释器/固定夹具文件。完整身份、退出码、物理启动及清理条目见[PROCESS_EVIDENCE](PROCESS_EVIDENCE.json)。

三轮清理汇总见[ITERATION_CLEANUP](ITERATION_CLEANUP.json)。额外审计仅查询本轮登记的885个不同PID/创建时间身份，没有枚举或结束其他进程：883次当前不可取得引用，2次PID已对应不同身份，未发现匹配的仍活跃身份，见[CLEANUP_AUDIT](CLEANUP_AUDIT.json)。退出证明来自先前保留引用的lifecycle记录；当前“找不到”或身份不匹配不被转换成退出码或写回业务库。

服务实际持久化：接受/START_INTENT、完整固定成员依据、真实OS身份、逐成员已观察退出事件及投影。控制器另外持有：其独立OS引用、原owner真正被终止、物理启动登记及清理结果。后者不作为预览资格，不回填缺失服务证据。

## 诊断样例

- [零退出收尾前](examples/zero_exit_unvalidated_before.json)、[零退出收尾后](examples/zero_exit_unvalidated_after.json)：四个退出已记录；本次显式决定将执行收尾为COMPLETED，Artifact仍NOT_RUN，门仍PAUSED。
- [非零退出收尾前](examples/nonzero_exit_unvalidated_before.json)、[非零退出收尾后](examples/nonzero_exit_unvalidated_after.json)：worker真实退出23，结论FAILED；不是因测试预期非零就将业务Run写为成功。
- [历史INVALID保留](examples/historical_invalid_after.json)：OS资格仍来自真实路径；另由既有独立validator取得FAIL，作为明确的持锁历史测试夹具登记，apply保留其值和时间。该样例不宣称新增了产品验证入口，也没有通过改库构造OS退出资格。

样例为同一时点的白名单投影；包含关联身份、历史状态/事件/验证/对账及摘要，不含授权、连接秘密、绝对路径、原产物字节或日志。诊断没有探测当前进程或再次验证产物；摘要只覆盖公开投影，不是签名、当前状态保证或执行许可。

## 边界

这是真实Windows进程终止/重启与正常SQLite事务边界验收，不是断电、OS崩溃、任意journal恢复或非Windows发布验收。清理进程没有顺手对缺证据Run收尾。单槽与保护只属于一个实验存储及固定四成员集合；仍存活、缺身份/退出、跨attempt或冲突历史继续阻断。没有Abaqus、遗留worker接管或自动恢复验收。
