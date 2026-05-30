# abqjobpilot

`abqjobpilot` 是一个面向 Abaqus `.inp` 文件的桌面队列运行与监控工具。它适合科研、仿真批处理、参数扫描和多策略算例管理：把一批 Abaqus job 放进队列，按顺序执行，实时看进度、日志、结果和资源占用。

![abqjobpilot GUI](sample.png)

## 主要功能

### 1. Abaqus Job 批量队列管理

- 支持单个 `.inp` 加入队列。
- 支持按文件夹批量扫描 `.inp`。
- 支持队列顺序执行，避免手动一个个提交 job。
- 支持 `datacheck` 后再执行 full run。
- 支持随时 `Stop After Current Job`，当前 job 跑完后自动停止队列。
- 支持跳过选中的 queued job。
- 支持打开当前 job 的工作目录。
- 每个 job 的输出仍保存在 `.inp` 所在文件夹，符合 Abaqus 原始使用习惯。

### 2. 实时监控与诊断

- 当前运行状态：job、batch、strategy、phase、step、increment、analysis time、ODB size、elapsed time。
- 实时读取 `.sta` tail。
- 实时读取 console log tail。
- 结果表显示 completed、warning、failed 等状态。
- 一键复制 console log，用于发给 AI 或同事快速诊断。
- 显示 CPU、内存、GPU 占用，便于判断机器是否空转或资源过载。

### 3. Agent Prompt 友好

`abqjobpilot` 内置 Agent Command Console，不是系统 shell，只接受安全的内部命令。

你可以把任务需求发给 ChatGPT、Codex 或其他 AI，让它生成如下命令，然后复制回 `abqjobpilot`：

```text
enqueue --inp "D:\path\Job_xxx.inp" --cpus 14 --gpus 1
enqueue-folder --folder "D:\path\strategy_folder" --pattern "*.inp"
list
help
clear
```

Console 支持：

- `Copy AI Prompt`：复制给 AI 的指令模板。
- `Paste`：从剪贴板导入 AI 生成的命令。
- `Paste & Run`：导入并立即执行命令。
- 多行命令批量执行。
- 未写 `--cpus` / `--gpus` 时自动使用 Settings 中的默认配置。
- 禁止执行任意系统命令，避免误删文件或误运行危险命令。

### 4. 更省资源，提高有效计算效率

很多 Abaqus 批处理浪费时间不是因为单个 job 太慢，而是因为：

- 人需要手动等待上一个 job 结束。
- 夜间或无人值守时没有及时提交下一个 job。
- `datacheck` 失败后仍然继续错误流程。
- CPU/GPU/内存占用不可见，机器资源没有被合理安排。
- 日志诊断慢，失败原因发现不及时。

`abqjobpilot` 通过队列顺序执行、状态监控、资源面板和快速诊断，减少人工等待和空转时间。在批量算例、参数扫描、策略池生成等场景中，通常可以提升约 `15%-40%` 的有效计算吞吐效率，具体取决于 job 数量、单个 job 时长、机器配置和人工值守情况。

## 安装与启动

```powershell
git clone https://github.com/BrunelXian/abq_job_pilot.git
cd abq_job_pilot
python run_gui.py
```

当前版本核心功能只依赖 Python 标准库。

## Abaqus 路径设置

每台电脑的 Abaqus 安装路径可能不同。第一次使用时，请打开 GUI 中的 `Settings`，设置本机 Abaqus command 路径，例如：

```text
D:\ABAQUS2024\Commands\abq2024.bat
```

也可以在 Settings 中设置：

- 默认 CPU 数量，例如 `12` 或 `14`。
- 是否使用 GPU。
- 默认 GPU 数量，例如 `1`。
- 是否默认执行 `datacheck`。
- 是否默认执行 full run。

## Agent Command 示例

加入单个 job：

```text
enqueue --inp "D:\Projects\models\batch_a\strategy_01\Job_test.inp" --batch batch_a --strategy strategy_01
```

指定 CPU/GPU：

```text
enqueue --inp "D:\Projects\models\batch_b\strategy_02\Job_test.inp" --cpus 12 --gpus 1
```

加入整个文件夹：

```text
enqueue-folder --folder "D:\Projects\models\batch_c\strategy_03" --pattern "*.inp"
```

查看队列：

```text
list
```

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

这些 runtime 文件不会上传到 GitHub。

## 安全设计

- Agent Command Console 只解析白名单内部命令。
- 不执行任意 PowerShell、cmd、Python 或 shell 命令。
- Abaqus 只会在用户点击 `Start Queue` 后开始提交。
- `.venv`、runtime 文件、Abaqus 大型输出文件默认被 `.gitignore` 排除。

## 测试

运行离线测试：

```powershell
python -m unittest discover -s tests -v
```

测试不会提交 Abaqus job。

## 当前阶段

当前版本是可用 MVP，重点覆盖：

- GUI 队列管理。
- Abaqus 顺序执行。
- 实时日志监控。
- Agent Prompt 友好命令入口。
- 基础资源监控。

后续计划：

- 更细的失败类型识别：license、input、numerical、interrupted。
- 更完整的 resume / rerun。
- 更现代的 GUI 主题。
- SQLite 队列后端。
- Windows 打包发布。
