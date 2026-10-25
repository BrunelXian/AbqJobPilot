# Run016 使用说明与唯一待审实验

当前状态：仅准备，Abaqus调用0；没有真实Grant、Run、提交回执或启动意图。不要现在点击启动/提交。须先取得针对本清单的明确批准。

## 固定对象

- 实验：`run016_8a85583d797345d0b9a4a27b64511b44`
- 清单：`D:\Projects\abqjobpilot_dev\docs\agent_first\run_016\ACCEPTANCE_MANIFEST.json`
- body SHA-256：`88ddae420d2fd73f0ecb7bace4171bb8f0eb6a6b2098b0d91e558c94338f3fd7`
- Project：`p_a9c341833aca442f9be8128eff40a484`；instance：`pi_4e7e059e0330465bab4ad35997ae4b71`
- 根：`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run016_8a85583d797345d0b9a4a27b64511b44`
- 存储：`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run016_8a85583d797345d0b9a4a27b64511b44\project\execution.sqlite3`（本轮全新format3；未迁移旧库）
- 入口：`D:\ABAQUS2024\Commands\abq2024.bat`，仍由 `C:\Windows\System32\cmd.exe /d /s /c` 固定模板调用；保持现有VS包装器风险，不修复或绕开。
- 两项均为 Standard analysis、CPU=1、GPU=0、2048MB、一次启动预算；额外Abaqus调用0。没有Datacheck/版本/许可探测/Viewer/ODB读取。
- Plan有效至 `2026-11-23T09:03:25+00:00`。这不是已发出的执行授权。

| 项 | A | B |
|---|---|---|
| Plan | `plan_10f4850d334947a3af4ec022c978d003` | `plan_7c45450805de438c85af08169a2a9ffa` |
| Plan digest | `sha256:08107cf8f0407a657b29d2c3ee40859cd6f25012a7af7e22fdab2ba6fc01ac79` | `sha256:386da2c474cd54a5338f49d795496c1cdec13393fe71d2e06a94362e01746bdb` |
| Job | `r016_bar_a_8a85583d` | `r016_bar_b_797345d0` |
| cwd/输出目录 | `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run016_8a85583d797345d0b9a4a27b64511b44\engineering_a` | `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run016_8a85583d797345d0b9a4a27b64511b44\engineering_b` |
| scratch | `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run016_8a85583d797345d0b9a4a27b64511b44\engineering_a\scratch` | `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run016_8a85583d797345d0b9a4a27b64511b44\engineering_b\scratch` |
| 输入 | cwd下 `axial_bar.inp` | cwd下 `axial_bar.inp` |
| 请求键 | `run016-A-once` | `run016-B-once` |

两个输入均是420字节冻结副本，SHA-256 `e2f91730b68f3af72b8054bc168d31b72a3f21ae186e899d64ab4b6b761523a3`。不改变模型延长运行。每项精确JOB_LIST/HANDLE_LIST策略和实现摘要已绑定Plan/待批准范围；Run ID只在以后公开接受事务时产生，不预造。

## 现在可用：无Solver核验

双击 [R16_01_Check.vbs](../../../examples/agent_first/R16_01_Check.vbs)。这是已有operator入口的薄包装，不会批准或执行。也已从非仓库cwd实际执行以下准确命令：

```powershell
Set-Location 'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run016_prepare_client_gbfmx1pc'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B 'D:\Projects\abqjobpilot_dev\examples\agent_first\standard_service.py' check --pair
```

实际输出 `MATERIALS_MATCH_NO_EXECUTION`、Grant=false、Abaqus=0；`CLI_CHECK.txt`保留。49项候选材料及独立Runtime材料按字节重新核验。自检不替代实际owner中的宿主查询、输入、窗口、授权、输出及一次尝试检查。

## 批准之后的现有入口（本轮未执行）

批准确认后，由可信操作者/本任务在既有 `authorize --pair --approval-source <真实授权来源引用>` 入口登记精确两项Grant。它持原独占准备租约、同事务绑定本批两个Plan，不提交、不启动，不自动恢复派发。这里的来源只是已给批准的审计引用；当前尚无此批准，不能填虚构来源。不要向普通客户端添加approved字段，也不要另建批准文件层级。

1. [R16_02_Start_Service.vbs](../../../examples/agent_first/R16_02_Start_Service.vbs)：启动原Supervisor；没有offer时明确GRANT_REQUIRED，不会擅自签发。owner日志进本实验logs目录。
2. [R16_04_View_A.vbs](../../../examples/agent_first/R16_04_View_A.vbs)：打开现有Dev GUI，显式隔离Project；在提交前会显示未提交。该GUI连接不批准或恢复。
3. [R16_03_Run_A_Then_B.vbs](../../../examples/agent_first/R16_03_Run_A_Then_B.vbs)：薄公共Python客户端执行A→等待→条件成立后提交B。所有最终资格仍由服务器重验。操作者无需拼长命令或保持PowerShell窗口；保持Windows会话/承载服务环境。
4. A仍求解时可正常关闭这次打开的整个GUI，再打开同一入口；只读重连原Run/回执。若错过时机记未观察到，不能再增加第三次启动。
5. [R16_05_View_B.vbs](../../../examples/agent_first/R16_05_View_B.vbs)：查看B同一Project Run。分别查看执行、范围收尾、Solver、验证和未知维度。
6. [R16_06_Read_A_Report.vbs](../../../examples/agent_first/R16_06_Read_A_Report.vbs)、[R16_07_Read_B_Report.vbs](../../../examples/agent_first/R16_07_Read_B_Report.vbs)：用原请求键查询回执并导出当前诊断快照，不重新提交。不确定应答先使用这些只读入口，不反复点击提交。
7. [R16_08_Stop_Owner.vbs](../../../examples/agent_first/R16_08_Stop_Owner.vbs) 是**独立显式停服动作**，不属于批次自动收尾。本轮及未来验收不自动点击。停止只在worker观察结束后退出服务，绝不代表Solver已停止；不清除未决槽/记录或删除文件。

VBS路径和参数已逐一静态核对；本轮没有把真实启动入口的双击描述为已执行。对应真实CLI仍是同一个 `standard_service.py` 的 `start/submit/gui/report --pair`，GUI/report可加 `--task A|B`。实际公开 `standard_client.run_pair` 已通过固定Python替身的Windows IPC链路验收，没有tests导入或直接SQL。

## 时限与失败

未来登记两项Grant时刻T开始计时，A必须在T+600秒前发起创建。A原接受回执时间S同时固定Run.created_at，B最迟在 `min(T+930,S+330)` 前发起原生创建；原生API调用紧前再检查一次。每项从创建调用返回起最多300秒观察，并截于S+630；外部创建耗时另外记录，不能声称它受观察计时器硬限制。

A只有范围结束不足以放行B。必须是本次策略的受管范围完成证据、正常终态事务、槽释放、Solver完成、三项DAT全PASS、有效B许可/输入/输出和OPEN派发门。行政释放、owner重启、PAUSED、到期、输出冲突都不能放行。

失联在B未接受前停止编排；已接受但丢失应答的B仍是原持久请求，可能在原窗口内启动，通信丢失不取消它。按原键查，不改键重试。观察结束不terminate/kill、不删除scratch/输出、不重试，不产生延后补启动。无法确认时保存阻断。

## 证据和完成判据

- 服务记录：Project内execution.sqlite3、runtime/standard_runs/<公开Run ID>/stdout.bin、stderr.bin、运行证据及独立validation。
- 真实工程文本/ODB文件若将来产生，分别留在engineering_a、engineering_b；各Job的隐藏.intent.json保留。ODB存在不代表内容验证。
- 原回执：实验根 `session/A/receipt.json`、`session/B/receipt.json`；诊断 `session/diagnostic_<uuid>.json`。
- owner及连接材料：`control/`、`private/`；private含连接秘密，不复制进报告。
- 正常范围收尾应为COMMITTED_EMPTY_SCOPE，来源是原Job直接查询和事务。全局Solver成员完整性/overall_exit仍UNKNOWN，不强行改成VERIFIED。
- 分别验证节点2 U1=0.01mm（1e-6）、单元1/IP1 S11=1MPa（1e-4）、节点1 RF1=-1N（1e-4）；输入、实体、读法和容差不改。
- 若发现关键求解/输出实际在域外服务或其他未覆盖范围内，该配置不能称为可靠自动收尾；保留事实并停止后续启动。不用已枚举PID数证明完整性。

当前准备材料和替身结果没有证明真实Abaqus新创建方式、外部服务边界、Windows注销/重启或终端关闭语义。受管范围不是整机资源/跨Project锁，也不是OS安全沙箱。

## 摘要算法

沿用 `execution.models.digest`：仅对JSON顶层body用UTF-8、ensure_ascii=False、sort_keys=True、separators=(',',':')序列化，禁止浮点，计算SHA-256；content_digest不参与自身摘要。materials保存真实文件原始字节摘要/大小/绝对路径。不是整个清单文件原始字节摘要，不是可信签名或审批本身。代码或材料变化后当前清单不再匹配，应停止，不偷偷重建后沿用批准。
