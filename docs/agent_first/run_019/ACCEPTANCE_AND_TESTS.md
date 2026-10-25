# Run019 验收与测试

最终按 `classname::testcase name`（含参数化名称）去重：**291 PASS / 0 FAIL / 0 SKIP**。逐项ID、选集和最后结果见 TEST_RESULTS_FINAL.json。不是全仓库测试，也没有复用历史通过数字。

| 批次 | 实际结果 | 范围 |
|---|---|---|
| final.xml | 275 PASS，343.29秒 | 相关核心/GUI/IPC/授权/受管范围/替身 Standard + 当时已收集生命周期用例 |
| legacy.xml | 15 PASS，6.91秒 | 独立进程中的 legacy Project/GUI/格式隔离 |
| lifecycle_final02.xml | 28 PASS / 1 FAIL | 新增跨 OS 客户端竞争；失败为证据序列化的测试浮点时间，不是服务断言 |
| gui_final03.xml | 1 PASS | 改用冻结 JSON 契约支持的整数秒，取得 UTF-8 完整 Windows 证据 |
| gui_attachment_final.xml | 4 PASS | GUI 显式 Disconnect 后保留 Run 选择、重连及失联服务标签修正后的相关最终组 |

最后三组与主回归重复的用例只计一次；跨 OS 客户端竞争是主回归收集之后新增的一项，所以最终 291 = 275 + 15 + 1。最终集合未弱化旧断言，也没有跳过失败场景。

## 验收映射

| 场景 | 直接证据/测试 | 结果 |
|---|---|---|
| A：正常 GUI 显式 Start 原本不存在的服务 | test_product_gui_start_worker_survives_normal_gui_and_launcher_exit：正常 run_gui.main、明确选择Project、NOT_RUNNING、真实按钮invoke、认证连接；windows_final/gui_attachment_product.json | PASS |
| 重复 Start、disconnect | test_idle_start_reuse_stop_restart_and_permission；GUI Start 后第二公共客户端返回原 owner、created=false | PASS |
| B：GUI及专属venv完整退出后owner/worker继续 | 同一Windows GUI测试：正常 WM_CLOSE、两个保留句柄exit=0，随后原owner/worker身份句柄仍未退出，progress增长；重开同Run/回执；同键submit重放 | PASS |
| GUI日志、Project/Run选择、切换和失联 | test_attachment_gui（3项）、test_service_attachment、test_project_view、test_execution_gui；Disconnect/Reconnect保留同Run并重验身份 | PASS |
| C：跨进程并发启动 | test_two_os_clients_race_same_original_owner_lock：两个独立Python调用者在屏障后竞争，仅一个 created/claimed；cross_process_race.json | PASS |
| 同进程两个调用者 | test_concurrent_start_single_reservation_and_owner | PASS |
| 启动确认超时、创建后丢响应 | test_handshake_timeout_inspect_no_retry；test_lost_start_reply_never_second_creation[intent_persisted/created] | PASS；保留预约，绝无第二创建 |
| owner锁冲突、不可认证、旧协议/身份/能力/端点 | test_old_lock_or_bad_credentials_never_replace；test_existing_owner_errors_never_replace（5项）；既有 discovery 身份组 | PASS |
| owner真实异常退出 | test_real_owner_crash_not_automatically_replaced：新测试owner持有身份核实句柄后真实终止；再次start阻断，只有一个创建记录 | PASS；不是生产 stop 路径 |
| 查询/权限/磁盘失败 | test_inspect_connect_disconnect_no_business_writes；test_precreation_faults_fail_closed（4项） | PASS，未调用外部进程 |
| D：空闲停服与显式重启 | GUI正常Stop、持久回执/PAUSED、实际owner正常exit；再次Start为新owner、PAUSED | PASS |
| 活跃/PENDING/UNKNOWN/槽占用/真实计划拒绝停止或启动 | GUI实际worker活动时拒绝；test_unresolved_store_cannot_stop_or_start（4项）；test_start_refuses_pending_without_owner_metadata | PASS |
| 停服事务失败不产生无记录解锁 | test_stop_transaction_failure_does_not_pause_or_unlock | PASS，派发原值、lease仍持有、0新回执 |
| 停服提交不确定、丢应答 | test_unknown_stop_commit_replay_uses_durable_decision；test_stop_response_lost_queries_original_receipt | PASS，按原键查询/重放、一次决定、无kill补偿 |
| 停服禁止并发接受/派发 | test_concurrent_stop_one_commit_and_submit_race_blocked：同键一次commit、不同键拒绝、stop之后原事务入口不能accept | PASS |
| 首次已有PAUSED及重启PAUSED | test_first_explicit_start_preserves_preexisting_paused_gate；idle/start/restart组；managed_paused_gate回归 | PASS；不自动恢复 |
| 原授权、一次尝试、自动收尾及历史资源策略 | test_execution_contract/store/ownership/isolation、test_process_contract、test_public_workflow、test_managed_scope、test_standard_managed/windows | PASS；Standard实际创建被固定Python替身替代 |

实际窗口操作由测试驱动正常 Dev Tk 入口和原按钮，测试注入仅用于UI动作/渲染证据采集；没有独立演示GUI或替换生命周期管理器。GUI子进程审计只容许固定 `service_owner.py` 创建，SQLite连接只容许 mode=ro；客户端操作仅允许原读取和 lifecycle_stop，不存在自批/直接Backend调用。普通跨进程 API 和非仓库公开例子不依赖GUI。

## 故障注入与实际 OS 的区分

真实：独立 GUI/venv/owner/worker、Windows Job观察、正常退出/存活、实际锁竞争、固定worker日志、正常停服、持有测试进程句柄后的owner终止。

注入：创建确认丢失、IsProcessInJob失败、磁盘/事务失败、提交已完成但返回SQLite错误、部分JSON、错误协议/身份、不能认证的端点。负向存储夹具只用来证明拒绝，不用手改库构造正向运行成功。生产路径没有这些故障开关。

## 测试副作用预审

主选集：test_project_view、test_service_attachment、test_attachment_gui、test_execution_contract、test_execution_store、test_execution_ownership、test_execution_isolation、test_fake_supervisor、test_process_contract、test_public_workflow、test_execution_gui、test_managed_scope、test_standard_managed、test_standard_managed_windows，以及本轮 test_lifecycle_boundaries/test_service_lifecycle。

已核实 ProcessHarness 只创建固定普通Python测试进程；managed/Standard回归在实际Win32创建接缝换成固定Python，保留无Abaqus/无无管理回退哨兵。旧默认Runtime/Recent、真实授予和任意命令仍受原隔离检查。Legacy另用 run_legacy_gui_tests.py 设置新home/Runtime/Recent并拒绝任何外部进程。

未执行无关GUI全套、真实Solver/ODB、生产迁移和全项目算法测试。未访问或操作 Run016 的活owner/GUI。真实Abaqus调用 **0**。

最终命令使用登记绝对Python、`-B -m pytest -p no:cacheprovider`、`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`、显式TEMP/TMP与每批独立 `--basetemp`；报告写Run019。早期迭代保留了pytest默认忽略缓存，业务Project/Runtime/Recent和私有材料仍全部在本轮新临时根。

## 失败迭代（全部保留）

1. smoke：测试误用 client.credential，实际私有字段为 _credential；修正测试，不改变连接权限。
2. iteration02/03：错误断言用异常文本匹配code；另GUI audit在Windows收到的是字符串命令行，测试误当列表。改为验证准确固定入口与结构化 `.code`，不放宽可执行范围。一次编辑脚本漏指定UTF-8，被本机GBK默认解码拒绝，iteration03因此重复了旧失败。
3. iteration04：GUI遥测原子replace期间Windows读文件短暂PermissionError；只在测试遥测读取做有界重试，业务查询失败不吞掉。
4. boundaries01/core02：负向测试误用服务返回dict、初始PAUSED不能正常提交，以及错误假设runs表有两列。改成符合实际schema的明确负向夹具，不修改接受/授权核心。
5. lifecycle_final02：补充OS证据时使用float时间，原canonical_json拒绝float。改为整数秒，最终GUI组通过。早期Windows证据输出误用本机CP936，保留原文件；最终 windows_final JSON显式UTF-8。
6. 最后UI审查发现 Disconnect 后重新连接会丢当前选择，服务标签也可能停留CONNECTED；修正仅展示/选择恢复，运行相关4项通过。

## 清理

本轮根为 `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run019_4uyet2rj`。CLEANUP_FINAL.json 汇总测试自有退出/句柄、私有配置清理，并仅对该根记录的454个唯一PID+创建时间+映像做后查：**0匹配存活，0剩余私有连接/操作者凭据文件**。后查“对象不可见/身份已变化”不补造过去退出；关键退出来自测试当时持有的Windows句柄。

保存业务测试库、预约和报告作证据；没有递归删除旧测试目录，不按进程名终止，没有触及历史真实实例。真实故障测试终止的仅是本轮新建且身份已核实的owner；产品 stop 没有任何终止功能。
