# Agent-first Run 007 — 最终交付

**PASS_ABQJOBPILOT_AGENT_FIRST_RUN007_RECORDED_EXIT_RECONCILIATION_READY**

仅表示完整、已持久化OS退出证据的固定测试进程显式收尾通过，不表示遗留worker重新挂接、自动接管、完整进程恢复、跨Project协调、Abaqus或完整0.3.0通过。

## 基线与实际改动

Dev保持 `Develop@fb7912ec9e0107b18f65948b147c87579c87cded`、应用0.3.0.dev0、实验Schema3。36个前轮源码/测试起始均匹配Run006哈希，前轮未提交成果保留。

新增process_reconciliation.py与test_recorded_exit_reconciliation.py。增量修改7个实验模块：process_contract、process_backend、service、reconciliation、client、supervisor、diagnostics。其余29个前置源码/测试哈希不变，包含所有旧测试、Store、授权验证、锁、固定夹具和独立validator。详见[改动范围](CHANGE_SCOPE.json)、[基线](BASELINE.md)、[契约](CONTRACT.md)、[实现与协议](IMPLEMENTATION_AND_PROTOCOL.md)。旧产品功能、版本和数据格式未改，不迁移旧实验或生产库。

## 能够收尾与仍然阻断的Run

只有支持的固定Backend/version、明确新成员合同、原接受/单启动尝试、全体必要角色OS身份及不可变退出历史完整一致的Run有候选。服务正常路径在保留Windows句柄上观察退出，独立process_observe事务持久化每个退出，然后才进入终态处理。本轮增加精确Project/Plan/attempt/原owner绑定和成员依据；缺这些关键证据的旧Run明确拒绝，不补造历史。

launcher单独退出、worker仍活或身份/退出缺失、仅PID/结果文件/自报完成、控制器独有观察、当前找不到进程、混入attempt或矛盾身份仍阻断。对账不重新检查OS、不打开产物、不运行validator或创建观察任务。

精确TEST_ONLY管理授权与执行Grant、Fake采纳、resume及连接credential分离。apply复用原事务/幂等机制，保留同Run、原receipt、attempt、执行消费和全部历史，只追加决定/事件并更新当前投影。成功后旧回执跨owner仍可重放，但不能在新owner下用旧授权执行新转换。

全零退出计算COMPLETED；完整集合中有非零则FAILED。Artifact原VALID/INVALID/NOT_RUN/UNKNOWN保持，Solver始终NOT_RUN。退出确认不等于产物已验证；对账仍PAUSED，恢复派发使用另一独立授权，仍检查其他不确定Run、slot和各待执行任务的Plan/Grant。现有策略没有“所有历史Artifact必须PASS才能运行下一独立任务”的全局要求，本轮未添加或放松该策略。

## 实际验收与证据

**343 passed，0 failed/errors/skipped，241.96s**：原293项全部重跑，加50项新增。R7-01～12逐项映射见[验收矩阵](ACCEPTANCE_MATRIX.md)。一次测试夹具外键失败已修正并记录；未删除、弱化旧断言。

真实Windows owner在四次退出观察提交后、终态前被终止，重启暂停后经预览/授权显式收尾；丢应答、真实客户端退出、再次换owner重放、并发、事务确认不明、缺证据拒绝均有测试。最终141个owner/client实际进程、71次物理Backend启动、284个fixture角色进程；全部退出并关闭持有句柄，私有凭据残留0。服务事实、控制器额外观察和清理严格区分，见[测试与进程证据](TEST_AND_PROCESS_EVIDENCE.md)。

进程诊断使用现有v2白名单格式及新增v3解释规则，旧v2导出兼容；明确历史退出收尾时间和证据引用，保留只读、脱敏及Artifact未重新验证说明。[收尾前后样例与复现入口](TEST_AND_PROCESS_EVIDENCE.md)均已保存。

## 剩余限制与停止

单槽/成员集合仅限单实验存储和固定四角色。没有重新挂接遗留worker、观察会话、自动接管/Retry、进程控制、强制关闭、人工退出码、通用进程树、主机或跨Project协调。测试管理许可不是生产人类批准，同OS用户任意改程序/数据库不在隔离威胁模型内。

下一最小切片建议：另行授权后先设计显式遗留进程观察会话，明确身份集合、权限、幂等、等待预算、句柄生命周期和观察owner再次崩溃；不能隐藏在preview/apply/diagnostics中。本轮未开始该工作。

Stable和生产数据未访问；未运行Abaqus/Datacheck/旧Runner，未改共享环境，未操作其他用户进程。没有Git切换、恢复、commit/push、同步或版本调整。成果保留在Dev未提交工作区，本轮到此停止，不自动进入下一Run。
