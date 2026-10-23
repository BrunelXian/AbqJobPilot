# Run 010 — Runtime 静态取证与最小接缝

本轮没有调用任何 Abaqus 入口。取证由 Dev `config.py:ABAQUS_CMD` 的明确字面路径开始，沿包装器和站点文件的明确引用只读展开；没有查 Stable、全盘搜索安装、读取真实工程或求值 `.env`。文件身份见 `RUNTIME_STATIC_IDENTITIES.json`，必要安装登记投影见 `INSTALL_METADATA.json`。摘要只能发现变化，不是签名或运行证明。

## Runtime 证据层级

| 层级 | 实际来源与结论 | 尚不能证明 |
|---|---|---|
| Dev 配置声明 | `abqjobpilot/config.py:ABAQUS_CMD` 为 `D:\ABAQUS2024\Commands\abq2024.bat`；只读文本，没有 import config | 路径可运行、有效许可证 |
| 包装器 | 182 字节 BAT，先 `call D:\ONEAPI\compiler\2022.2.0\env\vars.bat intel64 vs2022`，随后 setlocal，设 ABA_DRIVERNAME 为批处理文件名，将 `%*` 交给 `D:\ABAQUS2024\product\win_b64\code\bin\SMALauncher.exe`，最后 endlocal | 实际子进程集合、退出码传播、许可等待、错误输出 |
| 安装登记 | `product\InstallData\registry.json` 声明 ShortName=2024，LongName=SIMULIA Established Products 2024，Level/GAlevel/SPlevel=426/B426/426，PkgId=20230927T185011Z，平台 win_b64；Installed.cmp 列出 Standard solver | 文件完整性认证、已运行过这个版本；登记的 Trusted 字段不作独立信任证据 |
| PE 元数据 | SMALauncher FileVersion/ProductVersion=6.426.0.23224，OriginalFilename=SMALauncher.exe | Solver 实际版本与结果 |
| 随附配置和说明 | `SMA\site\abaqus.arg` 的 analysis 参数表含本次所用 job/input/analysis/interactive/cpus/gpus/memory/scratch；`SMA\info\memory.info` 说明 memory 的 MB/GB/百分比表达 | 参数的完整运行行为和 OS 资源硬限制 |

选用 **2048 MB** 的 Abaqus 内存请求、CPU=1、GPU=0。随附 memory.info 推荐机器至少2GB物理内存，并说明 memory 是 Standard 分析及预处理的请求上限；这不是所有辅助进程 RSS、OS 总内存或主机租约的硬限额。没有查询当前可用许可证或资源。

## 环境与静态未知

包装器的 Intel call 在 setlocal 之前，之后没有 errorlevel 门禁。vars.bat 会依赖 VS 环境或具体安装路径、调用 vcvarsall、修改 PATH/LIB/INCLUDE 等；还可能条件调用 fpgavars。仅沿文件内明确写出的 VS2022 Professional/Enterprise/Community 路径检查 vcvarsall，三处均不存在（见 `INDIRECT_CONFIG_PATHS.json`），不等于机器没有其他 VS 安装。未搜索其他位置。

冻结的子进程环境不继承当前 shell 的 VS/编译器变量，因此这个 Intel 前置步骤很可能报 VS 未找到；BAT 随后仍有可见的 SMALauncher 调用。本模型没有用户子程序，不需要编译；该静态事实作为**首次实验的已知启动链风险**交给批准者，不自动修复环境，不改用另一个入口，不因其报错附加重试。最终运行证据必须区分 Intel 前置错误与分析阶段结论。若实际链没有进入 Standard，记录失败并结束本次预算。

站点 `abaqus_v6.env` 使用 driverUtils 的 locateSite/locateFile 动态选择并执行 basic_v6、mpi_config、平台文件、graphicsConfig、jleConfig、custom_v6。custom_v6 又引用许可配置和动态文档配置。basic_v6 可见 MPI/parallel 默认值；jleConfig 含布局偏好。上述源码仅读取、不执行；默认值是否被 CPU=1 等显式参数覆盖、是否出现辅助成员，留待观察。许可配置只记录来源类别，不导出服务器、令牌或完整配置。未读取用户 home 的环境文件。

候选调用采用 manifest 中的**显式子进程环境字典**，不继承完整父环境；HOME/USERPROFILE/TEMP/TMP/APPDATA 等指向本次隔离目录，不创建 Abaqus 环境脚本。站点安装配置由程序正常加载，仍属于动态影响源。Windows 用户访问令牌没有被隔离；此方案不是安全沙箱，也不能保证供应商所有辅助文件都严格落在 TEMP 中。已知输入、输出、scratch、观察和提取目标均在实验根内。发现意外写入/访问只能报告，不能本轮修改安装或全局配置。

## 2024 与 2025 的适用边界

2024 在线关键字与执行手册此次仍返回403；未从2025文字推定2024所有参数相同，也未虚构版本差异清单。本机2024随附的参数表及 memory.info 是命令名/内存单位的版本对应补证。INP 的 T3D2、NODE PRINT、EL PRINT 语法参考是下列**厂商2025手册镜像**；能否由本安装接受，是这一次 analysis 的待观察结果，绝不另外追加 syntaxcheck/datacheck。

- [NODE PRINT (2025)](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEKEYRefMap/simakey-r-nodeprint.htm)：节点表、U/RF 输出；本算例使用全部节点、GLOBAL=YES、FREQUENCY=1、SUMMARY=NO、TOTALS=NO。
- [EL PRINT (2025)](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEKEYRefMap/simakey-r-elprint.htm)：BAR 集的积分点 S 表，SUMMARY/TOTALS 关闭。
- [Truss library (2025)](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEELMRefMap/simaelm-r-trusslibrary.htm)：T3D2 的活动自由度1/2/3，面积由 SOLID SECTION 定义，轴向 S11。
- [Execution (2025)](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEEXCRefMap/simaexc-c-analysisproc.htm)：job 输出命名、显式 input、interactive 与 scratch 的候选解释；本机行为仍须实测。

没有 INCLUDE，故跨版本相对 INCLUDE 规则不是本算例运行前提。没有 ODB API 提取、Python2/3供应商解释器、2025新增算法、用户子程序编译或远程队列依赖。2024文档不可用这一事实继续保留在 preview 的未解决项中，不悄悄改成已核验。

## 实际复用与变更

| 文件/函数 | 处理 | 权限及副作用 |
|---|---|---|
| `abaqus_preview.preview.prepare/inspect/export_preview` | 复用内容摘要、显式路径、白名单、状态与导出；增加可选 support_profile_version | 读输入；只有显式 export 写指定 JSON；不连数据库 |
| `abaqus_preview.inputs._block/read_inputs` | 新独立档案 `windows-standard-axial-print-v1` 只加两种固定打印请求 | 原 `windows-standard-static-subset-v1` 默认参数、规范化内容和拒绝行为保留；不增加执行能力 |
| `examples/agent_first/abaqus_offline_preview.py` | 加 `--support-profile`，其余公开调用、审计哨兵不变 | 普通离线客户端；无批准/提交 |
| `examples/agent_first/abaqus_probe_review.py:review` | 新增只读材料摘要/预览/旧输出检查 | 从独立审查摘要核对冻结 manifest；不执行、不产生许可，不预留目录；检查后仍可能竞争 |
| `execution.service._request/_check`、授权工厂、Supervisor | 不修改 | 只接受已有 Fake/固定Python Backend；新预览仍不能提交，不降级执行 |
| `execution.process_handles.ProcessReference` | 后续控制器可复用非继承 OS 引用、创建时间/映像核对及退出码观察 | `cleanup=False`；无自动 terminate；缺少引用或进程消失保留 UNKNOWN |
| `process_identity.py`、旧 Runner/GUI | 仅静态了解，不导入/调用 | 不引入默认 Runtime 或旧执行链 |
| `execution.process_validation` | 不作为 Abaqus 验证器复用 | 只适用固定Python夹具，不能验证真实 DAT/ODB |

新输出档案要求一个 NODE PRINT（精确 FREQUENCY=1/SUMMARY=NO/TOTALS=NO/GLOBAL=YES，数据行依次 U、RF）和一个 EL PRINT（再加 ELSET=BAR/POSITION=INTEGRATION POINTS，唯一数据行 S），且位于唯一 STATIC 步内。其他输出参数、变量、位置、重复或缺失拒绝。原 schema、应用版本、ExecutionPlan/Grant 摘要、API/数据库 schema 均不改变。预览档案是词法范围，不证明模型合理性；本次唯一输入另有人工解析校核。

材料复核中的安装文件允许Windows系统组件已有的NTFS硬链接（例如cmd.exe）；只读核对摘要、双读内容和文件身份/大小/时间，拒绝重解析路径，不宣称它们在未来运行时仍被锁定。工程INP仍由原公开prepare使用禁止多硬链接的固定引用读取。两种策略不混用；首次完整包复核发现cmd.exe的合法硬链接后进行了这项最小区分，未放宽INP规则。
