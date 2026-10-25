# Run021B 使用与下一次审批停止点

当前只可审查及只读核验。候选尚未获得真实执行批准，**不要执行authorize/submit/dispatch**。准备文件不是Grant；清单摘要也不是批准。

正常GUI入口：`D:\Projects\abqjobpilot_dev\Open_Dev_GUI.vbs`。后续获批时选择候选产品根，再显式Start Service；普通打开/连接不批准、不提交、不派发。

## 已实际验证的无Solver命令

登记解释器Python3.12.10。下面的check已从候选根（非仓库cwd）运行，结果保存在CANDIDATE_PUBLIC_CHECK.json：

```powershell
$py = 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe'
$entry = 'D:\Projects\abqjobpilot_dev\examples\agent_first\product_standard_acceptance.py'
$manifest = 'D:\Projects\abqjobpilot_dev\docs\agent_first\run_021b\ACCEPTANCE_MANIFEST.json'
$hash = 'efdee66a3639bbfe95d084e90036e6376eaa3120c975918423afedf0b72220e1'
& $py -B $entry --manifest $manifest --body-sha256 $hash --action check
```

它重新计算规范化body摘要，核对119项实际材料，读取产品Plan/输入/配置和冲突状态。无外部进程创建，无Owner租约，无Grant、Run、事件或gate写入。当前应显示1 Plan、0 Grant、0 Run、PAUSED和NOT_RUNNING。导入、help不执行任务。检查失败停止，不重建清单沿用旧授权。

## 获得下一次明确授权后才可执行的步骤

这些是已存在入口的准确参数；本轮只在替身中验证其底层控制接口，**未对候选执行以下写操作**。

1. 正常GUI选择候选根并Start，或上面命令追加 `--action start`。认证连接同一owner。
2. `--action authorize --subject <实际操作者引用> --source <实际授权消息引用>`：通过独立Standard能力向当前owner登记一次精确Grant。必须使用真实授权来源；占位文字不可作为批准。
3. `--action submit`：独立公共Python客户端使用冻结幂等键和原Grant创建唯一Run。仍PAUSED，无启动。
4. `--action dispatch`：独立明确许可，精确Run/revision/owner，25秒启动窗口。全局仍PAUSED，只有该Run可进入一次受管创建。不得因窗口过期换键补发。
5. `--action report`：只读原接收回执、Run、gate、诊断。GUI选同一Run看状态/有界日志。在身份匹配的Solver仍存活时正常关闭GUI，记录GUI及venv退出、owner/Solver身份与日志增长，再重开同Run。如果过快记NOT_OBSERVED，不重跑。
6. 最多300秒观察；不terminate、重试、删输出。缺少受管正常收尾或slot仍占用时，不停服、不清理。
7. 符合安全空闲条件时 `--action stop`。再 `--action restart`，确认PAUSED、原Run/回执/消费保持，未新增启动。重启后保留owner供只读观察；不要重复旧stop键停止另一个owner。

示例的authorize/dispatch操作参数会写入候选private下独立操作记录：原owner、原deadline和原键持久保留，没有连接秘密。同一操作应答丢失后，使用原键只读查询；同命令重放也保留原参数，不能删除记录延长窗口。

公共API与信任边界：

```python
from abqjobpilot.service_lifecycle import ServiceLifecycleManager
from abqjobpilot.product_standard import StandardOperator
manager = ServiceLifecycleManager(explicit_product_root)
client, context, health = manager.connect()  # 不需要Standard批准能力
receipt = client.management_receipt('product_standard_dispatch_once', original_key)
```

普通client只有连接上下文，不能从中得到StandardOperator的private能力。StandardOperator仅供可信本机操作者；不新增GUI/普通CLI/MCP批准功能。连接秘密不应复制到说明、session或报告；Project副本不得连接原owner。

## 唯一候选

- Project `p_fa698230f3e6499caf08517e3e82dbc2`；instance `pi_88118c5738214496aa2757ef5265df50`。
- 根 `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run021_42b9754ee29b457d8c86b2e97a26ec4b`。
- Plan `plan_499a7ab80b804e11939fc760ac3a2243`；Plan摘要 `sha256:627392a372ffd209e216d7a4f494c206db0fe28ff1e5a98c2d9c5d0bb5c9bf4a`。
- 输入 `engineering\axial_bar.inp`；SHA256 `e2f91730b68f3af72b8054bc168d31b72a3f21ae186e899d64ab4b6b761523a3`。
- Job `r021_bar_42b9754e`；cwd/output `engineering`；scratch `engineering\scratch`。
- 唯一入口 `D:\ABAQUS2024\Commands\abq2024.bat`；CPU1/GPU0/2048MB；一次analysis，额外调用0。
- 节点2 U1=0.01mm±1e−6；单元1/积分点1 S11=1MPa±1e−4；节点1 RF1=−1N±1e−4；ODB NOT_RUN。

Plan/源文件/Runtime/输入改变后原清单不匹配，必须停止重新审查。本轮旧不完整准备摘要仍保留，不作为该新候选授权依据。
