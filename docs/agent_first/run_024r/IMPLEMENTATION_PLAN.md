# 视觉确认后的最小实施计划（本轮不执行）

## 起点与停止门

先确认Compact主控台、Agent Command抽屉和Classic/Execution视觉关系。确认前不修改`Open_Dev_GUI.vbs`、`gui_app.py`、`desktop_workspace.py`及产品资源。保留Run024源码作为可复用适配与对照，不Git回滚、不删除九页实现来假装完成重置。

## 分段补丁

1. **容器替换**：只在`DesktopWorkspace`调整布局装配，将现有Reader/异步结果投影到Queue、Results及双日志。保留`attach_project`、生命周期generation、选择version等并发隔离。高级视图迁入抽屉；原型的模拟状态代码绝不导入产品。
2. **Classic共用视觉**：复用`open_classic`原惰性控制器，保持运行时/Project/队列边界。统一ttk样式与间距，切页仅显示隐藏。不重启Runner/Reader，不复制/迁移旧DB。顶部按钮一直可达，Classic中对应Execution Workspace返回。
3. **Inspector与Recovery聚合**：用现有`Reader`的核心诊断/Preview结构；先维度摘要，再展开证据/JSON。保留原始FAILED与UNKNOWN_INTERRUPTED诊断区分、历史行政释放语义；没有GUI授权或Apply。
4. **Agent Command适配**：复用原目标、输出、详情交互概念；区分Classic允许列表命令与公共服务只读接口。Session含写动作，不能直接跨格式复用。Service仍调用既有`ServiceLifecycleManager`，连接与执行授权分离。
5. **资源与用户偏好**：沿用现有翻译与显示偏好，追加确认过的key；仅存用户布局比例，校验旧偏好并提供可逆默认值。窗口按当前work-area限制，不把1600客户区硬设为所有屏幕默认。

以上各段只在之后明确批准的实施任务完成，不通过本轮独立原型自动切换产品入口。

## 必须回归的风险

| 风险 | 下一阶段验收 |
|---|---|
| 导航重新建立服务/任务 | 同Project/Run/Reader identity，切换前后revision/Grant/gate/slot不变 |
| 隐藏Classic仍写默认Runtime | 仅显式隔离Classic路径；未选时不实例化；旧流程回归 |
| 选历史行影响当前Run | 分离activity与inspected selection，日志来源和回执一致 |
| 项目切换异步串数据 | generation/version拒绝旧结果；两Project隔离、断线缓存标STALE |
| 双表格分页阻塞 | 有界公共分页、UI线程只渲染；日志限长且保留手动滚动 |
| 恢复/服务按钮权限越界 | 只读Preview无写入；Stop保留服务端安全拒绝；无批准/Grant/Retry入口 |
| Classic命令被跨格式执行 | 明确target及允许列表，不把AgentCommandSession直接绑定Execution Store |
| 窄屏/德语长串 | 1366×768和1600×900实际可用区；125/150%真实OS DPI、键盘焦点/tooltip |
| GUI退出影响执行 | 隔离固定Python任务，完整窗口/启动器退出后owner/worker身份及日志增长，重连原Run |
| 表面成功合并 | Scope/Solver/DAT/ODB各维度、UNKNOWN及行政释放不折叠为成功 |

验证仅使用新隔离Project/Runtime/Recent与固定Python夹具，不操作历史owner。真正主GUI替换后才跑Run018–024相关安全回归；本轮13个mock窗口不替代这些证明。

## 回退与发布

实施时以小补丁保存旧展示路径，通过显式用户级布局选择回退展示，不回滚执行记录、不改变Project格式、不执行Git reset/restore。遇到需要修改ExecutionService、Supervisor、授权、恢复状态机或Backend的需求，停止该补丁并单独评审。

RC审计成果继续保留，正式发布暂停。必须取得用户原生视觉确认及后续产品回归证据，不能用本轮review-ready状态宣布最终GUI通过。
