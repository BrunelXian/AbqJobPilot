# RC-G02 测试与验收

## 本轮实际结果

**763 个唯一用例最终 PASS，FAIL=0，SKIP=0。** 以 JUnit `classname::name`（含参数 ID）去重，重复执行取最后结果；全部批次保留，不将跨批次数量相加冒充唯一数量。机器清单 `TEST_RESULTS.json`。

| 批次 | 本次结果 | 覆盖 |
|---|---|---|
| fixtures | 114 PASS | 新合成 fixture、三项固定数值、v2 兼容、脱敏、精确授权及产品创建 |
| core | 458 PASS | Store/所有权/IPC/授权/幂等、固定 ProcessFixture、退出对账、Standard 受控替身、受管顺序派发 |
| product | 127 PASS | Project/凭据、服务发现/生命周期、GUI 连接、Standard 产品替身与单次派发 |
| recovery | 84 PASS | 中断只读诊断、精确恢复权限、排他 Apply、幂等与故障 |
| legacy | 58 PASS + 1 初次 SKIP | Classic 项目/历史/布局/queue-only/API；Tk 用例另见失败迭代 |
| isolation / semantics | 9 / 6 PASS | 导入与路径隔离、Cockpit 状态及日志来源 |
| cockpit_windows / native_windows | 1 / 3 PASS | 实际 Windows GUI、两 Run 选择联动、关闭后继续、同 owner/Run 重连 |
| cockpit 控件 | 2 初次 PASS，第三项初始化 ERROR；独立进程第三项 PASS | 1600/1366 布局、双日志、过期选择、排序筛选 |
| legacy_single | 1 PASS | 首次跳过的 Classic 原生工作区完整用例 |

本轮未以历史 Run024R 的数量替代实际结果。执行使用登记的 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，实测 Python 3.12.10 / pytest 9.1.0 / Tk 8.6，无依赖变更。

## 首次失败与修正

1. 同进程第三次创建 Tk 时 `tk.tcl` 报无法读取 `listbox.tcl`；文件实际存在。首次两控件测试通过，第三项在全新进程通过。仅调整测试承载方式，不修共享 Tk、不改 GUI。现有 Native GUI 验收也使用独立进程。不能将此诊断成已经证明安装损坏。
2. Legacy 批次一项因 `init.tcl` 初始化被 SKIP；同一原用例在独立进程 PASS。保留原 XML 的 SKIP 原因。
3. 操作脚本误追加一个不存在的控件测试名称，pytest exit=4、0 collected；这是选集错误，未改断言，没有把空跑当成功。该批次 XML 保留，之后按源码准确名称执行。

## 隔离与真实路径不可达

从 455 项白名单文件建立独立副本，原 DAT 和历史 v2 JSON 均不在其中。所有写入限定新临时根/本轮报告，显式 HOME/USERPROFILE/TEMP/Runtime/Recent；禁用插件自动加载与 pyc。父进程审计钩子拒绝真实 Abaqus 入口；离线 Standard 测试拦截所有进程创建；Windows 替身在子 owner 中替换 native creator，仅允许固定 Python worker，禁止无管理回退。没有运行旧 Run022 清理脚本。

复现：在**新的审核副本**中执行本轮 `prepare_snapshot.py`（拒绝覆盖已有验证根，核对所有 source SHA），随后用 `run_regression.py <mode> <新批次名>`。选集见脚本固定字典；控件逐项以第三参数指定实际测试名，Classic 单项用 `legacy_single`。不直接全仓 pytest，不运行历史 docs 实验脚本。

## 收尾及保留

13 个本轮新验证根完整保留，9,309 个文件均在 `local_verification/`，不在提交白名单和安装包中。夹具按自己记录的句柄/PID/创建时间正常收尾；部分明确故障测试只对自己创建的替身制造崩溃，未终止用户进程。Windows 测试 PASS 包含句柄关闭和服务停服断言。

只读审计 857 组记录身份（含注入身份），当前 854 不可确认、3 身份不匹配、0 匹配存活；586 组另有持久退出记录。**查不到进程不补写历史退出**，当前查询不能宣称所有域外进程闭合。详细本地 `NEW_TEST_CLEANUP_REVIEW.json` 不进发布包。

保留 311 个 DPAPI 容器、2 个固定明文负例；未发现保留的随机明文 credential/operator_token。未解密容器；测试服务临时可用连接材料由各自 fixture 收尾。采集到的凭据值与日志/JUnit 比对为 0 匹配，不宣称通用秘密检测完备。历史 45 根与 RC-G01 四根未清理、未操作其进程。

## 未执行

真实 Abaqus/ODB/生产恢复、旧 owner/历史实例活性认证、Windows 注销重启、其他用户/主机部署、全量历史实验脚本均未执行。MCP 本轮不新增写接口；既有源码及边界核对，不把本轮选集宣称所有可选插件环境全覆盖。真实 Solver 预算和实际调用均为 0。
