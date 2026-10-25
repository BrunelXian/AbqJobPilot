# Run020 — 产品 Project 与本机凭据契约

## 复用和本轮增量

现有 `execution/store.py` format3、ExecutionService、owner.lock、Supervisor、IPC、Plan/Grant、幂等、受管范围、对账和停服事务继续使用；没有第二调度器、认证协议、数据库 Schema 或迁移。Run019 的真实计划拒绝和严格空闲停服限制继续有效。

| 接缝 | 本轮改动 / 权威 |
|---|---|
| `product_project.py` | 新公开 create/open/inspect；明确目录、名称、format1产品封装，内部复用format3；创建之外只读 |
| `local_credentials.py` | 保护原IPC credential、原operator capability及启动配置的落盘；Windows DPAPI及私有目录DACL，不改变wire认证 |
| `service_discovery.py` | 解析产品根/内部执行目录；核对产品、宿主、实例后继续原endpoint/OS身份/认证/协议检查 |
| `service_lifecycle.py` | 原配置写入及读取增加受保护容器；start/stop算法不变 |
| `service_owner.py` | connection临时文件先加密再落盘，替换为该owner连接信息 |
| `execution_gui.py` | New按钮与异步创建，选择产品目录、名称/身份、结构化失败；仍使用公共客户端读Run |
| `product_inspect.py` | 普通独立Python只读示例，无测试内部依赖、SQL、授权工厂或服务启动 |

## 创建与数据归属

显式目标的父目录必须存在；目标本身必须不存在，包括已有空目录也拒绝。Project ID/instance随机生成；显示名称1–80个可打印字符。固定登记Python，Windows本地非重解析路径。

```text
用户指定的新目录/
  .agent-first-creation.json    永久创建标记；不是执行尝试记录
  agent_project.json           完成后才发布的公开产品manifest，format/version=1
  project/experiment.json      原执行format3身份
  project/execution.sqlite3    Run/Event/Evidence索引，Project拥有
  project/runtime/             本Project运行数据
  project/owner.lock           原所有权锁（不删除/强夺）
  private/                    仅本机运行材料，禁止加入可移植工程归档
```

创建先独占目录、写意图，建立原格式执行存储，在初始所有权租约内设PAUSED、配置生命周期身份，关闭存储后才将已fsync的manifest临时文件原子发布。失败不冒充完整Project：保留未完成目录及标记，打开拒绝，不清理、不重用、不修复。没有跨文件系统事务或故障后自动回滚承诺。读取内部project目录也检查父级创建标记，不能用其绕过未完成发布。

默认 **PAUSED，0 Plan/Grant/Run，未启动Supervisor**。配置中process_config=None，真实Standard未启用；后续测试设置与普通创建分开。没有导入/移动INP、CAE、ODB等工程文件，没有默认Recent推断。外部工程文件仍归原位置，Project只拥有其元数据、索引和本地运行数据。

Legacy project.json由Legacy入口继续处理；普通文件夹、未完成创建、不支持产品版本/执行格式、损坏DB、日志需维护均明确拒绝，不初始化或迁移。产品目录移动/复制后的只读打开也保守拒绝自动重绑定；工程内容可独立保存，但本轮不提供迁移或可恢复归档功能。

## 凭据交接和权限

原IPC高熵credential与独立operator_token首次创建时生成。新产品的lifecycle.json、operator.json、connection.json均为DPAPI密文容器，不存在先写明文再加密的中间文件。仅进程内解密后传给原认证客户端/owner。

保护使用 Windows **当前用户** CryptProtectData，UI_FORBIDDEN，未用LOCAL_MACHINE。额外熵关联context_digest与当前用户SID/本机MachineGuid的摘要；公开manifest只保留host_binding摘要，不保存SID、MachineGuid或完整环境。物理目录、绝对路径、存储generation与内容摘要继续由既有context绑定。复制同机其他目录、移动或跨用户/主机不能静默连接原owner；没有fallback或重新签发。

`private/` 在创建时即赋予受保护、可继承的DACL，只允许当前用户及SYSTEM；不修改旧目录/系统策略。DPAPI不同用户/主机拒绝还具有绑定检查；本轮实际测试当前用户跨进程解密与DACL，异用户/异主机拒绝为负向绑定注入，**未登录其他用户或迁移机器实测**。

同一Windows用户的GUI与Python经显式Project路径取得原连接上下文，无全机搜索/端口扫描。连接权限本身不能调用停服：仍需独立operator capability。生命周期权限不能创建任务Grant、恢复派发或行政处置；任务继续使用既有TEST_ONLY或精确真实批准。本轮没有新增真实Grant能力。

这是本机同用户的可信操作入口，不是OS级Agent角色隔离，也不能抵御同用户任意文件访问/调试、管理员或篡改源码。拥有本机文件访问权限的同用户可以取得生命周期能力，需显式调用start/stop；不因此取得Solver执行权限。

历史实验明文handoff保持原兼容行为，不迁移旧文件。新产品标记要求密文，拒绝降级为明文。owner重启沿用该Project本机凭据，更新endpoint及owner身份；旧endpoint不满足身份握手。连接失败不删除锁、替换owner或重新启动。

工程归档必须排除整个`private/`、活动owner发现材料、锁、未完成创建材料；本轮未提供产品归档工具。不得拿文件夹复制当可用Project导入。重新配置/显式迁移属于后续独立能力。

## 启动、停止与测试权限

创建/打开/检查不启动服务。显式Start通过原锁预约与固定service_owner路径；空Project从首次启动起PAUSED。GUI退出只断开自身读线程，不停owner、不删凭据。Stop仍要求当前owner、独立operator、原锁和事务、无活动/UNKNOWN/未决/保留资源；提交PAUSED和回执后正常退出，显式重启仍PAUSED。

固定Python实测的可信设置在**初始创建租约内**独立注入已有ProcessFixture配置、精确TEST_ONLY Grant与显式resume事务，然后公共客户端提交。普通New路径没有该注入。当前产品没有通用“启动后给自己批准”入口；曾启动实例不能由准备函数绕过owner直接写库。公开普通客户端没有mint/approve RPC。

## Windows依据与边界

当前用户保护、附加熵与内存释放遵循 [CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)。私有目录的保护继承DACL遵循 [Security Descriptor String Format](https://learn.microsoft.com/en-us/windows/win32/secauthz/security-descriptor-string-format)。使用同一IPC，未引入自制加密或远程服务。

Windows GUI与venv启动器退出后owner/worker存活以本轮真实句柄与创建时间证据为准；只支持保持Windows会话和外层宿主存活的已测环境，不承诺注销、关机、宿主关闭、系统重启或真实Abaqus链。
