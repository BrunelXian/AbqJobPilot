# Run024R Visual Refinement — approved B layout

用户已批准Compact Engineering Cockpit的布局基线。本轮只精修独立Tk原型，不回到九页侧栏，不改正常Dev GUI。原型以父目录`cockpit_prototype.Cockpit`为基类，覆盖显示与模拟交互；父目录原型、A/B图及历史报告保持原样。

## 本轮变化

| 区域 | 精修 |
|---|---|
| 字体 | Segoe UI 10为正文/按钮/表格；表头10 bold；当前Run11 bold；次要来源/资源9；Consolas10日志；品牌保留13。100%下行高27px |
| 顶部 | Project名称去掉重复DEMO尾缀避免截断；独立的全局运行摘要、琥珀Dispatch PAUSED标记、Supervisor与资源；Current Run右侧状态标记+Evidence |
| 表格 | 平坦表头、左对齐文本/居中数字、柔和蓝色选中行、淡条纹；失败红/未知琥珀。按实际字体测量列最小宽度，不靠挤小列宽隐藏表头 |
| 任务选择 | 鼠标或键盘选中Queue/Results任务，Current Run、STA、Console、Evidence使用同一模拟身份；非选中表取消旧高亮 |
| 日志 | 两路常驻，默认约42%主区高度；每1.2秒内存模拟追加，Follow latest真实控制滚动；手动滚轮/竖滚动条暂停跟随；横向滚动不自动复位 |
| 分隔条 | Queue/Results、两日志及上下比例可调整；上下分隔预留日志最小可读区，考虑边框与sash；缩放后重新约束 |
| Agent Command | 布局不变，减少抽屉外重复警告；服务按钮仍禁用，仅模拟；Inspector跟随任务选择 |

Current Run是**选中任务的查看上下文**，不是宣称选中任务正在运行。全局状态栏仍显示活动`axial_042`；选择`axial_041`时摘要标QUEUED，Scope NOT_STARTED，STA明确无输出，Console显示未启动。Dispatch PAUSED限制后续派发，不表示已经运行的任务被暂停。

100%下1600/1366截图无缩小处理。表头和右侧动作使用测量/控件边界断言；窄抽屉优先列保持B既定策略。日志长行通过水平滚动查看，不进行强制折行。对异常/失败仍使用不同状态，没有改写真实证据。

## 交互边界

所有记录、资源值、时间与日志为模拟值；没有Client、Supervisor、Classic Runner或产品数据库。New/Open只展示子区。恢复保持只读样例，无Apply、Grant、Retry或派发操作。GUI关闭只退出这个原型。

日志缓冲每路最多250行；旧行滚出缓冲后不承诺长期保留。切换任务会重建该任务的模拟日志，Follow关闭时从其顶部开始；同一任务追加时保持当前阅读行。产品日志流与持久索引不在本轮范围。

语言沿用English默认、中文以及法德Preview。技术状态代码和部分高级说明仍为英文；未宣称完整母语翻译。125/150%是进程内Tk字体/控件缩放检查，未改变Windows设置，未进行跨显示器DPI验收。

## 实际测试与迭代

`visual_checks.py`每场景使用独立普通Python/Tk进程，audit hook禁止外部执行、IPC和DB。14个唯一场景覆盖双尺寸、Agent Command、Queue/Results/Failed联动、日志跟随/水平滚动/有界缓冲、分隔条/缩放、三种非英语、空状态、Classic往返和失联。

首轮在`resize_splitters`失败：内容预留量未计入sash和边框，日志容器实际高度低于170px检查。原结果保留为`TEST_ITERATION_01.json`。修正后单项复核通过；再运行完整集合。随后高缩放布局将最小日志预留与字体按有限比例关联，避免150%时表格只剩极少行，并增加250行缓冲检查。最终结果见`TEST_RESULTS.json`及每张截图旁的JSON。

测试检查了原生Treeview点击选择、显示联动、Follow关闭不跳行/开启到尾、水平滚动、窗口1366↔1600改变、分隔条位置变化和日志高度。它不是产品服务生命周期回归，也不是实际鼠标手工用户验收。

截屏使用本轮Tk根窗口的HWND。`*_client.png`使用GetClientRect/PrintWindow(PW_CLIENTONLY)原生捕获客户区，PNG像素与窗口客户区逐项核对；不裁缩原截图来美化显示。无后缀PNG保留Windows边框/标题栏。GDI对象在finally释放。

未重跑产品核心测试：源码和执行行为无改动。保留原Run024测试结论，不把其测试数量算入本轮。
