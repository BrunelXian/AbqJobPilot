# Run021B 基线、增量与Git建议

实际Develop，完整HEAD `271c6f82fd6a4599dbae2df30d903dab2cef1f63`；无未解决冲突。读取实际AGENTS、环境登记、Run021总结及接缝审查。根及上级策略维持Dev-only，未访问Stable。登记LangChainEnv未改变，应用版本仍0.3.0.dev0。

BASELINE.json记录本轮前所有非忽略文件摘要和Git状态。历史25项tracked修改、大量untracked Run014–021成果完整保留。仅一名写入者，无并行代理改文件。

## 本轮实际增量

新增：
- `abqjobpilot/product_standard.py`：可信初始准备、只读核验、独立操作者API。
- `abqjobpilot/execution/product_standard.py`：服务端单项许可控制。
- `examples/agent_first/product_standard_acceptance.py`：固定清单步骤的薄调用示例。
- 2个test文件、2个Windows固定替身驱动及1个GUI测试包装；均不属于产品可选择插件。
- 本目录文档、冻结Plan/清单、准备脚本、XML与Windows证据。

增量修改原9文件：execution/client、service、store、standard_contract、supervisor、lifecycle；service_lifecycle、service_owner；tests/test_execution_isolation。后者仅给新模块登记hmac，不降低旧模块依赖约束。其余原有文件摘要需在FINAL_INTEGRITY.json核对；无版本/Schema/GUI布局/旧Runner改动。

当前候选只写一个正式Job/Plan及两个新的加密准备文件。CANDIDATE_CHANGE.json记录前后；原基础credentials、Project/instance、输入、gate、历史记录未改。原Run021不完整清单和报告不覆盖；新body不可被解释为执行批准。

## 候选提交范围建议（本轮不提交）

1. 将此前已验收核心与本轮接缝按有意义的功能提交审阅；核心变更必须连同授权/并发/Windows替身回归。
2. 文档、历史研究报告与本轮验收证据建议独立提交，保留PARTIAL及失败迭代。
3. 新候选真实数据根和全部测试根都在Temp；不得纳入数据库、DPAPI文件、连接材料、业务日志、Solver输出或原始Runtime。当前清单只保存固定元数据、源码/静态安装文件摘要和输入内容身份。
4. 继承Run021 Git审计的警示：历史约4.98MB PUBLIC_OBSERVATIONS.jsonl、二进制样例/图片、个人安装路径需提交前逐项审阅。不要把新增root全目录打包提交；不自动删除已有研究材料。
5. 真实执行能力实现、历史实机结果、替身结果、待批准候选分别标识。当前通过不表示本产品宿主已真实执行Standard。

没有Git stage/commit/push/reset/restore/clean/stash/分支切换。正式发布、Stable晋升和真实实验均需独立授权。
