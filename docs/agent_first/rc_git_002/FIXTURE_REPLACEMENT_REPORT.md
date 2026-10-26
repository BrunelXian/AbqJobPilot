# 可复现回归素材闭包

| 原始素材（本地保持不变） | 替代 | 覆盖 |
|---|---|---|
| `docs/agent_first/run_011/result_review_001/ORIGINAL_DAT.bin` | `tests/fixtures/synthetic/standard_axial_cp936.txt` | CP936 月字页头、完整固定步/增量、指定节点/积分点、原三项值和容差、完整完成尾部；保留缺失 RF 行不推零 |
| `docs/agent_first/run_007/examples/historical_invalid_after.json` | `tests/fixtures/synthetic/diagnostic_v2.json` | 严格 v2 envelope、旧格式缺少 managed 字段、两种允许的 validation source、摘要重算、额外字段拒绝 |

生成器 `tests/fixtures/synthetic/generate.py` 无历史输入读取，固定时间/身份/数值，无认证内容、用户路径或真实进程。静态文件与生成结果一致性有测试；测试读取冻结文件，不在运行时用当前 schema 偷换历史预期。

DAT 使用 `.txt` 是为了不被现有 `*.dat` 输出忽略规则掩盖；写入固定 Python 替身工程时仍按 Plan 生成 `.dat`。不改变 `.gitignore`。文件首行明确 SYNTHETIC，生产解析器仍原样限定标题/实体/输出语法；没有放宽解析器。v2 兼容样本不声明自身来自真实 Run。

变更引用：`test_standard_backend`、`test_standard_managed`、`test_product_standard_control`、固定 worker `run013_process`、`test_public_client_example`、`test_standard_pair_client`；两个 Windows 证据测试的来源标签改为 SYNTHETIC_DAT，避免新测试伪称历史真实 DAT。

原有成功/空输入/截断/重复整文件/缺少完成标记断言保留；另加数值失败、错误步、积分点、节点、重复行、缺失 RF、未知字段拒绝和脱敏测试。三项目标仍为 U1=0.01±1e−6 mm、S11=1±1e−4 MPa、RF1=−1±1e−4 N。

局限：合成文件不覆盖原 10,334 字节文件的所有空白、分页、安装信息。历史 Run011 的真实编码/版式验收仍是历史证据，不能改称本轮实测。旧冻结历史复核脚本仍可引用原件，但不属于发布源验证选集；维护中的 `tests/*.py` 已无两份原始路径引用。

独立源码副本仅由 455 项精确文件建立，未复制两份原件；安全回归在该副本运行。原件前后 SHA 核对见 `PRESERVATION.json`，替代文件大小和 SHA 见最终白名单。

其他受控工程 fixture 逐项保留：`tests/fixtures/Job_test.inp`（76 bytes，旧 Queue 固定哑输入）、`docs/agent_first/run_010/axial_bar.inp`（420 bytes，已公开的固定轴向杆模型，无外部 include）、Run010 的冻结清单/静态入口身份（测试只读模板，不能授权运行）。均不进入普通安装包的工程输出目录，也不将其他真实 DAT/ODB 一概纳入 Git。
