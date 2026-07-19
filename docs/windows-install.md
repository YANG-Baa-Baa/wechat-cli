# Windows 安装与初始化

本文档面向需要在登录微信的 Windows 电脑上读取微信 4.x 本地数据库的用户。

## 重要提示：不要直接双击 exe 使用

`wechat-cli.exe` 是命令行工具，不是桌面软件。直接双击时，Windows 会打开一个临时命令窗口，程序执行完就关闭，看起来就像“闪退”。

正确方式是在 PowerShell 或命令提示符里运行。

例如文件在 `D:\wechatcli`，请在 PowerShell 中运行：

```powershell
Set-Location D:\wechatcli
.\wechat-cli.exe --version
.\wechat-cli.exe init
.\wechat-cli.exe sessions --limit 10 --format json
```

如果中文显示乱码，可先运行：

```powershell
chcp 65001
```

如果你把 `wechat-cli.exe` 放进了 PATH，也可以直接运行：

```powershell
wechat-cli --version
```

## 推荐安装方式

### 方式一：使用 pipx 安装

适合已经安装 Python 3.10+ 的用户。

```powershell
python -m pip install --user pipx
python -m pipx ensurepath
pipx install git+https://github.com/YANG-Baa-Baa/wechat-cli.git
```

安装完成后重新打开终端，确认命令可用：

```powershell
wechat-cli --version
```

### 方式二：使用源码开发安装

适合需要修改或调试本项目的用户。

```powershell
git clone https://github.com/YANG-Baa-Baa/wechat-cli.git
Set-Location wechat-cli
python -m pip install -e .
```

### 方式三：使用发布页 exe

当 GitHub Release 已发布 Windows 构建后，下载 `wechat-cli-windows-x64.zip`，解压后在 PowerShell 里运行：

```powershell
Set-Location D:\wechatcli
.\wechat-cli.exe --version
```

## 初始化

初始化必须在登录微信的 Windows 电脑上执行。请确保微信正在运行，然后打开 PowerShell：

```powershell
.\wechat-cli.exe init
```

如果你使用的是 pipx 或已加入 PATH，也可以运行：

```powershell
wechat-cli init
```

如果提示无法打开 `Weixin.exe` 进程，请使用“以管理员身份运行”的 PowerShell 再试一次。

初始化成功后，配置和密钥会写入：

```text
%USERPROFILE%\.wechat-cli\
```

包括：

- `config.json`：本机微信数据库路径
- `all_keys.json`：本机数据库解密密钥

请不要把这些文件提交到 GitHub，也不要上传到服务器。

## 手动导入已知 key

Windows 4.x 的数据库结构和密钥提取是两件事：数据库读取逻辑相对稳定，但 `Weixin.exe` 内存里的 key 位置和形态可能随微信小版本变化。

如果自动扫描一直显示 `0/22 salts 找到密钥`，但你已经通过其他可信方式获得了当前账号的 64 位十六进制数据库 key，可以跳过内存扫描，直接导入：

```powershell
.\wechat-cli.exe init --force --key "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
```

工具会逐个验证本机 `.db` 文件。只有能通过验证的数据库才会写入 `%USERPROFILE%\.wechat-cli\all_keys.json`。

注意：

- `--key` 必须是 64 位 hex 字符串。
- key 只应保存在登录微信的本机，不要提交到 GitHub，也不要发到服务器。
- 如果该 key 无法解密任何数据库，说明 key 与当前微信账号或当前数据库不匹配。

## 验证读取

查看最近会话：

```powershell
.\wechat-cli.exe sessions --limit 10 --format json
```

读取指定聊天的时间段消息：

```powershell
.\wechat-cli.exe history "项目群" --start-time "2026-07-01 00:00:00" --end-time "2026-07-19 23:59:59" --limit 2000 --format json
```

搜索指定聊天：

```powershell
.\wechat-cli.exe search "截止日期" --chat "项目群" --start-time "2026-07-01" --end-time "2026-07-19" --format json
```

## 与 AI 摘要工具分层

`wechat-cli` 只负责本地读取和 JSON 输出。上层 AI 摘要工具应通过命令行调用它，例如：

```powershell
.\wechat-cli.exe history "项目群" --start-time "2026-07-01" --end-time "2026-07-19" --format json
```

然后再由上层工具调用大模型 API，生成会话摘要、待办事项和重要原文。

推荐分层：

```text
YANG-Baa-Baa/wechat-cli
  底层读取组件：密钥提取、数据库解密、消息查询、JSON 输出

YANG-Baa-Baa/wechat-ai-summary
  上层应用：批量读取、AI 摘要、结果存储、飞书/服务器推送
```

## 常见问题

### 双击 exe 后窗口一闪而过

这是命令行工具的正常表现。请打开 PowerShell，进入 exe 所在目录后运行命令。

### 输出中文乱码

在 PowerShell 里先运行：

```powershell
chcp 65001
```

### 已找到 Weixin.exe，但提取到 0 个密钥

请按顺序尝试：

1. 完全退出微信，再重新打开并登录
2. 使用 64 位 PowerShell，以管理员身份运行，不要使用标题带 `(x86)` 的 PowerShell
3. 执行：`.\wechat-cli.exe init --force`
4. 如果仍然失败，可尝试通过其他可信方式获取数据库 key，再执行：`.\wechat-cli.exe init --force --key "你的64位hex key"`
5. 如果自动扫描仍然显示大量候选但 `0/22 salts 找到密钥`，说明当前微信版本可能改变了 key 在内存中的形态，需要更新 Windows key 扫描策略

### 微信 4.1.11.55 自动提取失败

已观察到微信 Windows 4.1.11.55 可能出现这种情况：工具能检测到 `db_storage`、能读取 `Weixin.exe` 进程，也能扫描到大量候选值，但所有候选都无法通过数据库验证。

这通常不是命令写错，也不是没有管理员权限，而是当前微信小版本改变了 key 在内存中的表现形式。此时应把问题拆成两步：

1. 继续保留 `wechat-cli` 的数据库解析、联系人映射、时间范围查询和 JSON 输出能力。
2. 单独更新或替换 Windows key 提取策略；在自动提取修好前，可使用 `init --key` 导入已知 key。

### 找不到微信数据目录

确认微信 4.x 已登录，并且本机存在 `xwechat_files` 数据目录。也可以手动指定：

```powershell
.\wechat-cli.exe init --db-dir "D:\\WeChatData\\xwechat_files\\账号\\db_storage"
```

### Weixin.exe 未运行

先启动微信并登录，再执行：

```powershell
.\wechat-cli.exe init --force
```

### 权限不足

Windows 密钥提取需要读取 `Weixin.exe` 进程内存。遇到权限问题时，请以管理员身份运行 PowerShell。
