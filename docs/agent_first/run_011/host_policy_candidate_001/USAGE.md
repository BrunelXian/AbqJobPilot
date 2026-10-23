# 宿主政策候选：一键无 Solver 自检

本包是独立的待审候选，**尚未获得真实执行授权**。旧 Run011 候选及其原授权不覆盖改变后的宿主条件。本轮真实 Abaqus/真实 execute 调用均为0。

## 操作者入口

在 Windows 文件资源管理器中双击：

`D:\Projects\abqjobpilot_dev\docs\agent_first\run_011\host_policy_candidate_001\SELF_CHECK.cmd`

它只打开固定 Windows PowerShell 5.1 窗口，调用固定 self_check.ps1，再调用登记 LangChainEnv Python 的 **check**。窗口保持打开便于查看结果，没有执行菜单、execute 分支、任意参数转发或自检成功后自动执行。若脚本被系统策略拒绝，保留错误，不改执行策略或换承载渠道绕过。

也可以在现有 PowerShell 中一次调用同一脚本：

```powershell
& 'D:\Projects\abqjobpilot_dev\docs\agent_first\run_011\host_policy_candidate_001\self_check.ps1'
```

自动完成：新旧清单及引用材料复核、已归档操作者证据交叉核对、原公开离线预览、真实实验的既有意图和输出冲突检查、当前 Python/venv/PowerShell 父链身份及存活、同会话与控制台关联、自身和两级父进程的 Job 查询。**不重新跑 Python worker、不调用 Abaqus、不写真实实验根。**

脚本显示 STATUS、机器接口退出码和 REPORT 路径，再显示 JSON。报告独占写入：

`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run011_PolicyCheck_<随机标识>\SELF_CHECK.json`

`SELF_CHECK_PASS` / exit0 表示当前只读视图满足**此候选的有限条件**，同时仍明确 `execution_authorization=NOT_GRANTED`。`SELF_CHECK_BLOCKED` 或 `SELF_CHECK_BLOCKED_OR_UNKNOWN` / exit2 表示不满足或无法确认；保留报告，不删除意图、改输入或重试真实启动。脚本/材料读取错误也没有 execute 回退。

当前工具中的底层 PowerShell 脚本已经实测通过；双击批处理外壳只做固定命令/参数静态检查，未由 Codex 打开一个长期交互窗口。操作者这一次新自检尚未代为执行。它与此前已完成的固定 worker 存续实验是不同检查。

## Agent 机器接口

默认操作也是 check。以下是已有、已验证的机器入口；不要求 Agent 使用 GUI：

```powershell
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B `
  'D:\Projects\abqjobpilot_dev\docs\agent_first\run_011\host_policy_candidate_001\candidate.py' check `
  --candidate-digest 'sha256:d427264f99b2e1128a50d171c09b852cc57662ee002de5c31ba7cdc9d60b840c'
```

入口对父链有固定要求。直接从其他 Python、PowerShell 7 或服务宿主派生可能返回结构化阻断；不要用该错误触发另一个启动渠道。机器 check/report 本身有禁止外部创建、SQLite、网络和 shell 的审计钩子。

已有记录只读查询：

```powershell
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B `
  'D:\Projects\abqjobpilot_dev\docs\agent_first\run_011\host_policy_candidate_001\candidate.py' report `
  --candidate-digest 'sha256:d427264f99b2e1128a50d171c09b852cc57662ee002de5c31ba7cdc9d60b840c'
```

report 不要求模拟新的宿主准入，也不重新探测已有实验进程；只核对包并读取原路径的历史记录。本轮实际返回 NO_ATTEMPT_RECORDED。

candidate.py 保留供将来单独批准后使用的显式 execute 操作，要求外部提供这个新候选的摘要；它在自身进程重新复核，并调用原固定创建函数。**本轮不提供可顺手连续运行的执行步骤、不调用该操作。**摘要只表示对象身份，代码不认证人类批准；这是固定本地实验原有的同一OS用户信任边界，不是新的产品授权平台。正常 check 绝不生成批准文件或 TEST_ONLY/真实 Grant。

## 新政策的实际保证与弱化

- check 和执行 admit 共同使用 `host_policy.evaluate()`；不再一处看 bool、一处走另一规则。
- 仍必须成功查询自身和父链 Job 成员关系，未知拒绝；不读取某个直接 Job 的 kill_on_job_close=false 来放行，也不假装不在Job中。
- 固定链为实际基础Python ← 登记venv启动器 ← 已固定文件身份的 Windows PowerShell；核对 PID、创建时间、映像、当前存活及前后两次父关系；同一非零Windows会话且父PowerShell在当前控制台进程列表中。查询/身份/父链变化拒绝。
- **显式弱化**：允许该固定链处于 Job 中；只能承诺控制器自己的代码不终止后代，以及依赖操作者保持终端/Windows会话存活的有限条件。完整 Job 层级、Job 所有者、未来系统策略和外部终止仍未知。用户关闭终端/注销等行为不在保证内。
- 它不认证“由人从桌面启动”或排除受管工具。工具下也可能满足这些可观测条件；所以 SELF_CHECK_PASS 不是人工执行来源证明，更不是执行许可。未来真实调用仍只能在新候选另行批准后，由操作者按约定主动进行。
- 操作者历史夹具证明一次固定Python链行为；不证明同一政策适用于任意子树、BAT/Intel/Abaqus。参考证据不会被用来补造实际Abaqus成员退出。

## 固定实验预算不变

原实验 `abq2024_r010_a19d17ea`，唯一入口 `D:\ABAQUS2024\Commands\abq2024.bat`，Job `r010_bar_a19d17ea`，原input/cwd/scratch不变，一次Standard analysis、CPU1/GPU0/2048MB、额外调用0，300秒仅停止观察，不终止/重试/删除。

实际调用仍原样读取原清单的 application/command_line/environment，不重新组装。持久尝试仍为原实验根的 `observations\attempt.json`：旧候选、新候选、未来候选共享同一记录和输出身份。已有、半写、损坏或不确定记录均阻断；新摘要没有增加或返还一次尝试预算。

当前的新候选清单 body 摘要是 `sha256:d427264f99b2e1128a50d171c09b852cc57662ee002de5c31ba7cdc9d60b840c`。算法与原机制一致：`json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)` 的 UTF-8 SHA-256；不包含外层 content_digest，不是整个 JSON 文件字节摘要。body绑定37项新包/归档/旧候选/PowerShell材料，同时由旧候选验证其21项和原实验34项材料。

说明、测试、冻结工具和运行后自检报告不进入执行摘要，以避免自引用；实际入口、政策、执行适配、固定材料路径及一键脚本均在37项内。冻结工具不会覆盖既有候选。任何执行材料变更都需要独立新摘要和重新审查，不沿用旧授权。
