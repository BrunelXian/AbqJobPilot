# Run021B 唯一真实产品 Standard 验收 — PARTIAL

验收日期：2026-10-25，时间为 Asia/Shanghai（UTC+08:00）。这是原冻结候选之后追加的实测报告；不覆盖 Run021、Run021B 准备报告或清单。

**实际 analysis 1 次，额外 Abaqus 调用 0 次。** 受管范围正常结束、自动收尾、三项 DAT 验证、安全停服及重启保持均成立。GUI 与专属 venv 启动器已完整退出，原 owner 继续运行；重开连接了原 Run。但未取得“GUI 和启动器均退出后，身份匹配的 Solver 仍存活”的样本，该项 **NOT_OBSERVED**。整体 **PARTIAL**，不使用完整 E2E PASS，不补跑。

## 1. 批准对象与材料

| 对象 | 实际值 |
|---|---|
| Project | `p_fa698230f3e6499caf08517e3e82dbc2` |
| Project instance | `pi_88118c5738214496aa2757ef5265df50` |
| Plan | `plan_499a7ab80b804e11939fc760ac3a2243` |
| Plan digest | `sha256:627392a372ffd209e216d7a4f494c206db0fe28ff1e5a98c2d9c5d0bb5c9bf4a` |
| 清单 | `D:\Projects\abqjobpilot_dev\docs\agent_first\run_021b\ACCEPTANCE_MANIFEST.json` |
| 规范化 body SHA-256 | `efdee66a3639bbfe95d084e90036e6376eaa3120c975918423afedf0b72220e1` |
| 根 | `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run021_42b9754ee29b457d8c86b2e97a26ec4b` |
| INP | 根下 `engineering\axial_bar.inp` |
| 输入 SHA-256 | `e2f91730b68f3af72b8054bc168d31b72a3f21ae186e899d64ab4b6b761523a3` |
| Job | `r021_bar_42b9754e` |
| 入口 | `D:\ABAQUS2024\Commands\abq2024.bat` |
| cwd / output | 根下 `engineering` |
| scratch | 根下 `engineering\scratch` |
| 资源 | CPU=1，GPU=0，memory request=2048 MB；不是 OS 硬限额 |

使用冻结 `product_standard_acceptance.verify` 重新计算 body，并核对 119 项实际引用材料。启动前与最终核验均 MATCH，存储 Plan 仍与冻结 Plan 完全相等。解释器为登记的 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python 3.12.10；GUI Tk 8.6。未修改执行代码、配置、模型、数值目标或冻结材料。

批准依据为用户本轮“Run 021B 唯一真实 Standard 验收授权”消息；真实登记使用 subject `user_wuxia` 及该消息与清单摘要的实际来源引用。没有将 TEST_ONLY 权限扩展为真实批准。

## 2. 授权、提交及唯一启动

| 事实 | 标识 / 证据 |
|---|---|
| 精确 Grant | `grant_095b0af73ea8425d99c71ef9dc063510` |
| 授权操作 | `op_2a3da0ad99664dffb22ebfcdeef4702a` |
| 授权键 | `run021-product-authorize-42b9754e` |
| Run | `r_711c0afc7d49462c8b5c4faf914923b4` |
| 原接收回执 | `req_9fc6585f5f1741f3b30c802c0116c1b3` |
| 提交幂等键 | `run021-product-submit-42b9754e` |
| 派发操作 | `op_d979d5510466497c902652e4066dfaf8` |
| 派发键 | `run021-product-dispatch-42b9754e` |
| 启动尝试 | `phase_5ad46f94fb954afe84d730e894f7e8bc`，attempt_no=1 |
| 输出身份 | `sha256:a61597a6d97af061fc237bc10ec648c9b736d775e9eb0573b8cd78b684426a33` |

13:27:12 登记 Grant，原有效期至 13:37:12。首次 authorize 返回 `ACCEPTANCE_UNKNOWN`，没有再次登记或换键。通过原管理幂等键只读查询取得已提交原回执，再继续提交。

13:27:34 公共客户端接受唯一 Run；13:27:56 精确单次派发获准。25 秒窗口截止 **13:28:21**；实际 wrapper 创建时间为 13:27:57 左右，处于窗口内。单次许可最终为 CLAIMED，全局派发一直保持 PAUSED，没有通用 OPEN。意图、CREATE_ENTERING、CREATED 各一次，只有一个 wrapper OS 创建身份、一个 Run、一个 Grant 消费。没有重放实际创建，没有扩大窗口。

最终只读事务计数：1 Plan、1 Grant、1 Run、1 receipt、1 consumption、43 events、1 validation、0 reconciliation。详见 `FINAL_READONLY_STATE.json`。这是本次 Project 的计数，不包括历史实例。

## 3. 进程与受管范围

原 owner `owner_f29fe7de57304435b755896ce8a0599a`：PID 20864，创建时间 `134373795386097186`（Windows 100 ns），实际镜像 `D:\Program Files\Python312\python.exe`；其 venv 启动器 PID 31428，创建时间 `134373795385854055`。

实际启动接缝为原 Supervisor 内 Standard Backend 的 `CREATE_PROCESS_JOB_LIST`。每 Run 的无名 Job 没有 KILL_ON_JOB_CLOSE、没有 breakaway，没有普通启动回退；stdio 使用独立文件句柄。实际宿主检查为 eligible，完整宿主 Job 层级仍 UNKNOWN；不声称支持终端关闭、注销或关机。

| 对象 | 实际证据 |
|---|---|
| wrapper | PID 5716，创建时间 `134373796774248368`，cmd.exe；创建返回耗时 219 ms；退出码 0 |
| standard.exe | PID 7604，创建时间 `134373796956861492`；保留句柄得到退出码 0 |
| 已记录成员 | 11 个有 OS 身份的进程，服务取得各自退出码 0；不是完整成员枚举证明 |
| 受管对象 | `scope_9fd35094d0a246b09c7cc3cc154a2ac8` |
| 结束查询 | 13:28:26，`QueryInformationJobObject.BasicAccounting`，active=0、total=12、limit_terminated=0 |
| 管理条件 | creation_confirmed=true，pending_additions=false，state=EMPTY_CONFIRMED |
| 持久收尾 | `COMMITTED_EMPTY_SCOPE`；event 42 `STANDARD_MANAGED_COMPLETED`，event 43 `STANDARD_RESULT_RECORDED` |
| 最终投影 | revision 43，FINISHED / EVIDENCE_RECORDED，Backend COMPLETED，reconciliation NONE，slot=null |

Job accounting 的 total=12 与逐项留存的 11 个进程不能互相替代。受管范围结束只证明 **ROOT_AND_INHERITING_CREATEPROCESS_DESCENDANTS** 已空；域外服务、全机进程全集、member_completeness、overall_exit 和 exit_verification 继续 UNKNOWN。没有把成员列表改名为完整集合，也没有通过终止进程制造空范围。

服务在约 29 秒内取得范围结束并提交结果，`observation_deadline_reached=false`。没有触发 300 秒 Solver 观察上限。另一个只读审计观察器总预算 300 秒，包括启动前等待和生命周期观察；它不负责 Solver 监督、不写业务记录。

## 4. GUI 验收的已成立部分与缺口

从正常 `D:\Projects\abqjobpilot_dev\Open_Dev_GUI.vbs` 打开主窗口，显式选择本次产品 Project；通过 GUI Start Service 创建原 owner，认证连接。提交后选中相同 Run / 原接收回执，查看阶段与有界日志。未使用测试 GUI 或第二执行核心。

原 GUI PID 12056，创建时间 `134373793791429002`；venv pythonw 启动器 PID 22576，创建时间 `134373793791271888`。使用正常窗口关闭，两个进程均通过预先保留的 OS 句柄观察到退出码 0。

时间证据来自 `OS_TIMELINE_REVIEW.json` 与逐样本 `OBSERVATIONS.jsonl`：

- 最后一次 standard.exe 存活样本：Unix `1792906104.6387055`。
- 首次 standard.exe 已退出样本：`1792906105.20373`，retained handle exit=0。
- 首次 GUI 和 venv 均已退出样本：`1792906105.7273748`，两者 exit=0；原 owner 同身份仍存活。
- **不存在 GUI 与 venv 均已退出、Solver 仍存活的同一观察样本。** 不能反推短间隔内发生顺序，因此跨关闭 Solver 持续运行记 NOT_OBSERVED。

重开同一正常 GUI，重新选择本次 Project / Run，看到原 owner、原 Run、原回执及完成日志，没有重新提交。后续安全重启 owner 后，GUI 重新认证到新 owner，仍显示相同 Run、PAUSED、FINISHED、Solver 结论和验证结果。GUI 操作/可见显示由本轮桌面工具观察；OS 退出证据来自独立 retained-handle recorder，不把 UI 隐藏当作进程退出。

## 5. Runtime、Solver 与数值

运行时 stdout 第 6–7 行标明本次 Job 和 Abaqus 2024，第 13、17 行为 Standard analysis begin/end，第 23 行 Job COMPLETED。DAT 第 3、43、124 行及 MSG 第 3 行同样标明 Abaqus 2024。未为版本确认额外调用任何 Abaqus 入口。

Solver `COMPLETED_TEXT_EVIDENCE` 的组合依据：DAT 第 231/235 行完成与尾部、STA 第 8 行 `THE ANALYSIS HAS COMPLETED SUCCESSFULLY`、MSG 第 119 行 `THE ANALYSIS HAS BEEN COMPLETED`。不是仅凭 wrapper exit=0、文件存在或一行文本。

独立验证 `val_496426121dee47c59a075ba9b57fb8cf`，记录于 13:28:26，来源 `current_run_bounded_text_read`，策略 `fixed-2024-axial-dat-v1`，validator v1。Step 1 / increment 1 / final time 1，CP936 严格解码。后续普通 Python 只读审阅重新核对实际文件身份、时间、摘要及选定行，没有生成新的服务验证记录。

| 冻结检查 | 实际值 | 绝对误差 | 容差 | 位置 | 判定 |
|---|---:|---:|---:|---|---|
| 节点 2 U1 | 0.010000000 mm | 0 | 0.000001 mm | DAT header 215 / row 218 | PASS |
| 单元 1 / IP 1 S11 | 1.000 MPa | 0 | 0.0001 MPa | DAT header 200 / row 203 | PASS |
| 节点 1 RF1 | −1.0000000 N | 0 | 0.0001 N | DAT header 224 / row 227 | PASS |

DAT：10334 bytes，SHA-256 `05942b3b79aad64399d0618f7067435bb7dfdc4ffb292b8417655350c156110b`。STA：444 bytes，`b5bd561323563ce7b1f0791ff9846b14bd266ad5054a4885d61073477b0449ee`。MSG：7606 bytes，`cec22819b9dae66760b91c64f59ee9ba907cd8225859a11153324068844b0e3d`。三者均与服务原验证摘要、file identity 匹配，创建/修改不早于本次 intent。

PRIMARY_THREE_PASS 与 Artifact VALID 的范围是上述固定 DAT 验证。解析器额外列出的节点 1 位移没有打印行，仍为 NOT_RECORDED，`full_frozen_checks=NOT_ALL_ESTABLISHED`；不从边界条件推定数值，也不扩大为完整模型结果验证。**ODB 内容验证 NOT_RUN**，未打开 ODB，未调用 Abaqus Python/CAE/Viewer。没有单独 `.log`；原 stdout/stderr 保留在 Run runtime 下。

## 6. 安全停服及重启

确认 managed completion 已提交、slot=null、reconciliation NONE、PAUSED 后，通过原产品生命周期接口显式 stop，使用冻结键 `run021-product-stop-42b9754e`。回执 `stop_15f189d7ef5b48edbe38de2f6fec9ffb`，13:30:13 STOP_COMMITTED，effects 为 PAUSED / orderly_idle_stop。

保留句柄确认原 owner 20864 及其 venv 31428 正常 exit=0；随后 inspect 为 NOT_RUNNING / ORDERLY_STOP_RECORDED。没有 kill、删除锁或接管。再通过冻结入口 restart 一次：

- 新 owner `owner_ea3be94dcfcf4210b9fc6fc41f62154a`。
- PID 11216，创建时间 `134373798333408496`，最终身份匹配、仍存活。
- PAUSED version 4，slot=null。
- Run 整体内容及原 receipt 与停服前完全相等，revision 43、attempt_no 1。
- 仍只有 1 Grant / 1 consumption / 1 Run / 43 events，没有新启动。

重启后的空闲 PAUSED owner 与重开的 GUI 按原 USAGE 保留供查看。没有再次使用旧 stop 键停止新 owner；没有触碰其他 Project 的 owner。

## 7. 执行记录、异常及收尾

实际通过原入口执行的控制操作依次为 authorize（一次）、submit（一次）、dispatch（一次）、stop（一次）、restart（一次）；start 由正常 GUI 明确触发。check/report、原管理回执读取、readonly DB 快照和文本审阅均没有执行副作用。

- authorize 的不确定应答按原键确认已提交，没有补发 Grant。
- 初次受管工具下 GUI 启动未产生可操作窗口，后经正常审批使用同一 VBS 打开；不是更换 Solver 启动路径。
- 自动审批曾拒绝只读观察器的 1200 秒循环，原因为超过用户 300 秒观察限制。该版本未执行；将本轮新观察器收紧为 300 秒后重新经正常审批获准。没有绕过拒绝。没有修改冻结执行控制器。
- 一次报告读取使用系统默认 GBK 导致 UTF-8 JSON 解码失败；明确指定 UTF-8 后成功，未改变任何业务状态。
- 只读观察器正常 exit=0，关闭 13 个持有句柄，termination_calls=0；它未持有终止权限。没有残留后台观察器。
- 未修改核心代码，因此未另行重跑历史 pytest；本报告记录的是本次真实验收，不将历史用例数量复用为本轮结果。

## 8. Git、历史保护与证据位置

开始/结束分支 Develop，HEAD `271c6f82fd6a4599dbae2df30d903dab2cef1f63`，版本保持 0.3.0.dev0，无未解决冲突。原有大量已修改/未跟踪文件保留，最终状态见 `FINAL_GIT_STATE.txt`。本轮仅新增 `docs/agent_first/run_021b/real_001` 审计材料，并由授权的正式产品链产生当前 Project 的 Grant/Run/证据及生命周期记录；冻结执行代码与 119 项材料未变。

未访问 Stable、未操作历史真实 Run 或 owner、未修改共享环境/安装/版本、未迁移数据库、未执行 Git 恢复/提交/推送。未清理任何真实输出或一次尝试记录。只读 GUI 文件选择器曾显示系统保存的默认位置；未选择或打开该位置的 Project，实际目标始终为本次显式根。

主要证据：

- `PREFLIGHT.json` / `PRE_GRANT.json`：真实批准与启动前基线和材料复核。
- `AUTHORIZE.json`：原不确定应答，保留原样；已提交授权回执见 `PERSISTED_EVIDENCE.json`。
- `SUBMIT.json` / `DISPATCH.json`：原接收/派发回执。
- `OBSERVATIONS.jsonl` / `OS_TIMELINE_REVIEW.json` / `OBSERVER_CLOSED.json`：实际 OS 身份、退出样本、句柄收尾。
- `RESULT_BEFORE_STOP.json` / `PERSISTED_EVIDENCE.json`：持久 Run、事件、验证、管理回执及只读诊断。
- `STOP.json` / `STOPPED_INSPECT.json` / `RESTART.json`：安全生命周期回执。
- `RESULT_AFTER_RESTART.json` / `FINAL_READONLY_STATE.json`：重启后相同历史、精确计数、PAUSED、空槽。
- `TEXT_REVIEW.json`：当前原始文本身份及有限白名单行，未复制 ODB 或环境。
- 当前 Project 根下 `project\runtime\standard_runs\r_711c0afc7d49462c8b5c4faf914923b4\stdout.bin` / `stderr.bin`：原始输出；不迁入源码报告。

## 9. 最终验收矩阵与停止

| 项目 | 结论 |
|---|---|
| 冻结对象及 119 引用材料 | MATCH |
| 精确真实 Grant / 提交 / 25 秒单次派发 | PASS；1 次真实 analysis |
| 正常产品 GUI 连接及原 Run 显示 | PASS |
| GUI 与 venv 完整退出、owner 保持 | PASS |
| GUI 完整退出后 Solver 同身份仍活着 | **NOT_OBSERVED** |
| 重开 GUI / 相同 Project、owner、Run、回执 | PASS（后续授权重启后 owner 按预期改变） |
| 受管范围结束 / 正常自动收尾 / 空槽 | PASS（只限声明的受管范围） |
| Solver / 三项 DAT | PASS / PASS |
| ODB 内容 | NOT_RUN，按约定排除 |
| 安全空闲 stop / owner 正常退出 | PASS |
| restart 保持 PAUSED / Run / 消费 / 不重放 | PASS |
| 全体域外进程、完整 Job 层级 | UNKNOWN，不作成功推断 |
| 整体 | **PARTIAL** |

本次唯一真实启动预算已消费完毕。完整 GUI 退出后 Solver 持续运行证据未取得，不能由其他 Run 的历史结果替代。受管范围不能扩展为整机资源互斥、外部服务全部退出或任意 Abaqus 模式兼容；注销、关机、系统重启和故障恢复没有在本次验收。保留当前 PAUSED 服务及所有证据，结束本次工作，不补跑、不进入下一轮。
