# Run 003 — 逐项验收

最终 Windows 实测：**125 passed，0 failed，0 errors，0 skipped，52.10s**（JUnit suite 52.059s）。95项 Run002 回归 + 28项 Supervisor/协议验收 + 2项所有权/格式兼容补充。

证据：[JUnit](TEST_RESULTS.xml)、[原始输出](TEST_OUTPUT.txt)、[源码哈希](SOURCE_HASHES.json)、[进程/阶段记录](PROCESS_EVIDENCE.json)。P 指 [test_fake_supervisor.py](../../../tests/test_fake_supervisor.py)，O 指 [test_execution_ownership.py](../../../tests/test_execution_ownership.py)。下表每个命名测试及其全部参数实例均 PASS；多行共享测试，不能把引用数量相加当 case 数。

| ID | 实际测试 | 结果与可观察证据 |
| --- | --- | --- |
| R3-01 独立进程/绑定 | P::test_independent_client_exit_owner_continues_and_reconnects | PASS；owner实际PID26636、提交客户端14120、重连客户端28608；都通过登记解释器启动。endpoint、context、数据库位于同一明确临时测试根 |
| R3-02 客户端退出 | P::test_independent_client_exit_owner_continues_and_reconnects；P::test_client_timeout_after_accept_does_not_cancel_owner | PASS；START_INTENT屏障后以已核验句柄终止客户端，owner存活并完成；真实2秒通信超时得到ACCEPTANCE_UNKNOWN，原key可查且完成Fake |
| R3-03 接受应答丢失 | P::test_accept_commit_response_lost_reconnect_reuses_receipt_and_effect | PASS；submit:before_response屏障处接受已提交；首应答尚未发送时Fake仍完成；结束客户端后重连同key获得原receipt/Run；消费记录、START_INTENT、副作用各1份 |
| R3-04 并发与单槽 | P::test_multiclient_idempotency_and_different_requests_single_slot | PASS；6个并发连接同请求仅1个新接受/Run；第二请求保持PENDING，第一终态事件序号早于第二START_INTENT；异内容同key冲突。每实验存储单槽，非主机总槽 |
| R3-05 owner竞争 | P::test_competing_supervisor_and_supported_writer_cannot_bypass_owner；O::test_local_owner_cannot_release_lock_during_active_fake | PASS；第二真实Supervisor进程OWNER_BUSY退出，endpoint及业务inventory不变；执行期间显式close拒绝释放本地owner |
| R3-06 绕过入口 | P::test_competing_supervisor_and_supported_writer_cannot_bypass_owner | PASS；另一Python进程调用原ExperimentStore得到OWNER_UNCONFIRMED，显式acquire_supervisor_store得到OWNER_BUSY；父进程相同尝试也被拒绝 |
| R3-07 执行中查询/分页 | P::test_running_query_nonblocking_readonly_pages_reconnect_and_caps；P::test_maintenance_query_never_repairs_existing_sidecars | PASS；Fake产物屏障阻塞执行时receipt/run/validation/events/health可响应，查询前后业务inventory完全相同；分页游标经新连接追齐序号1～4；64条上限强制；journal/WAL/SHM三种维护标记查询拒绝且不修复 |
| R3-08 协议拒绝 | P::test_protocol_identity_authentication_whitelist_rejected_without_effect；P::test_malformed_json_refused_and_owner_remains_responsive；P::test_wrong_bootstrap_authority_cannot_adopt_and_does_not_poison_owner | PASS；9组错误credential/version/project/instance/context/owner/approve/反射/namespace；4组非法UTF8/重复key/NaN/非对象；无业务变化。错误可信bootstrap authority也不能接管；修正后原新实验可启动 |
| R3-09 消息边界 | P::test_message_bounds_truncation_partial_arrival_and_absolute_deadline；P::test_connection_cap_is_bounded_and_recovers_after_frame_deadline；P::test_response_serialization_bound_before_any_bytes_sent | PASS；超大长度立即拒绝、截断EOF关闭、分段输入完整解析；不完整请求2秒总截止并发不阻塞普通健康查询；超8连接有界拒绝/超时后恢复；超大响应发送前拒绝且未发送字节 |
| R3-10 实际owner崩溃 | P::test_actual_owner_crash_after_artifact_restart_uncertain_and_pending_blocked | PASS；dispatch:after_artifact（已fsync、终态事务前）屏障结束PID2964，重启owner29920。原Run显示RECONCILIATION_REQUIRED、无validation、原产物字节不变；另一Run保持PENDING；新提交DISPATCH_PAUSED；事件仍只有两次接受和一次START_INTENT，不重复Fake |
| R3-11 陈旧信息 | P::test_stale_endpoint_metadata_does_not_connect_takeover_or_autostart | PASS；伪陈旧owner.json不能绕过活跃内核锁；owner结束后旧client连接失败且文件不变/无新owner；显式重启后旧owner身份即使指向新端口仍拒绝；重启只读暂停 |
| R3-12 隔离/清理/回归 | P全部进程fixture清理；O全部；Run002原95项 | PASS；27个多进程case共39个实际Python进程，句柄均确认退出，4次明确测试终止。39个启动器也wait完成；私有凭据删除、剩余文件不含token；临时Recent不变，未生成工程文件/旧队列。格式1只读兼容且拒绝写入接管。原95项全部重新执行通过 |

## Run002 回归与断言保留

[test_execution_contract.py](../../../tests/test_execution_contract.py) 56项、[test_execution_store.py](../../../tests/test_execution_store.py) 30项、[test_execution_isolation.py](../../../tests/test_execution_isolation.py) 9项。其测试身份集合完整包含在本轮125项JUnit中；[Run002的R2-01～16映射](../run_002/ACCEPTANCE_MATRIX.md)继续适用，历史结果文件未覆盖。

原契约/存储测试及 execution_helpers.py 完全不改。隔离AST测试仅对新ownership/protocol/supervisor模块增加精确标准库白名单，Fake/Plan/Validator仍不可依赖启动/通信模块；新增client依赖限制。原运行时启动trap、路径inventory和复制拒绝断言均保留。首轮EOF内锁造成inventory/复制失败时修正的是锁实现，没有跳过或放宽断言。

## 实际命令与迭代记录

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B -m pytest -p no:cacheprovider tests/test_execution_contract.py tests/test_execution_store.py tests/test_execution_isolation.py tests/test_execution_ownership.py tests/test_fake_supervisor.py --basetemp='C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run003_6fcc0e2aa14c45dc97a3e68b980a3104\final' --junitxml='C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run003_6fcc0e2aa14c45dc97a3e68b980a3104\final.xml' -q
```

这是实际最终命令。重跑须用[复现说明](IMPLEMENTATION_AND_PROTOCOL.md)生成新的根，不能复用旧basetemp清空证据。插件自动加载与pyc关闭；未安装依赖。

| 轮次 | 结果 | 原因/处理 |
| --- | --- | --- |
| run1 | 90 passed，27 failed，32.41s | Windows文件内字节锁阻止读取/复制；venv转发器导致Popen PID与Python实际PID不同。修正EOF外锁、实际进程身份和句柄管理 |
| run2 | 117 passed，46.84s | 原95项及首批22项全部通过 |
| run3 | 125 passed，49.14s | 将暂停重放归入原服务、增加身份绑定屏障，补8项超时/协议/格式/锁生命周期覆盖 |
| final | 125 passed，52.10s | 增加本机固定盘检查、创建失败释放锁和测试凭据清理后的最终验证 |

各次原始文本/XML保留在上述本轮临时根；交付目录保存最终输出，源码与之绑定。测试计数不跨轮次相加。最终没有失败、跳过或未覆盖的R3验收项。

## 未验收边界

不宣称主机总资源槽、跨Project输出协调、自动恢复/人工对账解除、GUI/MCP适配、流式订阅、生产迁移、真实批准域、真实Abaqus Backend/Solver/ODB验证或正式0.3.0完成。崩溃验收是确定窗口的真实Windows进程终止，不是断电/OS崩溃/任意SQLite中间写入的恢复验收；sidecar明确拒绝维护。未运行无关GUI/Solver全量测试，Stable未访问。
