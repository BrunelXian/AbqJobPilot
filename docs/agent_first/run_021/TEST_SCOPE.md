# Run021 — 实际选集与副作用审查

本轮没有应用代码修改。主要新增是准备脚本、两个只读准入缺口测试和文档。自动审批拒绝的控制补丁未写入；不将既有测试通过当作该补丁已验收。

登记环境LangChainEnv，绝对解释器 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，实测Python3.12.10、pytest9.1.0、Tk8.6；无安装/升级。

## 主选集

实际执行列表：本目录test_readiness_boundaries.py；tests下test_product_project、test_product_windows、test_service_lifecycle、test_lifecycle_boundaries、test_service_attachment、test_attachment_gui、test_project_view、test_execution_contract、test_execution_store、test_execution_ownership、test_execution_isolation、test_fake_supervisor、test_process_contract、test_public_workflow、test_execution_gui、test_managed_scope、test_standard_managed、test_standard_managed_windows、test_standard_backend、test_standard_admission。

临时根 `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run021_regression_001`；PYTEST_DISABLE_PLUGIN_AUTOLOAD=1、-B、-p no:cacheprovider，显式basetemp到该根/cases。RUN020_EVIDENCE_DIR与RUN016_EVIDENCE_DIR指向本轮windows_product、windows_standard_substitute目录。

## 已审查的具体边界

- Product unit: Popen和Path.home陷阱；所有create/open/copy/tamper只在tmp_path。
- 产品Windows：正常run_gui.main与原UI按钮驱动，GUI/venv/owner/worker保留OS身份句柄；可信harness单独登记固定ProcessFixture，不是普通New创建授权；结束释放自己的测试屏障并空闲Stop。
- 服务启动/所有权/IPC：ProcessHarness固定Python，显式Runtime/Recent；故障终止仅测试创建且核验的对象；无进程名批量kill。
- Standard unit/admission：Popen/run等被阻断，StandardConfig验证和实际创建由标记的测试替身替换；模拟REAL_FIXED_STANDARD记录只存在无法执行真实入口的隔离配置，不是待审Project的可消费真实许可。
- Standard Windows：run016_process.py仅把ManagedScope.create_standard的目标换成固定run013_process.py worker，保留真实JOB_LIST创建、原Supervisor/Store/Backend事务；audit hook只准登记Python及固定夹具路径，禁止真实入口/无管理fallback。
- DAT来自Dev已有ORIGINAL_DAT.bin离线样本，写入替身新输出并明确历史来源，不能当候选已经求解。没有ODB读取或Abaqus Python。
- Legacy GUI另起干净测试进程，替换Path.home与Runtime，显式Recent；外部启动哨兵和写路径哨兵。避免legacy导入污染AF隔离断言。

未执行真实Abaqus、真实Grant登记到待审实例、产品Standard组合执行（尚未接入）、注销/关机、跨主机迁移、生产数据库和无关全部legacy测试。没有将历史Run016存储/owner/GUI作为测试对象。

## 准备迭代

第一次prepare_materials.py成功通过公共核心建立空Project，但公开离线prepare要求目录参数为str，脚本传了Path，得到UNSUPPORTED_PATH。没有启动服务、许可或Run。记录已创建的唯一目录后，仅改脚本参数为str，复用同一空Project并逐字节检查既有输入；未重建Project/改变Job/放宽检查。第二次离线预览成功。原执行核心及所有旧断言保持。

最终用例数量、失败/跳过迭代和清理在TEST_RESULTS.json、FINAL_SUMMARY.md列明；XML和console保留原始结果。
