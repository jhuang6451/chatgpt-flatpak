<div align="center">
  <img src="icons/hicolor/128x128/apps/com.openai.chatgpt.png" alt="ChatGPT" width="88" height="88" />

  <h1>ChatGPT for Linux (Flatpak)</h1>

  <p>OpenAI 官方 ChatGPT Linux 桌面客户端的 Flatpak 打包与软件源。</p>

  <p><a href="README.md">English</a> · 简体中文</p>

  <p>
    <a href="https://github.com/jhuang6451/chatgpt-flatpak/actions/workflows/build-and-deploy.yml"><img src="https://img.shields.io/github/actions/workflow/status/jhuang6451/chatgpt-flatpak/build-and-deploy.yml?branch=master&label=build&labelColor=0d0d0d&color=10a37f" alt="构建状态" /></a>
    <a href="https://github.com/jhuang6451/chatgpt-flatpak/actions/workflows/check-update.yml"><img src="https://img.shields.io/github/actions/workflow/status/jhuang6451/chatgpt-flatpak/check-update.yml?branch=master&label=upstream%20check&labelColor=0d0d0d&color=10a37f" alt="上游检查状态" /></a>
    <a href="https://github.com/jhuang6451/chatgpt-flatpak/releases/latest"><img src="https://img.shields.io/github/v/release/jhuang6451/chatgpt-flatpak?label=release&labelColor=0d0d0d&color=10a37f" alt="最新版本" /></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-10a37f?labelColor=0d0d0d" alt="许可证" /></a>
  </p>

  <p>
    <a href="https://jhuang6451.github.io/chatgpt-flatpak/">项目主页</a> ·
    <a href="https://github.com/jhuang6451/chatgpt-flatpak/releases/latest">下载离线包</a> ·
    <a href="#已知限制">已知限制</a>
  </p>
</div>

## 简介

OpenAI 只为 Linux 提供 RPM 格式的 ChatGPT 客户端,其中包含 Codex 编程智能体。本项目把这个官方 RPM 重新打成 Flatpak,并托管一个 OSTree 软件源,这样 Fedora Atomic、Bazzite、SteamOS、Debian、Ubuntu 这类不方便装 RPM 的系统也能用 `flatpak install` 安装和更新。

构建流程从 OpenAI 的 YUM 源下载 RPM,核对 SHA-256 后解包。和单纯的重新打包不同,构建时会修改自带的 `codex` 二进制,让 Codex 能在 Flatpak 里执行命令。具体改了什么、有什么代价,见 [Codex 在 Flatpak 中如何运行](#codex-在-flatpak-中如何运行)。

主要特性:

- 安装包来自 OpenAI 官方 YUM 源,清单中固定了下载地址和 SHA-256。
- 修补 `codex` 二进制中的两处检查,并用一个小的 `bwrap` 垫片替代 bubblewrap。每次构建后,持续集成会通过 Codex 沙箱实际执行一条命令。
- 启动脚本会检测 Wayland 并启用对应的 Ozone 参数,也支持用配置文件追加 Electron 参数。
- 登录状态保存在 GNOME Keyring 或 KDE Wallet 中。
- GitHub Actions 每 6 小时检查一次上游,发现新版本后自动更新清单、构建并发布。

当前只构建和发布 **x86_64**,因为 OpenAI 只发布 x86_64 的 RPM。

## 安装

### 通过软件源安装(推荐)

```bash
flatpak remote-add --if-not-exists chatgpt https://jhuang6451.github.io/chatgpt-flatpak/chatgpt.flatpakrepo
flatpak install chatgpt com.openai.chatgpt
flatpak run com.openai.chatgpt
```

添加软件源后,`flatpak update` 会和其他应用一起更新 ChatGPT。应用 Runtime 来自 Flathub,没有启用 Flathub 的系统需要先添加:

```bash
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
```

### 通过 `.flatpakref` 安装

下载 [chatgpt.flatpakref](https://jhuang6451.github.io/chatgpt-flatpak/chatgpt.flatpakref),双击用 GNOME 软件或 KDE Discover 打开。这个文件带有 Flathub 的地址,Runtime 会一并安装。

### 通过离线包安装

在 [Releases](https://github.com/jhuang6451/chatgpt-flatpak/releases/latest) 下载 `com.openai.chatgpt.flatpak`:

```bash
flatpak install --user com.openai.chatgpt.flatpak
```

离线包不会自动更新,升级时需要重新下载。

### 软件源签名

软件源的提交、appstream 分支和 summary 都用 GPG 签名,`chatgpt.flatpakrepo` 和 `chatgpt.flatpakref` 内嵌了公钥并启用了 `gpg-verify=true`,Flatpak 会在下载后校验。签名密钥指纹:

```text
5F01 B1FD 3DD6 D620 2FA9 0276 B82A 2266 6F3D EC39
```

如果你在签名启用之前就添加过 `chatgpt` 软件源,旧配置没有公钥,更新会失败。删除后重新添加即可:

```bash
flatpak remote-delete chatgpt
flatpak remote-add chatgpt https://jhuang6451.github.io/chatgpt-flatpak/chatgpt.flatpakrepo
```

离线包 `com.openai.chatgpt.flatpak` 不走这套校验,请从本仓库的 Releases 页面下载。

## 使用

### 启动参数

启动脚本从下面的文件读取额外参数,每行一个,空行和以 `#` 开头的行会被忽略。

```text
~/.var/app/com.openai.chatgpt/config/chatgpt-flags.conf
```

路径在沙箱内对应 `$XDG_CONFIG_HOME`,所以不是 `~/.config`。例如强制使用 X11:

```text
--ozone-platform=x11
```

在 Wayland 会话中,启动脚本默认加上 `--ozone-platform-hint=auto` 和 `--enable-features=WaylandWindowDecorations`。如果你在配置文件里也写了 `--enable-features=...`,启动脚本会把它和默认值合并,不需要重复写 `WaylandWindowDecorations`。

启动脚本还会把 `TMPDIR` 设为 `~/.var/app/com.openai.chatgpt/cache/tmp`。

### 数据位置

沙箱里的 `$HOME` 就是你真实的用户目录,所以 Codex 读写的 `~/.codex` 和宿主机上安装的 Codex CLI 是同一个。Electron 配置(Cookie、本地存储、缓存)保存在 `~/.var/app/com.openai.chatgpt/config/Codex`。

## Codex 在 Flatpak 中如何运行

Codex 通过 bubblewrap 执行每一条 shell 命令。在 Flatpak 里这会在两处出错:

1. 构建 bubblewrap 命令时,Codex 读取 `/proc/self/mountinfo`,要求每个挂载根都是绝对路径。Flatpak 在 `/run/.userns` 有一个 nsfs 挂载,挂载根是 `user:[<inode>]`,Codex 因此报 `mountinfo path is not absolute` 并停止。
2. Flatpak 本身就是一个 bubblewrap 沙箱,它的 seccomp 规则禁止创建非特权 user namespace,嵌套的 bubblewrap 无法启动。

构建时这样处理:

- `scripts/patch-codex.py` 把挂载根检查改成 NOP,并关掉 Codex 对自带 bubblewrap 的 SHA-256 校验。每个补丁必须恰好匹配一处,并且附近的代码要引用对应的错误信息。上游代码变化时构建会失败,不会改错位置。
- `bwrap_shim.c` 安装为 `resources/codex-resources/bwrap`,Codex 实际执行的就是这个副本。它处理 `--argv0`、`--chdir`、`--die-with-parent`、`--setenv`、`--unsetenv`、`--clearenv`,忽略所有挂载和命名空间参数,然后执行命令。`/app/bin/bwrap` 另有一份,因为 Codex 会先在 `PATH` 上探测 `bwrap --help`,之后才改用自带副本。
- 持续集成里,`scripts/verify-codex-sandbox.sh` 在构建好的包中运行 `codex sandbox -- sh -c 'echo ...'`。如果 Codex 报出上面任一被修补的错误,构建失败。

垫片不创建沙箱,所以 Codex 的文件系统限制不生效。即使在只读或 workspace-write 模式下,命令也能写入 Flatpak 允许的任何位置,包括整个用户目录。网络限制仍然有效:Codex 在 `codex-linux-sandbox` 中用 seccomp 实现它,实测受限命令的 DNS 解析和直接 TCP 连接都会失败。需要联网的任务,在应用里提升它的权限即可。

## 权限与安全

清单授予了 `--filesystem=home`,ChatGPT 和 Codex 执行的每条命令都能读写整个用户目录,包括 `~/.ssh` 这类点文件。由于 bubblewrap 垫片不做隔离,Codex 自己的沙箱模式也收窄不了这个范围。应用没有 `org.freedesktop.Flatpak` 权限,不能在宿主系统上执行命令。

完整权限如下:

| 权限 | 用途 |
| --- | --- |
| `--socket=wayland`、`--socket=fallback-x11`、`--share=ipc` | 显示 |
| `--share=network` | 访问 ChatGPT 和 Codex 服务 |
| `--socket=pulseaudio` | 音频和语音 |
| `--device=dri` | GPU 加速 |
| `--filesystem=home` | 读写用户目录,供 Codex 处理本地项目 |
| `--talk-name=org.freedesktop.Notifications`、`org.kde.StatusNotifierWatcher` | 通知、托盘图标 |
| `--talk-name=org.freedesktop.secrets`、`org.kde.kwalletd5`、`org.kde.kwalletd6` | Electron `safeStorage` 使用的密钥环 |

想只开放一个项目目录,可以用 [Flatseal](https://flathub.org/apps/com.github.tchx84.Flatseal) 或命令行:

```bash
flatpak override --user --nofilesystem=home --filesystem=~/Projects com.openai.chatgpt
```

用 `flatpak override --user --reset com.openai.chatgpt` 撤销所有覆盖。

## 已知限制

- **仅 x86_64。** OpenAI 只发布 x86_64 的 RPM。
- **Codex 的文件系统沙箱不生效。** 见 [Codex 在 Flatpak 中如何运行](#codex-在-flatpak-中如何运行)。网络限制仍然有效。
- **沙箱里的开发工具很少。** Codex 只能用 freedesktop Runtime 里的程序:有 `python3` 和 `curl`,没有 `git`、`node`、`gcc`、`make`,宿主系统的程序也不在 `PATH` 上。如果希望 Codex 使用宿主工具,可以执行 `flatpak override --user --talk-name=org.freedesktop.Flatpak com.openai.chatgpt`,再通过 `flatpak-spawn --host` 调用。这样应用就拥有了你在宿主系统上的全部用户权限。
- **上游新版本可能让补丁失效。** 如果 OpenAI 改动了两处检查附近的代码,`patch-codex.py` 会让构建失败,软件源停在上一个版本,直到补丁模式更新。
- **离线包的 Runtime 不会自动安装。** 安装前需要启用 Flathub。

## 本地构建

需要 `flatpak` 和 `flatpak-builder`(没有时脚本会安装 `org.flatpak.Builder`):

```bash
git clone https://github.com/jhuang6451/chatgpt-flatpak.git
cd chatgpt-flatpak
./scripts/build-local.sh
```

脚本会安装所需 Runtime,构建并把结果导出到本地 `repo/` 目录,同时生成 `com.openai.chatgpt.flatpak`。安装后可以运行 `scripts/verify-codex-sandbox.sh` 检查 Codex 能否执行命令。

## 自动更新流程

1. `check-update.yml` 每 6 小时运行 `scripts/update-checker.py`,读取 OpenAI YUM 源的 `repomd.xml` 和 `primary.xml.gz`。
2. 有新版本时,脚本更新 `com.openai.chatgpt.yaml` 里的下载地址和哈希,并在 `com.openai.chatgpt.metainfo.xml` 里添加版本记录,然后提交到 `master`。
3. 提交触发 `build-and-deploy.yml`:构建 Flatpak,检查 Codex 沙箱,签名软件源,创建 GitHub Release,并通过 GitHub Pages 发布 OSTree 仓库和项目主页。

每次发布都会从空仓库重新构建,软件源里只有最新一个提交。OSTree 按文件内容寻址,客户端更新时只下载本地没有的对象,但仓库不保存历史版本,也不提供从旧版本出发的增量包。

## 许可证与商标

本项目的打包脚本和配置以 [MIT 许可证](LICENSE)发布。ChatGPT、Codex 和 OpenAI 标志是 OpenAI 的商标,ChatGPT 桌面客户端是 OpenAI 的专有软件,本项目与 OpenAI 没有隶属关系,也未获其背书。
