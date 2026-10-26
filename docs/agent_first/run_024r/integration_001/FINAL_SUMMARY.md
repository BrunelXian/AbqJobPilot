# Run024R Integration — Compact Engineering Cockpit

状态：**PASS_ABQJOBPILOT_RUN024R_COMPACT_COCKPIT_INTEGRATED**。

正常 Dev GUI 已采用批准的 B 布局，已完成真实隔离 Python ProcessFixture、公共 IPC、Windows GUI 完整退出与重连验收。此状态不是用户最终视觉验收，也不是 0.3.0 发布批准。

## 使用与审阅

正常入口：[Open_Dev_GUI.vbs](../../../../Open_Dev_GUI.vbs)。先 New/Open Project，再在 Agent Command → Project & Service 明确连接或启动。打开窗口及切换页面不启动服务或任务。

- [1600×900 实际产品窗口](screenshots/cockpit_1600x900.png)
- [1366×768 实际产品窗口](screenshots/cockpit_1366x768.png)
- [Agent Command 展开](screenshots/agent_command.png)
- [两项实际 TEST Run 选择联动](screenshots/selection_linked.png)
- [Classic Queue 原生嵌入](screenshots/classic_connected.png)
- [实现与操作契约](IMPLEMENTATION_AND_USAGE.md)
- [验收及限制](TEST_AND_ACCEPTANCE.md)

截图为未缩放的原生 HWND 客户区 PNG；来源、尺寸、摘要见 SCREENSHOT_MANIFEST.json。测试运行时的 Project/Run 是实际隔离服务数据，不是原型模拟值。新窗口不会自动打开这些测试实例。

## 实测结论

768 个唯一测试最终 PASS，FAIL=0、SKIP=0；累计执行 793 次，重复项不叠加计数。详见 TEST_RESULTS.json 与各批次 XML。

最终 Windows 生命周期 Run：`r_2383a65a164a486eb0b728ae5d85ee5f`；回执 `req_0c2130840a11474eb217f5d28c4d92db`。GUI PID 1052 与专属 venv 启动器 PID 26664 均以保留 Windows 句柄取得 exit=0。原 owner PID 16408、worker PID 9496 的创建时间匹配，GUI 退出后日志继续增加；重开连接原 owner、Run、回执，只有一次该任务启动。完整身份及源证据见 evidence/NATIVE_EVIDENCE.json。

该 Python Run 最终 FINISHED、COMMITTED_EMPTY_SCOPE、Artifact VALID；Solver NOT_RUN。不能把它称为 Abaqus 求解成功。另一项测试切换两条实际 Run，验证历史与运行记录的双日志、摘要及证据不串行。

## 保护及剩余事项

- Develop / HEAD `9553755a24ff521dd2ac694ea39cab5a03f88466`、版本 0.3.0.dev0 保持。执行核心、Supervisor、授权、恢复 Apply、Project 格式未改；历史材料及原 A/B、精修原型保留，见 PRESERVATION.json。
- 本轮 Abaqus 调用 0；真实恢复 0；未访问 Stable、操作历史 owner、修改共享环境、提交或推送。
- Windows 实际窗口 DPI 为 96；125%/150% 是构建控件前设置的本进程 Tk 字体缩放测试。实际系统 DPI 切换、多屏移动仍未验收，不作等价声明。
- 法语、德语保持 Preview；Classic 沿用中英文。部分专业 API 码保留原文。
- 列表为当前客户端命名空间的每页最多 32 条；排序/筛选只作用于本页。STA/Text 展示服务已提供的有界 progress，不新增对任意工程文件的直接读取。
- 本轮测试夹具的正常退出和故障注入退出均按自身身份记录。临时连接交接文件已清除；45 个测试根目录，递归清理曾遭自动审批拒绝，原始原因 `blocked by policy`，未尝试绕过。隔离 Project 数据及加密本机测试绑定仍留在这些目录，不得打包入 Git。见 CLEANUP_BEFORE.json、CLEANUP_RESULT.json。

完成后停止，等待用户对实际 Dev GUI 的视觉和操作确认。未进入下一轮、未发布。
