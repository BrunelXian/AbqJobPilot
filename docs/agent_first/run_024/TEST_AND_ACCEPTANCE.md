# Run024 — 测试与验收

最终 **764 个唯一 pytest 用例，764 PASS，0最终 FAIL/ERROR/SKIP**。按最终 XML 的 classname + name 去重，重复迭代及 lifecycle_03 子集不重复计数。详见 TEST_RESULTS.json；与历史664或548采用不同选集，不能凭数量判断回归。

| 最终选集 | 唯一数 | 覆盖 |
|---|---:|---|
| core_01 | 458 | Store/所有权/精确授权/幂等/Run007对账/Run014处置/固定与Standard替身/受管范围/连续任务/正常收尾 |
| product_final | 127 | Run018认证/分页/身份隔离、Run019生命周期/并发/停服、Run020项目/凭据、Run021B单次派发、GUI退出/重连 |
| recovery_final | 84 | CR-D02诊断/进程身份/Windows固定替身、CR-D03预览/精确恢复/事务/幂等及原Run014一致性；只作用新隔离测试 |
| legacy_01 | 59 | Classic Project/队列表/Results/文件归属/公开Classic API/格式隔离 |
| isolation_final | 9 | 导入与真实路径不可达边界 |
| api_final | 11 | MCP五个只读/预览工具，无写能力扩展 |
| native_case_1～12 | 12 | 单根导航/实际Classic控件保留/四语/偏好/向导/显示投影/本地Tk缩放 |
| windows_final | 3 | 新原生GUI完整退出/重开、只读恢复RPC一致性、跨Project缓存和断线 |
| visual_final | 1 | 同一原生根跨四语言及9页/向导/窄窗/Classic截图 |

## 安全执行方式

运行前审查选集及原固定Python夹具。登记解释器 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，3.12.10 / Tk8.6 / pytest9.1.0。`run_safe_tests.py` 每批创建唯一 AbqJobPilot_Run024_* 临时根，显式 TEMP/TMP/HOME/USERPROFILE、Project/Runtime/Recent；不安装依赖，禁pytest第三方插件与写pycache。

外层审计禁止真实 abq2024/standard/smapython 创建和默认Runtime访问，写入只允许本批临时根/报告目录。Standard Windows夹具沿用受控Python替换真实创建路径；GUI纯监控进程另禁止 subprocess/SQL/Legacy导入，并严格限定只读Client调用。测试可以显式启动/停止/故障注入自己创建的固定进程，不能终止用户现有进程。

复现示例（使用新报告名，不能覆盖旧XML）：

```powershell
Set-Location 'D:\Projects\abqjobpilot_dev'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs/agent_first/run_024/run_safe_tests.py native_windows windows_review_new
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs/agent_first/run_024/run_safe_tests.py product product_review_new
```

控件用例最终逐 case 采用独立进程，例：

```powershell
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs/agent_first/run_024/run_safe_tests.py native native_review_new 'test_new_project_dialog_is_explicit_abaqus_no_process'
```

## 实际失败迭代（原XML保留）

1. product_01：40通过后1失败。新壳初始 NOT_RUNNING 早于异步inspect结束，测试/用户可过早点击Start；manager被busy保护拒绝，界面仍易误读。改为 NOT_SELECTED→INSPECTING；轮询失败不覆盖明确生命周期结果。
2. lifecycle_02：7通过后1失败。空Project身份显示在无Run时被路径覆盖。保存经核心核验的 project_metadata，修正上下文显示；lifecycle_03 20通过，之后完整product_final127通过。
3. visual_01：1通过后第二根Tk初始化出错；native_final/native_final2同类初始化错误，Tcl报tcl_findLibrary或组件文件不可读，实际文件存在。显式GC试验没有解决，未修改共享环境。产品本身仅一个根；最终视觉在同根切换全部语言，控件用例按独立OS进程执行，12项全部通过。**不把此问题说成已经修复的Tcl环境故障**；同一解释器反复销毁/重建Tk仍未验收。产品正常退出/重新启动是独立进程，已由Windows测试验证。
4. 视觉审查发现向导Project Type空白（临时StringVar被回收），修正为控件自身选择并加断言；窄窗资源说明/日志翻译相应修正。最终原生截图与Windows测试通过。
5. 只读依赖检查发现LangChainEnv没有Pillow；没有安装或换共享运行环境，复用已有stdlib/Win32截图工具。

详细失败测试名和原message见 FAILED_ITERATIONS.json。早期native_01/native_02与windows_01/windows_02通过记录保留，不冒充末次结果。

## 18项验收对应

| 要求 | 实际证据 |
|---|---|
| 1 正常入口 | run_gui.main 实际构造native_workspace，pythonw完整OS链；VBS文件未变 |
| 2–3 顶部Classic及返回 | native_case_1/7、visual_final实际控件与截图 |
| 4 无切页执行副作用 | GUI子进程禁止Popen/SQL，页间切换Store摘要/事实不变 |
| 5 Project/Run | windows_final三例、product_final跨Project/回执 |
| 6 四语/偏好 | native_case_2–6、149键/参数一致、保存/回退 |
| 7 New术语 | native_case_8、product新建实际向导、唯一Abaqus |
| 8 真实Supervisor/日志 | windows_final固定Python实际IPC和持续日志 |
| 9–10 完整退出/重连 | NATIVE_EVIDENCE.json，两GUI及专属启动器退出，原owner/worker存活日志增长、同Run/receipt |
| 11–12 诊断一致/只读 | RECOVERY_IPC.json，核心/RPC digest一致，多次查询事实不变 |
| 13 无Apply扩权 | 新Apply operation与observe_os参数均拒绝；本地可信通道不暴露 |
| 14 Classic Failed/Interrupted | native_case_7、gui_presentation精确raw映射与筛选 |
| 15 PAUSED/UNKNOWN原证据 | recovery_final、windows恢复例；只读查询不写revision/slot |
| 16 Legacy主要流程 | legacy59 + 嵌入原控件/筛选/导航测试 |
| 17 授权边界 | core458、product127、isolation9，真实Backend为替身 |
| 18 IPC不阻塞 | 原large-list/慢IPC用例、子GUI heartbeat、Reader异步和分页/日志有界 |

## Windows证据解释

`evidence/NATIVE_EVIDENCE.json` 保存完整Run/receipt、owner身份、GUI_A/B进程及venv启动器退出、GUI退出后worker精确PID+创建时间+映像身份、增长后的日志、正常自动收尾及VALID。Solver为NOT_RUN，不能称Abaqus求解成功。物理启动计数为1。

`evidence/RECOVERY_IPC.json` 是自己创建的固定Python owner故障样例，与已有core诊断/preview比较；`evidence/SWITCH_EVIDENCE.json` 是两个隔离Project和断线缓存。测试驱动仅操纵自己窗口的原生控件并记录视图；不是HTML，不是真实用户历史owner，也不是新运行控制器。

最终清理见 CLEANUP_FINAL.json（首次阻断记录保留在 CLEANUP.json）：只按本轮登记身份查询，句柄由原夹具wait/close，私有文件仅在本轮已确认临时根中移除；保留DB/输出/审计。事后不存在/身份不匹配不补写历史退出码。

未执行：真实Abaqus/ODB/生产恢复Apply、用户历史owner生命周期、系统注销/重启、多显示器真实DPI、任意新主机部署、未知第三方插件/全仓未隔离老测试。没有因扩大覆盖而访问默认生产路径。
