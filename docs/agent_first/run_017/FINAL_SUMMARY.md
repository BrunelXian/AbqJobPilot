# Run017 — Dev工程化基线收口

**PASS_ABQJOBPILOT_AGENT_FIRST_RUN017_DEV_PRODUCT_BASELINE_READY**

基于实际`Develop@271c6f82fd6a4599dbae2df30d903dab2cef1f63`、版本`0.3.0.dev0`完成审计。未确认需要本轮重写核心的P0缺陷；当前适合进入受控Dev检查点审查和下一阶段入口适配，**不具备正式0.3.0发布/Stable晋升结论**。

## 核心判断

1. 新Agent-first三类Backend共用ExecutionService、Supervisor、同一事务Store与owner/幂等机制。没有发现本轮累积实现另建平行的产品执行核心；历史Run010/011控制器是冻结研究资产。
2. 默认GUI/QueueRunner、旧Python API/CLI、五个只读MCP仍是legacy体系。新GUI只读连接模式不双写旧历史库。不能将“Agent-first核心已统一”扩大为“全部公开入口已统一”。
3. 固定Standard的真实A→B与GUI闭环有Run016保存证据：各一次、受管范围正常收尾后B才启动、Solver/DAT通过；全局成员全集/域外UNKNOWN、ODB NOT_RUN继续成立。本轮没有重复真实验收或查询其活动owner。
4. 产品最大可实施缺口是正常入口的明确Project选择、现有服务发现及任务列表。当前新GUI依赖连接材料和单request_key，VBS仍是可信开发支架。Run018宜先attach已有服务，不自动准备/批准/恢复/启动owner。
5. legacy/实验格式互不通用；新写入只支持明确的新format3实例，无生产迁移。legacy若与AF指向同一工程路径，尚无跨框架/跨Project统一租约，必须保持边界。

## 本轮改动与实际验证

- 91个应用/示例模块资产索引；1080个前置非忽略文件清单；21项原跟踪修改和404个未跟踪文件保留。523项冻结/保护摘要全部匹配；应用源码未变。保留中的Run016两个GUI仍刷新各自view.json，作为外部持续更新的派生视图单列，没有停止它们。完整核验见FINAL_INTEGRITY.json。
- 新增本目录6份主要交付、Run018草案、资产索引、可追溯测试/Windows证据、两项新旧格式无写入拒绝测试及仅用于本轮的审计脚本。
- 只修正README.md/README_CN.md中已过时的Dev能力说明。未修改应用源码、既有测试断言、版本、Schema、授权/所有权/进程/收尾状态机。
- 本轮实际执行656个case，去重647；每个唯一case的最后实测结果均PASS，0最终FAIL/ERROR/SKIP。首批589通过/1失败：旧native证据测试收集导入legacy，与AF“本进程未导入legacy”断言冲突；干净进程原隔离组9项全部通过，原失败证据保留。另57项覆盖旧Project/MCP/API及新格式边界。没有机械以测试数比较历史Run。
- Windows替身证据覆盖真实GUI进程关闭/重开、独立owner、托管Job范围、A→B服务端条件、崩溃/事务/丢应答及清理；真实Abaqus调用**0**。测试当时持有句柄的退出记录和事后身份核验分开；没有以PID消失补写历史退出。
- 132份harness inventory、181条生命周期记录及native清理证据保留；本轮登记687个身份当前均未发现匹配存活，私有目录残留0。测试故障仅操作自己的核验句柄；审计收尾没有终止进程/删除文件。当前Run016 owner与只读GUI保留。

## 验收索引

| ID | 结论与证据 |
|---|---|
| R17-01 | PASS：BASELINE.json/GIT_BEFORE/源码资产表；分支、HEAD、版本、完整dirty状态与忽略规则 |
| R17-02 | PASS：ARCHITECTURE_CONSISTENCY，AF唯一权威和legacy并存边界、无AF→旧历史双写 |
| R17-03 | PASS：应用/历史材料摘要保持；真实Backend授权、managed_scope/sequence/closeout相关本轮替身回归 |
| R17-04 | PASS：PRODUCT_CAPABILITY_MATRIX，普通客户端/可信操作者/legacy CLI与MCP分层；未测不冒充已测 |
| R17-05 | PASS：STARTUP_AND_LIFECYCLE_CONTRACT，已有服务attach、错Project/失联/PAUSED/关GUI/停服契约；不是已实现发现 |
| R17-06 | PASS：格式矩阵及两项实际互拒无写入测试；只在新临时实例测试 |
| R17-07 | PASS：TEST_RESULTS、三批JUnit、原失败/干净复核、未执行列表及清理证据 |
| R17-08 | PASS：真实Abaqus调用0；没有历史实例控制/提交/派发/数据库写入；保护核验 |
| R17-09 | PASS：资产/敏感数据候选审查、拆分检查点建议、发布门槛；未commit/push |
| R17-10 | PASS：RUN018_INSTRUCTION_DRAFT，受限只读发现/连接/列表与实际Windows验收计划 |

## 阅读入口

- [基线、资产与Git检查点](BASELINE_AND_CHANGE_INVENTORY.md)
- [调用链、权限、数据格式与恢复边界](ARCHITECTURE_CONSISTENCY.md)
- [GUI/Python/CLI/MCP能力矩阵](PRODUCT_CAPABILITY_MATRIX.md)
- [产品启动与生命周期契约](STARTUP_AND_LIFECYCLE_CONTRACT.md)
- [本轮测试、失败迭代与发布门槛](TEST_AND_RELEASE_GATES.md)
- [Run018可执行指令草案](RUN018_INSTRUCTION_DRAFT.md)

Run018建议只做正常Dev入口连接**已有**明确服务并列出/选择Run，复用公共只读接口。不存在服务或身份不符时诊断，不自行创建第二owner、批准、恢复PAUSED、Retry或迁移。服务启动、人类批准、真实Backend推广、生产迁移和跨Project保护分别审查。没有发现需用P0替代这一优先级的实际证据。

本轮未访问Stable，未改变历史真实实例派发/授权/退出证据/路径隔离，未启动真实Abaqus或打开ODB，未修改共享环境/安装，未清理旧目录，未执行Git写操作。正式0.3.0、Stable晋升、完整Abaqus模式、生产Project迁移、注销/重启恢复仍未验收。工作到此停止，没有开始Run018。
