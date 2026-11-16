# OpenAI ChatGPT Linux 客户端:Flatpak 打包上下文

[English](PROJECT_CONTEXT.md) · 简体中文

> **最后更新**:2026-11-15(同步至 26.1111.21308,Codex CLI 0.169.0-alpha.11.1)
> **GitHub 仓库**:`https://github.com/jhuang6451/chatgpt-flatpak`
> **Pages 主页与软件源**:`https://jhuang6451.github.io/chatgpt-flatpak/`

构建步骤和权限以清单 `com.openai.chatgpt.yaml` 为准。本文件记录各项决定的原因。

---

## 1. 上游来源

* **官方 YUM 源**:`https://persistent.oaistatic.com/codex-app-prod/linux/rpm/x86_64`
  * 索引:`repodata/repomd.xml`,指向含版本和 SHA-256 的 `primary.xml.gz`。
  * 软件包:`chatgpt-<version>-<release>.x86_64.rpm`,只发布 x86_64。
* **官方 RPM 的目录结构**:
  * 主程序:`/usr/lib/chatgpt/ChatGPT`(Electron)
  * Codex app server 与 CLI:`/usr/lib/chatgpt/resources/codex`(Rust,静态链接)
  * 自带 bubblewrap:`/usr/lib/chatgpt/resources/codex-resources/bwrap`
  * 图标:`/usr/share/pixmaps/chatgpt.png`,1024x1024。Flatpak 不接受大于 512x512 的图标,所以仓库在 `icons/hicolor/` 里放了预先缩放好的图标。
* `flatpak-builder` 解压归档时会去掉第一层路径,因此清单同时查找 `extracted/usr/lib/chatgpt` 和 `extracted/lib/chatgpt`。

---

## 2. Flatpak 方案

### 2.1 基座与沙箱
* **App ID**:`com.openai.chatgpt`
* **Runtime**:`org.freedesktop.Platform//25.08`
* **SDK**:`org.freedesktop.Sdk//25.08`
* **BaseApp**:`org.electronjs.Electron2.BaseApp//25.08`
* **原因**:与 Flathub 和 CI 容器镜像(`ghcr.io/flathub-infra/flatpak-github-actions:freedesktop-25.08`)一致。Electron 自身的沙箱需要非特权 user namespace,BaseApp 里的 `zypak-wrapper` 会把它转交给宿主。

### 2.2 启动脚本(`chatgpt.sh`,安装为 `/app/bin/chatgpt`)
* 在 Wayland 下加上 `--ozone-platform-hint=auto` 和 `WaylandWindowDecorations` 特性。
* 从 `$XDG_CONFIG_HOME/chatgpt-flags.conf` 读取额外参数,`--enable-features=` 会和默认值合并。
* 把 `TMPDIR` 设为 `$XDG_CACHE_HOME/tmp`,然后运行 `zypak-wrapper /app/lib/chatgpt/ChatGPT`。

### 2.3 Codex 命令执行
Codex 通过 bubblewrap 执行 shell 命令,在 Flatpak 里会失败:

1. Codex 解析 `/proc/self/mountinfo`,要求每个挂载根都是绝对路径。Flatpak 在 `/run/.userns` 的 nsfs 挂载根是 `user:[<inode>]`,于是 Codex 返回 `error building bubblewrap command: mountinfo path is not absolute`。
2. Flatpak 的 seccomp 规则禁止 `CLONE_NEWUSER`,嵌套的 bubblewrap 无法创建沙箱。

处理方式:

* `scripts/patch-codex.py` 修补 `resources/codex` 中的两个分支:
  * 挂载根检查(`cmp byte [r15], '/'` 之后的 `jne rel32`,替换为 6 个 NOP);
  * 对自带 bubblewrap 的 SHA-256 校验(`je rel8` 改为 `jmp`,旧版本则把 `jne rel8` 改为 NOP)。
  每个模式必须恰好匹配一处,并且在 0x400 字节范围内有代码引用对应的错误字符串,否则脚本以非零状态退出,构建失败。
* `bwrap_shim.c` 只处理影响子进程的参数(`--argv0`、`--chdir`、`--die-with-parent`、`--setenv`、`--unsetenv`、`--clearenv`),跳过 `--` 之前的其余参数,再 `execvp` 执行命令。
* 实际使用哪个副本(2026-11-15 把每个副本换成带日志的版本测试):Codex 先执行一次 `/app/bin/bwrap --help` 作为探测,之后所有命令都通过 `resources/codex-resources/bwrap` 执行。原来的第三个副本 `resources/bwrap` 从未被调用,已删除。
* `scripts/verify-codex-sandbox.sh` 运行 `codex sandbox -- sh -c 'echo codex-sandbox-ok'`。CI 对刚构建的软件源运行它,只在出现那两个被修补的错误时失败,其他失败记为警告,因为 CI 容器不一定支持 seccomp 或 user namespace。

### 2.4 真机验证结果(2026-11-15,26.1111.21308)
* 从签名软件源安装,`gpg-verify=true` 校验通过,应用提交带有 `B82A22666F3DEC39` 的有效签名。此前 appstream 分支没有签名,`flatpak update --appstream chatgpt` 会失败;现在 `scripts/sign-repo.sh` 会签名所有 ref 并检查结果。
* `codex sandbox` 能执行命令,两处补丁都生效。
* 网络限制有效:在 `codex sandbox` 中 DNS 解析失败,`connect()` 返回 `EPERM`。
* 文件系统限制无效:默认沙箱模式下的命令可以在工作目录之外的 `$HOME` 中创建文件。
* Electron `safeStorage` 使用系统密钥环:`config/Codex/Default/Cookies` 中的 Cookie 带 `v11` 前缀(密钥来自密钥环)。仅有的一条 `v10` 记录早于密钥环权限的加入。
* Runtime 里有 `python3` 和 `curl`,没有 `git`、`node`、`gcc`、`make`。有了 `org.freedesktop.Flatpak` 权限后,在开启网络(`sandbox_workspace_write.network_access=true`)或 `danger-full-access` 模式下,`codex sandbox` 里可以执行 `flatpak-spawn --host git --version`。默认的受限网络模式下会报 `Can't find bus: Operation not permitted`,因为 Codex 的 seccomp 规则也拦住了 D-Bus 套接字。

### 2.5 权限
* `--filesystem=home` 让 Codex 能处理用户目录中任意位置的项目。早先的 `--filesystem=xdg-documents:ro` 会覆盖它,使 `~/Documents` 变为只读,已删除。
* `org.freedesktop.Flatpak`(2026-11-15 加入)让 Codex 能通过 `flatpak-spawn --host` 使用宿主工具。可写的 `home` 本来就允许命令往 `~/.bashrc` 或自启动项里写代码,所以这项权限实际增加的暴露面很小,也与 flatpak-claude-desktop 和 antigravity-flatpak 保持一致。
* `org.freedesktop.secrets` 和 `org.kde.kwalletd5/6` 供 Electron `safeStorage` 使用。

---

## 3. CI/CD 与托管

1. **构建与部署(`.github/workflows/build-and-deploy.yml`)**:
   * 在推送到 `master` 且改动了清单、脚本、网页、图标或工作流时运行。
   * 在 Flathub Action 容器中构建,运行 Codex 沙箱检查,再用 `scripts/sign-repo.sh` 签名所有 ref 和 summary(需要 `GPG_PRIVATE_KEY` 和 `GPG_KEY_ID` 两个 secret)。
   * 每次从空仓库构建,软件源只保留最新提交,不提供从旧版本出发的增量包。
   * 打 `v<version>` 标签,发布包含 `.flatpak` 离线包、`ostree-repo.tar.gz`、`.flatpakref`、`.flatpakrepo` 的 GitHub Release。
   * 通过 Actions Pages API 部署 GitHub Pages,同时托管主页(`web/`)和 `repo/` 下的完整 OSTree 仓库。
2. **上游检查(`.github/workflows/check-update.yml`)**:
   * 每 6 小时运行 `scripts/update-checker.py --ci --update`。
   * 发现新版本时更新清单中的下载地址和哈希以及 metainfo 的版本记录,提交并触发构建。
