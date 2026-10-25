# 四语言资源与本地化规范

## 当前事实、交付覆盖与发布条件

当前Classic `_texts`/`MENU_LABELS`/条件表达式提供部分en/zh；新ExecutionView大量中文字面值和中英混排。没有统一全产品目录，法德未实现。不能把Classic初始en解释为整个应用已经English优先。

本目录提供 **110个消息键×4语言** 的设计资源：[en](design/locales/en.json)、[zh-CN](design/locales/zh-CN.json)、[fr-FR](design/locales/fr-FR.json)、[de-DE](design/locales/de-DE.json)。源为 [strings.tsv](design/strings.tsv)，生成器 [build.py](design/build.py) 同时嵌入HTML；仅标准库，不被应用导入。

| 语言 | 本次设计键覆盖 | 现有产品覆盖 | 还需要什么 |
|---|---|---|---|
| en / English | 110/110设计消息 | Classic部分；新监控未统一 | 全应用提取/回归、默认偏好接入 |
| zh-CN / 简体中文 | 110/110设计消息 | Classic部分zh别名、新视图中文较多 | 统一键与命名、术语校对 |
| fr-FR / Français | 110/110设计消息草稿 | 未实现 | 母语审校、全应用翻译、实际Tk回归 |
| de-DE / Deutsch | 110/110设计消息草稿 | 未实现 | 母语审校、长文本/DPI/窗口回归 |

这不是全产品翻译完成率。HTML审阅栏、合成工程名称、原始日志、API字段/状态码和部分技术样例标签仍保留English；不属于上述110键的全产品覆盖声明。设置页明确标“Design text translated · production translation pending”，法德有审校说明。最终产品选择列表须提供 `preview / incomplete` 状态，未达到发布标准不能隐去标识。

## 资源结构与消息接口设计

未来建议 `abqjobpilot/ui/i18n/{en,zh-CN,fr-FR,de-DE}.json`，`catalog.py`只读取受信任内置资源。资源schema_version与应用版本分开，不改Project模式。键按功能命名：`nav.runs`、`project.new.title`、`service.stop.reason.active_run`、`evidence.scope.unknown`、`error.PROJECT_IDENTITY_MISMATCH`。本次短键为原型使用；实施时有显式映射表，不拿英文原文当键。

消息接口候选：`tr(key, *, locale, params)`。只做有限命名参数替换，不eval、不执行format属性访问、不把任意错误载荷当模板。允许参数名为ASCII标识符，资源与代码检查同一placeholder集合；缺参显示受控缺失提示并写无敏感内容的开发诊断，不向用户泄漏对象repr。

例子：

```json
{
  "error.COMMUNICATION_UNKNOWN": "The service could not be reached. Last successful read: {time}. Reconnect to check its state.",
  "observed": "Last successful read: {time}",
  "held": "Occupied by {run}"
}
```

消息显示流程：稳定原因码 → 白名单映射 → 语言消息 + 经过筛选的参数 → Details中原始码和关联ID。`AUTHENTICATION_FAILED`不回显token、配置文件完整内容或底层异常堆栈；未知码用 `error.generic`。服务实际状态码、数据库字段、幂等键、授权主体、Plan摘要、证据原文均不本地化。

优先完整句子，禁止拼接“动词+翻译名词”组装法德句序。需要数量时使用明确 `.one/.other` 消息键；en/fr/de按各自语言规则，zh-CN使用other。首版尽量使用“数量：{count}”中性结构。参数单位由契约给定，数值显示可本地化但复制原始数值/API仍使用原值；不把十进制逗号写回输入/证据。

## 默认、回退与持久化

新用户明确默认 `en`，不根据系统地区自动改成中文。不修改Project的语言字段，因为不存在这样的工程语义。已有Classic内存状态 `zh` 可以在显示适配层映射到 `zh-CN`；不得改写历史证据。

语言资源缺键：当前locale → English → 稳定诊断占位；界面显示本语言尚不完整的提示。开发检查应阻止发布缺键，不用空串隐藏错误。损坏资源拒绝加载该语言并退回English；不能引发Project初始化。

用户偏好仅保存locale code与显示配置。语言切换广播到当前控件/菜单/对话框，保留Project、Run、表格选择、滚动、日志Follow和原Reader；不重启服务、不重连、不提交，不清缓存中的原始证据。UI重绘时不得用本地化文字作Treeview IID或状态判断。

## 布局规则

- 德语“Verbindung trennen”“Klassische Warteschlange”“Verwalteter Prozessumfang”按文字自然增长或两行；不能靠省略号隐藏操作含义。
- 导航保持文本；栏宽可调，德语Classic两行。按钮至少34逻辑px高，可增高到两行；对话框宽度/高度由内容决定，上下滚动保留底部操作。
- 表头按最小宽度+stretch分配，字段名可以两行；证据表允许横滚，不能截断退出码、错误码和验证数值。
- 原始日志不翻译、不换行重写；支持水平滚动与选中复制。UI说明使用当地语言并标来源/观察时间。
- 日期显示本地时区和偏移，原始UTC时间可查；不能根据语言偷偷改变时区。`UNKNOWN / NOT_RUN / NOT_OBSERVED / EVIDENCE_INSUFFICIENT`各自翻译，不能混成“失败”。

## 发布前本地化验收

资源键/占位符100%一致、没有意外重复键；格式化负向测试；所有动态控件切语不产生业务调用；四语言截图/键盘访问；德语最小窗口、125/150%缩放；错误对话框和空状态；屏幕阅读器焦点；母语审校签字与准确完成状态。上述Tk产品验收属于Run024之后，不由本轮浏览器布局检查代替。
