# CR-D03 — 隔离验收与必要回归

本轮 **548 个唯一用例全部通过，0 最终 FAIL/ERROR/SKIP**。按 pytest classname + 参数化用例名去重，最终选集不重叠；不是把历史各Run计数相加。逐项清单和所有XML迭代在 TEST_RESULTS.json。

| 最终报告 | 收集/执行 | 范围 |
|---|---:|---|
| new_final_04.xml | 39 | 新 Preview、精确权限/版本/幂等/回滚/核验、产品桥、模拟 reboot/PID与证明破损 |
| windows_final_03.xml | 4 | 原生 Job + 固定Python、owner退出、活worker拒绝、R7对账、R14行政分支 |
| diagnostics_final_02.xml | 47 | CR-D02纯诊断、OS查询、真实固定Python、GUI关闭不等于中断 |
| regression_final.xml | 170 | diagnostics/IPC、R7、R14/Windows、R15 managed、R16 Standard受控替身 |
| management_final.xml | 152 | 原Fake对账/管理IPC、所有权、执行契约和Store |
| product_final.xml | 127 | R18认证/Run选择、R19生命周期、R20产品/凭据、R21B单次控制及Windows替身 |
| isolation_final.xml | 9 | 依赖与运行隔离、旧Runtime不可达、禁止旁路执行 |

环境为登记的 LangChainEnv 绝对解释器、Python3.12.10 / pytest9.1.0，现有Windows。测试驱动 `run_safe_tests.py` 为每批创建独立 TEMP/TMP/HOME/USERPROFILE 与基于原夹具的 Project/Runtime/Recent，禁止默认Runtime、禁止真实Abaqus创建，显式证据目录。Standard创建接缝由测试固定替身替换，历史DAT只作标明来源的离线样本。没有为本轮测试安装依赖。

实际命令均采用 USAGE 中的绝对解释器和同一驱动，mode/report 分别为：`regression regression_final`、`management management_final`、`product product_final`、`diagnostics diagnostics_final_02`、`isolation isolation_final`、`new new_final_04`、`windows windows_final_03`。实际中间批次全部保留，不覆盖第一次失败。

## 失败与修正

- iteration_01：首个用例通过后管理准入回调重入非重入 session registry 锁而挂起；只中断本轮测试进程，无外部fixture启动。将回调改为接收原锁内 connection，不重入 ReadOnlyStore，修复实际死锁。无完整XML，ROOT记录保留。
- iteration_02：1通过/1失败，内部 document 帮助器不支持 management_grants；改为当前事务中的精确已有表查询。iteration_03=28通过；随后扩展产品桥、权限和故障覆盖，iteration_04=37通过，最终39通过。
- windows_01：1通过/1失败；在活动SQL写期间结束本轮owner得到原有 STORE_REQUIRES_MAINTENANCE，而非测试预期的活动进程拒绝。改确定性 process:after_identity 屏障，保留该维护拒绝记录。
- windows_02：1通过/1失败；测试释放worker时遗漏 owner-bound 固定握手，等待超时；finally已发出完整测试释放信号并等待退出。补齐测试信号后 windows_03=4通过。
- 一次驱动误传报告全路径而不是文件名前缀，在收集前失败；没有运行测试/调用Solver，也未触碰旧数据。不清理无法确认名称的空临时根。
- 强化“权限查询失败不能当PID消失”后 windows_final、windows_final_02 各1失败：已退出对象仍被测试观察者句柄保留，新的映像查询不能确认，**产品正确阻断**。正向夹具先归档自身退出事实并关闭自身句柄，再有界只读等待明确可查询结果；不把控制器退出事实注入服务、不重试Apply、不放宽准入。windows_final_03四条通过。临时查询样本完整保存。
- diagnostics_final：46通过/1失败；旧断言只允许退出/不可用，未包含新保守 QUERY_FAILED。保留“不得借用测试持有句柄证明”的语义，更新允许的未知分类；同时使用确定性屏障避免热journal竞态，diagnostics_final_02=47通过。
- 最终new_final系列均39通过；后续改动为创建结果链检查、到期再次核查、严格结构错误、并让boot/PID参数实际进入只读诊断，分别复验相应用例。没有为了PASS删去安全条件。

## 用户本轮22项风险

| # | 实际覆盖/结果 |
|---|---|
| 1 | D02活owner/worker、R15 GUI关闭实测 + 新同owner锁/活动身份拒绝；GUI退出本身无恢复权限 |
| 2 | test_owner_live_or_dead_with_worker_live_never_releases：本轮owner句柄退出后worker仍活，DB和第二PENDING不变 |
| 3–4 | test_missing_exit_not_replaced_by_pid_or_boot_estimate：注入后boot估计/PID不可用或复用，UNKNOWN_INTERRUPTED可成立但KEEP_BLOCKED；D02真实创建时间不匹配回归 |
| 5 | test_original_managed_proof_crash_reconcile_preserves_pending；test_recorded_four_roles_uses_existing_r7_policy：真实原证据及统一Apply |
| 6 | 产品桥负向改动scope/active/pending/monotonic/create/event链；不得VERIFIED；原无exit行政政策仍拒绝 |
| 7 | test_preview_only_no_ownership_or_files：两次摘要相同，完整文件字节和持久state相同 |
| 8 | 无Grant、伪approved、自报主体修改、TEST_ONLY、预览当请求均拒绝；普通IPC无新mint/Apply操作 |
| 9 | 新事件/revision后原许可STALE_PREVIEW；原R14 gate/slot/retention变化回归 |
| 10 | 两线程同key一提交一重放，异内容冲突；两个精确许可同revision最多一个效果 |
| 11 | 同进程registry及实际Windows旧owner同一owner.lock竞争均OWNER_BUSY |
| 12 | 主体、Project/instance/owner、动作、过期、风险不匹配拒绝；OS观察期间到期再次拒绝 |
| 13–15 | 原回执重复、不同请求冲突、after_commit丢应答查询；跨新管理owner重放；核验失败仍保留已提交回执 |
| 16 | 新统一入口before_commit故障完整回滚；真实owner在原管理事务内崩溃沿用R14热journal维护阻断测试；统一管理进程真实中途kill未另建重复夹具 |
| 17 | ADMIN原UNKNOWN、exit、Solver/validation、intent及路径保留，PAUSED、槽释放；invariants核验 |
| 18 | 已行政处置再预览KEEP，不再签发；正常完成/验证缺失分维度由D02回归，原历史文件摘要保护 |
| 19 | 实际Windows第二Run保持PENDING，只有一次物理Python启动；其他Run表摘要不变 |
| 20 | R21B真实Grant/一次派发、R16受管/A→B回归均替身通过；新管理Grant与执行Grant消费表分离 |
| 21 | ADMIN直接委托closeout.apply_recorded，Windows固定Python复验原policy/retention/UNKNOWN |
| 22 | 新Run/Attempt/执行Grant/原事件/输出不变；测试audit和固定替身切断Abaqus；没有Retry/Resume/新Attempt入口 |

## CR-D01 26项分阶段复核

| 原ID | 本阶段状态/依据 |
|---|---|
| T01 | D02/GUI生命周期回归；恢复管理另受原锁与活动身份否决。新GUI显示仍D04 |
| T02 | 新Windows活worker拒绝与原managed_owner_crash回归 |
| T03 | 新模拟boot/缺exit只诊断；缺exit行政政策未开放 |
| T04–05 | D02 PID/clock/query回归；权限失败来源收紧，绝不按退出处理 |
| T06 | 本地/Windows同原锁竞争，产品桥空Project及产品隔离回归 |
| T07 | 原managed query/身份故障回归，新破损proof拒绝，不重开Job |
| T08 | 新真实managed:after_empty崩溃 → 原proof对账；不填自动完成标记 |
| T09–10 | D02/diagnostics及R14回归；新Apply原Solver/validation/输出摘要保留 |
| T11 | 新回执重放、跨管理owner、应答丢失；无第二次效果 |
| T12 | 新同key冲突/并发与不同许可同revision冲突；旧管理并发回归 |
| T13 | 新revision变动拒绝，原R14状态/gate/slot/路径变动回归 |
| T14 | 新before_commit注入回滚；旧共享事务实际owner崩溃仍维护阻断。新入口独立强杀中途测试未重复实施 |
| T15 | 新after_commit丢应答/Verify失败不丢原回执 |
| T16 | 新精确授权拒绝矩阵；继承可信本地Python边界，远程操作者登记留D04独立审查 |
| T17 | 新真实第二PENDING保留、已处置不可再改；D02完成Run保留 |
| T18–19 | 新实际R14行政/原managed范围对账分开；均不伪造自动COMMITTED或验证成功 |
| T20 | 产品/副本/错误凭据/格式/生命周期阻断127项回归；新空产品恢复拒绝无DB变化 |
| T21 | D02限额/忙/错误回归；新审计有界，未另做超大历史性能基准 |
| T22–23 | **D04/Run024待实施**：无新CLI/MCP/GUI恢复能力，Classic误显示Failed仍P1必修 |
| T24 | **D05未实施**：Apply不能创建新Attempt；执行契约/预算回归保持 |
| T25 | 新空Project在acquisition业务写之前拒绝，不产生OPEN |
| T26 | 新OS活动/失败/到期否决；锁内前后digest检查；不宣称OS与SQL原子性 |

## 实际 Windows 证据与清理

WINDOWS_RECOVERY_EVIDENCE.json保存最终4用例的12份源记录/后查DB投影及SHA-256：原Job空查询、owner/worker身份、对账回执、原UNKNOWN、第二PENDING、PAUSED/slot、测试观察句柄退出和关闭、当前OS查询样本。源文件仍留在本轮ROOT记录的临时目录，不能作为历史真实Abaqus证据。

原生Windows正向使用固定普通Python；产品桥正向使用受控Standard替身和注入OS事实，明确非实际Abaqus/产品宿主恢复验收。模拟boot不重启Windows，故障owner仅本轮身份已绑定的夹具；没有按名称终止用户进程。

首批 CLEANUP.json：667个登记身份后查匹配存活0、报告已知秘密命中0；181份本轮私有文件移除。最后一个纯注入批次 CLEANUP_FINAL.json：新增真实身份0、秘密命中0、6份私有文件移除。合计187份临时私有文件，业务DB/输出/审计与所有旧目录保留。后查PID不可取得/复用不追认历史退出；退出码及句柄关闭来自各测试原记录。审计本身进程终止0、Abaqus0。

未执行完整无关Legacy选集、真实Abaqus、真实关机/重启/注销、历史生产恢复、live Job重挂接、CLI/MCP写操作或新GUI恢复交互。548是本轮选集，不与Run022的664直接比较为回归增减。
