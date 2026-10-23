# Run 012 逐项验收

**通过范围：固定 Python 进程的公共客户端、独立执行服务与现有 GUI 闭环。**

最终新增组：`gui_integration_003.xml`，5 passed，0 skipped。回归：`regression_001.xml`，359 passed；`legacy_gui_regression_002.xml`，5 passed。最终有效测试组合共 **369 passed**，没有计入重复迭代来增加数字。

新增组均在 `tests/test_execution_gui.py`，实际 Windows、登记的 Python 3.12.10。下表的短名映射：

- **loop** = `test_actual_gui_close_reopen_public_client_worker_survives`
- **progress** = `test_progress_auth_bounds_readonly_and_corruption`
- **product** = `test_product_entries_starter_exits_and_owner_is_independent`
- **crash** = `test_gui_observes_crashed_owner_uncertainty_without_recovery`
- **stall** = `test_stalled_ipc_keeps_tk_responsive_and_close_is_bounded`

| 要求 | 测试和实际结果 | 主要证据 |
|---|---|---|
| 1. GUI 前独立客户端提交 | loop：真实 client_workflow.py 子进程在非仓库 cwd 提交，exit0 后才创建 GUI；取得固定回执 | evidence_003/windows_gui_lifecycle.json 的 receipt/client_A_exit |
| 2. GUI 同 Project/Run/回执 | loop：从渲染后的 Tk Treeview 读取，逐项核对 Run ID 和 request_id；没有 UI 内部提交 | 同文件 gui_A、gui_B；actual_dev_gui.png |
| 3. worker 持续日志、GUI 不阻塞 | loop：两次可见日志序号增长；progress：分页、白名单、权限及超限；stall：真实 TCP 接受请求不应答期间 Tk heartbeat 仍执行，正常关闭 | windows_gui_lifecycle；gui_stalled_transport；新增组 JUnit |
| 4. GUI 整个进程关闭 | loop：给已核验 HWND/PID 发送 WM_CLOSE，保留实际 GUI 与 venv transport 的 OS 句柄；两者 wait signaled、exit0 | gui_A_exits、gui_B_exits，application.reader_joined |
| 5. GUI 退出后后台继续 | loop：两个 GUI 链成员都退出后，原 owner 身份一致、worker retained handle 未退出，日志游标继续增加 | worker_alive_after_gui_chain_exit、sequence_at_gui_chain_exit、progress_after_chain_exit |
| 6. 重开同 Run、无二次启动 | loop：重开现有 App，公开同键重放回原回执；进程成员集合不变；可信测试启动陷阱记录一次实际 Popen 和 OS 身份 | physical_launches、physical_member_set_unchanged、start_intent_count=1 |
| 7. GUI/客户端解释一致 | loop：比对 execution、exit_verification、artifact_validation；失联显示缓存不是实时状态 | gui_completed、service_final、disconnected |
| 8. 自行完成与独立验证 | loop：可信测试释放屏障，worker自行退出；product：产品固定45s计时自行释放。四角色 retained-handle exit0、FINISHED、VALID、Solver NOT_RUN 分开记录 | 两份过程 JSON 的 service_final/run；验证记录ID与时间在GUI投影中 |
| 9. 连接不改变授权/派发/恢复 | loop：运行等待期间前后回执、Run、事件、验证和 gate 完全相同，重启 owner 为 PAUSED；crash：真实终止 before-create 屏障处 owner，GUI显示待对账且无新启动，错误Project拒绝 | gui_owner_crash_block；R2～R7原授权/幂等/恢复回归359项 |
| 10. 清理与隔离 | 每个 GUI/venv/owner 进程按具体身份等待退出、关闭句柄；故障测试只终止本测试已持有身份句柄的 owner。私有连接及授权交接移除，临时Recent不变，禁止旧Runtime/SQL/启动陷阱有效 | cleanup、各临时根 lifecycle.json/inventory.json；product cleanup.private_remaining=0 |

## 实际执行和数量

相关实验回归（359）：

```text
test_execution_contract.py test_execution_store.py test_execution_ownership.py
test_execution_isolation.py test_fake_supervisor.py test_fake_reconciliation.py
test_reconciliation_supervisor.py test_run_diagnostics.py test_diagnostic_supervisor.py
test_process_contract.py test_process_fixture.py test_recorded_exit_reconciliation.py
test_public_workflow.py test_public_client_example.py
```

旧 GUI 回归（5）：`test_project_gui.py`、`test_gui_table_state.py`。它们使用临时 Project、Runtime 和 Recent，不启动 Solver。单独进程运行，避免将旧 GUI 必须导入的 config 混入“实验包不得导入旧模块”的原 AST/导入隔离测试。

本轮不运行 R9 离线 INP、R10/011 真实控制器，也没有重新运行整个旧 GUI/Solver 测试库。正式核心、Schema、版本没有变；上述组覆盖本轮确实改变的 GUI/fixture/IPC 和依赖的既有事务、所有权、恢复契约。

执行环境：显式 `PYTHONDONTWRITEBYTECODE=1`、`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`，绝对登记解释器，`-B -m pytest`。最终新组临时根：

`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run012_final_003`

实验回归临时根：`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run012_regression_001`。JUnit 保存在本目录；evidence_003 是最终新增组的业务/OS/GUI证据。没有把控制器额外 OS 观察写成实验服务当时的退出证据。

## 失败迭代如实保留

1. 最初闭环测试在**清理阶段**失败：测试额外连接文件在旧 harness 的秘密扫描之后才删除。已将本测试创建的私有交接先移除；失败根中的这两份本轮文件也单独移除，没有递归删除目录。闭环本身当时已完成。
2. 旧 GUI 首次回归 2 failed / 3 passed：延迟模块属性在 unittest.mock.patch 退出删除后，__getattr__ 未恢复单个符号。修改实现兼容恢复，原断言不变；`legacy_gui_regression_002.xml` 5 passed。
3. `gui_integration_001.xml` 1 failed / 2 passed：Windows 对测试用 view.json 原子替换瞬间返回 PermissionError。只修改测试遥测读写的有界重试/下帧重写，不把业务读取失败忽略为空成功；GUI已真实显示断线。evidence_001 保留该迭代。
4. `gui_integration_002.xml` 4 passed。补充明确 Project 绑定拒绝和无应答 IPC 的 Tk 响应证据后，最终 `gui_integration_003.xml` **5 passed**。

没有删除/弱化旧断言或跳过关键场景。仅给静态依赖测试的新只读 progress_log 增加 fstat 许可，原进程创建允许列表不扩大。

## 范围限制

通过的是 Windows 当前承载环境中的真实 Python/Tk 进程关闭与重开。不是仅窗口隐藏、函数返回或 mock。正常桌面点击入口已经提供，但没有将用户桌面 VBS 宿主、终端关闭、注销、重启或完整 Windows Job 层级宣称为通过。真实 Abaqus、跨 Project 资源互斥、完整进程树、真实授权及人类批准均不在本轮验收范围。
