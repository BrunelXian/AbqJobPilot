# Run020 — 验收与实际测试

解释器：`D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python3.12.10、pytest9.1.0、Tk8.6；Windows11 NT10.0.26300。未安装/调整依赖。GUI采用相同venv的pythonw.exe，执行正常`run_gui.main()`；测试只替代文件对话框答案、触发实际按钮和WM_CLOSE，不替代GUI业务方法。

## 场景逐项证据

| 场景 | 实际测试与证据 | 结果 |
|---|---|---|
| A 新建 | `test_gui_new_empty_product_start_reopen_independent_client_stop`；实际New按钮，新目录、显示名/Project ID、0Plan/Grant/Run、NOT_RUNNING、PAUSED；重复目录不覆盖 | PASS |
| B GUI启动/重连 | 同测试：Start按钮、第二独立客户端start复用owner、GUI及venv完整exit0后owner仍活；重开认证同Project；Stop后显式重启为新owner且PAUSED | PASS |
| C 固定Python | `test_fixed_worker_product_gui_chain_and_secret_free_reports`；独立client提交，GUI选Run，真实worker，正常关闭GUI/venv后保留句柄确认owner/worker活着且进度增长，重开原Run/回执，同请求重放 | PASS |
| C 自动收尾/验证 | 上述Run只有一个START_INTENT，最终FINISHED、COMMITTED_EMPTY_SCOPE、Artifact VALID、Solver NOT_RUN；GUI分别展示；未调用Abaqus | PASS |
| D 停服 | 产品活跃Run拒绝SERVICE_NOT_IDLE；空ProjectGUI正常Stop和明确重启PAUSED；原Run019故障/UNKNOWN/丢应答/停服事务回归 | PASS |
| E 错Project/凭据 | `test_product_credentials_wrong_context_copies_and_connection_permission`、4项`test_encrypted_handoff_fail_closed_no_second_owner`；密文中错误凭据/原端点/协议/Project以及明文降级拒绝，不创建第二owner | PASS |
| E 副本/格式 | `test_format_and_copy_boundaries` 8参数：普通目录、Legacy、future、损坏、缺DB、journal、移动、副本均不自动修复/迁移；inner目录也不能绕过未完成发布 | PASS |
| E 主机/用户保护 | `test_windows_dpapi_binding_tamper_and_plaintext_downgrade`；实际DPAPI同用户解密、篡改拒绝、错误host/user绑定注入拒绝；`test_private_acl_restricted_from_creation`读取真实Windows DACL | PASS（跨用户/跨主机未实测） |
| E 双Project | `test_two_product_gui_switch_and_pause_remain_isolated`：两个产品Project的GUI身份/缓存分开，均PAUSED；原Run018 UNKNOWN切换回归 | PASS |
| E 无秘密导出 | GUI遥测和同份diagnose导出无IPC/operator秘密；收尾工具扫描本轮报告无已取得秘密值 | PASS |
| 独立Python | `test_public_readonly_example_in_non_repository_cwd`运行普通`product_inspect.py`；另独立API进程start/query/submit/disconnect，无SQL、测试模块或授权工厂 | PASS |
| 原子性/失败 | 新建并发只一方成功；配置/发布故障保留INCOMPLETE；重复创建拒绝，路径越界/重解析/无效名不写入；纯创建组设置Popen/默认home失败哨兵 | PASS |

最新Windows证据在 `windows_verified/`：empty_gui_product.json、fixed_worker_product.json、public_example.json、product_gui.png。早期windows_04/windows_final/windows_final_chain/windows_ui_final记录保留，不能视为新测试次数。业务状态与测试控制器观察在JSON中分开；正常关闭时的GUI/venv退出为保留Windows句柄所得，不是PID消失推断。

测试可信权限设置仅用于固定Python：在创建方初始租约内确认原创建结果空/PAUSED，再由现有test issuer和管理事务准备受限计划、TEST_ONLY Grant及显式resume。普通GUI和独立client没有这个钩子。没有借打开Project、启动owner或重连恢复派发。

## 结果和去重

主回归 `final.xml` **303 PASS，0 FAIL/SKIP，381.08秒**。新增普通只读示例和owner启动器句柄收尾后，`chain_final.xml` **9 PASS**。最终补齐“服务尚未启动时显示Project ID”后，`ui_final.xml`运行全部新风险与原GUI相关回归；修正测试屏障后的 `verified.xml` **13 PASS，51.44秒**。Legacy独立选集首次14PASS/1SKIP，跳过的原GUI用例在干净进程中1PASS；不修改原断言。

按**classname + 参数化test name**去重，采用最后实际结果，最终 **319个唯一用例PASS，0最终FAIL/SKIP**：276项原核心/产品链回归、28项本轮新增、15项Legacy/格式边界。`TEST_RESULTS.json`包含全部批次、唯一ID和结果；重复迭代不累加为成果。

主选集明确包含：test_product_project、test_product_windows、test_service_lifecycle、test_lifecycle_boundaries、test_service_attachment、test_attachment_gui、test_project_view、test_execution_contract/store/ownership/isolation、test_fake_supervisor、test_process_contract、test_public_workflow、test_execution_gui、test_managed_scope、test_standard_managed、test_standard_managed_windows。

先审查了副作用：Fake组保留启动陷阱；进程组仅固定Python和身份绑定清理；Standard组的真实创建接缝被受控替身替换，无非受管fallback；历史DAT仅离线样本。Legacy包装设独立home/Runtime/Recent、禁外部进程和默认Runtime。未机械运行无关GUI全套、算法、真实Solver、ODB或生产迁移测试。

实际命令使用绝对解释器、`-B -m pytest -p no:cacheprovider`、`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`和专属TEMP/TMP/basetemp。前几轮允许pytest缓存但也明确放在本轮独立临时根。完整stdout与JUnit保留。

## 失败迭代（原证据保留）

1. 首个受管沙箱smoke在其临时目录下创建子目录收到WinError5，未启动任何进程。随后按授权申请原Windows用户上下文测试，自动审批通过；未绕过拒绝或修改系统策略。
2. unit_01：18PASS/1FAIL。Popen失败哨兵设为函数后，测试导入unittest.mock引入asyncio尝试继承Popen导致TypeError。改用既有monkeypatch，保持启动哨兵。
3. windows_01：20PASS/2FAIL。测试审计比较Windows反斜杠路径与SQLite file URI误拒绝；另一次原子遥测文件替换读竞争。修正测试URI规范化与有界读取等待，无业务放宽。
4. windows_02/03各2PASS/1FAIL。自动化在重新选择Project后误读前一代遥测，向已清空Treeview选择旧item。最终使用GUI选择代数的确定屏障；旧断言保留。
5. windows_04：3PASS；主回归303PASS；chain_final9PASS。原Legacy组1SKIP为`invalid command name tcl_findLibrary`，干净进程原用例通过。
6. 最终审查补充空Project在服务启动前显示已核验ID；ui_final为31PASS/1FAIL，失败是原Run018测试驱动同类旧遥测竞争（Treeview item not found）。给原Run018/019测试动作确认添加选择代数，公共测试helper等待对应代数再选择Run；不改产品状态机、不删除业务断言。随后运行verified相关GUI组复核。

真实GUI进程、生命周期与固定worker已实测；路径重解析位负向、磁盘/提交失败、错宿主绑定等是明确的模拟注入。没有用它们冒充另一个Windows用户/机器或真实Abaqus链的实测。

## 清理与历史保护

本轮只处理列明的Run020临时根。测试在成功路径正常退出GUI、释放自己的固定夹具屏障并安全空闲停服，持有的身份句柄记录退出。失败驱动若需终止，只作用于本轮已持有且核验的GUI句柄；不按名称杀进程。

`CLEANUP_FINAL.json`记录第一次后查396条身份无匹配存活、删除92份本轮私有材料、报告秘密命中0；`CLEANUP_UI_FINAL.json`最终汇总518条记录身份、匹配存活0、另删除30份补测私有材料、报告秘密命中0。`CLEANUP_VERIFICATION_FINAL.json`再次确认11个明确临时根内相应私有材料剩余0。后查“未找到身份”不补造历史退出证据。windows_verified下三个cleanup副本保留owner/venv/worker正常退出及句柄关闭。清理不删除DB/Run/事件/输出，也不递归删除目录。

`FINAL_INTEGRITY.json`对开始时1235份既有文件逐一比较：只有本轮明确修改的10条既有路径变化，无文件丢失。包括3条原GUI测试驱动/确认helper的确定性屏障修正。Run016实时view在基线即单列排除；没有查询、停止、重启或接管历史owner，也未修改冻结包/实验记录。版本仍0.3.0.dev0，Develop与HEAD不变，无Git写操作、Stable或生产Project接触。
