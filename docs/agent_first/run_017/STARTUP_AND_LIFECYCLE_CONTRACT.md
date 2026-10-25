# Run017 — 正常启动、连接与关闭契约（冻结建议）

这是下一步实现依据，**尚未实现正常服务发现**。现有默认GUI仍legacy；新Viewer需要连接文件+request_key。当前VBS启动器是开发支架，不能直接宣称最终产品安装/常驻方案。

## 当前事实

- `run_gui.py`→`gui_app.main`。只有明确的`--execution-connection`与`--request-key`组合进入只读服务查看；默认进入legacy，不会自动发现Supervisor。
- `FakeClient`普通构造/连接失败/析构不自动启动或停止owner；`Reader`不写执行DB，不按Recent或GUI旧Project猜目标。
- `FakeSupervisor`持有独占OSowner、独立worker和IPC；GUI关闭仅结束自己的Reader/线程/窗口。测试真实关闭GUI和venv后，owner/worker身份保持；源证据见本轮windows_evidence。
- `examples/agent_first/dev_gui_demo.py` start为可信prepare/固定TEST_ONLY授权+owner启动；有900秒演示寿命和独立stop控制文件，不是长期产品服务。不能把这一工具接到GUI自动打开动作里。
- `examples/agent_first/standard_service.py` stop仅显式写本实例控制请求，等待active_dispatches=0后退出owner。`serve finally`等待worker结束、PAUSED持久化、关闭自己的锁/线程；不terminate Solver。退出服务不意味着未知后代结束，未决记录和旧输出保护继续存在。

## 建议产品状态转换

| 条件/用户动作 | 允许行为 | 明确禁止 |
|---|---|---|
| 用户打开Dev并选择明确AF实例 | 只读校验manifest/format/身份；从本实例可信连接描述符发现候选endpoint | 从全盘、默认Recent或旧GUI当前项目猜测；建库、迁移、复制凭据 |
| 现有服务握手成功 | 校验Project/instance/context/owner；展示公共摘要和Run列表 | 再起owner、批准、submit、resume、retry |
| endpoint陈旧/超时 | 显示失联与最后成功时间；可有界重连同实例 | 以超时当锁已释放；删owner.lock或“修复”数据 |
| Project不存在/旧格式/身份不符 | 结构化诊断，停止自动流程 | 创建新Project冒充原目标，静默迁移，切换到legacy写库 |
| 用户明确要求启动尚无owner服务（后续独立切片） | 可信已配置上下文；同OS排他锁准入；失败或竞态只报告/连接赢家 | 绕锁、修改权限、复制执行授权、启动未知配置 |
| 首次新实例owner | 按现有fresh政策为OPEN，**这不产生任何执行许可** | 把OPEN当批准；为了产品化偷偷修改契约 |
| 已有实例owner重新启动 | 原记录保留，PAUSED；未知Run阻断 | 自动恢复派发、接管遗留进程、重跑原Run |
| 正常关闭GUI | 停轮询、关闭自己窗口/线程；不持有worker必要句柄 | stop owner、释放Run范围句柄、删除连接秘密或输出 |
| 重开GUI | 再认证同实例，读取同Run/原回执；只更新本地查看状态 | 重发业务请求以“恢复界面”，恢复PAUSED |
| 用户明确停服 | 独立动作；显示活跃观察/UNKNOWN/保留资源，按能力限制停服 | 将关闭GUI等同停服；将owner退出写成Solver结束 |

最小Run018只实现第一段“发现/连接已有服务”，不存在服务时明确提示可信操作者入口，不自动启动。这样避免把首次可信准备和自动批准隐藏在产品启动中。未来自动启动需单独实现可审查的生命周期合同，服务已存在/锁忙绝不竞争执行权。

## UI与错误语义

连接状态与业务状态分开：CONNECTING、CONNECTED、DISCONNECTED、PROJECT_MISMATCH、FORMAT_UNSUPPORTED、MAINTENANCE_REQUIRED。实际返回沿用已有原因码，不为了展示建立第二状态机。最近时间表示观察时间，不代表当前进程仍活着。事件按游标分页，不把其他Run占用的全局sequence当本Run缺失。

新任务列表若需要，仅增加一个有界只读Project摘要接口：Project/instance、owner、dispatch gate、slot、Run/Job/Plan公共ID、接收时间与各状态；事务一致读取，不返回私有连接材料、可用Grant、环境或任意路径。GUI选择Run后仍复用现有receipt/events/progress/diagnostics。日志只读有界，Tk不等待长请求。

GUI只读不要求额外ExecutionGrant，但连接认证不能省略。获取描述符不等于批准任务；描述符由可信操作者在明确目录交接，不从不可信Project压缩包继承。新旧Project必须显式区分，不向legacy历史双写服务Run。

## 关停、范围与持久性

受管Job范围由owner而非GUI持有；不启用KILL_ON_JOB_CLOSE。范围结束与Solver/DAT/ODB仍分开。owner退出后无法沿用旧Job句柄，不能用新空Job替代证据。正常停服等待正在进行的观察/写入完成；该等待可能持续到原观察预算，不承诺点击即瞬时退出。UNKNOWN时停服只代表结束观察所有者，原未决/隔离/PAUSED必须保留；是否允许具体历史实例停服是单独明确操作，本轮不执行。

本软件没有Windows Service、计划任务、自动更新器；未验收系统注销/重启/终端关闭后的存活或自动恢复。嵌套Job外层策略不可由本层无Kill标志证明。禁止通过breakaway、伪父进程或后台渠道绕过宿主。固定Python和固定Standard历史验收只支持所记录的Windows宿主条件。

## 准确入口与执行边界

既有查看器参数定义已静态核对，通用形状（占位符不声称已经实跑）为：

```powershell
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B 'D:\Projects\abqjobpilot_dev\run_gui.py' --execution-connection '<明确实例的私有连接文件>' --request-key '<该实例原提交幂等键>'
```

当前无无需显式连接材料的通用新服务产品入口。本轮没有重开历史GUI来演示。真实执行过的同一GUI路径由`tests/run012_gui.py`在临时实例驱动，Windows证据与本轮命令见测试报告。旧`03_Open_Dev_GUI.vbs`仅用于其自己的TEST演示实例；R16_04/05入口只对应已消耗预算的历史批次，不能当作新任务示例执行。
