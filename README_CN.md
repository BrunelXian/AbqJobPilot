<h1 align="center">Abaqus Job Pilot</h1>

<p align="center"><strong>对 Agent 友好的 Abaqus .inp 队列运行与实时监控工具。</strong></p>
<p align="center"><strong>批量加入、顺序执行、随时中止、实时 STA/日志诊断、资源感知调度。</strong></p>

<p align="center">
  <a href="README.md">English README</a>
</p>

<p align="center">
  <a href="#"><img alt="Python" src="https://img.shields.io/badge/Python-3.9%2B-blue"></a>
  <a href="#"><img alt="Platform" src="https://img.shields.io/badge/Platform-Windows-lightgrey"></a>
  <a href="#"><img alt="GUI" src="https://img.shields.io/badge/GUI-Tkinter-success"></a>
  <a href="#"><img alt="Abaqus" src="https://img.shields.io/badge/Abaqus-INP%20Queue-important"></a>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/License-MIT-green"></a>
</p>

![abqjobpilot interface](sample.png)

## 目录

- [为什么做 abqjobpilot](#为什么做-abqjobpilot)
- [核心功能](#核心功能)
- [快速启动](#快速启动)
- [Abaqus 路径设置](#abaqus-路径设置)
- [Agent Command 工作流](#agent-command-工作流)
- [输出位置](#输出位置)
- [安全设计](#安全设计)
- [测试](#测试)
- [路线图](#路线图)

## 为什么做 abqjobpilot

`abqjobpilot` 是一个面向 Abaqus `.inp` 文件的独立桌面队列运行与监控工具。它适合科研仿真、批处理、参数扫描、多策略算例池生成等场景。

很多 Abaqus 批处理浪费时间不是因为单个 job 太慢，而是因为 job 需要人工接力提交、失败发现太晚，或者夜间机器空转。`abqjobpilot` 通过队列顺序执行、datacheck 优先、实时监控、资源面板和 AI 辅助日志诊断，减少人工等待和空转时间。

在批量算例、参数扫描、策略池生成等工作流中，它通常可以提升约 `15%-40%` 的有效计算吞吐效率，具体取决于 job 时长、机器配置、队列规模和人工值守情况。

## 核心功能

| 模块 | 功能 |
| --- | --- |
| 批量队列 | 支持单个 `.inp` 加入，也支持按文件夹扫描多个 `.inp`。 |
| 顺序执行 | 按队列顺序自动运行 Abaqus job，减少手动提交。 |
| Datacheck 优先 | 先运行 `datacheck`，再进入 full run，提前发现输入问题。 |
| 安全中止 | `Stop After Current Job` 会在当前 job 结束后停止队列。 |
| 实时监控 | 显示 phase、step、increment、analysis time、ODB size、`.sta` tail 和 console log tail。 |
| 结果查看 | 单独结果表显示完成、警告和失败 job。 |
| Agent 友好 | 支持把 AI 生成的内部命令粘贴进 Agent Command Console。 |
| 资源感知 | 显示 CPU、内存、GPU 使用情况。 |
| 原生输出 | Abaqus `.odb`、`.sta`、`.msg`、`.dat`、`.log` 仍生成在原 `.inp` 文件夹。 |

## 快速启动

```powershell
git clone https://github.com/BrunelXian/abq_job_pilot.git
cd abq_job_pilot

python -m venv .venv
.\.venv\Scripts\activate

pip install -r requirements.txt
python run_gui.py
```

当前 MVP 的 GUI 核心功能只依赖 Python 标准库。

## Abaqus 路径设置

每台电脑的 Abaqus 安装路径可能不同。第一次使用时，请打开 GUI 中的 `Settings`，设置本机 Abaqus command 路径，例如：

```text
D:\ABAQUS2024\Commands\abq2024.bat
```

Settings 中还可以设置：

- 默认 CPU 数量，例如 `12` 或 `14`
- 是否启用 GPU
- 默认 GPU 数量，例如 `1`
- 是否默认执行 `datacheck`
- 是否默认执行 full run

## Agent Command 工作流

Agent Command Console 不是系统 shell，只接受白名单内部命令。

你可以把任务需求发给 ChatGPT、Codex、Grok 或其他 AI，让它生成如下命令，然后复制回 `abqjobpilot`：

```text
enqueue --inp "D:\path\Job_xxx.inp" --cpus 14 --gpus 1
enqueue-folder --folder "D:\path\strategy_folder" --pattern "*.inp"
list
help
clear
```

示例：

```text
enqueue --inp "D:\Projects\models\batch_a\strategy_01\Job_test.inp" --batch batch_a --strategy strategy_01
enqueue --inp "D:\Projects\models\batch_b\strategy_02\Job_test.inp" --cpus 12 --gpus 1
enqueue-folder --folder "D:\Projects\models\batch_c\strategy_03" --pattern "*.inp"
list
```

Console 工作流：

- `Copy AI Prompt`：复制给 AI 的命令生成提示词。
- `Paste`：从剪贴板导入 AI 生成的命令。
- `Paste & Run`：导入并立即执行命令。
- 未写 `--cpus` 或 `--gpus` 时，自动使用 Settings 默认值。

## 输出位置

Abaqus job 在 `.inp` 文件所在目录运行，因此 Abaqus 输出文件会生成在原 `.inp` 文件夹中：

```text
*.odb
*.sta
*.msg
*.dat
*.log
```

`abqjobpilot` 自己的运行状态和报告放在：

```text
runtime/
```

runtime 文件、虚拟环境和大型 Abaqus 输出文件不会上传到 GitHub。

## 安全设计

- Agent Command Console 只解析白名单内部命令。
- 不执行任意 PowerShell、cmd、Python 或 shell 命令。
- 只有用户点击 `Start Queue` 后才会提交 Abaqus job。
- runner 执行 Abaqus 时避免使用 `shell=True`。

## 测试

```powershell
python -m unittest discover -s tests -v
```

测试不会提交 Abaqus job。

## 路线图

- 更细的失败类型识别：license、input、numerical、interrupted。
- 更完整的 resume / rerun 工作流。
- 更现代的 GUI 主题。
- 可选 SQLite 队列后端。
- Windows 打包发布。
