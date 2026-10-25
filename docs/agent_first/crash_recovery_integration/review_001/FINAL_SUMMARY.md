# CR-D01 — Dev Crash Recovery 集成设计就绪

**PASS_ABQJOBPILOT_CR_D01_INTEGRATION_DESIGN_READY**

本轮完成技术交接包八份文档的完整阅读、Dev实际源码/测试与阶段报告对照、恢复语义及分阶段实施设计。**没有移植或实施恢复功能，没有修改执行核心或GUI，没有访问Stable。真实Abaqus调用0。**

## 主要结论

1. Dev已有可复用的安全基础：原owner排他锁、独立Supervisor、持久START_INTENT、幂等接受/管理回执、精确权限、只读诊断、四角色记录退出对账、Standard行政释放、受管范围正常收尾、PAUSED与路径隔离、产品生命周期和单次真实派发。不能复制Stable Runner或重新实现这些能力。
2. 实质缺口是：boot/session与监督中断的可信分类；产品凭据到排他无dispatcher管理会话的桥接；managed proof已记录但终态未提交的专用对账；退出缺失的历史Run适用什么受限行政政策。当前全部是保守阻断，不能以PID消失/重启估计值补造exit。
3. 推荐 UNKNOWN_INTERRUPTED 作为有版本、reason和证据引用的**诊断/显示投影**，不新增全局Run持久状态。CR-D02不需Schema迁移；CR-D03先复用现有管理表/事务，如出现确切约束不足再单独评审版本化扩展。
4. 已核实Classic具体差异：gui_presentation.status_presentation把UNKNOWN_INTERRUPTED显示为Failed，而规范化返回UNKNOWN。列为单独P1展示修复，不将其说成Agent-first状态机损坏，也不在本轮修改。
5. 本次未确认P0执行安全缺陷。Run022受限RC判断仍可保留，但若发布声明包含系统异常重启后的通用Crash Recovery，则必须先完成对应能力。历史Run021B NOT_OBSERVED、域外UNKNOWN和ODB NOT_RUN不变。
6. **CR-D02已具备实施条件**：最小只读快照/规则/probe适配及故障事实测试；不获取管理写锁、不新增Apply、不恢复PAUSED、不创建新Run。下一轮仍须用户授权实施。CR-D03/04/05分开审查，不自动接续。

## 本轮核查与保护

实际Develop@271c6f82fd6a4599dbae2df30d903dab2cef1f63，0.3.0.dev0，无冲突。开始25项tracked修改、827个untracked，1503个既有非忽略候选文件已记录摘要。写入前全部一致；最终保留及文档校验见 READ_ONLY_CHECKS.json。只在本专项目录新增材料，未覆盖Run022/023和历史真实报告。

本轮应用回归运行0；历史测试源码/报告用于能力证据，不将Run022的664项或其他阶段数量算作本轮通过。已执行文件摘要、来源定位和文档一致性校验；没有查询、停止、重启或接管任何历史owner；没有OS进程探测、数据库初始化/迁移、执行/管理Grant登记、Git写操作或共享环境修改。未创建需清理的应用测试进程及凭据。

## 交付

- [整体审查与RC影响](CRASH_RECOVERY_INTEGRATION_REVIEW.md)
- [逐项能力/缺口及源码测试依据](DEV_CAPABILITY_GAP_MATRIX.md)
- [术语、识别模型、Inspect/Preview/Apply/Verify契约](RECOVERY_STATE_AND_API_CONTRACT.md)
- [CR-D02～05最小补丁、开始/停止与回退条件](IMPLEMENTATION_AND_ROLLBACK_PLAN.md)
- [26项故障验收设计及本轮只读检查](TEST_AND_ACCEPTANCE_MATRIX.md)
- [基线与交接来源摘要](BASELINE.json)、[最终只读核查](READ_ONLY_CHECKS.json)

下一步建议仅授权CR-D02。真正恢复处置需要后续policy和操作者权限审查；Retry、新Attempt、Abaqus Restart不包含在本轮或D02内。完成后停止，等待实施授权。

