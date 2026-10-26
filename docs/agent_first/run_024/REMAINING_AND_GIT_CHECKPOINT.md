# Run024 — RC剩余门槛与Git检查点

本轮完成的是原生展示层集成和固定Python验收，不是0.3.0发布。Run022的窄范围RC判断和Run021B NOT_OBSERVED不改写。

## 最小剩余操作

1. 发布负责人审阅本轮原生截图、Classic兼容范围、法德Preview和原始证据JSON呈现；完成法德母语审校及必要无障碍/多显示器DPI检查。Classic现有英文/中文不能宣称全产品四语言。
2. 部署P1仍在：Open_Dev_GUI.vbs绑定登记LangChainEnv绝对路径；未知新主机、缺Tk/损坏依赖的首次启动诊断及安装包未验收。分发时必须包含 `abqjobpilot/locales/*.json`，不能仅复制py文件。
3. 本机同一Python测试进程重复销毁/建立Tk出现Tcl初始化错误，未修复共享环境。产品单根和独立进程重开已通过；不要将测试承载问题隐去，也不要承诺任意多根嵌入宿主。可独立诊断，不以本轮自动升级Python/Tk解决。
4. 审阅精确Git集合和敏感材料排除后，另行授权Develop检查点；在独立源代码副本复现安全选集，再单独批准RC打包/版本号/Tag。当前仍0.3.0.dev0。
5. 如需提升真实产品路径“Solver跨GUI退出继续运行”的单次完整声明，须另行授权最小真实验收；不得把本轮固定Python结果替代Abaqus证据。域外全集UNKNOWN、ODB NOT_RUN、注销/重启与跨Project资源保护均不扩大。

未发现本轮引入新的P0授权/派发/所有权缺陷。恢复Apply仍是既有本地可信管理接口；GUI仅诊断/Preview。

## 推荐提交边界（本轮不提交）

- 先独立审查原工作区未提交CR-D03核心/测试/契约；它不是本轮GUI补丁，也不能被遗漏使新readonly路由缺少依赖。
- 本轮源码原子集合：gui_app、desktop_workspace、classic_workspace、gui_presentation、ui_resources + 四catalog；execution_gui Reader及client/supervisor两个readonly路由需要与相应测试一起提交。
- 测试集合：新native控件/Windows/visual/driver；原Run018–020驱动/标签更新。不要只提交UI而不提交正常入口和兼容适配。
- 文档集合：本目录Markdown、精简测试结果/证据索引及必要截图。BASELINE/FINAL_CHECKS含本地文件清单；原XML/清理原记录/详细进程身份含本机路径，应在发布包筛选时评审，不盲目全部公开。
- 临时Project数据库、DPAPI/明文连接材料、bootstrap、运行日志和生成输出保留在隔离临时根，绝不作为源码资产。没有为筛选而删除历史文件或更改ignore。
- 提交说明建议：`feat(gui): unify native workspaces and Classic navigation`；`feat(gui): expose read-only interruption diagnostics and recovery previews`；`test(gui): verify native lifecycle, localization and isolation`。需要一起检查依赖，不自动执行拆分提交。

最后核验见 FINAL_CHECKS.json：Develop/HEAD不变，原1616文件中仅12个明确GUI/readonly适配及驱动文件修改，其他1604个摘要保持；既有CR-D03源码、历史Run材料、正常VBS入口、版本、Backend/授权/状态机均未改变。
