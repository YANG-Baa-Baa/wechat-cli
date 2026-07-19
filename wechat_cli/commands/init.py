"""init 命令 — 交互式初始化，提取密钥并生成配置"""

import json
import os
import platform
import re
import sys

import click

from ..core.config import STATE_DIR, CONFIG_FILE, KEYS_FILE, auto_detect_db_dir


HEX_KEY_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _normalize_manual_key(value):
    """Normalize a user supplied SQLCipher key string to 64 hex chars."""
    key = value.strip()
    if key.lower().startswith("x'") and key.endswith("'"):
        key = key[2:-1]
    key = key.strip()
    if not HEX_KEY_RE.match(key):
        raise click.ClickException("--key 必须是 64 位十六进制字符串，例如 0123...abcd")
    return key.lower()


def _import_manual_key(db_dir, manual_key, output_path):
    from ..keys.common import collect_db_files, verify_enc_key, verify_enc_key_by_plaintext

    enc_key_hex = _normalize_manual_key(manual_key)
    enc_key = bytes.fromhex(enc_key_hex)
    db_files, salt_to_dbs = collect_db_files(db_dir)
    result = {}

    click.echo(f"找到 {len(db_files)} 个数据库，开始验证手动 key...")
    for rel, path, sz, salt_hex, page1 in db_files:
        if verify_enc_key(enc_key, page1) or verify_enc_key_by_plaintext(enc_key, page1):
            result[rel] = {
                "enc_key": enc_key_hex,
                "salt": salt_hex,
                "size_mb": round(sz / 1024 / 1024, 1),
            }
            click.echo(f"  OK: {rel} ({sz / 1024 / 1024:.1f}MB)")
        else:
            click.echo(f"  MISSING: {rel} (salt={salt_hex})")

    if not result:
        raise click.ClickException("手动 key 无法解密任何数据库，请确认 key 和当前微信账号匹配")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    missing = len(db_files) - len(result)
    if missing:
        click.echo(f"\n[!] 有 {missing} 个数据库未能使用该 key 解密，可能使用了不同 key 或不是消息数据库")
    click.echo(f"\n密钥保存到: {output_path}")
    return result


@click.command()
@click.option("--db-dir", default=None, help="微信数据目录路径（默认自动检测）")
@click.option("--force", is_flag=True, help="强制重新提取密钥")
@click.option("--key", "manual_key", default=None, help="手动指定 64 位 hex 数据库密钥，跳过进程内存扫描")
def init(db_dir, force, manual_key):
    """初始化 wechat-cli：提取密钥并生成配置"""
    click.echo("WeChat CLI 初始化")
    click.echo("=" * 40)

    # 1. 检查是否已初始化
    if os.path.exists(CONFIG_FILE) and os.path.exists(KEYS_FILE) and not force:
        click.echo(f"已初始化（配置: {CONFIG_FILE}）")
        click.echo("使用 --force 重新提取密钥")
        return

    # 2. 创建状态目录
    os.makedirs(STATE_DIR, exist_ok=True)

    # 3. 确定 db_dir
    if db_dir is None:
        db_dir = auto_detect_db_dir()
        if db_dir is None:
            click.echo("[!] 未能自动检测到微信数据目录", err=True)
            click.echo("请通过 --db-dir 参数指定，例如:", err=True)
            click.echo("  wechat-cli init --db-dir ~/path/to/db_storage", err=True)
            sys.exit(1)
        click.echo(f"[+] 检测到微信数据目录: {db_dir}")
    else:
        db_dir = os.path.abspath(db_dir)
        if not os.path.isdir(db_dir):
            click.echo(f"[!] 目录不存在: {db_dir}", err=True)
            sys.exit(1)
        click.echo(f"[+] 使用指定数据目录: {db_dir}")

    # 4. 提取或导入密钥
    try:
        if manual_key:
            click.echo("\n开始导入手动密钥...")
            key_map = _import_manual_key(db_dir, manual_key, KEYS_FILE)
        else:
            click.echo("\n开始提取密钥...")
            from ..keys import extract_keys
            key_map = extract_keys(db_dir, KEYS_FILE)
    except click.ClickException as e:
        raise e
    except RuntimeError as e:
        click.echo(f"\n[!] 密钥提取失败: {e}", err=True)
        if platform.system().lower() == "windows":
            click.echo("提示: 请使用 64 位管理员 PowerShell，重启微信后执行 init --force；若仍失败，可使用 init --key 手动导入已知数据库密钥。", err=True)
        elif "sudo" not in str(e).lower():
            click.echo("提示: macOS/Linux 可能需要 sudo 权限", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"\n[!] 密钥提取出错: {e}", err=True)
        sys.exit(1)

    # 5. 写入配置
    cfg = {
        "db_dir": db_dir,
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    click.echo(f"\n[+] 初始化完成!")
    click.echo(f"    配置: {CONFIG_FILE}")
    click.echo(f"    密钥: {KEYS_FILE}")
    click.echo(f"    提取到 {len(key_map)} 个数据库密钥")
    click.echo("\n现在可以使用:")
    click.echo("  wechat-cli sessions")
    click.echo("  wechat-cli history \"联系人\"")
