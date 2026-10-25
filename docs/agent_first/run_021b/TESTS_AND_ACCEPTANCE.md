# Run021B 验收、测试与失败迭代

实际环境：Windows，登记 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python3.12.10、pytest9.1.0、Tk8.6。所有测试写入13个明确新临时根。未修改依赖；真实Abaqus创建不可达，不是仅观察调用数恰好为0。

## 最终唯一用例结果

**392 PASS / 0 FAIL / 0 SKIP**。按`classname::name`（含参数）去重，同一测试以最终对应复验结果为准，不把多次执行相加。原始失败XML不删除。完整ID、选集与结果在TEST_RESULTS.json。

| 批次 | 用例与结果 | 覆盖 |
|---|---|---|
| regression_002.xml | 213 PASS | Standard原路径/Grant隔离/managed pair；生命周期/Project；原契约、Store、IPC |
| regression_003.xml | 127 PASS、1初次FAIL | 产品Windows、GUI连接、只读列表、managed scope、Standard native替身、owner/隔离、公共流程 |
| isolation_verified.xml | 9 PASS，覆盖上述失败及其同文件用例 | 明确新模块hmac依赖和实际junction拒绝；旧断言保留 |
| control_verified.xml | 36 PASS | 32项新增精确控制/检查＋4项真实Windows产品替身链/owner崩溃 |
| windows_verified.xml | 同4项再次PASS，不重复计数 | 按owner独立保留native句柄关闭证据，避免重启覆盖第一任owner清理文件 |
| legacy.xml | 15 PASS | Legacy Project GUI、table、task workspace、format boundary；独立Home/Runtime/Recent、禁止外部进程 |

未跑全部历史测试，未测试生产库迁移、真实Abaqus、ODB、注销/关机。原运行的相关回归精确列表由XML的唯一ID给出；不使用Run021历史351项冒充本轮结果。

## 新风险逐项映射

| 要求 | 本轮证据 | 结果 |
|---|---|---|
| 精确Grant和审计 | exact_approval；原management receipt与control event、完整product_scope、subject/source | PASS |
| 普通连接/Stop/自报管理员不可批准 | connection_and_stop_permissions（三种token）；原TEST_ONLY隔离回归 | PASS |
| 输入、Plan、Project、额外参数、输出、有效期变化 | admission_denies_changed_or_test_authority；precise_dispatch_preconditions | PASS |
| Grant不可二次消费 | consumption_keys_and_concurrent_dispatch，另一请求键拒绝 | PASS |
| 只允许精确单Run | profile只绑定一Plan；接受/派发均核对；其他Run、revision、owner或gate拒绝 | PASS |
| PAUSED不自行启动 | 接受后无physical记录，execute无许可拒绝；全局一直PAUSED | PASS |
| 丢应答/并发/重连 | Windows dispatch_response_loss：ACCEPTANCE_UNKNOWN后原键回执；单物理启动 | PASS |
| owner硬退出 | after_claim与after_create用真实os._exit(97)，原生句柄观察；新服务启动被阻断；创建后worker仍活 | PASS |
| 迟到创建拒绝 | before_create确定性屏障后期限到达；原native API属性准备后期限检查回归 | PASS |
| 事务/查询/证据失败 | management、claim、intent、create、scopequery、resultcommit故障；无未记录OPEN、无再次启动 | PASS |
| 正常scope收尾 | native Job查询、COMMITTED_EMPTY_SCOPE、slot空；Solver/DAT/ODB分维度 | PASS |
| 安全停服 | active/pending/UNKNOWN拒绝；same mutex stop/submit竞争；空闲stop成功 | PASS |
| 重启历史和PAUSED | 新owner，原Run/回执/revision/消费不变；旧派发回执可读、旧授权不能新转换 | PASS |
| GUI/Public Client一致 | GUI显示原Run，独立Python提交；关闭venv+GUI后继续、重开同Run | PASS |
| 候选无执行副作用 | CANDIDATE_CHANGE / CANDIDATE_PUBLIC_CHECK，1Plan但0Grant/Run，原gate不变、owner从未启动 | PASS |

## Windows关键证据

完整保存在 `windows_verified/`，全程标明`PRODUCT_STANDARD_NATIVE_PYTHON_SUBSTITUTE_HISTORICAL_DAT_ONLY`。根进程创建被测试程序替换为固定Python，实际原生JOB_LIST和显式文件句柄仍被执行；audit hook在native创建前只允许该Python/固定脚本/本次临时目录。无配置选项能在产品入口选择此替换器；无管理fallback、subprocess直接启动Abaqus都抛错。

本批Run `r_a97a0ff746a3463eb4a29b6ce4fa4d92`。owner PID9880、creation100ns=134373718999848191；worker PID16864、creation100ns=134373719008863275，映像均有OS核验。GUI PID30968及venv PID26684均从保留句柄取得exit0；之后原owner/worker仍活，STA从116增长到126字节。重开GUI连接同Run/receipt，唯一physical记录，随后自然退出、范围收尾、slot释放。stop/restart新owner仍PAUSED，原记录没有重放。

结果为FINISHED、COMMITTED_EMPTY_SCOPE、COMPLETED_TEXT_EVIDENCE、PRIMARY_THREE_PASS，overall_exit UNKNOWN、ODB NOT_RUN。文本证据来自固定Python复制的明确历史DAT，不是候选或本次真实Solver成功。

硬退出场景的服务持久记录与控制器额外观察分别保存。只有控制器知道的worker身份不补入服务库；后续没有发现PID不补造历史退出证明。正常退出的native root/scope句柄分别记录closed=true；硬退出的用户态句柄由OS回收，不伪造正常finally记录。

## 失败迭代（未隐藏）

1. 默认受限工具环境的Windows集成2项失败，原因WinError10013本地socket限制；相关回归批次中止。通过正常审批获得当前Windows用户环境运行权限后继续，未改IPC安全策略。只读身份审计未发现那两项测试owner仍存活，没有终止其他进程。
2. 首次非受限Windows批次2项失败：新测试把已有独立client要求的原始request误包成`{"request":...}`。修正测试交接格式，产品代码未放宽；后续通过。
3. 相关128项中1项失败：新control导入hmac未加入精确模块依赖表。仅该模块增加hmac（常量时间能力比较）；没有放行subprocess、旧Runner或默认Runtime。9项隔离最终全通过。曾在受限环境复验junction遇到Win32错误5，随后正常用户环境原断言通过。
4. 清理脚本首次调用生产profile校验遇到测试故意无效的Standard配置KeyError；当时未删除。改为只对已知测试私有文件做DPAPI解密/内存秘密扫描，不放宽应用配置验证，再执行清理。
5. 增强测试证据文件：每个start_id保存独立native清理记录，额外复验4项通过；没有修改应用执行语义或候选材料。

## 清理与历史保护

CLEANUP.json首次核对362份身份，无匹配存活；删除387份本轮残留测试私有文件。CLEANUP_FINAL.json覆盖最终13根、373份身份，无匹配存活、无新增待删凭据。报告已知秘密值扫描0命中；不宣称通用匿名化。测试自身的保留句柄退出证据与事后身份未匹配明确分开。

没有按进程名终止、没有清理旧目录，没有触碰候选private或历史owner。保留数据库和输出作为隔离证据；只清理身份核验后的本轮凭据。Sandbox失败清理检查实际终止0进程。本轮真实Abaqus/ODB读取/候选Grant/Run/派发/owner启动全部0。
