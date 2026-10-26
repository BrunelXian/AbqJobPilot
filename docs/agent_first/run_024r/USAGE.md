# Run024R 原生视觉原型

这是供视觉确认的独立Tk程序。**未替换正常Dev入口，无真实Project、Supervisor、Runner或Abaqus连接。**

双击本目录 [Open_Cockpit_Prototype.vbs](Open_Cockpit_Prototype.vbs)。启动固定登记解释器`D:\XianLab\envs\LangChainEnv\Scripts\pythonw.exe`及本目录`cockpit_prototype.py`。不要把它当作正常`Open_Dev_GUI.vbs`。VBS入口已静态核对；实际测试通过同环境python.exe直接运行原型。

## 建议两分钟评审

1. 看默认Queue左/Results右与两路日志是否符合原Classic习惯。
2. 拖动三组分隔条；选择结果行、双击，查看Agent Command Inspector；Esc收起。
3. 点击Agent Command或F2，在五个子区切换；Project & Service的管理按钮为禁用占位。
4. 点击Classic Queue，再点击Execution Workspace返回；这里只换模拟显示，不启动原Classic执行器。
5. 右下Prototype sample选择empty/interrupted/disconnected/complete；empty中可Load sample。
6. 切换English/中文/法语Preview/德语Preview。检查未知、失败和未验证是否可区分。
7. 正常关闭原型窗口即可，不影响任何服务。

表格筛选可演示；列表数量是固定样例总量，不是产品分页计数实现。日志为固定模拟文本，未验证实时刷新、Follow行为或大量记录性能。New/Open只展示功能归属，不创建文件。没有可执行输入框、Grant、Recovery Apply、Retry或Resume。

## 已核对的PowerShell命令

```powershell
Set-Location -LiteralPath 'D:\Projects\abqjobpilot_dev'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B '.\docs\agent_first\run_024r\cockpit_prototype.py' --size 1366x768
```

德语放大布局检查（仅更改该原型Tk scaling，不改变Windows设置）：

```powershell
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B '.\docs\agent_first\run_024r\cockpit_prototype.py' --size 1366x768 --locale de-DE --scale 1.5 --scenario interrupted --drawer recovery
```

原型自检/截图入口：`check_prototype.py`。它只启动有限的原型子进程，输出位于本目录`screenshots`及`PROTOTYPE_CHECKS.json`；不启动产品服务。无需运行自检即可评审现有截图。

参考对照：[1600×900](screenshots/COMPARE_1600.png)、[1366×768](screenshots/COMPARE_1366.png)。详细范围和限制见[VISUAL_REVIEW](VISUAL_REVIEW.md)。
