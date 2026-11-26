# Code Signing & Verification Policy

AutoClip is a free, MIT-licensed desktop application maintained independently. While public releases are built transparently on GitHub Actions, commercial code-signing certificates (Apple Developer ID notarization and Windows EV Authenticode) are not yet enabled — progress is tracked in [#119](https://github.com/zhouxiaoka/autoclip/issues/119).

Because the installers are currently unsigned, macOS Gatekeeper and Windows SmartScreen will show an "unidentified developer" warning on first launch. This document explains how to verify an installer and safely open it.

---

## Opening an Unsigned Build

### macOS (Apple Silicon)

After dragging **AutoClip Desktop** to `/Applications`, if macOS says the app cannot be opened or is damaged:

1. **Via Terminal (fastest):**
   ```bash
   xattr -dr com.apple.quarantine "/Applications/AutoClip Desktop.app"
   ```
2. **Or via System Settings:** open **System Settings → Privacy & Security**, scroll to the Security section, and click **Open Anyway**.

### Windows (x64)

When running `AutoClip Desktop_*_x64-setup.exe`, if **Windows Defender SmartScreen** appears:

1. Click **More info** (*更多信息*).
2. Click **Run anyway** (*仍要运行*).

---

## How to Verify Installer Integrity

Every official release is built exclusively from tagged commits on GitHub Actions ([`Desktop Build`](.github/workflows/desktop-build.yml)) and ships with `build-provenance.json` containing the exact source commit SHA and SHA-256 hashes of every installer.

- **macOS / Linux:**
  ```bash
  shasum -a 256 "AutoClip Desktop_"*"_aarch64.dmg"
  ```
- **Windows (PowerShell):**
  ```powershell
  Get-FileHash "AutoClip Desktop_*_x64-setup.exe" -Algorithm SHA256
  ```

Compare the output against the SHA-256 listed in the corresponding [GitHub Release](https://github.com/zhouxiaoka/autoclip/releases/latest) assets.

---

## Network & Privacy Guarantee

AutoClip is **local-first**:

- Cutting, reframing, caption burning, and rendering run locally on your machine.
- Your videos are **never** uploaded to any AutoClip server.
- API keys are stored locally on your machine and sent only to the model provider endpoint you configure.
- Optional anonymous crash reports and usage analytics can be turned off at any time in **Settings**. See [Privacy Policy](docs/PRIVACY.en.md).

---

## 中文说明（未签名安装包放行指引）

AutoClip 目前由独立开发者免费维护，尚未购买商业代码签名证书（Apple 公证与 Windows 签名进度见 [#119](https://github.com/zhouxiaoka/autoclip/issues/119)）。所有正式安装包均通过 GitHub Actions 公开构建并附带 SHA-256 校验值：

- **macOS**：安装后若提示“无法打开”或“已损坏”，在终端执行 `xattr -dr com.apple.quarantine "/Applications/AutoClip Desktop.app"`，或在「系统设置 → 隐私与安全性」中点击**仍要打开**。
- **Windows**：若弹出 SmartScreen 蓝色拦截框，点击**更多信息 → 仍要运行**即可。
- **隐私承诺**：剪辑与渲染完全在本机完成，不会上传你的视频或 API Key；可选匿名统计可在设置页随时关闭。
