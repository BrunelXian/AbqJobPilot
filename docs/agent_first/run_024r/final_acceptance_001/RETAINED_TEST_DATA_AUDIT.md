# 45 个历史测试目录：保留、隔离及发布排除

## 范围及结果

仅使用 `integration_001/CLEANUP_BEFORE.json` 已登记的 **45 个绝对路径**，没有扫描整个 Temp 或其他 Project。完整逐目录位置、数量、后缀分类、字节数、进程身份来源见 [LEGACY_TEMP_AUDIT.json](LEGACY_TEMP_AUDIT.json)，其中绑定了原清单 SHA-256。

- 45 个目录全部存在，均为 `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run024R_*` 的明确隔离测试根。
- 9,105 个普通文件，141,730,293 字节，约 135.16 MiB。无读取失败。三个 reparse link 未跟随，目标文字均指向同一测试根内夹具；详见 [REPARSE_REVIEW.json](REPARSE_REVIEW.json)。不是向 Stable 或生产目录扩展访问。
- 分类包含测试 JSON/事件与证据（5,725）、文本（994）、锁（679）、SQLite 测试存储（663）、bin（230）、固定输入副本（186）、截图（141）、日志（120）、JSONL（114）及离线 DAT/STA/MSG 样本（51/48/47）。这些输入和输出属于此前安全测试材料；本轮没有求解。
- 全部位于 Git 工作树之外，不属于当前 Git 可提交文件集合。没有复制其中数据库、凭据或结果到产品运行目录。

## 凭据

有 161 个 JSON 凭据字段候选文件：160 个 Windows 用户绑定加密容器；另 1 个是 `test_windows_dpapi_binding_tamper_and_plaintext_downgrade` 的**明文降级负例**。

唯一明文文件：

`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run024R_product_z65qejw5\cases\test_windows_dpapi_binding_tam0\new\private\lifecycle.json`

源码 `tests/test_product_project.py:120` 明确创建新空 Project，然后将 profile 写成明文以断言 `_profile()` 拒绝 `LOCAL_CREDENTIAL_UNAVAILABLE`。该测试未启动 Supervisor，没有绑定活动 owner，也未生成 Solver 许可。不能将此文件称为“已加密”，也不能把它打包成普通示例。

根目录与所有 161 个候选文件均进行只读 ACL 检查，见 [TEMP_ACL_AUDIT.json](TEMP_ACL_AUDIT.json)、[CREDENTIAL_FILE_ACL.json](CREDENTIAL_FILE_ACL.json)。未发现 Everyone/普通 Users 读权限；明文负例仅当前 Windows 用户及 SYSTEM 继承 FullControl。其他容器的权限主体为当前用户/OWNER RIGHTS/SYSTEM/Administrators。审计只记录字段类型、路径和 ACL，不输出秘密或 ciphertext。该检查不是对同一 OS 用户或管理员的安全隔离承诺，也不声称已穷举所有任意编码秘密。

结论：未发现凭据对普通用户或 Git/发布资料泄漏；保留的明文负例必须作为敏感测试数据排除。没有修改凭据、ACL 或配置，也没有用凭据连接任何服务。

## 进程

从已有证据提取 887 个 PID + 创建时间 + image_path 身份，仅对这些身份做只读查询：856 PROCESS_UNAVAILABLE、28 IDENTITY_MISMATCH、3 QUERY_FAILED、0 匹配存活。

三个 QUERY_FAILED 不直接判定退出。另查其原始证据，均有同一 PID、创建时间和 image_path 对应的保留句柄 exit=0：

| PID | 创建时间（100ns） | 已有退出证据 |
|---|---:|---|
| 35176 | 134374249246655143 | `test_public_disposition_lost_r0.json` → `all_retained_handle_exits[3]` |
| 4220 | 134374245259659467 | `NATIVE_EVIDENCE.json` → `final.process_exits[3]`；fixture cleanup_exits[0] |
| 14280 | 134374247584364133 | `normal_gui_lifecycle.json` → `gui_B_exit.gui` |

完整来源和 JSON 定位见 [UNCERTAIN_QUERY_REVIEW.json](UNCERTAIN_QUERY_REVIEW.json)。当前查询失败的原因不作推定；没有将 PID 消失或复用等同于未知后代已退出。本次未发现遗留的身份匹配测试进程，历史固定夹具收尾记录仍保留；该结论不覆盖全机或未记录的任意进程。

## 发布排除和处理决定

**保留，不删除。** 此前递归删除被自动审批拒绝，原始理由 `blocked by policy`；本轮未再次提出删除命令，未提升权限或更换删除手段。

下一步 Git 检查点/RC 打包必须采用源码及获选文档白名单，排除：

1. 本报告列出的全部 45 个根，以及本轮新增 `AbqJobPilot_CockpitFinal_*` 根。
2. 测试/产品 `private` 凭据容器、bootstrap/连接交接文件、数据库、锁、运行目录、真实和替身工程输出。
3. 不沿文档中的绝对路径或 reparse link 收集归档文件。

无需为这些仓库外路径更改 `.gitignore`；不能以“Git 不包含”替代发布打包器的排除规则。目录尚占用磁盘，这是已记录的清理待办，不构成本轮已发现的凭据泄漏或活跃进程 P0。没有授权或执行清理绕过。
