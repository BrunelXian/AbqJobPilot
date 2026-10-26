# 无Solver测试支持包使用

`AbqJobPilot-RCF02-no-solver-qualification-kit-003.zip` 是独立的工程验收工具，不是产品运行包；包含同一114文件运行快照、明确列出的测试源码和控制器，无测试数据库或凭据。内容见QUALIFICATION_KIT_003.json和包内KIT_CONTENTS.json。旧未编号包/002保留作追踪，不是最终验收输入；003纳入已审查的最终GUI测试守卫、此说明，并准确标记Tcl patchlevel（Tk可用性由启动预检及原生GUI测试另行验证）。

在用户明确指定的干净guest内执行；本轮没有可用guest，以下流程尚待真实VM验收。安装Python只允许guest内；不要在宿主执行pip安装。

1. 从已核对签名的官方CPython3.12.10 x64安装创建guest专用venv，例如 `C:\RC F02\.venv`，包含Tk。明确使用该venv绝对路径。
2. 解压测试支持包到新目录 `C:\RC F02\Qualification`。逐文件比对KIT_CONTENTS.json，先审查requirements-qualification.txt；仅guest venv中安装pytest9.1.0、mcp2.3.0。保存实际依赖版本及下载来源/摘要。这里的版本固定不等于全部间接依赖wheel已锁定，离线部署应另行冻结wheel集合。
3. 确认桌面保持登录、无Abaqus、没有宿主数据共享，从该目录运行：

```powershell
& 'C:\RC F02\.venv\Scripts\python.exe' -B .\qualify.py
```

控制器运行既有固定Python测试，使用相对路径定位 `qualification\Moved App F02`；新Project/Runtime/Recent位于测试包中新建的测试根。产品模块必须从运行快照导入，有副作用的子程序受现有fixture白名单约束，拒绝Abaqus创建。每个阶段独立进程，失败停止且不覆盖旧报告；不要在同一个解压根重复运行，需保留失败证据并明确复验。

输出GUEST_ENVIRONMENT.json、GUEST_QUALIFICATION.json、各阶段JUnit/IMPORTS/ROOT及原生截图。环境是否为干净VM必须由操作者补充平台、全新用户及无旧Project的证据；控制器不会自行认定干净环境。产品GUI的明确New/Start、worker存活、关闭重连、安全停服等由现有测试真实点击与OS身份验证，并非模拟服务。

测试根会包含新生成的本机认证材料。不要整体上传测试目录或当作发布包。正常fixture会关闭自己的进程和句柄；其余私有测试文件须先核对确切身份，再按已审查清理流程处理，不能批量Kill或递归清理历史目录。只回传去敏的清单、JUnit、截图及身份/退出证据。实例未能安全收尾时保留现场并报告。

MCP验收只覆盖其五个既有只读/预览工具，使用相应临时Classic格式；不能把它当作新Project的Solver执行工具。所有Test Grant仅用于固定Python，不能兑换真实授权。Sandbox若另有授权可用，关闭会话会销毁环境，必须先保存脱敏证据；不据此宣称系统重启恢复通过。
