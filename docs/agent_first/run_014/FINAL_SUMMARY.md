# Run014 最终报告

**实现与隔离验收完成；当前真实实例保持未处置。Abaqus新增调用0。**

Dev实际基线 `Develop@271c6f82fd6a4599dbae2df30d903dab2cef1f63`，版本仍0.3.0.dev0。没有修改Git状态历史、提交或推送；没有访问Stable、生产Project或共享环境。

## 完成交付

- `execution/closeout.py`：一致只读收尾评估；明确“保留资源”与“行政释放逻辑槽”两个动作；精确独立管理许可、原管理事务/幂等、留存路径政策。
- 既有service/client/supervisor接入2个公共操作；原正常停服路径补持久PAUSED；原恢复入口继续独立授权并检查其余未决Run。没有新执行框架、终止接口或真实启动能力。
- 既有Dev GUI增加只读评估行；诊断规则Standard v2明确行政决定不等于证据收尾，原v3/rules-v1导出仍可读。
- `standard_closeout_operator.py`：无Solver只读命令，以及只在明确操作者执行时取得现有排他管理lease的可信交互入口；普通IPC不能mint/approve。
- 隔离测试、Windows实际owner正常退出/重启/崩溃、真实GUI展示与关闭证据；修复旧测试支架身份文件原子发布竞态，未弱化旧断言。

具体契约、权限、正常收尾缺口见 [CONTRACT.md](CONTRACT.md)；命令和GUI入口见 [USAGE.md](USAGE.md)；逐项证据见 [ACCEPTANCE_MATRIX.md](ACCEPTANCE_MATRIX.md)。

## 实际测试与限制

最终分批去重 **369项通过：新增30项、既有相关339项**，无跳过。单元批65通过；大回归302通过、1用例初始化失败并伴随清理错误；修复旧支架完整身份发布后，受影响整组及关键回归83通过；SQLite并发视图额外1通过。不是一次全量369通过，详见 [TEST_RESULTS.md](TEST_RESULTS.md)、TEST_CASE_INDEX.json与原始日志/XML。

Windows新验收确认：固定worker在owner/venv退出后继续运行和写日志；重启仍PAUSED/原未决Run及slot保留；已授权隔离处置后只释放逻辑slot，旧工程/输出拒绝复用；实际提交前owner崩溃产生维护拒绝，未隐式修复；丢应答原key返回原回执。最终各新场景已持有句柄均取得退出事实并关闭，私有凭据清理。初次支架竞态缺少保留退出码的历史限制另存FIXTURE_RACE_CLEANUP.json，没有倒填0。

测试仅证明当前Windows会话中的固定Python替身条件。未证明真实Abaqus在owner停止、终端关闭、注销/系统重启后的行为；未实现自动接管、完整成员追踪、旧输出解锁、整机或跨Project资源保护、ODB验证。正常自动收尾仍需未来新Run从启动前建立可验证的受管成员边界，不能倒推本次历史全集完整。

## 当前真实实例实际只读结论

| 项目 | 当前事实 |
|---|---|
| Run | `r_609c9bbfd9c54b3ca2fce23bbd6059e4`，revision20 |
| 记录owner | `owner_17886eb60d8349e880d61131a04be3b3`；PID17528/creation100ns134372377146539267 |
| 当前owner观察 | 旧IPC健康查询超时，未取得上述身份匹配的引用；不能声明owner或未知Solver已确认退出 |
| 进程/数值 | 历史11个已观察成员退出0；Solver COMPLETED_TEXT_EVIDENCE；DAT PRIMARY_THREE_PASS；全集/整体退出UNKNOWN，ODB NOT_RUN |
| 控制 | PAUSED v3，slot仍占用；Run待对账；管理回执/对账记录0 |
| 保护 | 295份历史材料摘要均匹配；当前Run、slot、gate、事件/验证/消费数量和库字节摘要未改变 |

完整当前评估：[CURRENT_CLOSEOUT_PREVIEW.json](CURRENT_CLOSEOUT_PREVIEW.json)。其证据满足“观察结束且已观察子集退出记录匹配”，但离线读owner_id=null，`CURRENT_QUIESCENT_OWNER_REQUIRED`尚不满足，故不能直接apply。

当前库SHA256：`74bff58c7e1167f6a7f394ab130cbf6d21dd2c5b8f75d1e173c5e4675075ef94`。最终复核见 [FINAL_AUDIT.json](FINAL_AUDIT.json)。没有重启/重载/停止原owner，没有登记真实管理Grant，也没有修改真实槽或派发门。

## 针对当前Run的一次待确认建议

详见 [CURRENT_RECOMMENDATION.md](CURRENT_RECOMMENDATION.md)。建议操作者明确接受上述残余不确定性后，**仅在正常取得排他管理lease且重新评估通过时**，对这个Run执行一次 `release_standard_logical_slot` 行政处置：

- 仅释放逻辑槽，记录理由、授权来源、评估/证据指纹、回执与事件；
- 完整成员/整体退出UNKNOWN保持，原回执/attempt/执行消费不变；
- 原engineering/scratch/输出及一次意图继续保留隔离；
- 派发保持PAUSED，不Retry、不重新验证、不运行任何Abaqus、不删除输出；
- 如果原owner仍持锁或存储/证据不满足条件，就停止，不抢占或修复；管理完成只退出本次无worker管理lease。

目前**不具备直接停止旧owner的确认条件**；不向旧PID发终止或stop请求。新代码也不能沿用旧候选摘要把执行材料变化视为已批准。旧 `standard_service stop` 校验失败时不可绕过。

需要用户对这项真实实例处置另行确认，是因为Run014指令明确要求：未经针对当前实例的确认，不改变其收尾、资源占用或owner生命周期。本轮已经完成具体实现、评估和隔离验证，停在这项确认之前。

未自动进入下一轮。
