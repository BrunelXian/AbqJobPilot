# Run022 — 0.3.0 Release Candidate Preflight

**PASS_ABQJOBPILOT_AGENT_FIRST_RUN022_RC_PREFLIGHT_READY**

当前可以冻结一个**范围受限的 Agent-first Execution MVP**，并准备经过筛选的Develop Git检查点。本轮审查与安全回归没有确认P0执行安全缺陷。**这不表示正式RC已打包、0.3.0已发布，或允许自动提交／推送／Stable晋升。** 通用新主机部署、首次启动诊断与提交包筛选仍需完成。

## 五个结论

1. **MVP范围可以冻结。** 显式新Project、独立Supervisor、公共Python客户端、认证、精确真实Grant、限定单Run派发、受管执行/正常收尾、分离证据、GUI监控和安全空闲停服/重启已有源码与证据。真实能力限当前登记Windows主机、Abaqus2024固定Standard轴向杆、CPU1/GPU0/2048MB；不扩大成通用工程平台的全模式验收。
2. **本轮未确认真正P0。** 原授权/幂等/所有权/管理范围/停服边界未修改，安全选集最终664项通过。该结论受审查和选集范围限制，不代表同一OS用户恶意任意代码被隔离。发现有效凭据或Project DB混入最终发布包时必须阻断；本轮未发现这种泄漏，仍须筛选提交集。
3. **Run021B的NOT_OBSERVED保持。** 它不等于Solver生命周期失败，也不能改成已观察。Run013/016分别有真实Solver跨GUI退出的证据；Run021B证明新产品Project的批准、一次分析、正常收尾/数值、安全停服与重启，但其原整体PARTIAL不改。本RC只能使用跨Run分别标注的窄声明。需要更强产品路径声明时另批准一次最小实测，本轮不补跑、不创建Grant。
4. **可以建立审阅后的Develop检查点，不能全量盲目提交。** 应选择完整源码/测试/精选契约，排除本地私有数据、旧测试临时产物和不适合公开的原始日志。已tracked的大日志不能靠新ignore自动移除；历史证据原样保留。具体拆分和提交说明见GIT_CHECKPOINT_PLAN。
5. **距离正式RC的最小操作**：确认发布支持范围；处理或明确排除通用部署P1；批准精确Git集合和脱敏策略；在获得授权后建立检查点并在独立源代码副本复现安全回归；另行批准版本号/RC Tag/打包/发行说明。Stable晋升仍是单独事项。

## 实际审查与改动

- 基线：`Develop@271c6f82fd6a4599dbae2df30d903dab2cef1f63`，版本0.3.0.dev0，无冲突；开始25个tracked修改、739个原有untracked，完整清单/摘要在 BASELINE.json。
- 本轮只新增 `docs/agent_first/run_022`审计、测试驱动及报告，修正README.md/README_CN.md中“生命周期仅支持TEST_ONLY”、默认GUI却按Classic操作、通用venv承诺、两种Project格式混淆等误导说明。
- 没有修改ExecutionService、Supervisor、Backend、授权、派发、进程管理、Project格式或GUI实现。既有1415个候选文件中，除两份README外，前轮文件摘要全部保持；历史报告、冻结包及原测试断言未覆盖。
- 只阅读Dev内历史证据，没有访问外部历史实验根/DB、查询或控制保留owner/GUI。未访问Stable，没有Git切换/恢复/清理/暂存/提交/推送，没有版本更改、共享环境修改或生产迁移。

## 实测结果

使用登记LangChainEnv绝对解释器，Python3.12.10 / Tk8.6 / pytest9.1.0 / Windows11 build26300。

| 最终批次 | 唯一用例 | 结果 |
|---|---:|---|
| 核心/受管进程/对账/Standard离线替身 | 458 | PASS |
| Project/凭据/GUI/生命周期/产品单次控制 | 127 | PASS |
| 干净进程隔离断言 | 9 | PASS |
| Legacy GUI/Project/API/格式拒绝 | 59 | PASS |
| MCP只读/可选依赖/导入 | 11 | PASS |
| **去重合计** | **664** | **0最终FAIL/ERROR/SKIP** |

原始失败未隐藏：本轮审计驱动先后误拦截pytest日志NUL和subprocess的NUL标准输入，产生一次收集前失败及首轮81FAIL/57ERROR；其中teardown附加记录不能算新case。修正的是本轮审计设备例外及日志/证据路径，不是应用逻辑或旧断言。核心重新完整458PASS。清理审计初稿遇到负向测试重解析点时安全停止，随后改为不跟随路径。一次只读证据汇总未指定UTF-8导致解码错误，指定UTF-8后读取；不影响测试或进程状态。

本轮真实Windows固定Python证据包括：正常新Project、明确启动、GUI/venv完整退出后owner/worker仍活且日志增长、重连原Run、单次派发应答丢失重放、受管范围结束、正常空闲停服与重启PAUSED。**Standard路径由固定Python替身替代，真实Abaqus调用始终0。** DAT来自标明来源的历史只读样本，不作为本轮真实求解结论。

7个本轮临时根中808个登记身份后查匹配存活0（790原对象不可取得、18身份不匹配）；不追认历史退出码。保留句柄退出/关闭由原测试记录证明，精选产品Standard替身包括原root/scope句柄关闭。新增清理审计不终止进程；287份本轮私有文件已移除，剩余顶层明文/DPAPI凭据候选0，报告已知秘密命中0。旧测试目录、真实结果和凭据均未触碰。

## 仍需发布负责人处理

- **P1部署**：VBS与产品核心绑定LangChainEnv固定绝对路径，Standard仍是固定安装/模型；缺Tk或损坏环境的完整启动诊断未验收。可先限定登记主机开发预览，不能宣传任意Windows一键安装。
- **P1证据声明**：Run021B跨GUI存活NOT_OBSERVED；不同Run不合成单次通过。域外进程全集UNKNOWN、ODB NOT_RUN、主机/跨Project资源协调未实现。
- **P1交付包**：精确提交选择、敏感路径审阅、原始大日志归档、独立快照复现及RC打包仍未执行。
- **P2体验**：Classic双向导航、用户术语、多语言与视觉层级尚未统一；可以进入后续设计审阅，但本轮不开始Run023或重写GUI。

## 交付索引

- [MVP与跨Run证据](RC_SCOPE_AND_EVIDENCE.md)
- [P0/P1/P2及最小处置](RELEASE_BLOCKERS.md)
- [安全回归、部署、失败迭代与清理](TEST_AND_DEPLOYMENT_REVIEW.md)
- [Git检查点计划](GIT_CHECKPOINT_PLAN.md)
- [RC检查表](RELEASE_CANDIDATE_CHECKLIST.md)
- [逐case结果](TEST_RESULTS.json)、[精选Windows证据索引](WINDOWS_EVIDENCE_INDEX.json)
- [基线](BASELINE.json)、[最终库存](FINAL_INVENTORY.json)、[候选敏感内容复核](CANDIDATE_CONTENT_REVIEW.json)、[清理原始记录](CLEANUP.json)

本轮完成后停止。没有启动新的真实实验，没有停止保留服务，没有自动进入Run023，没有发布或更新Stable。
