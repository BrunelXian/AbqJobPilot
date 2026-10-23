# Agent-first Run 002 — 最终交付

日期：2026-10-21。状态：**PASS_ABQJOBPILOT_AGENT_FIRST_RUN002_FAKE_SLICE**。

约定的单进程 Fake 内部服务切片完成；R2-01～16 均关联实际测试并通过。最终 **95 passed，0 failed，0 errors，0 skipped**。此状态不表示完整 Agent-first 服务、真实 Abaqus 验收或正式0.3.0发布完成。

## 实际基线与前置内容

工作区 `D:\Projects\abqjobpilot_dev`，分支 `Develop`，实际 HEAD 为 `fb7912ec9e0107b18f65948b147c87579c87cded`，版本仍为 `0.3.0.dev0`。它相对已知 `af3fd796...` 只提交了 Run 001R 的8份文档，功能源码/测试没有变化；起始工作区干净、无冲突。因此按本次用户澄清继续，并保留全部前置内容。详见 [BASELINE.md](BASELINE.md)。本轮未创建提交。

## 实际改动

- 新增 [abqjobpilot/execution](../../../abqjobpilot/execution/__init__.py) 的9个模块：context/值对象、计划、测试授权验证、事务存储、服务、唯一 Fake Backend、独立验证及路径约束。
- 新增 [契约测试](../../../tests/test_execution_contract.py)、[存储/故障测试](../../../tests/test_execution_store.py)、[隔离测试](../../../tests/test_execution_isolation.py) 和 [测试支持夹具](../../../tests/execution_helpers.py)。
- 新增本 Run 的 [实现说明](IMPLEMENTATION.md)、[逐项验收矩阵](ACCEPTANCE_MATRIX.md)、基线/总结，以及 [JUnit](TEST_RESULTS.xml)、[原始输出](TEST_OUTPUT.txt)、[源码哈希](SOURCE_HASHES.json)。

没有修改旧功能源码、已有测试、AGENTS/README/Run 001R 交付、应用版本或旧 API/JSON/Project/history schema。新增代码没有接入旧产品界面。

## 关键行为与实测结论

1. 接受事务原子保存 receipt、Run、幂等摘要、grant 消费与事件；Fake 副作用前已经可以读到 Run 和 START_INTENT。
2. 同键同内容返回原 receipt/Run；同键不同内容返回结构化冲突；真正 Retry 新建 Run 并关联 retry_of。
3. 多个服务和 Store 对象共用创建 owner session，执行领取用数据库 slot 和 Run 条件 UPDATE 原子提交。**单槽是每个实验存储一个槽**，不是主机全局；另一个 Run 遇 SLOT_BUSY 保留接受事实，正常释放后可显式调度。
4. 文件副作用发生后若终态提交失败，保留不确定状态/已提交启动意图与槽占用，禁止自动重复执行；数据库回滚不撤销文件。
5. Fake COMPLETED、Artifact VALID/INVALID/UNKNOWN 分开；Solver 永远 NOT_RUN。验证结果带 Run/phase/Plan 与摘要证据。
6. 新实验库不接管旧 queue/project.db；严格只读重开可查历史，缺库/未知格式/sidecar 不触发初始化、迁移或修复。
7. 真实启动在本切片依赖/接口中不可达；静态白名单和运行时 trap 通过。测试只在新临时根使用 TXT/JSON 和实验数据库，实际临时 junction 的拒绝测试也通过。

每项验收的测试名称、参数情况、观察结果和未运行边界都列于 [ACCEPTANCE_MATRIX.md](ACCEPTANCE_MATRIX.md)，不是只用总 passed 数代替验收。

## 检查与限制

使用现有绝对解释器 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`：Python3.12.10、SQLite3.49.1、pytest9.1.0；无安装或依赖修改。先后运行新增测试85项、95项、最终95项，全部通过；最终代码以源码哈希绑定。已有全量测试没有运行，因为旧模块未改且部分旧测试有默认路径副作用。

尚未实现/验证：独立 Supervisor、IPC、GUI/MCP/外部 SDK 接入、跨进程崩溃恢复、跨 Project 输出身份协调、主机全局资源槽、真实批准 UI/隔离域、真实 Abaqus Backend、生产迁移和发布。实验 writer 只允许创建进程的活跃 session；关闭后只读重开，不提供自动恢复写入或清除未知槽。复制/移动实验目录没有导入或重定位接口，不能继承许可。同用户任意 shell 权限不在应用 grant 的强安全保证内。

## 建议下一最小切片（未开始）

在独立 Run 中，仍仅 Fake、新建临时 Project/一个槽：用一个独立 Supervisor 进程承载已验证内部契约，增加最小本地 IPC 的提交/查询及客户端断线重连测试。重点证明客户端退出不终止持久 Run、重发仍幂等、owner 失联时不重复派发。暂不加入真实 Backend、GUI/MCP、跨 Project 输出协调或自动崩溃恢复；对应完整模拟矩阵分步推进。本轮不创建该进程、不实现该切片，也不自动进入下一 Run。

## 操作边界与结束检查

Stable 完全排除且未访问；未启动真实 Solver/Datacheck/Runner，未打开真实 Project、默认 Recent 或生产数据库；未修改共享环境、用户其他进程或 GitHub 设置；未 checkout/reset/restore/clean/stash/merge/rebase/commit/push，未清理恢复备份或保护引用。新增实现与报告保持本地未提交状态。

- 最终分支/HEAD 保持 `Develop@fb7912ec9e0107b18f65948b147c87579c87cded`，无未解决冲突；全部已跟踪文件相对 HEAD 无 diff，前置8份交付和旧源码/测试保持不变。
- 本轮共新增20个文件：9个实现模块、4个测试/支持文件、7个报告/证据文件；全部未提交。
- 13个源码/测试 SHA-256 与最终测试快照一致；36个本地文档链接目标均存在；16行验收中的46处测试引用全部在最终 JUnit 中找到且通过。
- `git diff --check` 通过，新增源码/测试无行尾空白，文档代码围栏配对。JUnit 为95 tests、0 failures、0 errors、0 skipped。
- 未继续扩大测试范围或开始后续实现；本轮到此结束。
