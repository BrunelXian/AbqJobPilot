# 测试、证据及剩余范围

## 口径与隔离

使用登记绝对解释器 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe -B`，Python3.12.10、Tk8.6、pytest9.1.0。未安装依赖。复用并适配 Run024 已审查的 run_safe_tests.py：每批创建新 AbqJobPilot_Run024R_* 根，独立 HOME/USERPROFILE/TEMP/TMP/Recent/Project/Runtime、禁用插件自动装载及 pycache；审计钩子拒绝默认 Runtime 写入和真实 Abaqus 入口。受限 Standard 测试使用既有受控替身；GUI 监控进程禁止 sqlite3.connect/Popen/执行能力导入，IPC 操作限定公共只读集合。

|范围|唯一用例|结果|
|---|---:|---|
|Execution / ownership / process / managed scope / Standard替身 / closeout / pair|458|PASS|
|Project / authenticated attachment / IPC / service lifecycle / product control|127|PASS|
|CR-D02/D03 interruption与Recovery授权/事务/预览|84|PASS|
|Classic/legacy Project/table/API格式兼容|59|PASS|
|执行隔离|9|PASS|
|MCP只读|11|PASS|
|原生窗口单位测试（含4语言、3缩放）|12|PASS|
|新增Cockpit控件/排序/旧快照拒绝|3|PASS|
|实际Windows退出/重开、恢复只读、Project切换|3|PASS|
|两条实际Python Run选择/双日志|1|PASS|
|原生4语言、Wizard、Classic截图|1|PASS|
|合计|768|0 FAIL / 0 SKIP|

原始执行793次，按JUnit classname+name去重，取同用例最后结果；TEST_RESULTS.json保留每批及全部唯一身份。没有失败用例被删除或以SKIP掩盖。

复现示例：`& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs/agent_first/run_024r/integration_001/run_safe_tests.py native_windows new_review_batch`。批次名必须未存在，避免覆盖证据。native单位用例各在独立解释器运行，避免既有多Tk根退出回调干扰；具体选择见各XML。

## 实际风险验收

A：空窗口无默认Runtime/服务；同根Classic双向切换保持原Runner/过滤/选择及queue文件摘要；明确Project向导无自动进程。B：公共客户端先提交受限Python任务，正常主GUI连接、双表选择，真实OS句柄证明整窗及venv启动器退出，owner/worker继续且日志增长；重开原回执、一次创建；读取期间执行存储摘要不变。C：Preview与诊断相同核心结果、Apply不在普通IPC允许表；UNKNOWN/PAUSED不因读取改变；Project切换及服务失联缓存有实际记录。

两任务联动的历史Run `r_6248aac3ed5f49b295d3bd87b1ddb22f` 与运行Run `r_2d7e95ad0a3e45978ff12ec6f2dcaa41`，Results选历史后没有WAITING日志，快速切回后无历史身份混入；见 evidence/SELECTION_EVIDENCE.json。

生命周期：evidence/NATIVE_EVIDENCE.json；Project切换/失联：SWITCH_EVIDENCE.json；只读恢复和版本/状态不变：RECOVERY_IPC.json。普通GUI测试不允许Backend调用；故障回归中仅终止新建、持有身份句柄的夹具owner，不终止用户进程。历史owner未参与测试。

## 迭代记录

自动测试首轮即通过。人工截图复核发现三项问题并在最终相应用例重测：
1. 旧整窗PrintWindow捕获在缩放后有局部重绘残影，改为原生客户区捕获并处理待绘事件；未修图或生成图片。
2. Agent Command的Close缺资源键、长Notebook标签压缩抽屉；补齐四语言Close，并改为紧凑Inspector下拉选择，不改权限。
3. 最初Tk缩放在控件构建后设置，125/150截图相同，不能证明字号变化；改在构建前设置并重新捕获。最终三份图摘要不同，记录真实OS DPI96。该测试不等同于系统级125/150显示设置或跨屏DPI切换。

目录归档时曾将同名 `private/lifecycle.json` 误识别为退出记录；识别为加密凭据容器后从交付清理汇总排除。交付不包含该密文、连接秘密或Project数据库。测试根保留情况如下。

## 收尾和限制

CLEANUP_BEFORE.json保存45个本轮根、实际生命周期记录和GUI退出记录；215条夹具/客户端身份记录均有退出事实（包括故障注入的非零退出），41份GUI退出记录。临时private-process/bootstrap/gui-private-connection交接文件残留0。它们不是历史真实Run的收尾证明。

目录递归清理被自动审批以 `blocked by policy` 拒绝，未改用其他命令绕过；测试根与其中加密本机Project绑定仍保留，详见CLEANUP_RESULT.json。不要提交这些临时数据。报告、截图及原Run024R/精修证据保留。

尚待用户实际GUI视觉/操作验收；真实Abaqus、生产恢复、历史owner、真实系统125/150 DPI与多屏移动、Windows注销/重启没有执行。法德继续Preview，Classic仍沿用中英文。未扩大CLI/MCP写能力或真实执行权限。
