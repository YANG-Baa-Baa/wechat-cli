# Windows Release 操作清单

这份清单用于把 `wechat-cli` 发布成 Windows 用户可直接下载的 `wechat-cli.exe`。

## 1. 手动构建测试

打开仓库页面：

https://github.com/YANG-Baa-Baa/wechat-cli

进入：

```text
Actions -> Build Windows executable -> Run workflow
```

选择 `main` 分支，然后点击运行。

构建完成后，在该次 workflow run 的页面下载 artifact：

```text
wechat-cli-windows-x64
```

里面应包含：

```text
wechat-cli.exe
```

## 2. 本机验证 exe

下载并解压后，在登录微信的 Windows 电脑上运行：

```powershell
.\wechat-cli.exe --version
.\wechat-cli.exe init
.\wechat-cli.exe sessions --limit 10 --format json
```

如果 `init` 提示无法访问 `Weixin.exe`，请用“以管理员身份运行”的 PowerShell 再试一次。

## 3. 发布正式版本

当手动构建和本机验证都通过后，创建一个 tag，例如：

```text
v0.2.5-ybb.1
```

推送 tag 后，`.github/workflows/windows-build.yml` 会自动打包并上传：

```text
wechat-cli-windows-x64.zip
```

## 4. 发布说明建议

Release 描述里建议写清楚：

- 本工具必须在登录微信的 Windows 电脑上运行
- 首次使用前需要执行 `wechat-cli init`
- 初始化会在本机 `~/.wechat-cli/` 保存配置和密钥
- 不要上传 `~/.wechat-cli/all_keys.json`
- 本工具只做本地读取，不做 AI 摘要
- AI 摘要由上层项目 `wechat-ai-summary` 负责

## 5. 分层边界

```text
wechat-cli
  底层读取组件：读取本机微信数据库并输出 JSON

wechat-ai-summary
  上层摘要应用：调用 wechat-cli，再调用大模型生成摘要、待办和重要原文
```
