# Run020 — 基线与本轮差异

只读核验：`D:\Projects\abqjobpilot_dev`，Develop，完整HEAD `271c6f82fd6a4599dbae2df30d903dab2cef1f63`，无未解决冲突；应用版本0.3.0.dev0。读取实际AGENTS、环境登记、Run017–019总结/契约及相关源码。适用上级没有额外AGENTS；没有切分支、恢复、暂存、提交或推送。

开始时已有25条跟踪修改及Run014–019等未跟踪工作。`BASELINE.json`保存原Git状态和1235份既有非忽略文件摘要。不是把历史实现重新计作本轮新增。旧实时Run016 view.json在开始时明确排除哈希稳定性判断，没有操作其owner或窗口。

新增应用：`abqjobpilot/product_project.py`、`local_credentials.py`；新增只读示例：`examples/agent_first/product_inspect.py`。本轮不修改ExecutionService、授权、所有权、数据库Schema、Backend、受管进程、对账或自动收尾核心。

对开始时已有文件的增量：

| 文件 | 本轮范围 |
|---|---|
| service_discovery.py | 产品manifest识别/实例绑定及密文交接读取；原协议/认证/进程检查不变 |
| service_lifecycle.py | 初始保护目录/加密配置，原profile/operator读取接入；生命周期算法不变 |
| service_owner.py | 发布已加密connection；不落明文临时文件 |
| execution_gui.py | New产品Project按钮、异步共享API、创建前后身份与失败展示 |
| README.md / README_CN.md | 标明Run020产品能力及测试执行边界 |
| tests/test_execution_gui.py | 可选Run020正常GUI驱动，原路径默认不变 |
| tests/run018_gui.py / run019_gui.py / test_attachment_gui.py | 实测暴露的旧遥测竞争：测试确认绑定GUI选择代数，原业务断言保留 |

新增测试为test_product_project.py、test_product_windows.py、run020_gui.py、run020_client.py。普通独立client无测试模块、SQL或授权工厂；测试harness另行承担可信设置。

所有本轮创建的实例均在显式Run020临时根。未访问Stable/生产Project，未更改共享环境或Abaqus安装。测试只运行固定Python进程，Abaqus调用0。保留所有历史冻结包、真实输出、尝试记录和报告。

主回归选集、必要失败迭代与清理见ACCEPTANCE_AND_TESTS.md；最终现状及原文件差异见FINAL_INTEGRITY.json。不以与某一历史选集的测试数量大小比较推断回归。
