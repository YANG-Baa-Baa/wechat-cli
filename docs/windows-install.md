# Windows 安装与初始化

本文档面向需要在登录微信的 Windows 电脑上读取微信 4.x 本地数据库的用户。

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
cd wechat-cli
python -m pip install -e .
```

### 方式三：使用发布页 exe

当 GitHub Release 已发布 Windows 构建后，下载 `wechat-cli-windows-x64.zip`，解压后运行：

```powershell
.\wechat-cli.exe --version
```

## 初始化

初始化必须在登录微信的 Windows 电脑上执行。请确保微信正在运行，然后打开 PowerShell：

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

## 验证读取

查看最近会话：

```powershell
wechat-cli sessions --limit 10 --format json
```

读取指定聊天的时间段消息：

```powershell
wechat-cli history "项目群" --start-time "2026-07-01 00:00:00" --end-time "2026-07-19 23:59:59" --limit 2000 --format json
```

搜索指定聊天：

```powershell
wechat-cli search "截止日期" --chat "项目群" --start-time "2026-07-01" --end-time "2026-07-19" --format json
```

## 与 AI 摘要工具分层

`wechat-cli` 只负责本地读取和 JSON 输出。上层 AI 摘要工具应通过命令行调用它，例如：

```powershell
wechat-cli history "项目群" --start-time "2026-07-01" --end-time "2026-07-19" --format json
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

### 找不到微信数据目录

确认微信 4.x 已登录，并且本机存在 `xwechat_files` 数据目录。也可以手动指定：

```powershell
wechat-cli init --db-dir "D:\\WeChatData\\xwechat_files\\账号\\db_storage"
```

### Weixin.exe 未运行

先启动微信并登录，再执行：

```powershell
wechat-cli init --force
```

### 权限不足

Windows 密钥提取需要读取 `Weixin.exe` 进程内存。遇到权限问题时，请以管理员身份运行 PowerShell。
