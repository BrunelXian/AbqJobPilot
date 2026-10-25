# Run021B — 产品单项真实执行控制候选就绪

**PASS_ABQJOBPILOT_AGENT_FIRST_RUN021B_CONTROL_PLANE_READY**

本轮已实现精确真实Grant登记、服务端单Run一次派发、产品Standard配置及安全停服接缝，复用同一ExecutionService、Supervisor、存储、授权消费、Job范围和DAT验证。通过392个唯一测试，真实Abaqus调用 **0**。这是候选实现验收，不是真实产品Standard实机通过。

## 实现与关键保证

- 正常产品Project默认仍空、PAUSED、无Grant，不自动获得真实能力。可信初始准备才绑定一个single Standard Plan。
- 独立DPAPI操作者能力不同于IPC和Start/Stop权限。真实Grant精确绑定Project/Plan/输入/入口/资源/输出/期限/单次预算和授权出处；TEST_ONLY不能升级。
- 接受与派发分离。**全局PAUSED从未打开**；只允许精确owner/Plan/Grant/Run/revision在限定窗口消费一项许可。START_INTENT/slot/许可消费同事务，实际创建前再次检查。失败和owner崩溃不补发、不重跑。
- 沿用原management回执和只读查询；同键重放不重复效果。正常受管结束和原事件成立、slot空、无未决执行才可Stop。重启PAUSED，历史和消费保持。
- GUI仍为既有Dev主窗口，普通客户端仍通过原IPC；没有第二执行核心、新Backend、MCP写工具、数据库迁移或系统服务。

设计和精确权限见[CONTROL_CONTRACT.md](CONTROL_CONTRACT.md)，入口见[USAGE.md](USAGE.md)。

## 当前待审候选（未执行）

| 字段 | 已固定值 |
|---|---|
| 实验 | run021_42b9754ee29b457d8c86b2e97a26ec4b |
| Project | p_fa698230f3e6499caf08517e3e82dbc2 |
| instance | pi_88118c5738214496aa2757ef5265df50 |
| 根 | C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run021_42b9754ee29b457d8c86b2e97a26ec4b |
| Plan | plan_499a7ab80b804e11939fc760ac3a2243 |
| Plan摘要 | sha256:627392a372ffd209e216d7a4f494c206db0fe28ff1e5a98c2d9c5d0bb5c9bf4a |
| 输入 | 根下engineering\axial_bar.inp，420字节 |
| 输入SHA256 | e2f91730b68f3af72b8054bc168d31b72a3f21ae186e899d64ab4b6b761523a3 |
| Job | r021_bar_42b9754e |
| cwd/output / scratch | 根下engineering / engineering\scratch |
| 唯一入口 | D:\ABAQUS2024\Commands\abq2024.bat |
| 资源/调用 | CPU1、GPU0、2048MB；最多一次analysis；额外调用0 |
| 观察 | 最多300秒，仅结束观察，不终止、不重试、不删除 |
| Grant / 派发窗口 | 待后续批准才登记；最多600秒Grant，显式单项25秒启动窗口 |
| 当前持久状态 | 1正式Plan、0Grant、0Run、0消费/回执/事件；PAUSED版本1；supervisor_started=0 |
| 冻结清单 | ACCEPTANCE_MANIFEST.json，119项引用材料 |
| 规范化body SHA256 | **efdee66a3639bbfe95d084e90036e6376eaa3120c975918423afedf0b72220e1** |

摘要是UTF8 canonical_json(body)的SHA256，不是完整JSON原始字节摘要；引用文件分别核对原始字节身份。旧不完整准备摘要c5b2…保留，仅追溯来源，不升级为授权。原候选目录只增加离线Plan/服务准备材料，未启动owner；CANDIDATE_CHANGE和CANDIDATE_PUBLIC_CHECK给出实际结果。Plan有效期由PLAN.json的expires_at固定，过期不静默延长。

## 实测结论与限制

新增32项控制/离线测试及4项真实Windows替身测试；相关回归和Legacy合计最终392唯一PASS，0最终FAIL/0SKIP。失败迭代和选集见[TESTS_AND_ACCEPTANCE.md](TESTS_AND_ACCEPTANCE.md)及XML。没有凑数或删除旧断言。

最新Windows Run `r_a97a0ff746a3463eb4a29b6ce4fa4d92`：正常GUI启动产品Supervisor；独立客户端提交后仍PAUSED；明确许可后固定Python创建一次。GUI及venv实际exit0后，原owner/worker身份匹配仍活，STA116→126字节；重开原Run。范围正常结束、slot释放、独立DAT结果分开显示；空闲stop/restart后PAUSED、历史回执/消费不变。每个owner的native Job/root句柄关闭证据独立保存。

确定性硬退出发生在claim后及create后。创建后worker仍活，旧许可不复活，产品入口拒绝不安全重启。此事实不等于自动恢复能力；本轮没有实现接管、补造退出或重跑。

Standard执行被强制固定Python替代，native audit在创建前拒绝Abaqus和无管理fallback。文本来自明确历史DAT样本，故测试的Solver/DAT结论不代表候选已经执行。完整物理进程全集仍UNKNOWN；ODB NOT_RUN；实际Abaqus产品宿主、域外服务、注销/重启和主机级资源竞争仍待验收。

最终373份本轮进程身份核对无匹配存活；387份残留测试私有文件已清理，后续最终复查无新增残留。候选private与历史根排除清理；没有停止/接管历史owner。没有Stable访问、共享环境/安装修改、Git提交推送，版本仍0.3.0.dev0。

## 唯一下一步：独立真实审批

现在停止在候选真实Grant创建之前。请求用户另行批准：

**为上述清单body `efdee66a…72220e1` 绑定的新产品Project/Plan登记一次精确真实Grant，经公共客户端提交唯一Run并显式消费一次25秒派发许可，执行最多一次固定Abaqus Standard analysis；按300秒仅观察、禁止终止/重试/删除的边界，完成GUI关闭重连、受管收尾与三项DAT验证，在符合严格空闲条件时正常停服，再显式重启确认PAUSED和原历史保留。**

数值标准不变：节点2 U1=0.01mm±1e−6；单元1/积分点1 S11=1MPa±1e−4；节点1 RF1=−1N±1e−4。ODB不验证；GUI时机错过则NOT_OBSERVED，不增加第二次analysis。无法安全收尾时不Stop，不释放未知资源。重启后的owner保持PAUSED供只读检查，不自动执行下一任务。

本轮开发授权没有批准这次实机动作；等待明确批准，不自动进入真实执行或下一轮。
