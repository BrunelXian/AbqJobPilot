# Run 011 — 固定实验控制器候选交付

**PASS_ABQJOBPILOT_AGENT_FIRST_RUN011_CONTROLLER_CANDIDATE_READY**

候选代码与非 Solver 验证已完成。**真实 Abaqus 调用 0 次；真实 execute 操作调用 0 次。** 该状态不表示操作者宿主、真实包装器、完整 Abaqus 进程链、实际数值或产品 Backend 已验收。

## 实现结果

为固定实验 `abq2024_r010_a19d17ea` 实现了独立普通 Python 控制器。默认 check，另有明确 execute 和只读 report；没有任意命令、路径、模型、观察期限或跳过 Job 检查的公开参数。

真实入口在自身进程重新核对新旧材料、固定参数/目录、公开预览、输出痕迹和生命周期条件。必须 IsProcessInJob 成功且不属于任何 Job，之后才可独占创建并 fsync 固定 `observations/attempt.json`。意图与实际输出身份绑定，不随候选版本或调用 cwd 变化；空、半写、损坏、既有意图均阻断。无自动删除、重试或重置。

调用数据直接来自原冻结清单，保留绝对 cmd.exe/BAT、参数、cwd、完整替换环境及 stdout/stderr 普通文件。没有修复 VS2022 风险。实现保留OS引用的身份/退出记录、有限候选后代发现、300秒观察结束路径和有界打印数值检查。创建事实、退出事实、Solver文本、数值和ODB各自表达；成员完整性和整体退出保持UNKNOWN，不把观察到的子集当作全部成员。

没有修改正式 ExecutionService、原 Runner、GUI、SDK/MCP、Project DB、Backend 或授权核心；版本仍为0.3.0.dev0。所有新增实现、测试与交付均位于 `docs/agent_first/run_011`。

## 实际验证

| 范围 | 结果 |
|---|---|
| 最终控制器针对性测试 | **56 passed，0 failed，0 skipped，5.40s**；TEST_RESULTS_04.xml |
| 复用的离线检查依赖 | **21 passed，0 failed，0 skipped，0.61s**；DEPENDENCY_RESULTS.xml |
| Windows 真实普通Python夹具 | 三轮通过的进程组共12个worker、3个launcher，全部按PID/创建时间/映像关联到保留OS引用的退出码0；控制器有正常退出及阶段自退出91/92证据 |
| 并发/重放 | 四个独立控制器经屏障同时争同根，仅一个实际创建worker；不同候选标识、重复调用仍拒绝第二次物理启动 |
| 观察超时/launcher提前退出 | 0.6秒测试预算后控制器返回；worker仍由真实引用确认存活、继续写文件，随后自行退出；未误报完整退出 |
| 非仓库cwd公开命令 | 实际 check 返回材料MATCH、当前工具宿主BLOCKED（exit2）；report 返回NO_ATTEMPT_RECORDED（exit0）。PUBLIC_CHECK.json / PUBLIC_REPORT.json |
| 材料保留 | 新候选21项及原清单34项引用全部匹配；106项原文件大小/摘要不变；原experiment observations/extracted空、无Job输出 |

最终相关集合共77项，不把前轮测试数作为本轮结果。第一次35通过11失败：10项测试哨兵对Windows audit命令字符串的处理错误，1项测试预算过短；修正支架后46通过，扩展边界后53通过，最终56通过。保留全部迭代输出，没有删改旧断言或跳过关键场景。逐项 R11-01～08 见 [ACCEPTANCE_MATRIX.md](D:/Projects/abqjobpilot_dev/docs/agent_first/run_011/ACCEPTANCE_MATRIX.md)。

Windows集成通过**测试专用DI**模拟无Job准入，实际工具Job结果同时保存；真实CLI没有绕过入口。模拟注入、真实普通Python生命周期和操作者未验证宿主严格分开。测试控制器额外登记只用于核对物理启动和安全收尾，不补写被测控制器遗漏的创建/退出记录。

所有夹具自行退出；父harness核对引用/句柄/日志文件关闭。没有调用kill/terminate、按名称处理进程或生成私有连接凭据。新临时测试根保留以供审查，路径见 TEST_ROOT_*.txt；旧三个被拒绝清理目录和五个脚本未动。Windows自动产生的conhost按候选证据报告，不宣称任意完整进程树已被证明。

## 新的具体批准对象

- 候选清单：[CANDIDATE_MANIFEST.json](D:/Projects/abqjobpilot_dev/docs/agent_first/run_011/CANDIDATE_MANIFEST.json)。
- **候选 body SHA-256：`645389d8f25942e908f04dca25fbefed820d6f63b35fcfb6c308977b6c016824`**。
- 引用的原 body SHA-256：`04ed053817a7d05c2355d9a93a41216309bb5d28a235f569a250eea6ee4af2b6`。
- 实际新入口：[controller/probe.py](D:/Projects/abqjobpilot_dev/docs/agent_first/run_011/controller/probe.py)。
- 唯一未来动作仍是 `D:\ABAQUS2024\Commands\abq2024.bat` 的一次Standard analysis，原实验根/输入/Job/cwd/scratch，CPU1/GPU0/2048MB，额外Abaqus调用0，观察300秒、不自动终止/重试/删除。

新候选需要另行明确批准后，才由操作者在独立终端执行。旧一次调用授权和旧SHA不覆盖新增控制器。摘要只证明对象身份，候选不产生“已获准真实执行”记录或产品Grant。准确已存在的三个命令及返回语义见 [USAGE.md](D:/Projects/abqjobpilot_dev/docs/agent_first/run_011/USAGE.md)。check/report已运行，execute只做静态审查和参数捕获替身验证。

## 保证范围与仍待验证

1. 一次尝试保护只覆盖遵守此协议的固定实验/实际输出身份；不是主机级或跨Project锁，不防同一OS用户篡改，不承诺OS进程与文件记录的exactly-once。
2. 300秒是观察预算，不是Solver运行上限。创建调用和磁盘IO可能影响实际返回时间；到期不继续等待成员结束，不终止后代，不隐藏后台观察者。操作者必须保持终端/会话，不用关闭窗口或Ctrl+C停止等待。
3. 操作者独立终端的实际同进程无Job条件尚未验证；先前check结果不能代替execute自己的最新检查。当前受管工具环境仍阻断，不修改Job或尝试脱离。
4. 正常Python夹具不替代真实BAT/Intel环境/许可证/Standard成员集合及实际退出验收。真实Runtime未调用，完整成员未知使整体报告保持PARTIAL；没有活进程重挂接、自动接管或强制收尾。
5. 打印解析只支持明示的窄文本表格式，人工样例有源标识；尚未取得真实2024 DAT版式。缺失/不支持/重复/不完整/旧输出均拒绝通过，参考0.01mm、1MPa、−1N及容差不变。ODB内容一律NOT_RUN。原方案与实现的日志合并/数值记录位置差异已列在DESIGN_AND_DIFF.md。

本轮未访问Stable或生产数据，未调用真实Abaqus/旧Runner/队列，未修改安装、共享环境、依赖、版本或数据库；未执行Git切换、恢复、提交、推送。原Run010准备PARTIAL、real_001阻断报告及operator_handoff均保持。

完成候选交付后停止。不自动执行新候选、不开始下一轮。
