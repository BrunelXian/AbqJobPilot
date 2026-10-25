# Run020 — 产品 Project 与安全本机凭据交接

**PASS_ABQJOBPILOT_AGENT_FIRST_RUN020_PRODUCT_PROJECT_AND_CREDENTIAL_HANDOFF_READY**

正常 Dev GUI 已支持：**New Agent-first Project → 显示身份/空PAUSED → 明确Start → 认证连接 → GUI完整退出 → 重开同Project/owner → 安全空闲Stop**。普通独立Python通过同一项目核心、ServiceLifecycleManager及公共IPC连接。固定ProcessFixture任务的真实Windows生命周期也已验证。

本轮真实Abaqus调用 **0**。未发布0.3.0、未迁移生产数据、未访问Stable、未改变任何历史owner/Run/冻结材料、未提交或推送；完成后停止。

## 实现与产品入口

- 正常入口仍为 `D:\Projects\abqjobpilot_dev\Open_Dev_GUI.vbs`。新增New按钮，现有布局、Project/Run列表、日志、Start/Disconnect/Stop继续使用。空Project在启动服务前即显示核实的Project/instance身份。
- 新公共核心 `abqjobpilot/product_project.py`：显式目录创建、只读打开/分类。产品manifest v1包裹原format3执行存储，零Plan/Grant/Run，初始PAUSED，不启动进程、不搬移外部工程文件。
- 新 `local_credentials.py`：原IPC/生命周期凭据采用Windows当前用户DPAPI落盘，绑定本机和实例；private目录创建即限制当前用户/SYSTEM访问。没有新认证协议、明文临时文件或普通客户端mint入口。
- 原发现/manager/owner仅接入产品身份与密文读写。没有改Backend、ExecutionService、Grant匹配、所有权、幂等、派发、自动收尾、对账或Schema核心。
- 独立只读例子 `examples/agent_first/product_inspect.py` 已从非仓库cwd实际运行；普通API客户端也实际启动/复用服务、提交已授权固定Python、查询及断开。CLI/MCP没有新增写接口。

具体API、GUI操作和错误见 [USAGE.md](USAGE.md)；数据/凭据/迁移边界见 [PROJECT_AND_CREDENTIAL_CONTRACT.md](PROJECT_AND_CREDENTIAL_CONTRACT.md)。开始基线和本轮增量见 [BASELINE_AND_SCOPE.md](BASELINE_AND_SCOPE.md)。

## 实际 Windows 证据

Windows11 NT10.0.26300；登记LangChainEnv Python3.12.10、Tk8.6。最新证据见 [windows_verified/fixed_worker_product.json](windows_verified/fixed_worker_product.json)及 [正常GUI截图](windows_verified/product_gui.png)。

测试Run `r_131e47590aff47f5bb50394da4bb7f84` 经独立普通客户端提交。GUI/专属venv启动器正常退出码0后，保留身份句柄确认原owner与worker仍存活，进度游标从4增长到5；重开GUI看到原Run/回执，同请求重放，只有一个START_INTENT。最终FINISHED、受管范围收尾COMMITTED_EMPTY_SCOPE、Artifact VALID，Solver **NOT_RUN**，不称Abaqus成功。

空ProjectGUI创建/启动/停服/重启与独立客户端证据见 [empty_gui_product.json](windows_verified/empty_gui_product.json)：没有自动Grant/Run，首次启动及显式重启均PAUSED；重复创建拒绝，重复Start复用owner；错误凭据、旧/错误端点、复制目录、跨Project材料与明文降级均拒绝。

固定任务的授权属于单独可信harness，在创建方初始租约内调用既有issuer和精确resume事务；普通New和client没有测试钩子。尚未提供通用的运行中Project批准界面或动态Backend配置入口。

## 测试、迭代与清理

最终 **319个唯一用例PASS，0最终FAIL/SKIP**。主回归303PASS；新增/补强GUI链9项及最终13项重复验证按ID去重，Legacy15项。首次Legacy有一个Tk初始化SKIP，原用例在干净隔离进程通过。测试驱动的SQLite URI与遥测竞争失败均保留，未削弱旧业务断言；完整批次见 [TEST_RESULTS.json](TEST_RESULTS.json)和 [验收说明](ACCEPTANCE_AND_TESTS.md)。

第一次审计与最终追加审计共清理122份本轮私有材料；最终11个明确临时根的相应凭据剩余0。累计518条记录身份后查无匹配存活，报告中已知秘密值命中0。测试保留句柄的退出事实与后续“未发现匹配身份”分别记录；收尾审计没有终止进程或递归删除目录。见 CLEANUP_FINAL.json、CLEANUP_UI_FINAL.json、CLEANUP_VERIFICATION_FINAL.json，以及windows_verified下的三个cleanup副本。

Dev仍为Develop@`271c6f82fd6a4599dbae2df30d903dab2cef1f63`、0.3.0.dev0。开始记录的1235份既有文件无丢失；仅10条已列明路径变化（含3条共享GUI测试屏障修正），核心及历史冻结证据保持。没有为了干净工作区执行任何Git恢复/清理操作。

## 仍未覆盖与 Run021 最小范围

- 当前产品生命周期仍仅支持受限测试执行；原真实Standard路径没有被New操作自动启用。真实计划/保留资源停服限制继续有效。
- 同用户跨进程凭据/DACL已实测；异用户/异主机仅负向绑定注入，未做跨机实测。副本/移动保守拒绝；通用重新配置、迁移和产品归档尚未实现。
- 同一OS用户任意代码/文件权限不在本地凭据机制的隔离保证内。没有通用人类审批或跨用户Agent角色平台。
- 仅验证当前Windows会话持续存活的GUI退出/重连；不声明终端/外层宿主关闭、注销、关机、系统重启或真实Abaqus产品宿主已验收。

Run021建议先在零Abaqus预算下，审查固定Standard的可信产品配置及真实完成后安全停服判据，再准备**一个全新产品Project、一个固定受管Standard analysis、一次启动、额外调用0**的清单。精确真实Grant、提交/必要派发及实机调用必须取得新的授权；旧Run016/历史批准不能复用。具体范围见 [RUN021_MINIMUM_SCOPE.md](RUN021_MINIMUM_SCOPE.md)。本轮未开始该工作。
