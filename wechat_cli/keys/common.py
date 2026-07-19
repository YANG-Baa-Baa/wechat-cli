"""
跨平台共享的内存扫描逻辑：HMAC 验证、DB 收集、hex 模式匹配与结果输出。

从 wechat-decrypt/key_scan_common.py 适配，save_results 改为返回 dict。
"""

import hashlib
import hmac as hmac_mod
import json
import os
import re
import struct

from Crypto.Cipher import AES

PAGE_SZ = 4096
KEY_SZ = 32
SALT_SZ = 16
RESERVE_SZ = 80
SQLITE_HDR = b"SQLite format 3\x00"


def verify_enc_key(enc_key, db_page1):
    """通过 HMAC-SHA512 校验 page 1 验证 enc_key 是否正确。"""
    salt = db_page1[:SALT_SZ]
    mac_salt = bytes(b ^ 0x3A for b in salt)
    mac_key = hashlib.pbkdf2_hmac("sha512", enc_key, mac_salt, 2, dklen=KEY_SZ)
    hmac_data = db_page1[SALT_SZ: PAGE_SZ - 80 + 16]
    stored_hmac = db_page1[PAGE_SZ - 64: PAGE_SZ]
    hm = hmac_mod.new(mac_key, hmac_data, hashlib.sha512)
    hm.update(struct.pack("<I", 1))
    return hm.digest() == stored_hmac


def verify_enc_key_by_plaintext(enc_key, db_page1):
    """通过解密第一页后的 SQLite 页头字段验证 enc_key。

    这是 HMAC 校验的补充，用于兼容 HMAC 参数可能变化的 SQLCipher 变体。
    """
    try:
        iv = db_page1[PAGE_SZ - RESERVE_SZ: PAGE_SZ - RESERVE_SZ + 16]
        encrypted = db_page1[SALT_SZ: PAGE_SZ - RESERVE_SZ]
        decrypted = AES.new(enc_key, AES.MODE_CBC, iv).decrypt(encrypted)
    except Exception:
        return False

    page = SQLITE_HDR + decrypted + b"\x00" * RESERVE_SZ
    if not page.startswith(SQLITE_HDR):
        return False

    page_size = struct.unpack(">H", page[16:18])[0]
    if page_size == 1:
        page_size = 65536
    if page_size != PAGE_SZ:
        return False
    if page[18] not in (1, 2) or page[19] not in (1, 2):
        return False
    if page[20] != 0:
        return False
    if page[21:24] != b"\x40\x20\x20":
        return False
    schema_format = struct.unpack(">I", page[44:48])[0]
    if schema_format not in (0, 1, 2, 3, 4):
        return False
    text_encoding = struct.unpack(">I", page[56:60])[0]
    if text_encoding not in (0, 1, 2, 3):
        return False
    return True


def collect_db_files(db_dir):
    """遍历 db_dir 收集所有 .db 文件及其 salt。

    返回 (db_files, salt_to_dbs):
      db_files: [(rel_path, abs_path, size, salt_hex, page1_bytes), ...]
      salt_to_dbs: {salt_hex: [rel_path, ...]}
    """
    db_files = []
    salt_to_dbs = {}
    for root, dirs, files in os.walk(db_dir):
        for name in files:
            if not name.endswith(".db") or name.endswith("-wal") or name.endswith("-shm"):
                continue
            path = os.path.join(root, name)
            size = os.path.getsize(path)
            if size < PAGE_SZ:
                continue
            with open(path, "rb") as f:
                page1 = f.read(PAGE_SZ)
            rel = os.path.relpath(path, db_dir)
            salt = page1[:SALT_SZ].hex()
            db_files.append((rel, path, size, salt, page1))
            salt_to_dbs.setdefault(salt, []).append(rel)
    return db_files, salt_to_dbs


def _verify_candidate_key(enc_key, page1):
    if verify_enc_key(enc_key, page1):
        return "hmac"
    if verify_enc_key_by_plaintext(enc_key, page1):
        return "plaintext"
    return ""


def _record_found_key(enc_key_hex, salt_hex, db_files, salt_to_dbs, key_map,
                      remaining_salts, addr, pid, print_fn, source, verified_by):
    key_map[salt_hex] = enc_key_hex
    remaining_salts.discard(salt_hex)
    dbs = salt_to_dbs[salt_hex]
    print_fn(f"\n  [FOUND] salt={salt_hex} ({source}, verified={verified_by})")
    print_fn(f"    enc_key={enc_key_hex}")
    print_fn(f"    PID={pid} 地址: 0x{addr:016X}")
    print_fn(f"    数据库: {', '.join(dbs)}")


def _try_raw_key(enc_key, db_files, salt_to_dbs, key_map, remaining_salts,
                 addr, pid, print_fn, source):
    if len(enc_key) != KEY_SZ or enc_key == b"\x00" * KEY_SZ:
        return False
    enc_key_hex = enc_key.hex()
    for rel, path, sz, salt_hex_db, page1 in db_files:
        if salt_hex_db in remaining_salts:
            verified_by = _verify_candidate_key(enc_key, page1)
            if verified_by:
                _record_found_key(
                    enc_key_hex, salt_hex_db, db_files, salt_to_dbs, key_map,
                    remaining_salts, addr, pid, print_fn, source, verified_by,
                )
                return True
    return False


def _try_hex_key(hex_str, db_files, salt_to_dbs, key_map, remaining_salts,
                 addr, pid, print_fn, source="ascii"):
    hex_len = len(hex_str)

    if hex_len == 96:
        enc_key_hex = hex_str[:64]
        salt_hex = hex_str[64:]
        if salt_hex in remaining_salts:
            enc_key = bytes.fromhex(enc_key_hex)
            for rel, path, sz, s, page1 in db_files:
                if s == salt_hex:
                    verified_by = _verify_candidate_key(enc_key, page1)
                    if verified_by:
                        _record_found_key(
                            enc_key_hex, salt_hex, db_files, salt_to_dbs, key_map,
                            remaining_salts, addr, pid, print_fn, source, verified_by,
                        )
                        return True

    elif hex_len == 64:
        if not remaining_salts:
            return False
        return _try_raw_key(
            bytes.fromhex(hex_str), db_files, salt_to_dbs, key_map,
            remaining_salts, addr, pid, print_fn, source,
        )

    elif hex_len > 96 and hex_len % 2 == 0:
        enc_key_hex = hex_str[:64]
        salt_hex = hex_str[-32:]
        if salt_hex in remaining_salts:
            enc_key = bytes.fromhex(enc_key_hex)
            for rel, path, sz, s, page1 in db_files:
                if s == salt_hex:
                    verified_by = _verify_candidate_key(enc_key, page1)
                    if verified_by:
                        _record_found_key(
                            enc_key_hex, salt_hex, db_files, salt_to_dbs, key_map,
                            remaining_salts, addr, pid, print_fn,
                            f"{source}, long hex {hex_len}", verified_by,
                        )
                        return True

    return False


def scan_memory_for_keys(data, hex_re, db_files, salt_to_dbs, key_map,
                         remaining_salts, base_addr, pid, print_fn):
    """扫描一段内存数据，匹配 ASCII x'hex' 模式并验证密钥。"""
    matches = 0
    for m in hex_re.finditer(data):
        hex_str = m.group(1).decode()
        addr = base_addr + m.start()
        matches += 1
        _try_hex_key(
            hex_str, db_files, salt_to_dbs, key_map,
            remaining_salts, addr, pid, print_fn,
        )
    return matches


def scan_memory_for_bare_keys(data, bare_hex_re, db_files, salt_to_dbs, key_map,
                              remaining_salts, base_addr, pid, print_fn):
    """扫描裸 64/96 位 hex 字符串并验证密钥。"""
    matches = 0
    for m in bare_hex_re.finditer(data):
        hex_str = m.group(1).decode()
        addr = base_addr + m.start(1)
        matches += 1
        _try_hex_key(
            hex_str, db_files, salt_to_dbs, key_map,
            remaining_salts, addr, pid, print_fn, source="bare-ascii",
        )
    return matches


def scan_memory_for_wide_keys(data, wide_hex_re, db_files, salt_to_dbs, key_map,
                              remaining_salts, base_addr, pid, print_fn):
    """扫描 UTF-16LE 形式的 x'hex' 字符串并验证密钥。"""
    matches = 0
    for m in wide_hex_re.finditer(data):
        raw = m.group(1)
        hex_str = raw.replace(b"\x00", b"").decode()
        addr = base_addr + m.start()
        matches += 1
        _try_hex_key(
            hex_str, db_files, salt_to_dbs, key_map,
            remaining_salts, addr, pid, print_fn, source="utf-16le",
        )
    return matches


def scan_memory_for_bare_wide_keys(data, bare_wide_hex_re, db_files, salt_to_dbs,
                                   key_map, remaining_salts, base_addr, pid, print_fn):
    """扫描 UTF-16LE 形式的裸 64/96 位 hex 字符串并验证密钥。"""
    matches = 0
    for m in bare_wide_hex_re.finditer(data):
        raw = m.group(1)
        hex_str = raw.replace(b"\x00", b"").decode()
        addr = base_addr + m.start(1)
        matches += 1
        _try_hex_key(
            hex_str, db_files, salt_to_dbs, key_map,
            remaining_salts, addr, pid, print_fn, source="bare-utf-16le",
        )
    return matches


def scan_memory_for_salt_nearby_raw_keys(data, db_files, salt_to_dbs, key_map,
                                         remaining_salts, base_addr, pid, print_fn,
                                         window=96):
    """寻找数据库 salt 原始字节，并在附近尝试 32 字节 raw key 候选。"""
    attempts = 0
    salts = [(bytes.fromhex(salt_hex), salt_hex) for salt_hex in remaining_salts]
    for salt, salt_hex in salts:
        start = 0
        while True:
            pos = data.find(salt, start)
            if pos < 0:
                break
            start = pos + 1
            lower = max(0, pos - window)
            upper = min(len(data), pos + SALT_SZ + window)
            for key_pos in range(lower, upper - KEY_SZ + 1):
                if key_pos <= pos < key_pos + KEY_SZ:
                    continue
                candidate = data[key_pos:key_pos + KEY_SZ]
                attempts += 1
                if _try_raw_key(
                    candidate, db_files, salt_to_dbs, key_map, remaining_salts,
                    base_addr + key_pos, pid, print_fn, source=f"raw-near-salt:{salt_hex}",
                ):
                    return attempts
    return attempts


def cross_verify_keys(db_files, salt_to_dbs, key_map, print_fn):
    """用已找到的 key 交叉验证未匹配的 salt。"""
    missing_salts = set(salt_to_dbs.keys()) - set(key_map.keys())
    if not missing_salts or not key_map:
        return
    print_fn(f"\n还有 {len(missing_salts)} 个 salt 未匹配，尝试交叉验证...")
    for salt_hex in list(missing_salts):
        for rel, path, sz, s, page1 in db_files:
            if s == salt_hex:
                for known_salt, known_key_hex in key_map.items():
                    enc_key = bytes.fromhex(known_key_hex)
                    verified_by = _verify_candidate_key(enc_key, page1)
                    if verified_by:
                        key_map[salt_hex] = known_key_hex
                        print_fn(f"  [CROSS] salt={salt_hex} 可用 key from salt={known_salt} (verified={verified_by})")
                        missing_salts.discard(salt_hex)
                break


def save_results(db_files, salt_to_dbs, key_map, output_path, print_fn):
    """保存密钥结果到 JSON 文件。

    Args:
        db_files: collect_db_files 返回的 db_files
        salt_to_dbs: collect_db_files 返回的 salt_to_dbs
        key_map: {salt_hex: enc_key_hex}
        output_path: 输出 JSON 文件路径
        print_fn: 日志输出函数

    Returns:
        dict: salt_hex -> enc_key_hex 映射

    Raises:
        RuntimeError: 未提取到任何密钥
    """
    print_fn(f"\n{'=' * 60}")
    print_fn(f"结果: {len(key_map)}/{len(salt_to_dbs)} salts 找到密钥")

    result = {}
    for rel, path, sz, salt_hex, page1 in db_files:
        if salt_hex in key_map:
            result[rel] = {
                "enc_key": key_map[salt_hex],
                "salt": salt_hex,
                "size_mb": round(sz / 1024 / 1024, 1)
            }
            print_fn(f"  OK: {rel} ({sz / 1024 / 1024:.1f}MB)")
        else:
            print_fn(f"  MISSING: {rel} (salt={salt_hex})")

    if not result:
        print_fn(f"\n[!] 未提取到任何密钥")
        raise RuntimeError("未能从任何微信进程中提取到密钥")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print_fn(f"\n密钥保存到: {output_path}")

    missing = [rel for rel, path, sz, salt_hex, page1 in db_files if salt_hex not in key_map]
    if missing:
        print_fn(f"\n未找到密钥的数据库:")
        for rel in missing:
            print_fn(f"  {rel}")

    return key_map
