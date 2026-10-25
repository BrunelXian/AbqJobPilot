# Run018 指令草案 — 正常Dev入口连接已有执行服务

这是建议，未开始实施；本轮不授权运行它。

请仅在`D:\Projects\abqjobpilot_dev`按实际AGENTS、环境登记和Run017报告工作。核对Develop、HEAD、0.3.0.dev0，保留所有未提交成果及历史真实实例。真实Abaqus预算0；不得访问Stable、共享环境、迁移生产数据、重启/接管历史owner或重放历史实验。仅一个写入者，不commit/push。

## 唯一最小目标

让用户从现有Dev GUI入口选择一个**明确的已有Agent-first实验Project连接描述符**，自动认证并连接该Project的既有Supervisor，显示有界任务列表，选择原Run查看状态/日志；关闭完整GUI后再打开能恢复观察。Agent使用同一公共接口。

本切片只做attach/discovery，**不自动启动Supervisor**。未运行/端点陈旧/格式不符/锁状态不明时提供准确诊断和已有可信操作者启动说明。不得把当前dev_gui_demo.start（含prepare/TEST_ONLY许可）嵌入GUI启动；不创建第二owner。

## 建议改动接缝

1. `gui_app.main/AbqJobPilotApp`：正常入口提供明确AF连接选择，不把旧Project当AF，不自动用Recent猜根；保留旧模式兼容，避免自动打开生产Project做测试。
2. `execution_gui.Reader/ExecutionView`：复用只读异步模式、断线缓存标记、事件游标、bounded日志和独立状态维度；从一请求查看扩为有界Run选择。可以记忆本地查看选择，但不将连接秘密写业务导出/普通日志。
3. 若现有接口不足，给同一`ReadOnlyStore→ExecutionService→Supervisor→FakeClient`增加**一个有界只读Project摘要/Run列表**。一次短事务取得Project/instance、gate/slot及白名单Run/Job/Plan/回执关联，规定limit/游标/错误；不返回Grant、私有凭据或任意文件。已有run/events/progress/diagnose不造同义入口。
4. 连接描述符只指向明确实例，握手必须核对Project/instance/context/owner；错误端点不自动改绑，不删除锁、不修复库、不初始化Schema。普通GUI没有批准/恢复/提交/Retry按钮。

## 明确排除

不实现服务安装、任务计划、自动更新、自动owner创建、真实批准GUI、MCP写工具、通用Plan编辑/迁移、跨Project协调、自动恢复/对账。GUI关闭不停止owner、不关闭Run管理句柄、不清理private；服务失联不能推断Run结束。保持已有首次新实例OPEN与重启PAUSED原语义，不在展示适配中改派发策略。

## 必要验收

- 固定Python任务由独立客户端提交在先；新GUI不依赖手工request_key拼命令即可选到同Run、原回执。
- 两个GUI并存/重复打开均连接同owner；业务接收、Grant消费、事件、gate/slot不因查看变化。
- GUI完整退出（含专属venv），身份匹配owner/worker继续，日志增长；重开连原Run，物理启动仍一次。
- 错误Project、未来格式、缺库、未决journal、凭据错误、陈旧owner、断线与超限均诚实拒绝，无init/migrate/repair。
- PAUSED/待对账/行政槽释放的状态正确分开；GUI重连不resume、retry、approve。
- 新列表查询是有界一致读取，响应/导出无凭据和任意载荷；慢IPC不阻塞Tk；窗口关闭清理自身线程。
- 原legacy API/MCP五工具语义不变；所有测试新建隔离根，实际WindowsGUI与固定Python生命周期验收，必要R2–R16回归，保留失败迭代及清理证据。

交付实际入口、简短使用说明、公共只读契约、逐项验收和最终报告。若上述最小目标必须改核心授权/所有权/状态机，先记录具体证据和受限修正方案，不借此扩展。本轮结束停止，不自动进入真实Abaqus验收或下一阶段。
