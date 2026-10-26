# Run024 — 本地化与原生视觉验收

四个 catalog 各 **149 个资源键**，键集合和参数占位符一致（LOCALIZATION_COVERAGE.json，native_case_2～5）。English 为新用户默认；已保存用户 locale 保留。法语/德语标注 Preview，**母语审校未完成**。没有将“字典齐全”声称为所有 Classic/高级工具/错误码的全产品翻译完成。

## 实现规则

- 集中在 `abqjobpilot/locales/{en,zh-CN,fr-FR,de-DE}.json`，通过 `translate(locale,key,**values)` 获取。
- locale 不支持、非英文资源损坏或缺键回退 English；完全未知键返回有界的 DISPLAY_MESSAGE_UNAVAILABLE 文本，不向用户暴露资源键。参数缺失显示 DISPLAY_PARAMETER_MISSING。
- 原始 API key/code、工程路径、ID、数值单位、回执和证据 JSON 不翻译、不修改。Recovery 的核心原因和分类保留机器原码，外层标签/警告/说明本地化。
- 本轮新导航、向导、Service 说明/确认、空态、Evidence/Recovery 标签、Settings 均纳入目录。服务端状态/诊断错误码仍可见以便追溯。
- Classic 工具复用原 en/zh；切换法德时 Classic 明确回退英文。它不是新增的一套独立翻译状态。
- 旧源码 Classic 的 `lang='en'` 没有既有持久 locale 读取，未从旧 Runtime/Recent 猜测偏好或迁移工程设置。新显示偏好是用户级有界文件，不含凭据/执行字段。

## 实际视觉检查

截图来自测试自己创建的原生 HWND（Win32 PrintWindow），不是 Run023 HTML，不包含真实工程或历史 owner。

- 四语言逐页切换：9个工作区及 New Project 向导，保存全部临时截图；仓库选择保存 Overview、Agent、Service、Settings、Wizard、1024×768 窄窗。
- 1366×900 默认检查；实际 Windows 运行监控截图另使用默认窗口尺寸。Tk 本地 scaling 100%/125%/150% 的德语按钮/导航边界断言分别通过，没有修改 Windows 全局 DPI。
- 德语长按钮与项目向导、法语重音与窄窗滚动、中文文本、Classic 队列左右结构和反向入口已查看。
- 首次视觉检查发现 Abaqus 类型的临时 StringVar 生命周期问题，修正为持久控件 current(0)，新增断言。语言切换后空日志提示也更新；系统采样显示单独一行，避免窄窗挤占。
- 长日志是有界原始文本，保留水平滚动；详情使用可滚动摘要/JSON。未进行屏幕阅读器完整审校、全键盘覆盖或跨显示器 Per-Monitor DPI 验收。

## 审阅图

- [真实固定Python运行监控](screenshots/running.png)
- [原生Classic双向入口](screenshots/classic_connected.png)
- [返回Execution Workspace](screenshots/execution_return.png)
- [德语向导](screenshots/de-DE_wizard.png)
- [法语窄窗](screenshots/fr-FR_narrow.png)
- [中文空态](screenshots/zh-CN_overview.png)
- [English Agent Access](screenshots/en_agent.png)
- [English Service](screenshots/en_service.png)

完整路径及 SHA-256 见 WINDOWS_EVIDENCE_INDEX.json。原生截图呈现本轮测试状态，不作为真实 Abaqus 结果证据。
