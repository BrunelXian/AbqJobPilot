# 设计验收、复现与保护记录

## 本轮实际验证

这是一轮设计交付，没有应用源码改动，因此没有重跑Supervisor、Solver替身或历史664项回归。Run022历史结果用于理解已成立边界，**不能算本轮结果**。

| 检查 | 实际范围 | 最终结果 |
|---|---|---|
| 标准库设计检查 | 四语言键集合、非空/重复、命名参数一致、HTML嵌入、静态翻译键、默认English、无网络请求/真实命令、文档相对链接 | 10个测试PASS，0FAIL/ERROR/SKIP；DESIGN_CHECKS.json |
| 浏览器原型检查 | 14场景/语言渲染、四语言向导、导航、Tab、键盘分隔、德语1100宽、四语言Service按钮、Classic日志/结果隔离 | 78个命名断言PASS；design/QA_RESULTS.json。是浏览器断言数，不是78个应用测试 |
| 可视检查 | 首次空态、Overview、Runs、Classic、Service、法语向导、德语Overview/窄窗等实际PNG | 阅读截图后修正了Classic混用示例来源、空态日志与未选Project服务语义；最终截图在design/screenshots |
| 历史保护 | git非忽略原有1462个文件逐字节SHA-256、分支/HEAD/冲突 | 无变化、无丢失；新增均在run_023，PRESERVATION_CHECK.json |

HTML原型用当前安装Chrome无头模式，独立临时profile/cache。沒有启动AbqJobPilot GUI、Supervisor、worker或任何Abaqus；没有连接历史Project、读取其外部实验目录或操作owner。所审真实GUI截图是Dev文档内保存的Run020截图，不是新采集。

## 失败迭代与清理

第一轮渲染前失败：工具包Playwright默认期待的 `chromium_headless_shell-1234` 可执行文件不存在，错误 `browserType.launch: Executable doesn't exist`。未创建浏览器、更未运行应用。没有按提示下载/安装；改为显式使用已存在 `C:\Program Files\Google\Chrome\Application\chrome.exe`，复用原工具包API。

初版渲染72断言通过；人工视觉审阅发现设计中的Classic结果/日志错误复用了产品示例，以及未选Project显示Not running过早下结论。已修改**本目录原型**：Classic独立样例、原始Classic状态，无DAT已验证宣称；未选Project显示No project selected；空日志折叠。增加6项来源隔离/Service长文检查，最终78断言通过。没有修改应用、历史测试断言或执行证据。

每次成功渲染通过 `browser.close()` 关闭本次独立无头浏览器，记录disconnected=true；新临时profile/cache清理仅限该次 `design/.render-temp-*` 的已解析绝对路径。第一次失败留下的空目录 `.render-temp-mJgWN4` 核对完全为空后单独删除。没有按进程名终止，也没有删除任何既有测试、Project、输出或凭据。外部网页请求数0；原型CSP禁止connect/form提交，无fetch/XHR/IPC。

## 准确复现命令

在Dev目录内，以下命令本轮实际执行过。它们仅生成/检查本目录设计文件；浏览器工具路径属于本机开发QA，不是产品运行依赖或通用部署方案。

```powershell
Set-Location -LiteralPath 'D:\Projects\abqjobpilot_dev'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs/agent_first/run_023/design/build.py
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs/agent_first/run_023/verify_design.py
& 'C:\Users\wuxia\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' docs/agent_first/run_023/design/qa.cjs
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B docs/agent_first/run_023/audit.py verify
```

浏览设计只需打开 `design/index.html`，不需要Python、Node、服务、Project凭据或网络。原型没有运行时依赖。

## 需求验收矩阵

| 项目 | 交付依据 | 结论 |
|---|---|---|
| 现状/入口/基线 | GUI_AUDIT与BASELINE，根AGENTS/环境核验 | 完成源码与历史截图审查 |
| 八工作区+独立Service | NAVIGATION_AND_CONTRACT、HTML侧栏 | 设计完成，非已实现Tk |
| 双向导航及缺陷根因 | ExecutionView.legacy/main/Classic构造审查、原型各页面互达 | 已定位，最小修复方案待确认实施 |
| Project命名/仅Abaqus/格式兼容 | New两步向导、命名/分类表 | 设计完成，无schema改变 |
| 四主设计组 | 01空态、02Overview、03Runs、04Classic | 具备PNG和可交互HTML |
| 向导/Service/Agent/Settings | 独立页面与四语言向导PNG | 设计完成，所有按钮不执行业务 |
| 多语言默认/资源/长文本 | 4×110键、占位符测试、法德长文截图 | 子集资源完成；法德母语审校和全产品翻译待实施 |
| 状态/日志/时效/布局 | 分维度示例、断线/UNKNOWN/完成场景、可调分隔 | 设计完成；Tk高DPI/无障碍待实际实现后验收 |
| 组件复用/下一步 | LAYOUT_AND_COMPONENTS、IMPLEMENTATION_PLAN | 复用Tk与现有公共接口，未扩执行权限 |
| 历史/核心保护/停止 | PRESERVATION_CHECK、实际Git状态 | 原文件保留，Abaqus0，未触碰Stable，无Git写操作 |

## 本轮未验收

实际统一Tk窗口、Classic适配重构、真实Windows GUI关闭/重连、全语言翻译、Windows高DPI与辅助功能、偏好持久化均尚未实施。浏览器原型不证明这些已通过。设计审阅完成状态不意味着用户已经确认视觉方向或批准Run024开发。
