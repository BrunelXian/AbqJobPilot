# Run022 — 安全回归与部署审查

## 环境与执行方法

先读取根AGENTS和环境登记；复用 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python3.12.10、Windows11 build26300、pytest9.1.0、Tk8.6、SQLite3.49.1，详见 [ENVIRONMENT.json](ENVIRONMENT.json)。没有安装/升级依赖。版本保持0.3.0.dev0；执行协议`af-experiment-v1`，IPC `af-local-json-v1`，新产品manifest v1、执行存储v3；Classic manifest1.0/历史schema v1独立。

本轮选择审阅后的安全子集，不运行无差别全仓库pytest。`run_safe_tests.py`固定五个选择组，每次创建唯一 `AbqJobPilot_Run022_<group>_*` 临时根，并显式TEMP/TMP、basetemp、日志、证据路径；不读取GUI当前Project或默认Recent。Legacy与新执行链分进程收集，防止旧config导入污染隔离断言。Legacy的Path.home/Runtime/Recent显式重定向；API子进程使用本轮USERPROFILE/HOME。禁用额外pytest插件加载、cacheprovider和字节码写入。

父测试进程审计钩子拒绝Abaqus启动及临时根/本报告目录外的文件写入；Windows NUL仅作为subprocess标准输入空设备例外。固定子进程另有各自已有trap/限定根/固定启动路径。该钩子不是通用沙箱声明：native创建在既有测试owner中使用具体审查过的固定Python替身。

## 测试副作用审查依据

| 组 | 实际入口与范围 | 限制与清理 |
|---|---|---|
| core | execution contract/store/ownership；process contract/fixture；Fake与退出证据对账；诊断/公共工作流；Standard backend/admission/supervisor/closeout；managed scope/pair | `execution_helpers.guard_environment`禁止legacy/默认Home/外部创建；`supervisor_helpers.ProcessHarness`仅绑定本轮子进程PID+创建时间+映像，故障测试允许终止自身保留句柄；无按进程名终止 |
| Standard替身 | `tests/run013_process.py`、`run016_process.py`、`run021b_service_owner.py` | `_launch`或`ManagedScope.create_standard`替换为固定普通Python；child audit拒绝真实调用，原始冻结DAT仅从Dev文档样本读取到临时工程。样本不被当成新真实实验 |
| product | service_attachment/project_view/attachment_gui/execution_gui；service_lifecycle/lifecycle_boundaries；product_project/product_windows；product_standard_control/windows | 正常主窗口类和公共API；新临时Project及私有材料；实际Windows WM_CLOSE只给本轮核验HWND，保留GUI/venv/owner/worker引用；不操作现有用户窗口 |
| isolation | test_execution_isolation独立进程 | 原隔离和静态依赖断言不削弱；测试不与legacy模块同进程收集 |
| legacy | project_gui/gui_table_state/g2_task_workspace，Project model/database/ownership/queue-only，TestPublicApi，Run017两项格式拒绝 | 显式临时Home/Runtime；该组拒绝任何进程创建；不执行旧Runner真实求解 |
| api | test_mcp_readonly | MCP5工具只读、缺SDK、正常GUI/API无SDK导入、双stdio客户端；只启动固定Python，explicit临时Project和USERPROFILE |

完整文件列表是 `run_safe_tests.py:SELECTIONS`；每个参数化case ID、批次及最终状态见 [TEST_RESULTS.json](TEST_RESULTS.json)。最终统计以实际XML为准，不引用历史392/319/647等数字代替本轮结果。

## 批次与失败迭代

最终 **664个唯一参数化case全部PASS，0最终FAIL/ERROR/SKIP**。去重键为`classname::parameterized name`；不是执行次数相加，也不将失败后重测计作新用例。全部首轮/复核XML保留。

| 批次 | 收集并执行的唯一case | 最终结果 | 用时 |
|---|---:|---|---:|
| core | 458 | 458 PASS | 362.46s |
| product | 127 | 127 PASS | 221.21s |
| isolation | 9 | 9 PASS | 1.97s |
| legacy | 59 | 59 PASS | 8.61s |
| api / MCP | 11 | 11 PASS | 6.58s |

首轮core的458项与最终core重复，不另计。首轮XML有同case的teardown附加条目，因此其461条record不是461个唯一用例。全轮共1122次case执行、1125条JUnit记录（另有一次收集前setup失败）。这与Run021B的392或Run017的647采用不同选集，不以数值差判定回归。

已保留的真实失败：

1. `core_setup_failed.txt`：pytest配置阶段默认写Windows `\\.\nul`，本轮新增文件审计误判越界；尚未收集用例。改用临时pytest.log。
2. `core_guard_failed.xml/txt`：subprocess内部`os.open('nul', O_RDWR)`仍触发误判，458个唯一case尝试中pytest报告323PASS/81FAIL/57ERROR（包含同一case teardown附加记录，不能直接相加作唯一用例数）。135个异常条目含NUL拦截，另外3个teardown缺少因创建未发生而未生成的native cleanup文件。没有真实Abaqus创建，也没有为通过修改应用或旧断言。
3. 审计脚本只为准确的Windows NUL设备加例外，保留其他写入约束；补齐本轮证据目录创建，后续批次启用maxfail=1以避免环境问题级联。核心458项重新完整通过，362.46秒。重测不计为新增用例。

部分初轮trace包含后续清理等待超时，它们和NUL创建被阻止处于同一失败链，不据此宣布Supervisor产品故障。最终仍须通过原业务断言和实际Windows重测确认。

## 实际覆盖与未执行

本次覆盖Project创建/分类/凭据复制与误连拒绝、唯一owner/握手失败/权限隔离、公共幂等/丢应答、启动意图与owner崩溃、精确真实Grant及TEST_ONLY拒绝、单次派发窗口、受管多级/瞬时后代与正常收尾、PAUSED/UNKNOWN/行政释放、空闲stop与并发、GUI异步查询/缓存/分页/断线/正常退出及重连、Standard历史DAT离线解析。

未执行：真实Abaqus、Datacheck/CAE/Viewer/Abaqus Python、ODB、生产Project/Schema迁移、历史服务查询或控制、注销/关机/主机重启、跨主机/用户真实迁移、跨Project整机调度；非本轮选择的旧Runner/Runtime/命令控制台/恢复及历史独立实验控制器测试。它们没有被记为PASS或偷偷SKIP。Legacy兼容覆盖是明确子集，不宣称所有旧GUI工作流全量认证。

逐文件未收集清单见 [UNEXECUTED_TEST_FILES.json](UNEXECUTED_TEST_FILES.json)；`test_public_api.py`只执行TestPublicApi，未运行TestPublicCli。可选MCP实际安装版本另已核验为2.3.0，并记录于ENVIRONMENT.json。

## 部署与正常入口

`Open_Dev_GUI.vbs`从脚本位置求Dev根，使用引号传递 `pythonw -B run_gui.py`，无shell字符串任意参数入口；无用户目录硬编码，但解释器是固定 `D:\XianLab\envs\LangChainEnv\Scripts\pythonw.exe`。找不到文件时MsgBox并退出2，不启动服务。仅文件存在不能证明Tk/模块完整，因此缺Tk、损坏环境、干净新主机诊断仍P1，不能声称本轮全验。

`gui_app.main`默认attachment模式，不创建旧QueueRunner或调用默认Recent；只有明确Legacy入口才初始化旧路径。`ExecutionView`用后台Reader和Tk事件队列做IPC，不将执行服务绑定于GUI mainloop。service stdout/stderr为独立磁盘文件、close_fds，任务Job句柄由owner持有。Windows外层Job层级和用户会话仍是环境边界，CREATE_NO_WINDOW本身不是独立性证明。

本轮Windows测试通过现有主窗口类、normal attachment路径、公共生命周期与独立客户端驱动真实固定Python进程。未直接双击VBS打开用户默认环境；**原样VBS的直接产品真实GUI使用证据来自Run021B**，本轮对其进行静态入口核对，不混称重新完成该真实实验。未改快捷方式、PATH、注册表、任务计划或系统服务。

最低实际验证范围：Windows11 x64 build26300，同一持续存活的交互会话，已登记LangChainEnv Python3.12.10/Tk8.6，用户可写的新本地Project目录，Windows DPAPI与Job-list API可用。std library为核心依赖，MCP SDK2.3.0是可选只读适配依赖。Python3.10+是旧源码声明，不是新产品的全面支持矩阵；其他机器、安装位置、Windows版本和虚拟环境需独立验证。

## 可复现安全命令

以下是本轮实际调用的入口，内部总是新建临时根。重新复测应另用一个报告目录，勿覆盖本轮XML；它们不会自动执行历史真实实验。

```powershell
Set-Location 'D:\Projects\abqjobpilot_dev'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs\agent_first\run_022\run_safe_tests.py core
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs\agent_first\run_022\run_safe_tests.py product
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs\agent_first\run_022\run_safe_tests.py isolation
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs\agent_first\run_022\run_safe_tests.py legacy
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs\agent_first\run_022\run_safe_tests.py api
```

不是用户正常使用GUI前必须运行的步骤；正常使用流程见README，历史一次性真实验收入口不得重放。

## 清理与证据

各测试自带身份绑定清理；结束后的 `verify_cleanup.py`只读取本轮ROOT记录指定的新临时根，只检查有记录的PID+创建时间+映像，不扫描全机Python，不接触历史owner。当前未找到匹配身份不被追写成历史退出；历史退出/句柄关闭来自测试保留引用。确认没有本轮匹配存活、报告不含已知测试秘密后，才清理本轮精确私有凭据文件，保留DB和合成输出供审计。不递归删除目录。最终事实见 CLEANUP.json。

最终7个本轮临时根，808个唯一登记PID+创建身份的后查结果：790个原身份不可取得，18个PID身份不匹配，**匹配存活0**；并未将这些后查补成历史exit0。886份lifecycle/inventory/cleanup记录保留；审计本身终止进程0，删除本轮精确私有文件287份，已知测试秘密在报告命中0。二次检查 [PRIVATE_RESIDUAL_REVIEW.json](PRIVATE_RESIDUAL_REVIEW.json) 为0，含顶层明文凭据及DPAPI副本。5个负向测试重解析路径未跟随；第一次审计因此提前停止，修正说明见 CLEANUP_FIRST_CHECK.md。此前被拒绝清理的旧目录均保持。

精选实际Windows证据按原字节归档，源和sha256见 [WINDOWS_EVIDENCE_INDEX.json](WINDOWS_EVIDENCE_INDEX.json)：

- [产品空Project](windows/empty_gui_product.json)：新建、无任务启动、GUI/独立客户端认证、空闲停服/重启。
- [固定worker跨GUI](windows/fixed_worker_product.json)：本轮GUI26044/venv12188均exit0后，原owner/worker仍活，日志游标3→4，重开原Run。该TEST实例可信设置曾显式OPEN；不能据此说所有产品新建默认OPEN。
- [产品Standard替身](windows/test_product_standard_gui_full0.json)：真实native Job-list中启动固定Python一次，owner17940/worker23464跨GUI退出继续运行，STA126→136；原Run/回执重连、正常scope收尾、精确单次许可、idle stop/restart后PAUSED。cleanup记录5个保留句柄exit0/关闭，原root及scope句柄关闭；**真实Abaqus调用0**，Solver/DAT内容是有来源的历史离线样本，不是本轮真实求解。

证据只是本轮创建的Windows进程，不是Run016或Run021B仍保留的服务。本轮没有查询那些历史活动实例。
