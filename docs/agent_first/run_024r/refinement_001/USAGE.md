# 打开精修原型

双击 [Open_Refined_Prototype.vbs](Open_Refined_Prototype.vbs)。它仅用已登记的LangChainEnv运行本目录`refined_cockpit.py`，不会启动正常产品GUI或服务。入口已静态核对；测试通过同环境python.exe执行。父目录原型需要保留，当前程序复用其构图和四语言资源。

## 原始比例截图

- [1600×900客户区](screenshots/refined_1600_client.png)
- [1366×768客户区](screenshots/refined_1366_client.png)
- [Agent Command展开，1600×900](screenshots/agent_command_1600_client.png)
- [Queue选中与日志/Evidence联动，1366×768](screenshots/queue_selected_1366_client.png)
- [Results选中，1600×900](screenshots/result_selected_1600_client.png)
- [德语150%布局检查](screenshots/de_150_drawer_client.png)

以上是原生客户区1:1 PNG。请用图片查看器100%查看文字；聊天应用可能缩放预览。相同文件名去掉`_client`可查看包含Windows标题栏的原始窗口截图。

原始A/B对照仍在父目录`screenshots/COMPARE_1600.png`与`COMPARE_1366.png`，未覆盖。

## 推荐交互

1. 选择Queue第二行：摘要变为QUEUED，两路日志和Evidence切换到该任务；顶部仍显示另一任务RUNNING和Dispatch PAUSED。
2. 选择运行的第一行：约每1.2秒看到模拟日志增加。取消Follow latest后滚动阅读；重新勾选回到最新行。
3. 拖动上下、左右分隔条；缩小窗口检查日志仍有可读高度。长日志行可以横向滚动。
4. 双击行或点Evidence打开Agent Command Inspector；Esc关闭。F2可快速展开/收起抽屉。
5. 查看Results中的FAILED/UNKNOWN和通过项；它们有独立结果状态，不等同于受管范围证明。
6. Classic Queue/Execution Workspace可往返，模拟身份与选择缓存分离。关闭窗口即结束原型。

命令行（不更改共享环境）：

```powershell
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B 'D:\Projects\abqjobpilot_dev\docs\agent_first\run_024r\refinement_001\refined_cockpit.py' --size 1366x768
```

这是视觉确认入口。所有服务按钮仍为禁用占位，没有真实Project或Supervisor连接。不得将这些截图当作产品执行证据。
