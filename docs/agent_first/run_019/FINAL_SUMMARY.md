# Run019 — 产品服务生命周期

**PASS_ABQJOBPILOT_AGENT_FIRST_RUN019_PRODUCT_SERVICE_LIFECYCLE_READY**

本轮完成正常 Dev GUI 和公共 Python 共用的显式 Supervisor 生命周期，范围为**预配置、有效格式3、无未决任务的隔离 TEST_ONLY Project**。真实 Abaqus 调用为 **0**；真实服务生命周期没有被此次固定Python验收代替。

## 实际改动

- `abqjobpilot/service_lifecycle.py`：inspect/start/connect/disconnect/stop，固定注册Python入口，原owner锁内预约、保守启动失败、同一实例管理能力和正常停服后的显式重启。
- `abqjobpilot/service_owner.py`、`service_host.py`：原Supervisor的固定产品宿主、独立磁盘输出、只读Windows身份/Job观察。未创建新调度器、服务安装或系统托管渠道。
- `abqjobpilot/execution/lifecycle.py`：同一owner/session/SQLite保护下的空闲检查、PAUSED与幂等停服回执事务。
- 原 `store.py/supervisor.py/client.py` 仅增加可选生命周期接缝、停服后写入门禁与明确RPC；旧启动器默认未启用新权限。格式与版本不变。
- 现有 `execution_gui.py` 加 Start Service / Disconnect / Stop Service，异步操作、独立权限、失联标记与同Run重连；原Run018发现/认证、分页与日志继续复用。
- `examples/agent_first/lifecycle_demo.py` 提供明确的新实例可信测试设置及公共调用，README两种语言更新；新增针对性测试与正常GUI测试驱动。原测试断言保留，依赖图仅明确允许新增生命周期模块所需的精确导入。

完整调用链、权限和停止事务见 LIFECYCLE_CONTRACT.md；操作见 USAGE.md。正常入口仍是根目录 **Open_Dev_GUI.vbs**，没有新测试GUI替代产品界面。

## Windows 实证

实际 Windows 11 NT10.0.26300；登记 LangChainEnv Python 3.12.10、Tk8.6。正常run_gui.main经过真实按钮启动owner，固定受管ProcessFixture worker执行；正常WM_CLOSE后，GUI与专属venv启动器两个保留句柄证实exit=0，原owner/worker仍存活且日志增长。重开同Project/Run/原回执，没有第二次物理启动。

worker完成后独立显示范围收尾 COMMITTED_EMPTY_SCOPE、Artifact VALID、Solver NOT_RUN；活动时Stop拒绝，空闲时GUI Stop形成持久回执并正常退出，再次显式Start的新owner保持PAUSED。windows_final/gui_attachment_product.json 为最后一次全链证据，windows_final/normal_gui_final.png 为实际窗口；先前完整证据也保留。

直接Job观察为0x3000，完整层级及Job所有者仍UNKNOWN；没有改变Job、使用breakaway，或依据单个kill_on_close=false放行。该结论限于已测试普通创建链和持续存活的Windows会话，**不覆盖外层宿主/终端关闭、注销、关机或系统重启**。

## 验证、历史保护与剩余状态

最终 **291个唯一用例PASS，0最终FAIL/SKIP**；主回归275、legacy15，另一个后补跨OS进程竞争用例，重复组去重。公开例子从非仓库cwd实际运行通过。失败迭代、选集、未执行范围逐项记录于 ACCEPTANCE_AND_TESTS.md 与 TEST_RESULTS_FINAL.json。

CLEANUP_FINAL.json：454个本轮记录身份后查无匹配存活，剩余私有连接/操作者凭据0；保留测试业务证据。FINAL_INTEGRITY_FINAL.json：Develop@271c6f82fd6a4599dbae2df30d903dab2cef1f63，冲突0，原文件仅本轮明确修改的8个路径发生变化，无意外历史材料改写。版本仍0.3.0.dev0。

没有访问Stable/生产Project，没有调用Abaqus或修改其安装/共享Python；没有停止、重启、升级、接管历史owner，也没有改变Run013/014/016的授权、PAUSED、UNKNOWN、隔离或输出。未提交、推送、切分支或进入下一轮。

## 0.3.0 Agent-first Execution MVP 剩余门槛

| 门槛 | 当前限制 / 所需最小工作 |
|---|---|
| 产品Project与配置交接 | 本轮只支持新隔离格式3、可信开发设置；正常用户Project创建/识别、生命周期配置及凭据交接需产品入口和兼容验收，不能拿旧Project直接写入 |
| 真实服务生命周期范围 | 原Standard执行/授权仍在既有链路；本轮生命周期管理器主动拒绝真实计划/历史实例，尚未声明通用真实服务启动/空闲停服支持 |
| 执行批准 | 连接、生命周期能力与执行Grant已分离，但真实人类批准产品体验、撤销/过期提示和审计交接尚非通用审批系统 |
| 宿主与部署 | 登记解释器和当前Windows开发安装已测；跨安装位置、用户权限、杀进程型外层宿主、注销/重启未覆盖；不发布系统服务或自动恢复承诺 |
| 不确定性与资源 | 未确认启动/异常owner不自动替换；历史隔离、受管范围外服务、真实未知Run处置仍需既有显式政策，不能一键强制关闭 |
| GUI与公开接口 | GUI为只读监控加受限生命周期，CLI/MCP未扩写；通用工程准备/授权/验证和格式兼容需要明确发布能力表，ODB验证仍NOT_RUN |
| 发布工程 | 累积未提交资产和报告仍需授权下的Git检查点、私有数据/大文件审查、打包及回滚/升级策略；本轮不发布或晋升Stable |

## 最小最终验收建议

先收口**明确支持的产品Project配置及凭据交接**，让普通启动不依赖测试设置脚本；保持无自动恢复/批准/重试。然后在全新受支持Project上做一次统一验收：正常GUI发现/明确启动，Agent同服务提交精确批准任务，GUI完整退出/重开，原Run不重复，空闲Stop/显式重启PAUSED、凭据与历史不变，错误Project和旧owner明确拒绝。

真实Standard若纳入这个最终生命周期范围，须先评审最小启用补丁及只读资源保留判据，再另行授权**新实例、固定一项analysis、额外调用0**的宿主验收；不能复用或接管历史真实owner补测。现阶段不运行该建议，也不新增Solver功能。

本轮完成后停止。
