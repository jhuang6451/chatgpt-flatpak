# TODO

来源：2026-10-31 仓库代码与构建结果审查（CI run 40928773294 / Release v26.1027.30824），对照 flatpak-claude-desktop 已完成的修复。

## 高

- [ ] **#1 Codex 补丁很可能打错位置**：最近三次构建（40928773294、40625366350、40443000886）的 bwrap 摘要校验补丁都走了启发式分支，位置为 `0x120e59b` / `0x114a34b` / `0x115170b`，而已确认的正确位置在 `0x9436af4` 附近。启发式只找全文第一个 `83 f1 0f 74`，这个序列非常常见，推测改坏了无关跳转，真正的校验没被绕过（未反汇编验证）。其中两次的 mountinfo 补丁也走了启发式。`patch-codex.py` 只要打上一个补丁就返回成功，CI 因此一直是绿的。→ 删除启发式搜索，精确模式匹配不到就让构建失败；对 26.1023+ 重新定位两处补丁；考虑在 CI 里加一步验证（例如在构建好的沙箱里跑一次 Codex 命令）。
- [ ] **#2 Pages 双源冲突**：Pages 源仍是 legacy `gh-pages` 分支，工作流却同时用 peaceiris 往 `gh-pages` 推不含 OSTree 的网页，再用 `actions/deploy-pages` 发布完整内容。`web/` 一改，`gh-pages` 推送触发的 legacy 构建就可能晚于 deploy-pages 完成，用不含 `repo/` 的内容覆盖线上仓库。→ 移除 `peaceiris/actions-gh-pages`，Pages Source 切换为 GitHub Actions。
- [ ] **#3 `deploy-pages` 设了 `continue-on-error`**：软件源部署失败时工作流仍为绿色。→ 移除。
- [ ] **#4 软件源未 GPG 签名**（`gpg-verify=false`）。→ 移植 `scripts/sign-repo.sh`，CI 用仓库 secret 签名，公钥内嵌到 `.flatpakrepo` / `.flatpakref`，`gpg-verify=true`。
- [ ] **#5 `chatgpt.flatpakref` 缺少 `RuntimeRepo=`**：未配置 flathub 的用户无法解析 `org.freedesktop.Platform//25.08`。

## 中

- [ ] **#6 bwrap 垫片让 Codex 沙箱失效**：垫片丢弃 `--` 之前的全部参数，bwrap 负责的只读挂载、可写目录白名单都不再生效，`--setenv` 也被丢弃。网络隔离是否还在取决于 `codex-linux-sandbox` 自身的 seccomp，未验证。PROJECT_CONTEXT 写的“沙箱内网络受限”目前不可信。→ 实测网络隔离；README 明确说明 Codex 执行的命令拥有整个 Flatpak 沙箱的权限（可读写整个 home）；评估是否至少处理 `--setenv` / `--unsetenv`。
- [ ] **#7 缺少密钥环权限**：没有 `org.freedesktop.secrets`、`org.kde.kwalletd5/6`，Electron safeStorage 可能退回 basic（明文）存储登录凭据。→ 补上 talk-name 并实测。
- [ ] **#8 “增量更新”不成立**：CI 每次从空 `repo` 构建，static delta 只有 from-scratch，`--prune` 无意义。→ 先拉取线上仓库再 commit，或修正 README / 主页描述。
- [ ] **#9 版本提取硬编码回退 `26.1016.51333`**：提取失败会给新构建打旧 tag。→ 改为报错退出。
- [ ] **#10 `update-checker.py` 取第一个 `chatgpt` 条目**：依赖 primary.xml 中条目顺序。→ 按版本比较取最大值。
  - [ ] 附带：删除自动探测 `127.0.0.1:7890` 代理的本机逻辑（需要代理就用环境变量）；删除未使用的 `json`、`urllib.request`、`USER_AGENT`。
- [ ] **#11 工作流触发与并发**：`paths` 未包含 `web/**`、`chatgpt.flatpakref`、`chatgpt.flatpakrepo`；无 `concurrency`；同版本重新打包时 tag 不会移动。

## 低 / 文档与权限

- [ ] **#12 清单清理**：`--env=OZONE_PLATFORM=wayland` 无效（Electron 不读此变量）；`xdg-download` / `xdg-documents` 与 `home` 冗余；构建命令里的 `ls -la` 与 `find` 兜底是调试遗留；bwrap 垫片复制到三个位置，确认哪个才是 Codex 实际使用的。
- [ ] **#13 `chatgpt.sh`**：改为 `set -euo pipefail`；Wayland 检测补上 `XDG_SESSION_TYPE`；用户 flags 中的 `--enable-features` 应与默认值合并（Chromium 只认最后一个）；`TMPDIR` 改为 `$XDG_CACHE_HOME/tmp`。
- [ ] **#14 `.desktop`**：`Categories` 含三个主类别，只保留一个；MimeType 把应用注册为 csv/tsv/docx/pptx/xlsx 的打开方式，确认是否有必要。
- [ ] **#15 metainfo**：描述里的 “GPT-4o, o1” 过时，“Production-grade” 等宣传语删掉；`<categories>` 与 `.desktop` 保持一致。
- [ ] **#16 README / 网页 / PROJECT_CONTEXT**：
  - 英文为默认语言，中文另存 `README.zh-CN.md` / `web/zh-CN.html` / `PROJECT_CONTEXT.zh-CN.md`，用 Humanizer 改写，去掉 emoji 标题和“生产级”“彻底攻克”“完美解决”。
  - README 增加“权限说明”与“已知限制”两节（含 #6）；流程图里的 “gh-pages 分支” 与实际部署方式不符。
  - PROJECT_CONTEXT 过时：runtime 写 26.08（实际 25.08）、内嵌旧版清单、`conversation://` 链接与本机绝对路径。
  - 网页只有深色主题、无手机端断点、无语言切换；复制按钮依赖全局 `event`。
- [ ] **#17 杂项**：`actions/cache` 与 flatpak-builder `cache: true` 重复缓存；`build-local.sh` 生成 bundle 未加 `--runtime-repo`；Release 说明改为英文；Actions 升级到不再使用 Node 20 的版本。
