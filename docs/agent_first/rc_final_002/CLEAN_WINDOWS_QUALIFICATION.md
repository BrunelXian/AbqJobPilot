# 干净Windows资格：NOT_TESTED

2026-10-27仅做只读发现，详见VM_DISCOVERY.json。宿主为Windows11家庭版中文版10.0.26300；Get-VM、WindowsSandbox.exe、VBoxManage、vmrun未发现，vmms/vmcompute未发现；VirtualMachinePlatform报告InstallState=2，HypervisorPresent=True。后者不证明有可用VM。未做全盘VM文件扫描，未假定外部测试机不存在。

没有用户指定且当前可访问的独立Windows11环境，因此18项干净环境实测均为NOT_TESTED。没有启用Windows功能、创建系统用户、安装虚拟化软件或修改系统设置。同机新目录和两个已有解释器的通过记录不替代此项。

Microsoft说明Windows Sandbox不支持Home版；即使未来使用已有Sandbox，它也是临时会话，退出即丢失运行上下文，不证明持久VM、注销/重启恢复或生产部署。[官方范围](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox)

## 精确后续环境

建议由用户提供已允许开发测试的独立Win11 x64 VM：4 vCPU、8GB内存、80GB磁盘（测试建议配置，并非产品最低保证），普通交互测试用户，可写C盘测试根，无Abaqus、历史Project、D盘开发环境或宿主凭据挂载。记录真实版本、权限、虚拟化平台和Job宿主条件。保持桌面登录；不测试注销/关机。

安装测试用CPython3.12.10 x64及Tk，使用官方签名安装程序，仅在guest内安装，不改宿主。验证签名和下载SHA并记录；本轮没有下载或安装。[官方3.12.10下载](https://www.python.org/downloads/release/python-31210/)。在guest专用目录建立venv，明确记录绝对解释器、版本和Tk patchlevel。只有可选MCP和测试控制器需要在guest venv安装审查后的pytest9.1.0、mcp2.3.0及其依赖，保存实际依赖版本/来源；普通GUI/owner不用pytest。

## 操作顺序与证据

1. 只转入本轮ZIP、BUILD.json和受审测试支持包，不共享宿主仓库、私人凭据或历史测试目录。核对ZIP SHA `7972e961e104aafc99fac6c6fd7e947b3bb67424892783a14a4933552332d047`。
2. 解压到含空格目录，如 `C:\RC F02\App One`，逐项比对BUILD.json。将应用目录搬至 `C:\RC F02\Moved App` 后再次核对，从另一个cwd启动。不得从原Dev导入源码。
3. python-path.txt配置guest venv的绝对python.exe，运行 `-I -B launch_gui.py --check`。记录READY以及没有服务/Grant产生。另用独立启动器副本指定不存在解释器，记录可见错误及退出码2。
4. 双击正常VBS。验证Cockpit、Classic双向切换、English默认和中文设置重开；fr/de仍Preview。保留原始尺寸截图、GUI与启动器身份。
5. 用正常New Project创建guest新目录；检查0 Grant/0 Run/PAUSED和NOT_RUNNING。明确Start Service；独立Python客户端连接并核对Project/owner。
6. 仅由可信TEST设置登记固定Python ProcessFixture，不登记Standard配置或真实Grant。通过公共客户端提交一次；记录回执和启动次数。
7. worker运行时正常关闭GUI与启动器，保存退出证据；以PID+创建时间+image核对原owner/worker继续存活且日志增长。重开同Project/Run，不重新提交。
8. worker自行完成，核对受管范围提交、槽位释放和独立验证维度。明确安全停服、owner退出，再启动并核对PAUSED及历史保留；不把停服当成Solver结束。
9. 检查只读Crash Recovery诊断与Preview，revision/Grant/槽位不变。CLI/MCP按既有格式使用临时Classic Project，不能将新执行存储误当旧Project；MCP仅五项只读/预览。
10. 对无Abaqus环境核对未授权、TEST_ONLY/真实Grant分离和实际进程白名单；不得安装或运行Solver验证。服务/进程无法安全收尾时停止对应步骤并保存证据，不Kill或删除锁。
11. 精确核对本次创建的进程和私有凭据，导出脱敏报告。Sandbox必须先保存证据，再人工结束会话，且仅在本次任务无活跃进程后。

本地提供的测试支持运行器采用与RC-F01相同的固定Python测试与真实GUI接缝，供新guest复验；它不是正式产品启动器，也不授予生产执行权。实际执行记录、错误迭代、环境信息和SHA均需回传后才能关闭此P1。宿主本轮没有执行以上guest步骤。
