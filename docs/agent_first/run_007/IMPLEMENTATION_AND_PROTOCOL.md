# Run 007 — 实现与复现

## 实际调用链

可信harness固定计划/测试执行授权 → 原submit接受事务 → 原worker领取slot/START_INTENT → ProcessBackend固定OS启动与身份核验 → PROCESS_IDENTITIES（含完整成员依据） → 四次真实句柄退出观察与独立process_observe提交 → process:after_exit屏障 → PROCESS_COMPLETED → 原独立Artifact validator → 原terminal事务。

本轮真实故障验收在process:after_exit屏障结束owner：退出事实已经分别提交，集合终态和Artifact验证尚未执行。重启仍PAUSED、slot仍占用。控制器保留的句柄及启动登记只作独立核对，不回填服务。

preview_process_reconciliation → 新process_reconciliation.inspect，显式只读BEGIN；apply_process_reconciliation → 原reconciliation.manage → 原授权/幂等/management事务 → 新apply_recorded。没有新的调度器、队列、数据库、观察器或Backend。

原PROCESS_EXIT_OBSERVED事件就是不可覆盖的退出观察账本。新增的Run投影可查询，但只有与完整历史一致才具资格；单独改投影不会产生资格。PROCESS_RECONCILIATION_APPLIED的时间是本次决定时间，不伪造过去的PROCESS_COMPLETED或验证事件。

## 两个新增RPC

沿用原协议版本、127.0.0.1 TCP、4字节长度分帧、64KiB请求/256KiB响应、2秒IO截止、最多8连接，既有credential和Project/context/当前endpoint owner握手不变。

```text
preview_process_reconciliation { run_id }
apply_process_reconciliation { request }
```

request必须且只能含：contract_version=af-management-v1、operation=reconcile_recorded_process_exits、project_id、project_instance_id、owner_id、management_grant_id、idempotency_key，加[契约](CONTRACT.md)规定的全部scope。没有OS探测、文件路径、command、target_state或批准字段。客户端调用是薄包装；lost response为ACCEPTANCE_UNKNOWN，使用原动作/原key查询management_receipt。

管理授权仍由tests/reconciliation_helpers.FakeManagementFixture通过owner的事务登记。这个历史类名不表示进程授权等同Fake采纳；action和scope严格不同。可信控制通道仍是tests/run003_process.py的受限grant请求文件，由owner执行登记；没有approve/mint RPC，没有绕开活跃owner直接写库。

## 兼容与副作用

旧Fake采纳入口及其验证/快照完全保留，并继续拒绝process Backend。旧submit/claim/消费、客户端断线、每存储单槽、重启默认暂停和resume策略不变。旧R2～R6测试文件不修改。

新Plan在同一实验Schema3增加membership_contract和required_roles；固定Backend仍version1，新证据合同显式版本化。旧实验只读查询仍可用，缺新成员合同的历史Run拒绝本轮收尾，不迁移或补写。新派发不会静默改写旧Plan。

对账新增写入只有原库中的决定/Run/事件/管理回执/消费/slot；没有Artifact IO、新Validation、证据快照或进程启动。未知提交不能用新键盲重试。已成功旧回执跨owner重放只返回历史回执，不转换当前状态或打开门。

## 可复现Windows演示

在Dev根，用登记解释器，每次生成一个全新的临时根；不要把basetemp指向既有证据目录。

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$r7DemoRoot = Join-Path ([IO.Path]::GetTempPath()) ('AbqJobPilot_Run007_demo_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $r7DemoRoot | Out-Null
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B -m pytest -p no:cacheprovider tests/test_recorded_exit_reconciliation.py::test_real_exit_commit_owner_crash_reconcile_and_separate_resume --basetemp="$r7DemoRoot\cases" --junitxml="$r7DemoRoot\results.xml" -q
```

三个场景分别为正常退出、非零退出、故意无效产物。owner在退出已持久化但验证未运行的真实窗口退出；三者Artifact都保持NOT_RUN，不能按场景预期补造VALID/INVALID。每例导出before/after.json，记录reconciliation-evidence.json、physical-launches.json、fixture-lifecycle.json、lifecycle.json和inventory.json。对账后第二个合法Fake任务仍等待，另一次resume授权才执行。

历史VALID/INVALID/UNKNOWN保留测试另调用既有独立validator产生真实判定，并由持锁测试owner显式登记为历史测试夹具；只验证已有Validation的保留，不宣称产品新增了独立验证RPC，也不用于制造任何正向OS退出资格。其退出证据仍来自同一真实owner崩溃路径。
