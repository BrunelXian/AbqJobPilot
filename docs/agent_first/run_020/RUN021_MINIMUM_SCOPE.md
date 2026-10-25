# Run021 最小建议：一个真实 Standard 产品生命周期

这只是下一轮建议，本轮未实施或授权真实执行。

先做零Abaqus预算的受限准备：

1. 在全新产品Project中，通过可信操作者准备一个固定轴向杆Standard计划、独立工程/输出/scratch/Job和受管策略；默认New仍为空PAUSED，不自动启用真实Backend或批准。
2. 审查Run019/020产品profile对真实计划和`standard_config`的明确拒绝。若要启用，仅增加这一固定配置的可信接入和匹配能力；不能通过改TEST_ONLY字段升级真实许可，也不能移除整个真实计划拒绝。
3. 明确真实Run完成后的安全空闲停服判据及持久工程/输出保留。当前产品`require_idle`仍拒绝真实计划，不能把固定Python的Stop通过推定为真实服务Stop已支持。必要补丁先用替身验证，无管理回退禁止。
4. 准备一份现有机制下的待审清单，固定新Project/计划/输入/入口/受管配置/资源/一次预算/时间窗口。不得复用历史Run016实例、Grant或输出，不接管旧owner。

然后另行申请**新的明确真实Abaqus授权**，范围建议只有一个固定Standard analysis：CPU1/GPU0/2048MB，每Run最多一次，额外调用0；300秒只停止观察，不终止、不重试、不删除。精确Grant创建/提交、必要的显式派发许可、以及完成后若满足新审查条件的正常停服，都应明确列入清单及授权。

实测步骤：正常Dev GUI New/选择新Project → 明确Start → 独立公共客户端提交准确授权计划 → GUI查看同Run → 身份匹配Solver运行时完整退出GUI及启动器 → owner/Solver存活与日志证据 → 重开原Run → 受管范围正常收尾、Solver和三项DAT分别判定 → 条件满足后明确Stop/Start保持PAUSED。窗口过快而错过时标NOT_OBSERVED，不增加调用。

三项数值仍为节点2 U1=0.01mm±1e-6、单元1/积分点1 S11=1MPa±1e-4、节点1 RF1=-1N±1e-4。ODB内容NOT_RUN；不追加Python/Viewer/license/datacheck调用。

仍不覆盖通用人类审批、任意模型、跨Project资源协调、域外服务全集、注销/关机/重启恢复、生产迁移及正式0.3.0发布。未经新的真实授权停在待审准备，不将本轮固定PythonPASS当Solver授权。
