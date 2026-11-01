# TODO

来源：2026-10-31 仓库代码与构建结果审查。已完成的条目已移除，见 git 历史。

## 待实测验证

构建、签名、Pages 部署已通过（CI run 41267377008，补丁位置 `0x9ef66cc` / `0x9e7f5aa`），以下需要在真机上验证：

- [ ] **从签名软件源安装**：`flatpak remote-add` + `flatpak install`，确认 `gpg-verify=true` 能通过。
- [ ] **#1 补丁生效**：在新构建的包里运行一次 Codex 命令，确认两处补丁真正绕过了校验；考虑把它做成 CI 验证步骤。
- [ ] **#6 沙箱与网络隔离**：bwrap 垫片不创建沙箱，Codex 执行的命令拥有整个 Flatpak 沙箱的权限。实测网络隔离是否仍由 `codex-linux-sandbox` 的 seccomp 保证。
- [ ] **#7 密钥环**：已补 `org.freedesktop.secrets` / `org.kde.kwalletd5/6`，实测 Electron safeStorage 是否使用系统密钥环而不是明文。
- [ ] **#12 bwrap 副本**：垫片复制到 `/app/bin/bwrap`、`resources/codex-resources/bwrap`、`resources/bwrap` 三处，确认 Codex 实际使用哪个，删掉多余的。

## 文档（暂缓）

- [ ] **#8 “增量更新”不成立**：CI 每次从空 `repo` 构建，static delta 只有 from-scratch。`--prune` 已去掉；README / 主页里“增量更新”的描述需修正，或改为先拉取线上仓库再 commit。
- [ ] **#16 README / 网页 / PROJECT_CONTEXT**：
  - 英文为默认语言，中文另存 `README.zh-CN.md` / `web/zh-CN.html` / `PROJECT_CONTEXT.zh-CN.md`，用 Humanizer 改写，去掉 emoji 标题和“生产级”“彻底攻克”“完美解决”。
  - README 增加“权限说明”与“已知限制”两节（含 #6）；流程图里的 “gh-pages 分支” 与实际部署方式不符；补充 GPG 签名与公钥指纹。
  - PROJECT_CONTEXT 过时：runtime 写 26.08（实际 25.08）、内嵌旧版清单、`conversation://` 链接与本机绝对路径。
  - 网页只有深色主题、无手机端断点、无语言切换；复制按钮依赖全局 `event`。
