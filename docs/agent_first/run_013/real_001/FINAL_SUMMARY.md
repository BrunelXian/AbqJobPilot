# Run013 唯一实机验收结果

**整体：PARTIAL。** 一次真实服务链 Standard 分析、GUI 完整退出后的 Solver 持续运行、重连原 Run，以及冻结的三项 DAT 数值验证已取得证据。完整 Solver 成员集合及整体退出仍为 UNKNOWN；未将这些未知项推定为成功。

实验 `run013_e52135d71d2c43d2a45301c586cbfb7e`；清单 body SHA-256 `3c59461d53e658eb9894d6936bd405f85a7f27b6ebc3deb5343c81d8411ceebe`。

- Project：`p_9204fe8fced549d28d8bd62d1b2f8455`
- instance：`pi_776faf62f2d64a4ab23e83c53b665788`
- Plan：`plan_ed1ac113f464496497d8787268189c4f`
- **Run：`r_609c9bbfd9c54b3ca2fce23bbd6059e4`**
- 回执：`req_c17228560b40411585817099ed5ddbd3`
- 启动阶段尝试：`phase_5b46d6d7f0aa42bf82d3a353a4b1e359`
- owner：`owner_17886eb60d8349e880d61131a04be3b3`，OS PID17528，创建身份 `134372377146539267`。

## 分维度结论

| 维度 | 实测结果 | 证据 |
|---|---|---|
| 批准对象及实际材料 | 清单规范化 body、42项候选材料、20项Runtime引用、库内固定Plan及输入匹配；执行后再次匹配 | PREFLIGHT.json、FINAL_AUDIT.json |
| 批准与提交 | 现有可信 authorize 入口登记精确 REAL_FIXED_STANDARD；现有公共 submit 入口提交1次，非重放；接收事务在外部创建前持久化 | ORIGINAL_RECEIPT.json、FINAL_EVENTS.json、FINAL_AUDIT.json |
| 实际调用 | 包装器入口启动1次；额外Abaqus入口调用0次；单一启动意图、创建记录及wrapper身份 | FINAL_EVENTS.json、FINAL_PUBLIC_RUN.json、工程目录的意图文件 |
| Runtime | stdout记录 `Abaqus 2024`、本次Job及 Standard Analysis 开始/结束；OS观察到固定安装路径的 standard.exe / pre.exe | FINAL_AUDIT.json、TEXT_FILE_IDENTITIES.json、FINAL_PUBLIC_RUN.json |
| GUI退出时Solver | PID612、创建身份134372378234532047的 standard.exe，在关闭前、GUI及venv完整退出后、重连时均由保留句柄确认仍存活 | BEFORE_GUI_CLOSE.json、AFTER_GUI_CLOSE.json、GUI_RECONNECTED.json |
| 重连 | GUI B连接同Project、同owner、同Run、同原回执；没有新提交/新启动 | GUI_RECONNECTED.json、FINAL_GUI_VIEW.json、FINAL_AUDIT.json |
| 已观察进程退出 | 11个已记录进程均取得句柄退出码0；包装器cmd.exe PID8536约创建16秒后被观察为退出 | FINAL_PUBLIC_RUN.json、EARLY_EXIT_OBSERVATION.json |
| 完整成员/整体退出 | **UNKNOWN / UNKNOWN**。父子关系候选与已记录成员退出不是完整集合证明 | FINAL_PUBLIC_RUN.json、DIAGNOSTIC.json |
| Solver | **COMPLETED_TEXT_EVIDENCE**：当前DAT完整页脚与STA、MSG完成标记交叉成立 | FINAL_VALIDATIONS.json |
| DAT主三项 | **PRIMARY_THREE_PASS**，独立验证记录PASS，范围仅 fixed_standard_dat_only | 下表、FINAL_VALIDATIONS.json |
| ODB内容 | **NOT_RUN**；未读取ODB内容，未调用Abaqus Python/Viewer等补验 | FINAL_PUBLIC_RUN.json |
| 300秒观察 | 到期正常结束观察；没有终止、重试、删除或后台追加观察。期限到达前所有已观察成员已退出 | STANDARD_OBSERVATION_ENDED事件、FINAL_PUBLIC_RUN.json |
| 保留门禁 | execution=BLOCKED，RECONCILIATION_REQUIRED；派发门PAUSED version3；单槽仍绑定本Run | FINAL_GATE.json、FINAL_AUDIT.json |

`eliT_CheckLicense.exe` 等是此次唯一 analysis 包装器自然启动链中的观察对象，不是另外发起的许可证查询。未额外调用任何 Abaqus 入口。

## 数值验证

服务使用既有 `standard_dat.py` 的严格CP936解析和固定2024版式规则。位置固定为Step1 / Increment1 / final time1，没有改输入、读取对象或容差。

| 量与位置 | 实际值 | 参考值 | 绝对误差 | 冻结有效容差 | 判定 / DAT行 |
|---|---:|---:|---:|---:|---|
| 节点2，全局U1 | 0.010000000 mm | 0.01 mm | 0 | 0.000001 mm | PASS / 218 |
| 单元1，积分点1，S11 | 1.000 MPa | 1 MPa | 0 | 0.0001 MPa | PASS / 203 |
| 节点1，全局RF1 | −1.0000000 N | −1 N | 0 | 0.0001 N | PASS / 227 |

DAT：`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run013_e52135d71d2c43d2a45301c586cbfb7e\engineering\r013_bar_d48c54f7.dat`，10334字节，SHA-256 `41488640e73e3d3d4ac8d19b26b5a512e125c7e731e6463b1f7e89bfee8be363`。

输入副本420字节，SHA-256 `e2f91730b68f3af72b8054bc168d31b72a3f21ae186e899d64ab4b6b761523a3`。输入保留R010 Heading，但证据归属由本次新Job、目录、Run/尝试、启动前无输出、创建/修改时间及内容摘要建立，不使用旧实验结果。DAT/STA/MSG的文件身份、时间及摘要与服务持久化验证一致。

服务附加检查中的节点1 U1/U2/U3没有打印行，诚实保留NOT_RECORDED，`full_frozen_checks=NOT_ALL_ESTABLISHED`。它不改变本次明确授权的三项主标准PASS，也不被补成0。没有宣称“所有可选检查均通过”。

验证ID：`val_67bc37128dcb48d7b4978095713a3174`；观察引用 `obs_3805c9e40111420291557e6eabd12c6a`。这些由实际服务结果事务生成，不是测量程序写库。

## GUI实际生命周期与时序（本机UTC+08）

1. 服务先启动并保持独立owner，GUI A显示显式Project且“未提交”。随后只调用一次冻结公共提交入口。
2. 22:03:34 接收/启动意图/外部创建发生；创建调用耗时记录15ms，服务观察期限为创建返回后300秒，非Solver运行硬限。
3. 22:03:43.583 关闭前：标准求解进程PID612、创建身份134372378234532047已核实且仍存活；GUI已显示本Run及原回执。
4. 22:03:43.786～.792：向仅本次GUI的已核验HWND发送正常WM_CLOSE；实际GUI PID16664、专属venv PID12700均取得退出码0。主循环返回，非daemon公共读取线程已join。此后原owner与同一Solver句柄仍未signaled。
5. 22:03:44.342：GUI B已重连原Run和回执；此时同一Solver仍存活。没有重提请求、批准、恢复或owner重建。
6. 22:03:50.595 公共读取取得关闭后新增的STA444字节、MSG7605字节及完成标记。此时服务已记录Solver退出；不将该日志更新额外宣称为“当时Solver仍在运行”。见 LOG_UPDATE_AFTER_GUI_CLOSE.json。
7. 22:08:34 到达观察期限，服务保存文本观察/独立验证并PAUSED。GUI B继续显示原Run及各维度终态/未知项。

GUI测量复用已有 `tests/run012_gui.py`，实际构造现有 `AbqJobPilotApp`，与产品 `standard_service.py gui`使用同一连接和请求键。已有回调读取实际渲染widget，未替换界面、公共客户端或业务逻辑。测量驱动不含授权、提交、Backend启动、数据库写入或owner控制，只进行自身GUI生命周期及OS身份观察；真正执行仍完全由冻结服务负责。

测量程序中的 `log_change_after_close` 原始字段可能包括读取时间变化，**不作为字节增长证据**；本报告使用独立的 LOG_UPDATE_AFTER_GUI_CLOSE.json 对实际byte-count变化的核验。

## 实际宿主与保留状态

实际owner的同进程准入记录：Job查询成功、in_any_job=true、标准输出/错误为普通磁盘文件[1,1]、eligible=true；使用已批准的 `independent-service-same-windows-session-v1`。这是限定的服务宿主契约，未使用breakaway、调度服务或Job修改，也没有套用旧PowerShell承载链结论。

11个观察成员的退出记录来自服务保留的Windows句柄/直接Popen句柄；测量程序额外取得的关闭GUI前后存活证据单列在测量JSON中，没有反写为服务观察。

截至最终审计，**owner和重开的GUI B仍运行**；测量程序已正常退出并关闭自身保留句柄。活动连接凭据、数据库、意图、输出和scratch均保留，没有自动调用stop。可以正常关闭这个只读Dev GUI；这不会停止owner。但本次没有授权/执行owner收尾，继续保持Windows会话；不从已观察进程退出推导未知成员绝不存在，也不自动解除门禁。

完整成员集合、真实Run显式对账/安全释放、owner/Job退出、终端关闭、注销/重启、真实进程接管及跨Project资源协调仍未验收。ODB内容验证仍未执行。

## 审计与文件位置

实际基线仍为Develop@fb7912ec9e0107b18f65948b147c87579c87cded，版本0.3.0.dev0，无未解决冲突。只新增本目录测量、报告及本次隔离实例的正常授权/服务执行记录。原候选与42+20项引用材料执行后复核保持，Run010/011未读取、修改或清理。既有未提交成果保留。

- 原生服务存储：实验根下 `project\execution.sqlite3`。最终plans/grants/runs/receipts/consumption均为1，events20，observations1，validations1；slot仍绑定原Run。
- 实际 stdout/stderr：实验根下 `project\runtime\standard_runs\r_609c9bbfd9c54b3ca2fce23bbd6059e4\stdout.bin`、`stderr.bin`。原始输出留在隔离根；报告不转录许可证服务器等无关信息。
- 一次尝试意图：实验根下 `engineering\.r013_bar_d48c54f7.intent.json`，原样保留。
- 服务持久化证据公开快照：FINAL_PUBLIC_RUN.json、FINAL_EVENTS.json、FINAL_VALIDATIONS.json、FINAL_GATE.json。
- 白名单只读导出：DIAGNOSTIC.json；只代表声明的读取时点，不含Artifact原始字节，不是执行或恢复许可。
- GUI测量：READY.json、BEFORE_GUI_CLOSE.json、AFTER_GUI_CLOSE.json、GUI_RECONNECTED.json、FINAL_GUI_VIEW.json及gui_A/gui_B目录。
- 启动前后审计：PREFLIGHT.json、FINAL_AUDIT.json、TEXT_FILE_IDENTITIES.json、MEASUREMENT_RESULT.json。

本次没有修改执行核心，未重跑无关离线回归；新增验收证据是一次真实Windows服务链执行。一个早期只读PowerShell检查命令因引用转义失败，随后用标准输入脚本完成复核；该错误发生在授权登记及提交之前，未创建执行尝试。实际唯一提交成功后没有任何重提或修复重跑。

未访问Stable、生产Project/队列/数据库，未修改共享环境或安装，未执行Git写操作。额外Abaqus调用0；未调用Viewer/CAE/Abaqus Python，也未打开ODB。到此停止，不进入下一轮。
