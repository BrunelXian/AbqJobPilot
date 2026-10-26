# RC-F02 综合安全回归与部署证据

**808个唯一用例 PASS，最终FAIL=0、SKIP=0；875条JUnit执行记录。** 按classname::name含参数去重；首次失败、支持快照纠正和复验均保留。另有2套解释器的真实VBS正常启动/退出和3条VBS拒绝路径，不额外包装为JUnit用例数。详见TEST_RESULTS.json、FIRST_FAILURES.md、test_results/SEQUENCE_FINAL.json和PACKAGE_SEQUENCE_FINAL.json。

本轮不是重新声称RC-F01的1081项全量已运行。选集覆盖部署新增风险及用户指定安全契约；未重复不相关旧界面/其他纯功能用例。最终114文件产品字节与RC-F01逐一相同，只有可选图标不再分发。F01既有全量结果是历史证据，不能加入本轮统计。

## 执行范围

- 构建/图标11、启动器11、凭据生成/导出4；路径白名单、正文变化拒绝、可重复构建、可选图标缺失/损坏回退。
- 核心458、产品127、恢复84、隔离9、语义6、MCP11、Legacy59及单独Tk用例；覆盖Project/认证/所有权、Grant/单次派发/幂等、Managed Scope/收尾、PAUSED/UNKNOWN/行政隔离、CR-D02/03、CP936/DAT离线验证。不同批次有重叠，不能把批次总和当唯一数。
- GUI排序/筛选/选择、实际双日志、原生Windows关闭/后台存活/重连、English/中文及法德Preview显示、CLI已有能力、13项确定性合成fixture。
- 实际最终ZIP解压到含空格目录，移动新运行副本后从不同cwd验收。基础Python：产品9、原生3、空态/中英各1、启动器11；注册环境：CLI3、MCP11及最终服务生命周期7。IMPORTS.json证明产品模块来自解压包；综合选集使用同字节源码快照，不借用Dev未打包模块。

两个测试支持守卫初次取自旧快照的错误已纠正；最终support与当前tests源码仅允许Git行尾差异，最终身份在TEST_INPUTS_FINAL.json。新构建器的空路径段错误也已修复。没有为通过测试改变ExecutionService、Solver授权、Schema或恢复状态机。

## 真实Windows证据（同机，不是干净VM）

环境：Windows11家庭版10.0.26300，同一用户。LangChainEnv与基础Python312均为CPython3.12.10 x64；基础环境没有安装依赖，测试父控制器只读借用现有pytest目录，产品owner仍以隔离参数启动。正常VBS另在没有测试PYTHONPATH的环境验证。MCP2.3.0只在已安装的注册环境验证。

基础Python产品Project为 `p_4bd037df05fb4aa4b29851f1264039c2`；独立原生监控测试Run为 `r_9f5ab7dce8324d84a99b69f541d3998e`。这是不同的隔离测试上下文，不能合成单次实验。

WINDOWS_base_EVIDENCE.json记录产品worker跨GUI退出：原owner和worker身份匹配且存活，日志cursor由4增长到5；重开连接原身份。结束维度分别为FINISHED、COMMITTED_EMPTY_SCOPE、Artifact VALID、exit VERIFICATION VERIFIED、Solver NOT_RUN。空Project明确停服和重启后PAUSED保持。原生Run诊断/Preview保持只读hash；截图位于screenshots_base，含1600×900、1366×768、Agent Command。两套真实VBS的WSH/GUI/启动链身份及全部退出码0另保存在qualification/vbs_*/VBS_EVIDENCE.json。

## 清理与边界

本轮34个新测试根、897个记录的Python身份当前匹配存活为0；测试各自还有wait/join/保留句柄退出断言。审计只对这些新根的精确私有文件收尾：173个临时凭据文件移除，敏感残留对象0，已知新凭据在日志/JUnit中匹配0。无目录递归清理，无用户进程批量终止。两个正常VBS另有精确进程链退出及句柄关闭证据，3个错误WSH也正常退出。见NEW_TEST_CLEANUP.json。

现在PID未匹配不被提升为历史成员全集证明。没有使用历史凭据认证/解密、没有访问Stable、生产Project或历史owner。Abaqus调用0，旧测试目录和旧ZIP不变。

## 干净环境18项矩阵

| 项目 | 本轮同机最终包/对应源码 | 干净Win11 guest |
|---|---|---|
| 解压/完整性/移动/变更cwd | PASS：114项SHA | NOT_TESTED |
| Python/依赖与无解释器错误 | PASS：两环境及WSH拒绝 | NOT_TESTED |
| Cockpit/Classic双向切换 | PASS：原生GUI | NOT_TESTED |
| English/中文及fr/de Preview | PASS：显示层 | NOT_TESTED |
| New/Open/空Project PAUSED | PASS | NOT_TESTED |
| 明确唯一TEST服务、GUI/Python认证 | PASS | NOT_TESTED |
| worker/收尾/槽位 | PASS：固定Python | NOT_TESTED |
| GUI全退出、存活、重连 | PASS：OS身份和日志 | NOT_TESTED |
| 停服/重启PAUSED | PASS | NOT_TESTED |
| CR诊断/Preview只读及越权阻断 | PASS | NOT_TESTED |
| CLI/MCP既有格式/只读预览范围 | PASS；不等同新服务执行API | NOT_TESTED |
| 禁止未授权Solver | PASS：trap/授权负例；宿主并非无Abaqus干净机 | NOT_TESTED |

18条用户要求在此按关联项合并，全部guest实测仍为空。其他用户、VM/主机、系统级DPI、多显示器、注销/重启、真实Abaqus新宿主、ODB内容均未执行。CI YAML/支持脚本AST通过，本轮未触发GitHub Actions或修改仓库保护。
