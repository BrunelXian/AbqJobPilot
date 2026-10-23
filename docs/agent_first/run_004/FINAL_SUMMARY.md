# Agent-first Run 004 — 最终交付

**PASS_ABQJOBPILOT_AGENT_FIRST_RUN004_FAKE_RECONCILIATION_READY**

仅表示限定范围的Fake对账及受控恢复派发通过，不表示真实Abaqus、真实进程监督、完整恢复平台或正式0.3.0已验收。

## 1. 实际基线与前置保留

Dev `Develop@fb7912ec9e0107b18f65948b147c87579c87cded`，版本保持0.3.0.dev0。起始37个Run002/003未跟踪文件保留，21个前置源码/测试与Run003哈希一致；不要求工作区干净。根AGENTS、README、旧GUI/Runner/Project/MCP及历史报告未改。见[基线](BASELINE.md)。

## 2. 实际改动

新增实验模块reconciliation.py，提供纯读取预览、授权采纳既有Fake结果和独立resume_dispatch；原service/store/supervisor/client增加薄入口、事务化管理回执与持久门。新增实验格式3，只给新建临时实例使用，旧1/2格式保留原只读查询、写入明确拒绝，未迁移。

修改8个前置实验模块：authorization、client、fake_backend、models、service、store、supervisor、validation。Fake固定输出公式抽取复用，行为不改；validator可核验一次捕获的同一内容，再写该内容快照。管理授权与原ExecutionGrant和IPC凭据分离，没有mint/approve RPC。原计划、独立validator、锁、执行槽和worker继续复用。

测试新增reconciliation_helpers、test_fake_reconciliation、test_reconciliation_supervisor；前置run003_process增添显式测试控制与故障屏障，授权登记由持锁owner执行；test_execution_isolation仅补精确依赖白名单。其余11个前置源码/测试文件哈希不变。完整25文件清单与差异见[SOURCE_HASHES.json](SOURCE_HASHES.json)和[PROCESS_EVIDENCE.json](PROCESS_EVIDENCE.json)。

新增本目录5份说明文档及4份结果证据：BASELINE、[设计与协议](DESIGN_AND_PROTOCOL.md)、[验收矩阵](ACCEPTANCE_MATRIX.md)、[进程与故障证据](PROCESS_AND_FAILURE_EVIDENCE.md)、本总结，以及JUnit、控制台、源码哈希、结构化进程证据。

## 3. 验收结论

最终 **189 passed，0 failed，0 errors，0 skipped，89.13s**；原R2/R3的125项完整通过，新增61项本地对账/授权/故障测试和3项Windows真实多进程case。R4-01～15逐项PASS，矩阵关联实际测试名与观察；初轮2项测试夹具失败及修正已如实记录。没有机械运行无关GUI/Solver全量测试。

验证了真实owner在产物写出后、终态事务前退出：重启暂停，原Run只读预览、精确授权采纳后保持同Run/回执/attempt/消费历史，Fake不再调用；只有另一次恢复授权才让合法PENDING派发。证据变化、历史缺失、越界、无权限、旧owner或修订拒绝；管理丢应答、同键重放、并发竞争、文件保存与事务失败、过期任务和重启后旧resume重放均有实测。

30个多进程case产生49个实际Python进程；8次故障终止只用已核验且持有的本轮进程句柄。全部进程与启动器已退出、句柄已关闭，私有连接凭据已删除；非秘密测试数据保留作为证据。解释器为登记LangChainEnv绝对路径，未改共享环境。

## 4. 当前限制

仅Windows本机固定盘、每临时实验存储一个owner和执行槽、唯一固定Fake Backend。对账唯一动作是采纳证据充分的既有固定结果；缺失或不符继续不确定并阻断，没有强制关闭/忽略证据/自动Retry。快照不可覆盖是应用约束，不防同OS用户任意篡改。

对账推定完成在本次时间记录，不能伪造过去的进程观察。Solver保持NOT_RUN、验证范围simulation。重启一律暂停；恢复门不延长或复活Plan/Grant。没有完整pause/cancel/terminate控制、真实Backend、主机总槽/跨Project协调、生产批准、GUI/MCP适配或数据迁移。真实进程终止不等于OS/断电恢复验收。

## 5. 下一最小切片建议（未执行）

继续临时Fake范围，单独授权后增加只读管理诊断与审计导出：按Run展示原回执、未解决原因、对账/恢复回执、当前门和不可变快照引用，验证导出内容摘要及缺失快照提示。复用现有查询与管理契约，不新增写入动作，不绕过证据不足门禁；验收包括查询/导出不写实验库、分页一致性、凭据不出现在导出、重启后历史回执与当前门分开显示。暂不接真实Backend或通用权限平台。

## 6. 操作边界与结束

Stable完全排除且未访问。没有读取生产Project/Runtime/Recent/数据库，没有启动Solver/Datacheck/旧Runner/真实队列，没有修改共享环境，没有关闭其他用户进程。未执行切分支、reset/restore/clean/stash写入/merge/rebase/commit/push；未安装后台服务；未自动进入下一Run。

无影响本轮限定验收的未解决缺口。最终本地校验记录见[基线结束检查](BASELINE.md)。成果留在Dev未提交工作区，到此停止。
