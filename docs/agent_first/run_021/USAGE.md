# Run021 — 当前可用操作与不可执行的候选

状态为 **PARTIAL**。没有发布新的真实执行命令；不要将本目录离线预览交给提交接口，不使用旧Run016按钮代替产品流程。

## 现有正常入口

正常GUI仍为 `D:\Projects\abqjobpilot_dev\Open_Dev_GUI.vbs`。New Agent-first Project、明确Start/Stop、认证连接和只读Run列表继续沿用Run020。创建/打开不产生执行许可。

本轮准备目录记录在 `PREPARATION_LOCATION.json`，名称为Run021 Standard product candidate。它目前是一个空PAUSED产品Project，保留新输入与离线预览，未启动Supervisor。**为后续首次配置租约保留该状态，请不要对这个候选点击Start。** 可以只读打开和查看身份。独立普通客户端只读检查：

```powershell
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B 'D:\Projects\abqjobpilot_dev\examples\agent_first\product_inspect.py' --project 'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run021_42b9754ee29b457d8c86b2e97a26ec4b'
```

无服务时返回NOT_RUNNING；不会自动启动。普通client无真实批准能力。

## 交付材料

- `PREPARATION_MANIFEST.json` 是**不完整准备清单**，不是待批准的可执行验收包。规范化body摘要仅绑定现有准备事实，`execution_plan_id=null`明确没有服务Plan。
- `OFFLINE_PREVIEW.json` 使用Run009/010公开prepare/inspect、轴向打印支持档案。其schema中的“真实Backend未实现”等历史未解决项是离线工具自身不可执行范围，不能解读成当前整个仓库没有Standard实现；接入现状由INTEGRATION_AND_PATCH_REVIEW说明。
- `PREPARATION_FACTS.json` 记录0Plan/Grant/Run/消费/事件、PAUSED、未启动。
- `private/`中的DPAPI材料只供这个本机用户及实例使用，不放入报告、不归档、不复制为另一Project凭据。本轮候选凭据保留；测试实例凭据另行清理。

## 未来流程草案（本轮不可执行）

补丁审查及替身组合链通过、真正ExecutionPlan和执行材料摘要冻结后，才形成新的完整清单：GUI选择候选→明确Start→Python认证→复核→精确真实Grant（需新授权）→公共submit唯一Run→明确单次派发→Solver运行时GUI退出→OS身份与日志继续→重开同Run→范围收尾及独立DAT→PAUSED/安全Stop→明确Start保留PAUSED和历史。

每项真实analysis最多1次，额外调用0，CPU1/GPU0/2048MB，300秒仅结束观察。错过GUI观测窗口标NOT_OBSERVED，不补跑；不确定时只查原幂等身份。停服条件不足则保留owner和记录，不杀进程或清理输出。没有ODB内容验证。

当前不能给出上述真实执行命令，因为精确在线批准、单次派发、产品Standard停服尚未实现；不拼接shell命令，不要求用户先试运行补证据。
