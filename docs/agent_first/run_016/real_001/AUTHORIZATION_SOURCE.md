# 本次人类授权来源（审计引用，不是新授权协议）

来源：本会话最新用户消息，以“继续 Run016。我批准以下唯一清单内的受限真实 Abaqus 验收”开头。用户明确批准通过既有可信入口登记精确 Grant，并经公共客户端、Supervisor、Project 存储执行。

- 实验：run016_8a85583d797345d0b9a4a27b64511b44。
- 原清单：docs/agent_first/run_016/ACCEPTANCE_MANIFEST.json。
- 经实际 canonical body 重算的批准摘要：88ddae420d2fd73f0ecb7bace4171bb8f0eb6a6b2098b0d91e558c94338f3fd7。
- A=r016_bar_a_8a85583d；B=r016_bar_b_797345d0；各最多一次 Standard analysis，CPU1/GPU0/2048MB，总计最多2次，额外 Abaqus 调用0。次数不可互换。
- A必须先经批准受管路径完成、范围结束证据持久化、正常收尾和槽释放提交、Solver及三项冻结DAT全通过，B才可在原授权窗口内创建。行政释放不能满足条件。
- 每项最多300秒观察；不终止、不重试、不删除、不延长窗口。应答不确定只按原幂等身份查询。
- 允许关闭本次创建的GUI并重开观察同Run；禁止关闭其他窗口、停止owner或操作历史实例。
- ODB内容验证不执行。用户要求本轮完成报告后停止，不提交、推送或进入Run017。

PREFLIGHT.json保存本次实际匹配结果：49项执行材料、20项Runtime材料、原2个Plan、0 Grant/Run/尝试/输出冲突；517项历史保护材料未变。

后续通过既有 standard_service.py authorize --pair --approval-source 引用本文件。文件本身不能给普通客户端授予任何权限，也不会覆盖服务端当前前置检查。
