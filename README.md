# cxdy-antigravity

这套配置用于官方 Antigravity 2.34.0。点击 Mac 上原有的官方图标后，应用会正常重开一次，再加载窗口内的简体中文和 Context Viewer 看板。后端通过 Clash 的本地代理访问模型接口，TUN 可以关闭。

## 安装前

- 安装官方 Antigravity 2.34.0，路径为 `/Applications/Antigravity.app`。Apple Silicon Mac 已完成实机验收。
- 保持 Clash 运行，确认 HTTP 或混合代理端口。交付包默认使用 `7897`。
- 在 Mac 登录会话的终端里准备 Node.js 22.4 或更高版本，以及带 `python3` 和 `swiftc` 的 Xcode 命令行工具。

## 安装与使用

在解压目录打开终端，运行以下命令。Clash 端口不同就替换 `--port` 后的数字。

```sh
python3 setup.py check
python3 setup.py install --port 7897
```

退出已打开的 Antigravity，再点官方图标。应用重开后，检查“新建会话”和“设置”是否显示中文。打开模型选择器确认有模型，再点击 Context Viewer 的额度或 Token 用量入口。

安装脚本仅在当前用户下写入启动配置和 LaunchAgent。它保留官方应用包和签名。自动增强只在 2.34.0 执行。调试端口由系统分配，仅监听 `127.0.0.1`，退出 App 后关闭。

## 卸载

```sh
python3 setup.py uninstall
```

退出并重新打开官方 App，使卸载生效。脚本会移除自己的后台任务和代理配置段，并保留 `.zshenv` 中的其他内容。与此前的手动安装同名时，先按原文档卸载旧任务，再运行交付包的安装脚本。

## 文件说明

| 文件 | 用途 |
| --- | --- |
| [排障归档](docs/排障与实测.md) | 故障根因、实测结果、检查命令和回滚步骤 |
| [安装脚本](setup.py) | 检查前提，安装、编译和卸载 |
| [启动辅助](src/AntigravityLauncher.swift) | 监听官方 App 启动，正常重开一次 |
| [界面加载脚本](src/load-interface.cjs) | 验证本机调试端口，加载汉化和看板 |
| [Shell 代理模板](src/proxy.zsh.in) | 给 Antigravity 后端提供代理变量 |
| [临时加载脚本](scripts/临时加载看板.zsh) | 排障时手动启动并临时挂载两项界面增强 |
| [脚本自检](scripts/自检.py) | 在临时目录验证安装、卸载和失败回滚 |
| [Context Viewer](vendor/context-viewer/) | v0.8.10 运行源码、汉化词库和 MIT 许可证 |

排障时可用 `zsh scripts/临时加载看板.zsh 7897`。正常使用只点官方图标。需要执行安装的其他工具应先读本说明，按 `check → install → 验收` 的顺序操作。

原方案已在本机实测中文版导航、设置、模型菜单、额度看板和 Token 用量。交付包的安装流程通过隔离测试，首次部署到其他 Mac 后需要按上面的步骤重新验收。macOS 原生菜单和部分模型标签仍是英文，实测未发送模型消息。

## 第三方文件与引用

| 来源 | 仓库中的位置 | 用途与许可证 |
| --- | --- | --- |
| [Antigravity Context Viewer](https://github.com/elviscjn-cjn/antigravity-context-viewer) | [`vendor/context-viewer/`](vendor/context-viewer/) | 用量看板、临时加载命令、本机调试桥接、简体中文词库与翻译运行时。保留上游 [MIT 许可证](vendor/context-viewer/LICENSE)和版权声明。 |

Context Viewer 固定到 [v0.8.10](https://github.com/elviscjn-cjn/antigravity-context-viewer/releases/tag/v0.8.10) 的[提交 `ab5a41b`](https://github.com/elviscjn-cjn/antigravity-context-viewer/commit/ab5a41b7d515643fbbdd9dde8dc940e520a131b0)。仓库保留运行源码，省略演示媒体和上游 GitHub 工作流。

启动辅助参考 Apple 的用户级后台任务机制。界面加载使用 Electron 的本机调试接口。[Apple LaunchAgent 文档](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html) · [Electron 调试参数](https://www.electronjs.org/docs/latest/api/command-line-switches/#--remote-debugging-portport)
