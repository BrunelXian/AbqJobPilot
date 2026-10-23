# Run 010 — 已验证的离线入口与待批准动作

所有命令中的Python均为已登记解释器。下面两个入口**只读/离线**，不调用Abaqus、数据库或执行服务；示例内保留进程/数据库/网络调用审计哨兵。已在所示非仓库cwd以独立Python进程运行，见 `PUBLIC_CLIENT_PROCESS.json`、`PACKAGE_RECHECK_PROCESS.json`。

## 实际已运行：公开prepare、inspect及JSON导出

```powershell
Set-Location 'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\client_cwd'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B `
  'D:\Projects\abqjobpilot_dev\examples\agent_first\abaqus_offline_preview.py' `
  --source 'D:\Projects\abqjobpilot_dev' `
  --project 'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\materials\project.json' `
  --profile 'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\materials\profile.json' `
  --engineering-root 'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\engineering' `
  --submission-cwd 'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\engineering' `
  --main-input axial_bar.inp --job r010_bar_a19d17ea `
  --support-profile windows-standard-axial-print-v1 `
  --export-root 'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\materials'
```

返回PREVIEW_PREPARED，实际客户端PID16756、venv启动器PID7296；已退出并关闭句柄。现在同名 `preview.json` 已存在，**重跑上面带导出的原命令会拒绝覆盖**。如只想重新读取检查，去掉 `--export-root` 即可，不删除冻结文件。`--source`只影响该进程导入路径，不安装依赖或改变全局PYTHONPATH。

## 实际已运行：冻结包只读复核

```powershell
Set-Location 'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\client_cwd'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B `
  'D:\Projects\abqjobpilot_dev\examples\agent_first\abaqus_probe_review.py' `
  --source 'D:\Projects\abqjobpilot_dev' `
  --manifest 'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\materials\experiment_manifest.json' `
  --expected-manifest-digest 'sha256:04ed053817a7d05c2355d9a93a41216309bb5d28a235f569a250eea6ee4af2b6'
```

返回OFFLINE_PACKAGE_UNCHANGED；实验目录内的文件摘要前后完全相同。32KiB预览、64KiB清单读取及最多64项/每项16MiB的材料复核有界。该入口不将匹配摘要解释为已批准、Runtime通过或输出已预留；不生成可执行Plan。材料变化/同名旧输出分别拒绝 PACKAGE_CHANGED/OUTPUT_EXISTS；缺失或无法读取返回PACKAGE_UNAVAILABLE，输入路径不支持仍明确拒绝。

manifest的 `execution_authorized=false` 是本次准备时事实，**不要把它改成true作为批准方式**。用户后续批准应引用完整摘要；只允许该清单声明的一次性人工/受审控制器实验，不成为产品执行许可。换材料、输入、环境策略或参数都须重新冻结和批准。

## 尚未运行：精确候选动作

实验ID `abq2024_r010_a19d17ea`；Job `r010_bar_a19d17ea`。一次 `D:\ABAQUS2024\Commands\abq2024.bat` 的 Standard analysis，CPU=1、GPU=0、memory="2048 mb"、interactive。工作目录是工程根，input=axial_bar.inp，scratch是工程根的scratch子目录。完整绝对路径、显式环境字典、固定Windows command_line、stdout/stderr路径在 `EXPERIMENT_MANIFEST.json:body.windows_call/environment_policy`。该命令行仅作为待审数据保存，**未执行**。

调用预算：analysis=1；datacheck/syntaxcheck/CAE/Viewer/Abaqus Python/信息或许可证探测/其他模型/重试/continue/recover=0。独立结果读取仅普通文本工具读取本次DAT；没有隐含Abaqus后处理。300秒停止等待、不自动kill、不删除输出scratch；不含停止命令。完整策略见 `OBSERVATION_AND_ACCEPTANCE_PLAN.md`。

准备资料不是通用任务SDK或真实Backend，也没有审批GUI；它把首次实验动作固定为可审查清单。保留2024关键词文档缺口、Intel前置环境风险以及真实成员集合/退出/许可/结果版式未知，实际运行才能取得这些证据。
