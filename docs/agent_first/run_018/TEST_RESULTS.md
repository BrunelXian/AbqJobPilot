# Run018 — 实测、失败迭代与清理

## 环境和隔离

已读取实际AGENTS与环境登记。Windows NT10.0.26300、登记LangChainEnv Python3.12.10、pytest9.1.0、Tk8.6。主测试解释器`D:\XianLab\envs\LangChainEnv\Scripts\python.exe`；最终正常GUI子进程使用同环境`pythonw.exe`，实际映像为基础安装Python312的pythonw。未安装或升级依赖。

所有可写测试数据位于新根：
`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run018_eobivebj`

TEMP/TMP、pytest basetemp、进程登记、Project/Runtime/Recent、私有连接和证据目录全部显式设置。使用`-B`、`PYTHONDONTWRITEBYTECODE=1`、`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`、`-p no:cacheprovider`。未读取历史真实实例的连接材料/数据库、未查询或操作其owner。

先审查了所选测试与helper：Fake用`guard_environment`阻断进程/默认目录/legacy；进程harness只允许固定Python夹具，并将所有数据限制在新根。受管Standard回归`run016_process.py`使用受控Python替身和Dev已有历史DAT离线样本，明确禁止真实Abaqus及无管理回退。历史样本不是本轮真实求解证据。GUI只对自己登记的HWND/PID+创建身份发WM_CLOSE；故障终止仅持有的测试句柄。

正常GUI驱动对import、SQLite和进程启动设陷阱，公共client另设只读操作白名单。Legacy回归单独进程运行：先屏蔽仓库旧Runtime探测、显式临时home/Runtime，再收集测试；外部启动和测试根外文件写入为失败。测试默认路径不会误落生产环境。

## 数量与结果

| 批次 | 收集/执行 | 结果 |
|---|---:|---|
| 首次只读列表单元 | 14 | 14 PASS，11.26秒；console记录，后续全覆盖重跑 |
| attach01 | 12 | 11 PASS / 1 FAIL / 0 SKIP，33.81秒 |
| attach02 | 3 | 3 PASS / 0 FAIL / 0 SKIP，22.92秒 |
| 主回归（14个文件） | 246 | 245 PASS / 1 FAIL / 0 SKIP，347.32秒 |
| 独立legacy GUI/格式回归 | 15 | 15 PASS / 0 FAIL / 0 SKIP，7.65秒 |
| 最终新增组（登记pythonw链） | 28 | 28 PASS / 0 FAIL / 0 SKIP，42.57秒 |

共318次case执行，其中XML记录304次，另有首次console14次。按完整`classname::name`去重并取最后结果：**262个唯一case最终全部PASS，0最终FAIL/ERROR/SKIP**。初次一个测试名字从“legacy_directory_and_reparse”更正为“legacy_directory”，同一断言计一个case；不把措辞修正计为额外覆盖。完整ID、批次、耗时及原始失败在`TEST_RESULTS.json`和`test_evidence`。不是首次全绿，也不是重跑所有历史测试。

失败迭代：

1. attach01的切换用例误用了不存在的`fake:after_output`屏障，等待失败。按真实服务改为`dispatch:after_artifact`，补测通过。没有更改被测状态机。
2. 主回归切换用例读取旧view.json后过早对新Project的Run选择，Tk报不存在的item。为测试UI动作增加独立action_id、确认回执和新观察时间等待。最后正常入口组通过；未削弱原身份、只读或退出断言。
3. legacy测试启动前，额外写入审计把pytest默认NUL日志句柄识别为测试根外写入，配置阶段0项执行即拒绝。改为显式临时pytest.log，15项通过。首次INTERNALERROR日志保留；没有放开真实文件写入。

## 精确回归范围

主回归：`test_project_view`、`test_service_attachment`、`test_attachment_gui`、`test_execution_contract`、`test_execution_store`、`test_execution_ownership`、`test_execution_isolation`、`test_fake_supervisor`、`test_process_contract`、`test_public_workflow`、`test_execution_gui`、`test_managed_scope`、`test_standard_managed`、`test_standard_managed_windows`。

Legacy单独：`test_project_gui`、`test_gui_table_state`、`test_g2_task_workspace`、Run017的`test_format_boundaries`。覆盖旧Project切换/Queue/Results、历史窗口、菜单与日志、主要布局/语言/操作及新旧格式互拒。旧GUI类直接构造语义保持，正常入口另走显式AF视图。

未运行无关全量解析、全部旧Runner、旧恢复、其它科研模型及MCP全套；本轮未改它们。真实Abaqus、生产迁移、注销/重启/终端关闭、历史owner升级和自动启动管理不在验收范围。没有因测试数量比历史少宣称退化。

## 真实Windows闭环

最终实际Run：`r_05e74fceda7148f3a1ed223dd8d73818`，原回执`req_01d4f83aaa6546cf81d2fc992d56a726`。

- 独立普通客户端先提交，GUI尚未启动；所有关联标识通过公开接口取得。
- GUI A实际PID30808，专属venv启动器32100：正常WM_CLOSE后，持有的两个OS句柄均证实exit=0。
- 原owner PID15456、worker15384按创建时间/映像核实仍活着，progress继续增长；物理JOB_LIST根启动记录只有一次。
- 正常无参数GUI B实际PID31804、venv24792，连接原Project/Run/回执；独立客户端状态一致。检查期间DB SHA-256完全不变，覆盖Run/revision、消费、事件、gate/slot，不只比较UI文本。
- 可信夹具释放屏障后worker自行完成；`COMMITTED_EMPTY_SCOPE`、Artifact VALID与Solver NOT_RUN分别显示。
- 只对本轮已完成测试owner停服再重启，GUI显示过期缓存后连接新owner，PAUSED保留；GUI本身不执行stop或resume。两个GUI读线程和实际进程均正常结束。

截图及原始身份/创建时间/退出观察在`windows_evidence/normal_gui_lifecycle.json/.png`。Project切换与不确定状态在`project_switch_and_paused_unknown.json`；70项真实接受记录的三页32/32/6及Tk心跳在`large_list.json`。替身时点、OS观察、持久记录分开，不冒充Abaqus验收。

## 清理和保留

`CLEANUP.json`有98个harness inventory、98组（117条）进程生命周期和14组native句柄清理记录，均证实其拥有的进程退出、Recent未变、私有凭据移除；剩余可能私有连接/启动材料文件0。最终新增GUI有mainloop返回、读线程join、实际GUI及venv退出句柄证据。故障测试的强制退出明确记录，不能称所有测试均自然退出。

对本轮新临时根的固定进程登记进行了只读后查：260个唯一身份中259个无法打开原对象、1个PID已不匹配，未发现身份匹配的存活进程。后查不是补造历史退出；历史退出由测试当时的句柄证明。没有全机进程扫描或按名字终止。临时业务库和测试证据保留，不递归删除，也未清理以前被拒绝的目录。

保留核对：基线1135个文件中1125个字节未变，10个为本轮明确修改，未丢失任何基线文件；两个历史GUI实时view文件在开始时已排除。Git还出现历史`run_016/real_001/gui_B/exit.json`新路径；仅记录目录条目，未读取/修改其内容、未推定原因。它不是本轮产物，也不作为本轮清理对象。当前分支/HEAD未变、无冲突。详见FINAL_CHECKS.json。

## 复现入口

本轮实际调用：登记Python `-B -m pytest -q -p no:cacheprovider --basetemp <新根> --junitxml <新根内文件>`，后接以上显式主选文件；最终组为三个新测试文件。旧GUI用`docs/agent_first/run_018/run_legacy_gui_tests.py`，该入口每次新建子根。准确当时根/批次见JSON和日志。重新执行必须建立新证据目录，不能覆盖这里的最终材料；已有测试服务有自己的有限寿命和身份清理，GUI没有执行控制权限。
