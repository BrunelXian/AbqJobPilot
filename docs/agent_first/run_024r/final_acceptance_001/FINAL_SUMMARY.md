# Compact Cockpit Final Acceptance

**本轮局部语义、可读性与隔离安全验收通过。** 用户已确认的 Compact Engineering Cockpit 布局保持冻结，未重新设计主窗口；这不是正式 0.3.0 发布批准。

## 三项结论

1. **Results 保留 START_INTENT / NOT_RUN。** 它是 Run 证据概览，不是“完成结果”过滤器。已补 Stage 列，未隐藏 UNKNOWN 或需要人工关注的未决执行。
2. **PROCESS_EXIT_OBSERVED 不代表整个 Run 完成。** 实际隔离服务复测取得部分成员退出、worker 仍等待、受管范围 active_processes=3 的同时证据；顶部 START_INTENT 符合当前核心契约。新增退出记录提示，保持受管范围、Solver、验证分维度显示，未修改核心状态。
3. **日志按真实来源命名。** 固定 Python 为 Worker Log；服务记录为 Events；Standard 现有摘要来源为 STA/MSG/LOG summaries。未伪称 stdout 或完整 STA。Run ID 显示缩短但可查看/筛选完整身份，时间显示到秒且保留时区，原始字段不变。

详细依据及最小修改清单见 [SEMANTIC_REVIEW.md](SEMANTIC_REVIEW.md)。Queue 左、Results 右、Current Run、双日志、Agent Command、Classic 双向导航与语言设置均保留。

## 验证

**225 个唯一用例最终 PASS，FAIL=0、SKIP=0。** 一次混合批次导入隔离失败及独立进程复测记录完整保留；没有修改断言以掩盖失败。见 [TEST_AND_ACCEPTANCE.md](TEST_AND_ACCEPTANCE.md)、[TEST_RESULTS.json](TEST_RESULTS.json)。

Windows 实测：Run `r_f8f9585b56c449b2a84b0aacbc4557ce`，GUI PID 18532 / venv launcher 28000 句柄 exit=0 后，原 owner 18856 与 worker 26504 身份匹配且仍运行，日志继续增长；重开连接原 Run / 回执，启动一次。最终 FINISHED、COMMITTED_EMPTY_SCOPE、Artifact VALID；Solver NOT_RUN。只读监控与 Recovery Preview 不改变 Store hash、派发或授权。

- [1600×900 实际窗口](screenshots/cockpit_1600.png)
- [1366×768 实际窗口](screenshots/cockpit_1366.png)
- [Agent Command](screenshots/agent_command.png)
- [两项实际 TEST Run 选择联动](screenshots/selection_linked.png)
- 正常 Dev 入口：[Open_Dev_GUI.vbs](../../../../Open_Dev_GUI.vbs)

## 旧目录与保护

45 个旧测试目录全部逐项审计，约 135.16 MiB，均在仓库外。160 个加密凭据容器及 1 个未启动服务的明文降级测试负例均具受限 ACL，秘密未导出；未发现身份匹配存活测试进程。三个当前查询失败身份均另有原始保留句柄退出证据。没有据“查不到”补写完整退出。准确路径及发布排除要求见 [RETAINED_TEST_DATA_AUDIT.md](RETAINED_TEST_DATA_AUDIT.md)。

45 个旧根保留原样，未重试此前遭策略拒绝的递归删除。本轮 21 个新测试根也保留在临时区并排除发布；夹具临时连接凭据已按自身收尾契约移除。见 [CURRENT_TEST_CLEANUP.json](CURRENT_TEST_CLEANUP.json)。

Develop / HEAD `9553755a24ff521dd2ac694ea39cab5a03f88466` / 0.3.0.dev0 保持。历史原型、截图、报告和执行核心 hash 未变，既有未提交成果保留，见 [PRESERVATION.json](PRESERVATION.json)。

本轮 Abaqus 调用 **0**，真实恢复 **0**；未访问 Stable、操作历史 owner、修改共享环境、提交或推送。未发现本轮核查范围内的新 P0；全量 RC、跨系统 DPI、域外完整性等仍受既有范围限制。

完成后停止。下一步仅为 Develop Git 检查点与 RC 发布核验；本轮未执行提交、打包或发布。
