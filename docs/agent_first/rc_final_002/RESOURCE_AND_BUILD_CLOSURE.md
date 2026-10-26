# 资源与可重复构建闭包

最终运行源码包为 **114文件**，与RC-F01 candidate-004的115文件相比，只排除根目录的可选 `abqjobpilot.ico`；其余114文件的SHA-256全部相同。包未增添模拟数据、测试授权、数据库或私有连接配置。

## 图标决定

现有图标是未跟踪且被 `.gitignore:49` 排除的本机文件。RC-F01证明其与旧内部包相同，不能证明设计来源或许可。本轮没有得到额外许可证据，不将其提交或分发，也不删除、替换或修改本机原件。

`abqjobpilot/gui_app.py:295` 的 `_apply_icon` 只在应用相对路径存在图标时调用 `iconbitmap`，并捕获TclError。缺失或损坏时保留Tk原生默认图标。正常Execution主窗口与Classic共享此Tk根和导航；配置中的APP_ICON_FILE也是应用相对路径，不是必须存在的启动依赖。

因此使用现有默认图标策略，不修改GUI布局或执行代码，不引入其他图像素材。新增11项构建/资源测试包含缺失与损坏图标两种回退；实际无图标部署GUI另行实测。后续品牌图标需要明确来源/许可及独立审查，当前不再作为功能启动P1。

## 构建入口

`scripts/release_inputs.json` 是114项明确白名单和规范化内容哈希；`scripts/build_source_candidate.py` 只读取白名单，不枚举未跟踪目录，不需要Git、开发机D盘或第三方包。

在含这两个文件的受审源码快照中，用已确认的绝对Python运行：

```powershell
& '<qualified-python.exe>' -B scripts/build_source_candidate.py --output '<new-output-directory>'
```

输出目录必须不存在；输入变更、路径越界或重复路径拒绝。Git Windows检出可能将LF变成CRLF，构建器仅在规范化CRLF→LF后SHA仍精确匹配时接受，不改写源文件。首轮检查的LICENSE差异正属此情况；没有放宽正文校验。

ZIP按文件名排序、固定时间/权限/压缩参数。当前仓库和无.git的隔离源码快照各构建一次，SHA均为 `7972e961e104aafc99fac6c6fd7e947b3bb67424892783a14a4933552332d047`。见 `candidate_001/BUILD.json` 和 `candidate_repro_001/BUILD.json`。跨不同Python/zlib版本的压缩字节一致性尚未宣称。

## 依赖闭包

白名单包含全部部署Python模块、四种语言JSON、正常VBS与Python启动器、requirements说明、LICENSE、公共API帮助及既有公开示例。标准GUI/服务依赖CPython3.12x64与Tk；MCP为可选依赖，测试专用pytest不在运行包。构建脚本和测试属于仓库开发工具，不混入114文件运行包。

排除：`.git`、测试/历史Project、Runtime、Recent、凭据、进程记录、数据库、ODB/DAT/STA/MSG/日志、ZIP、截图、机器特定python-path.txt、venv、未审查文件。本机114文件包仍为源码部署目录，不是自带Python的便携程序或安装器。
