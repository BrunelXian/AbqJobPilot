# CR-D02 — 实际测试与验收

## 最终结果与口径

登记解释器 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python3.12.10 / pytest9.1.0；Windows版本见 TEST_RESULTS.json。每批新建 `AbqJobPilot_CRD02_*` 根，明确TEMP/TMP/HOME/Runtime/Recent，禁用pytest缓存/字节码。Standard真实创建接缝被固定Python替身/失败哨兵替换；没有真实Abaqus调用。

| 最终批次 | 唯一用例 | PASS | FAIL / SKIP | 原始报告 |
|---|---:|---:|---:|---|
| 新诊断、证据/boot模拟、实际Windows查询 | 47 | 47 | 0 / 0 | new_final.xml |
| 诊断、记录退出对账、行政处置、受管范围、Standard顺序替身 | 170 | 170 | 0 / 0 | regression_iteration_02.xml |
| R18–21B发现/GUI/生命周期/Project/凭据/产品单次控制 | 127 | 127 | 0 / 0 | product_final.xml |
| 独立进程依赖与无执行副作用检查 | 9 | 9 | 0 / 0 | isolation_current.xml |
| **去重合计** | **353** | **353** | **0 / 0** | TEST_RESULTS.json |

按最终完整批次的 `classname::name`（包含参数ID）去重，四批无重复；最终收集并执行353项。此前迭代、旧Run测试数量不累加。没有为了总数重跑Run022全部664项；未修改CLI/MCP、Classic布局或通用输入解析，相应完整旧选集未重跑。新GUI诊断接入/真正Recovery Apply/Retry属于后续阶段，不能计为本轮通过。

## 失败迭代与修正

1. `new_iteration_01`：11 PASS/1 FAIL，测试误将既有故障夹具的Artifact UNKNOWN写成NOT_RUN。按原源码/原记录修正测试预期；诊断没有改写该值。
2. `new_iteration_02`：38 PASS/1 FAIL，测试错误假设新打开句柄必能取得已退出owner的映像。实际新读为PROCESS_UNAVAILABLE；fixture原保留句柄有退出事实，但公共诊断没有该句柄，不能借用其事实。测试分别断言当前诊断保守输出与fixture退出事实。模拟精确退出分支另行覆盖。
3. `new_iteration_03`：37 PASS/1 FAIL，活跃owner事务期间既有read-only sidecar策略短暂拒绝读。诊断不改策略；实测驱动只对STORE_REQUIRES_MAINTENANCE/STORE_UNAVAILABLE有界重读，无执行重试。新增确定性sidecar拒绝与读写交错用例。`new_iteration_04`为39 PASS，后补边界后`new_iteration_05`为43 PASS，最终47 PASS。
4. 首个 `regression_final`：128 PASS/1 FAIL，原R14 fixture仅等待Run已待对账，紧接着要求closeout eligible；原Backend在Run提交后才完成PAUSED及dispatch guard退出。事后只读复核本轮临时DB，假定quiescence的原assessor满足全部持久证据条件（REGRESSION_FAILURE_REVIEW.json）；原瞬间preview未保存，不能声称事后报告就是原瞬间证据。修正测试同步，等待原PAUSED及quiescent-owner前提，记录样本，**原release准入断言与产品逻辑不变**。完整170项重新通过。
5. 清理审计复用脚本按文件名收集lifecycle记录时，将45份本轮私有profile原结构带入审计文件。交付前检查发现后，删除新审计文件中的这些私有内容，改为只记录排除路径/原因，并修正生成器过滤及写后秘密检查；不保存原秘密载荷，仅保留原报告摘要和修正记录 AUDIT_REPORT_CORRECTION.json。最终目录对这些已知材料匹配0，JSON无credential/operator_token/ciphertext值。该修正不涉及历史资料或执行核心，最终诊断样例本身未包含这些秘密。

所有首次失败XML保留；无用“最后一次PASS”掩盖上述问题。只读检索还出现PowerShell通配符/误猜测试文件名的失败，后按实际文件修正；没有执行错误命令或产生业务写入。

## CR-D01的26项矩阵落地

“D02通过”只指本轮诊断范围；原Apply回归通过不代表新增恢复政策已完成。

| ID | 本轮证据 / 结论 | 后续保留 |
|---|---|---|
| T01 GUI退出、owner/worker正常 | D02模拟原owner及成员活动不判中断；原managed_scope、execution_gui、attachment_gui实际Windows关闭/重连回归通过 | 新投影GUI展示D04/Run024 |
| T02 owner退出worker仍活 | test_owned_owner_exit_worker_alive_no_requeue_or_takeover：真实本轮owner退出、同worker存活、DB字节不变、第二项PENDING不变；新句柄身份不足仍保守 | 无重新挂接/Apply |
| T03 模拟重启缺exit | 参数化LATER_BOOT_ESTIMATE+owner不可查询+START_INTENT得到疑似投影，状态/槽不变 | 不是真实OS重启或新boot ID证明 |
| T04 PID复用 | 实际当前PID+错误创建时间拒绝；注入身份冲突不推断退出 | 不控制该PID |
| T05 时钟/误差/查询失败 | 实际GetTickCount64只作估计；注入误差交叠、采样时钟跳变、拒绝查询；无独立依据保持UNKNOWN | 历史时钟变化不可验证 |
| T06 owner锁冲突 | 实际owner持锁时D02查询，无取锁/接管；原生命周期锁冲突回归通过 | 新管理会话竞争D03 |
| T07 scope丢失 | missing_scope、scope_id、missing_commit及原managed故障回归；不重新创建空Job，不填完整退出 | 新证据对账D03 |
| T08 empty但终态未提交 | missing_commit诊断保留未知；原真实测试owner崩溃窗口回归通过 | 新policy Apply未做 |
| T09 Solver完成验证未完成 | Standard替身+有来源历史DAT，validation_only仍分维度；不因验证缺失判Crash | 不重新验证产物 |
| T10 只有输出文件 | 新无归属DAT/ODB哨兵不读取/改写，不提升结论；原只读陷阱回归 | 无真实ODB读取 |
| T11 重放/丢应答 | 原closeout/product control幂等回归通过 | 新恢复请求D03未验 |
| T12 并发操作冲突 | 原closeout并发、生命周期/单次控制回归通过 | 新恢复策略D03未验 |
| T13 旧preview | 原stale_assessment回归通过；D02提供revision和snapshot摘要，无Apply | D03锁内重评估 |
| T14 提交前崩溃 | 原本轮新隔离owner的处置事务故障回归通过 | 新恢复策略D03 |
| T15 commit丢应答 | 原管理/产品回执回归通过 | 不新增恢复key机制 |
| T16 未授权Agent | 原真实/TEST_ONLY/管理权限与产品单次控制回归通过；D02无写入口 | 新管理能力独立审查 |
| T17 PENDING和历史完成 | 新默认未启动、正常完成、另一排队Run不变，整根hash/mtime与DB字节断言 | 不Requeue |
| T18 行政处置 | 新诊断读取原受控替身administrative release；UNKNOWN、PAUSED、隔离和无槽并存 | 无历史真实处置 |
| T19 正常/行政区别 | 新scope提交与admin不同分类，原A→B前置回归通过 | 不将admin作为正常完成 |
| T20 错Project/旧schema/副本 | 新只读拒绝与原product_project/lifecycle/attachment回归通过 | 无迁移 |
| T21 限额/sidecar/损坏/竞态 | 新读边界、元数据上限、无修复、失配不探测、JSON脱敏；旧诊断导出回归通过 | 新报告IPC导出D04 |
| T22 多客户端展示 | 同一内部/Python分类器已测试 | CLI/MCP/新GUI适配未实施 |
| T23 Classic误标Failed | 已核实源码P1，RUN024_GUI_HANDOFF明确必修 | 本轮不改GUI，不标通过 |
| T24 新Attempt/Retry | D02无这些操作，AST/副作用断言；原语义保持 | D05独立设计/授权 |
| T25 空Project管理 | D02只读查找无Run返回NOT_FOUND，无管理owner | D03空实例拒绝未新增 |
| T26 OS/DB竞态 | 新只读事务关闭后才probe；确定性writer交错证明快照一致、writer可继续；明确非跨系统原子 | Apply时效/锁内竞态D03 |

## Windows证据及清理

WINDOWS_DIAGNOSTIC_EVIDENCE.json复制本轮两个新测试的公开诊断与保留句柄清理事实，附原临时证据路径/SHA-256。它们只证明固定Python；没有宣称Abaqus、真实关机/重启、完整域外集合或新GUI展示通过。

具体清理见CLEANUP.json：后查890个本轮记录的时间范围内身份，身份匹配仍活0；合成/旧时间身份不探测。仅凭当前对象不可取得不补写历史退出。夹具原保留句柄证明自身测试进程退出/关闭；本轮审计额外终止0。155份本轮私有文件在确认无匹配存活对象后按精确路径移除；不删除测试DB/结果/历史目录。最终私有profile排除和报告脱敏修正在独立记录中。

真实Abaqus0、历史owner操作0、原Project/Run/授权/派发变化0、Schema迁移0。最后基线比对仅允许store.py、两个测试文件及本轮新文件改变。
