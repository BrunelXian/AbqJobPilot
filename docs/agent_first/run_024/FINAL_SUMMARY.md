# Run024 — Native GUI Integration

**PASS_ABQJOBPILOT_RUN024_NATIVE_GUI_INTEGRATION_READY**

已将 Run023 的统一导航与核心信息层级落到正常 Dev 原生 Tk/ttk 主窗口：九个工作区、顶部常驻 Classic Queue、Classic 中 Execution Workspace 返回入口、New/Open/Recent/Project Settings、独立 Service 管理、四语言显示资源，以及 CR-D02/03 的只读诊断/恢复预览。**HTML 没有成为产品运行界面。**

正常入口仍为 [Open_Dev_GUI.vbs](../../../Open_Dev_GUI.vbs)，版本0.3.0.dev0。打开软件不自动选Project、不启动服务、不授权或派发。

## 已完成与实际证据

- 一个Tk根窗口和mainloop；Classic显式有效Project后惰性嵌入原控件/控制器。双向切页保留Project/Run、Classic选中项/筛选和Runner对象，不通过关闭进程模拟导航。
- 产品公共Client/Reader提供分页、异步日志/事件、断线缓存与最后观察时间；GUI不直接写执行DB。Service操作复用原生命周期准入，活跃/未知Run仍由原规则阻断危险停服。
- 新增两个认证只读IPC路由，复用核心诊断和Preview，不新增Apply/批准/恢复派发权。实际RPC与核心decision/preview digest一致，重复读取revision/gate/slot/Grant和Store摘要保持。
- Classic raw UNKNOWN_INTERRUPTED 独立显示Interrupted (Unverified)，真实FAILED保持Failed；没有修改Run状态机、Schema或恢复核心。
- 四语言各149键，参数一致。默认English、用户偏好持久化；法德标Preview并待母语审校。Classic仍为原en/zh工具，法德明确英文回退。

**764个唯一用例全部PASS，最终FAIL/ERROR/SKIP均0。** 458核心、127产品、84恢复、59Legacy、9隔离、11MCP、12新原生控件、3新Windows、1四语视觉。失败迭代原XML和清单保留，详见[测试报告](TEST_AND_ACCEPTANCE.md)。

最新Windows原生正常main验收Run：`r_c6a665bca2884c53a88f0b64f712ac62`（固定Python）。GUI A本体PID32116及venv启动器31976均通过保留句柄取得exit0；之后原owner PID25504和worker PID12372的完整记录身份仍匹配，日志继续增长。GUI B重开连接同一Run/回执，物理启动仍1；随后固定worker自行完成，COMMITTED_EMPTY_SCOPE、Artifact VALID，Solver NOT_RUN。GUI B及启动器亦exit0。创建时间/映像/回执和原始事实见 [NATIVE_EVIDENCE](evidence/NATIVE_EVIDENCE.json)，不是仅依据PID或函数返回。

恢复界面另使用自己创建的owner崩溃样例，核心投影确为UNKNOWN_INTERRUPTED；GUI展示相同SUPERVISION_INTERRUPTION_SUSPECTED及Preview，没有执行GUI Apply。[恢复IPC证据](evidence/RECOVERY_IPC.json)。产品创建/显式启动/空闲停服测试只作用新临时实例。

## 保护和清理

Develop HEAD保持 `9553755a24ff521dd2ac694ea39cab5a03f88466`。1616个基线文件中，仅12个明确GUI、只读适配和旧GUI测试驱动/断言文件修改，其余1604个摘要一致；前轮未提交CR-D03核心/历史材料全部保留。新文件均为展示资源、针对性测试和本轮交付，见 [FINAL_CHECKS](FINAL_CHECKS.json)。

31个本轮临时根，1048个本轮登记身份只读后查：匹配活动0、最终查询未决0；164份本轮私有连接/授权材料移除，报告已知秘密命中0，DB/输出/审计保留。首次清理遇58条完整映像查询不明，保持凭据未动；后续只读PID+创建时间+OS退出句柄核验补充57条（其余首次不明此时原查询已明确），才清理本轮私有文件。没有终止任何进程，也没有将后查结果写成Run历史退出证据。见 [初次清理](CLEANUP.json) 与 [最终清理](CLEANUP_FINAL.json)。

**真实Abaqus调用0，历史/生产Recovery Apply 0，历史owner操作0。** 隔离回归中的固定Python恢复/故障注入不属于生产恢复。未访问Stable，未修改共享环境/Backend/授权或派发状态机，未迁移Project，未提交或推送。

## 保留的限制

- 本机单进程反复重建Tk的单测出现Tcl初始化异常；未修改共享环境，最终采用与产品一致的独立进程用例与单根多语言切换。正常产品退出/重开已实测，不宣称多Tk嵌入宿主验收。
- FR/DE母语审校、完整无障碍和跨显示器真实DPI仍待做；本轮测试本地Tk100/125/150%及原生窗口1024×768/1366×900。
- 原生详情保留可滚动核心JSON与维度摘要，没有复制HTML模拟器/装饰；恢复仅只读。Classic的旧工具和执行边界保留，不能把其Runner当独立服务。
- 通用新主机部署/缺Tk诊断/发行打包仍未验收，VBS继续绑定登记环境；本轮没有新增依赖。真实Abaqus兼容性、Run021B NOT_OBSERVED、域外UNKNOWN、ODB NOT_RUN等历史边界不扩大。

## 交付入口

- [使用说明](USAGE.md) · [实现与统一导航](IMPLEMENTATION_AND_NAVIGATION.md)
- [恢复只读契约](READONLY_RECOVERY_CONTRACT.md)
- [本地化及原生截图](LOCALIZATION_AND_VISUAL_REVIEW.md)
- [测试及验收矩阵](TEST_AND_ACCEPTANCE.md) · [逐用例结果](TEST_RESULTS.json)
- [Windows证据索引/摘要](WINDOWS_EVIDENCE_INDEX.json)
- [RC剩余最小操作与Git检查点建议](REMAINING_AND_GIT_CHECKPOINT.md)

可以进入本轮界面审阅和经过筛选的Git检查点准备；不能自动发布、提交、晋升Stable或开始下一轮。完成后停止。
