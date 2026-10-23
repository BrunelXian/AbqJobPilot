# Run 010 已授权实验 — 启动前阻断记录

**BLOCKED_BEFORE_LAUNCH**。用户已经明确授权，不缺少授权。本次按用户“无法保证300秒仅停止等待、不终止时必须在启动前停止”的要求停止：现有工具会话下普通Python子进程仍处于带KILL_ON_JOB_CLOSE的Windows Job中，未能证明会话结束不会终止后代。

**Abaqus包装器实际调用0次，额外Abaqus调用0次。** 未写START_INTENT，没有发起、丢失或重放实际启动尝试；没有Solver结果。不是“求解失败”，也不是“已运行后超时”。没有收到真实调用的自动审批拒绝，因为尚未提出真实调用。原准备阶段PARTIAL报告、冻结清单和53项源码均保留不变。

## 批准对象与材料核验

- 实验：`abq2024_r010_a19d17ea`，Job=`r010_bar_a19d17ea`。
- 原清单：`D:\Projects\abqjobpilot_dev\docs\agent_first\run_010\EXPERIMENT_MANIFEST.json`。
- 按原`execution.models.digest(body)`规范化规则得到：`sha256:04ed053817a7d05c2355d9a93a41216309bb5d28a235f569a250eea6ee4af2b6`。这是规范化body摘要，不是排版JSON文件的字节摘要；两者分别记录。
- 调用原`examples/agent_first/abaqus_probe_review.py`，返回OFFLINE_PACKAGE_UNCHANGED；随后逐项记录34份实际引用材料的字节摘要与大小，全部匹配，包括输入、预览、Profile、BAT、SMALauncher、Intel脚本、站点配置和观察方案。
- Dev仍为`Develop@fb7912ec9e0107b18f65948b147c87579c87cded`，无冲突，版本0.3.0.dev0。原53项源码摘要全部不变，没有持续并行修改迹象。
- 原隔离根`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a`内，engineering只有axial_bar.inp和空scratch；observations/extracted为空；没有该Job输出、既有START_INTENT或运行证据。准备阶段中间脚本及三个测试目录处于其他子目录，本次没有执行、修改或清理它们。
- 入口/阶段/cwd/CPU1/GPU0/2048MB/一次analysis/额外0次均与用户批准对象一致；本次没有重拼或替换实际命令。

逐项证据见`MATERIAL_PRECHECK.json`、`AUTHORIZATION_SCOPE.json`和`BASELINE_STATUS.txt`。

## 第7项启动前条件未通过

使用已登记LangChainEnv Python3.12.10进行只读材料核验；Windows11 10.0.26300。普通Python生命周期探针另使用登记的Python312绝对基础解释器，只调用Windows身份/Job查询，不执行Abaqus、不改Job配置。

| 观察对象 | 实测结果 |
|---|---|
| 工具内Python PID29140 | IsProcessInJob=true；扩展限制查询成功，flags=0x3000：KILL_ON_JOB_CLOSE + SILENT_BREAKAWAY_OK |
| 通过同样Popen、shell=False、close_fds=True、CREATE_NO_WINDOW生成的venv Python | 实际PID31188，仍在Job中；venv启动器PID20896；正常退出0 |
| 直接使用基础Python，排除venv重定向器影响 | PID17472，仍在Job中，正常退出0 |
| 基础Python中进一步查询Job限制 | PID10244，flags=0x2800：KILL_ON_JOB_CLOSE + BREAKAWAY_OK；没有SILENT_BREAKAWAY；正常退出0 |
| 仅对普通Python试验显式CREATE_BREAKAWAY_FROM_JOB | PID20324仍报告IsProcessInJob=true；正常退出0。没有证明剩余Job链限制已被排除，也未把该标志应用到Abaqus调用 |

首次venv探针的预期“子进程不在Job中”断言失败；该Python已返回0后才断言，未打印保存其PID。此诊断证据限制保留在`HOST_LIFECYCLE_PRECHECK.json`。后续探针均记录PID、正常退出，并显式关闭本次持有的管道和Popen句柄。没有使用kill/terminate，也没有按名称操作进程；探针的10秒communicate等待未超时，且没有使用会在超时kill子进程的subprocess.run。

微软说明，KILL_ON_JOB_CLOSE可在Job最后一个句柄关闭时终止关联成员；嵌套Job会影响breakaway行为。因此，不能只看到父层SILENT_BREAKAWAY就认为后代已脱离，也不能把300秒应用层poll截止当作整个工具生命周期的存续保证。[Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)、[Job limit flags](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information)。

当前证据并非证明“300秒一定杀进程”，而是**尚不能排除外层会话收尾杀进程**。没有用真实Solver试错这一边界，没有修改外部Job限制、换Abaqus入口、扩大终止权限或增加后台服务来绕过它。真实启动尝试预算没有被使用，但也不自动再试；需要先有可核验的控制器/工具会话生命周期方案，后续仍必须重新核对原批准材料与输出冲突。

## 实际结果表

| 维度 | 实际结果与证据 |
|---|---|
| 清单及引用材料 | 全部匹配；34项实际材料及53项既有源码不变，MATERIAL_PRECHECK |
| 实际调用次数 | 包装器0；额外Abaqus0；未产生启动意图 |
| Runtime | **未运行验证**；仅原安装登记2024、SMALauncher静态版本6.426.0.23224仍匹配，没有新的产品横幅 |
| 启动和退出 | 没有包装器或Solver进程；只有普通Python前置探针正常退出。不能把这些当成Abaqus成员退出证据 |
| Solver结论 | NOT_RUN / 未发起；没有分析完成或失败结论 |
| 打印数值验证 | NOT_RUN；没有本次DAT，下表实际值/误差不可得 |
| ODB内容验证 | 本次未执行；没有通过结论 |
| 观察上限 | 300秒实验计时未开始，未触发实验超时；没有超时停止Solver的操作 |
| 遗留事项 | 需解决外层会话/嵌套Job的非终止保证；原三个测试目录及中间脚本按用户指令保留；待批准输入与所有材料保留，没有新求解输出 |

## 冻结数值判据（未运行，不填造实际值）

统一规则：`abs(actual-reference) <= max(abs_tol, rel_tol*abs(reference))`。

| 量与实体 | 参考值 | 实际值 | 误差 | 冻结容差 | 判定 |
|---|---|---|---|---|---|
| step1最终time1，node2 U1 | +0.01 mm | 未取得 | 不可计算 | abs=1e-6 mm，rel=1e-4，有效阈值1e-6 mm | NOT_RUN |
| 同步，element1积分点S11 | +1 MPa | 未取得 | 不可计算 | abs=1e-4 MPa，rel=1e-4，有效阈值1e-4 MPa | NOT_RUN |
| 同步，node1 RF1 | −1 N | 未取得 | 不可计算 | abs=1e-4 N，rel=1e-4，有效阈值1e-4 N | NOT_RUN |

约束位移、节点2反力与全局X平衡也均未取得；参考值和容差未修改。不将缺失输出解释为0或求解失败。

## 停止与范围

本次只新增`docs/agent_first/run_010/real_001`证据，不覆盖原报告或清单，不修改执行核心/授权/Backend、版本或生产数据。没有访问Stable、调用旧Runner、创建正式Project Run、迁移数据库、修改安装/许可/全局环境、Git切换/恢复/提交/推送。没有再尝试此前被拒绝的文件清理。停止在启动前阻断报告，不自动开始下一实验或阶段。
