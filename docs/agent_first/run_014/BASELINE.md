# Run014 实际基线与范围

2026-10-24；唯一工作区 `D:\Projects\abqjobpilot_dev`。开始时实际分支 **Develop**，HEAD **271c6f82fd6a4599dbae2df30d903dab2cef1f63**，工作区干净、无未解决冲突。`fb7912ec...` 是历史交接值，不执行回退。当前HEAD已包含前轮成果；本轮改动均以这个实际基线为准。

版本 `abqjobpilot/__init__.py` 为 **0.3.0.dev0**，本轮不修改。实际读取根AGENTS、环境登记、Run007/012/013说明和Run013 real_001最终证据。明确父路径的AGENTS检查未发现额外文件；没有采用其他项目协议。沿用每Run独立文档/证据目录，本次新建run_014，不覆盖历史目录。

环境 `D:\XianLab\envs\ENVIRONMENTS.md` 指向现有 LangChainEnv；绝对解释器 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，实际Python3.12.10、pytest9.1.0、Tk8.6。未安装/更新依赖。

## 保留与证据

- `before/`：修改前执行包及GUI/操作者入口源文件快照，便于审查本轮差异。
- `PROTECTED_BASELINE.json`：Run010/011/013历史文档、冻结文件、归档证据共295文件的字节摘要；排除原GUI活动view临时输出，避免把旧GUI自行刷新误认为本轮修改。最终保护复核另存，不更新这些基线。
- `CURRENT_READONLY.json`：当前真实库的严格只读事务快照，以及旧endpoint超时/记录owner身份不能匹配的当前事实；没有取得owner写lease。
- `CURRENT_CLOSEOUT_PREVIEW.json`：用新增只读评估逻辑读取同一库；原Run内容、计数、slot、gate均与初读一致；读取前后库字节摘要相同。
- 当前保护根仍为原Run013实验根；历史Runtime静态配置/安装没有读取或修改。Run010/011实验输入、尝试和输出没有清理或再次使用。

## 本轮变更

新增 `execution/closeout.py`、可信本地 `examples/agent_first/standard_closeout_operator.py`、针对性单元/Windows测试。增量修改既有service/client/supervisor/reconciliation接口、Standard路径保留检查、诊断白名单和现有GUI reader/显示。没有修改旧Runner/GUI默认Project逻辑、进程Backend启动命令、求解参数、schema或版本。

只读评估可在现有v3实验存储工作；显式行政写入复用原管理事务表，没有迁移。**没有把新逻辑应用到当前真实Run**，没有重载或重启旧owner。

## 本轮真实实例身份

- 实验 `run013_e52135d71d2c43d2a45301c586cbfb7e`
- Project `p_9204fe8fced549d28d8bd62d1b2f8455`
- instance `pi_776faf62f2d64a4ab23e83c53b665788`
- Run `r_609c9bbfd9c54b3ca2fce23bbd6059e4`
- 原回执 `req_c17228560b40411585817099ed5ddbd3`
- 原attempt `phase_5b46d6d7f0aa42bf82d3a353a4b1e359`
- 记录owner `owner_17886eb60d8349e880d61131a04be3b3`；PID17528，创建时间100ns值134372377146539267。**当前未确认其仍存活，也未取得其历史退出证据。**

目前不是“可响应owner已保留”的已确认状态。不能直接向旧PID发任何操作，不能根据端点超时接管。

## 明确未做

真实Abaqus调用0；未运行帮助/版本/许可证/Datacheck/CAE/Viewer/Abaqus Python，未打开ODB。未访问Stable、生产Project或共享环境，未改安装和Windows Job策略。未操作真实slot/gate/Grant/owner。未进行checkout/switch/reset/stash/merge/rebase/commit/push，未自动进入后续Run。
