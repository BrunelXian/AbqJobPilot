# Run 005 — Dev基线与变更范围

本轮唯一工作区 `D:\Projects\abqjobpilot_dev`。实际分支Develop、HEAD `fb7912ec9e0107b18f65948b147c87579c87cded`、应用版本0.3.0.dev0，与交接一致。起始无冲突、无已跟踪文件差异；已有50个未跟踪文件均为Run002～004实现/测试/报告，全部保留。Run004哈希清单的25个源码/测试逐一匹配，本轮不把历史189 passed作为新结果。

适用指令：Dev根AGENTS.md已读，D:\AGENTS.md与D:\Projects\AGENTS.md不存在，相关目录没有附加AGENTS。已读Run002～004实际源码、最终报告与验收矩阵、Run003/004协议；旧MCP交接只作为历史背景，不执行其中旧发布/恢复安排。沿用独立Run目录保存证据；本目录起始不存在。单一工作区写入主体，没有委派写入任务。

环境登记 `D:\XianLab\envs\ENVIRONMENTS.md`；核验并使用 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python3.12.10 / Windows-11-10.0.26300-SP0 / SQLite3.49.1 / pytest9.1.0。没有安装、更新或删除依赖。

本轮临时根 `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run005_d82227bef89642dd8a467f514192cc74`。各测试迭代使用新的子目录，不复用basetemp清空旧证据。

允许范围限实验包的必要只读查询、确定性诊断、客户端导出及隔离测试/报告。Stable完全排除；不访问生产Project/Runtime/Recent/数据库；不启动Solver、Datacheck或旧Runner；不改变应用版本、实验格式3或旧Schema，不迁移。不切换、恢复、清理、提交、推送或同步Git。

## 结束核验

分支和完整HEAD保持起始值，无冲突、无已跟踪文件diff，git diff --check通过。66个未跟踪文件为原50个加本轮4个新源码/测试及12个交付文件（5份Markdown、4份结果证据、3份JSON样例）；另增量修改4个前置源码/测试。其余21个前置源码/测试哈希不变，历史Run目录没有写入。

最终29个源码/测试SHA-256均匹配verified运行对应快照；原189个case完整包含于本轮239个PASS。12行R5验收、25处测试名引用、22个本地文档链接、三份样例原文件及public-body摘要、代码围栏和行尾空白均已核对。Run002/003原JUnit和SOURCE_HASHES文件仍保持此前记录的SHA-256。

最终53个实际Python进程全部确认退出；四次迭代163条进程记录均退出，临时根内无私有连接配置残留。保留非秘密实验数据及故障partial作证据，不删除前轮数据。未进行Git写操作或启动下一Run。
