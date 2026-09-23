# OpenAI ChatGPT Linux 客户端 Flatpak 打包工程完整上下文 (Session 迁移存档)

> **关联原始会话**: [ChatGPT 打包全流程记录](conversation://60352bf5-a979-4fbe-9b25-7d0a5d0ec82e)  
> **归档时间**: 2026-09-23  
> **维护工程目录**: `/var/home/jhuang/Workspace/flatpak-chatgpt`

---

## 1. 软件源与上游规格信息

* **官方 RPM 下载地址**: `https://persistent.oaistatic.com/codex-app-prod/linux/rpm/latest/chatgpt.x86_64.rpm`
* **软件包规格**:
  * 包名: `chatgpt-26.917.61114-1.x86_64`
  * 类型: 基于 Electron / Chromium 的 Codex Desktop Client
  * 压缩体积: 443.6 MiB
  * 解压后体积: ~1.4 GiB
* **上游包内目录结构**:
  * 核心应用: `/usr/lib/chatgpt/ChatGPT`（ELF 主程序）、`/usr/lib/chatgpt/codex-launcher`
  * 快捷方式: `/usr/share/applications/chatgpt.desktop`
  * 图标文件: `/usr/share/pixmaps/chatgpt.png`（实际分辨率为 1024×1024）
  * AppStream 元数据: `/usr/share/metainfo/com.openai.chatgpt.metainfo.xml`
  * 官方 YUM 软件源: `/etc/yum.repos.d/chatgpt.repo` (源地址: `https://persistent.oaistatic.com/codex-app-prod/linux/rpm/$basearch`)

---

## 2. Flatpak 规范与关键架构决策

### 2.1 基座与沙盒选型
* **App ID**: `com.openai.chatgpt`
* **Runtime**: `org.freedesktop.Platform//26.08`
* **SDK**: `org.freedesktop.Sdk//26.08`
* **BaseApp**: `org.electronjs.Electron2.BaseApp//26.08`
  * **选型原因**: Chromium / Electron 原生依赖 Linux User Namespaces 沙盒，在 Flatpak 内部无法直接二层嵌套。必须使用 `Electron2.BaseApp` 内置的 `zypak-wrapper` 进行沙盒转发。

### 2.2 启动包装器 (`/app/bin/chatgpt`)
```bash
#!/bin/sh
exec zypak-wrapper /app/lib/chatgpt/ChatGPT "$@"
```

### 2.3 踩坑与针对性修复 (关键经验)
1. **图标尺寸合规报错**:
   * *问题*: OpenAI 提供的 `chatgpt.png` 尺寸为 1024×1024，直接置于 `256x256` 目录会导致 Flatpak 导出阶段报错：`Image too large (1024x1024). Max. size 512x512`。
   * *解决*: 在构建阶段利用 SDK 自带的 `ffmpeg`，自动切分为 16x16、32x32、48x48、64x64、128x128、256x256、512x512 全套标准尺寸。
2. **构建环境**:
   * 宿主机自带 Flatpak 版构建工具 `org.flatpak.Builder`。
   * 宿主机已有 `org.freedesktop.Platform//26.08`、`Sdk//26.08` 与 `Electron2.BaseApp//26.08`，直接调用 `flatpak run org.flatpak.Builder ...` 仅需 20 秒即可完成组装构建。

---

## 3. 完整 Flatpak 清单文件 (`com.openai.chatgpt.yaml`)

```yaml
app-id: com.openai.chatgpt
runtime: org.freedesktop.Platform
runtime-version: "26.08"
sdk: org.freedesktop.Sdk
base: org.electronjs.Electron2.BaseApp
base-version: "26.08"
command: chatgpt
separate-locales: false

finish-args:
  - --socket=wayland
  - --socket=fallback-x11
  - --share=ipc
  - --device=dri
  - --socket=pulseaudio
  - --share=network
  - --talk-name=org.freedesktop.Notifications
  - --talk-name=org.kde.StatusNotifierWatcher
  - --filesystem=xdg-download
  - --filesystem=xdg-documents:ro
  - --env=OZONE_PLATFORM=wayland

modules:
  - name: chatgpt
    buildsystem: simple
    build-options:
      no-debuginfo: true
      strip: false
    sources:
      - type: dir
        path: extracted
    build-commands:
      # 1. 部署程序本体
      - mkdir -p /app/lib/chatgpt /app/share/applications /app/bin /app/share/metainfo
      - cp -a usr/lib/chatgpt/* /app/lib/chatgpt/

      # 2. 安装并修正桌面文件
      - install -Dm644 usr/share/applications/chatgpt.desktop /app/share/applications/com.openai.chatgpt.desktop
      - desktop-file-edit --set-key=Exec --set-value="chatgpt %U" /app/share/applications/com.openai.chatgpt.desktop
      - desktop-file-edit --set-key=Icon --set-value="com.openai.chatgpt" /app/share/applications/com.openai.chatgpt.desktop

      # 3. 安装 AppStream 元数据
      - install -Dm644 usr/share/metainfo/com.openai.chatgpt.metainfo.xml /app/share/metainfo/com.openai.chatgpt.metainfo.xml

      # 4. 生成符合 Freedesktop 标准的多尺寸图标（避免 1024x1024 校验失败）
      - |
        for size in 16 32 48 64 128 256 512; do
          mkdir -p /app/share/icons/hicolor/${size}x${size}/apps
          ffmpeg -y -v error -i usr/share/pixmaps/chatgpt.png -vf scale=${size}:${size} /app/share/icons/hicolor/${size}x${size}/apps/com.openai.chatgpt.png
        done

      # 5. 生成 zypak 启动脚本
      - |
        cat << 'EOF' > /app/bin/chatgpt
        #!/bin/sh
        exec zypak-wrapper /app/lib/chatgpt/ChatGPT "$@"
        EOF
      - chmod +x /app/bin/chatgpt
```

---

## 4. 构建、安装与测试指令备忘

```bash
# 进入工程目录
cd /var/home/jhuang/Workspace/flatpak-chatgpt

# 本地直接构建并安装到当前用户环境
flatpak run org.flatpak.Builder --user --install --force-clean build-dir com.openai.chatgpt.yaml

# 验证沙盒运行与版本号
flatpak run com.openai.chatgpt --version
# 输出: 26.917.61114

# 导出为单文件离线分发 Bundle (约 376MB)
flatpak build-bundle ~/.local/share/flatpak/repo com.openai.chatgpt.flatpak com.openai.chatgpt

# 任何机器离线安装 Bundle
flatpak install com.openai.chatgpt.flatpak
```
