#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IndexNow 自动提交脚本：发文后把新 URL 推送到 IndexNow 搜索引擎。

工作流程：
1. 从仓库根目录 sitemap.xml 提取全部 URL
2. API key 取自站根 <key>.txt 文件（key 即文件名主干，文件内容与文件名一致）
3. 构造 {host, key, keyLocation, urlList} POST 到 https://api.indexnow.org/indexnow
4. 成功后把已提交 URL 写入记录文件 .indexnow-submitted.json，供 --new 模式去重

模式：
    --all            全量提交 sitemap 中的全部 URL
    --new [--limit N] 仅提交最近 N 条新增 URL（默认 10）；记录文件为空时退化为全量

用法：
    python3 scripts/indexnow.py --new
    python3 scripts/indexnow.py --all
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITEMAP_FILE = ROOT / "sitemap.xml"
RECORD_FILE = ROOT / ".indexnow-submitted.json"
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"

#: 站根 key 文件：32 位十六进制文件名，内容即 key
KEY_FILE_RE = re.compile(r"^[0-9a-f]{32}\.txt$")
#: sitemap <loc> 提取（sitemap 由本仓库生成，格式固定，正则足够稳健）
LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
#: IndexNow 视为成功的 HTTP 状态码（200 OK / 202 Accepted）
OK_STATUS = (200, 202)
#: 网络重试次数与间隔（秒）
RETRY_TIMES = 3
RETRY_DELAY = 5


def find_key() -> tuple:
    """在站根查找 IndexNow key 文件，返回 (key, key_file_path)。

    Raises:
        FileNotFoundError: 站根不存在符合命名规则的 key 文件。
    """
    candidates = [p for p in ROOT.glob("*.txt") if KEY_FILE_RE.match(p.name)]
    if not candidates:
        raise FileNotFoundError(
            "站根未找到 IndexNow key 文件（应为 32 位十六进制 .txt）"
        )
    key_file = sorted(candidates, key=lambda p: p.name)[0]
    key = key_file.stem
    content = key_file.read_text(encoding="utf-8").strip()
    if content and content != key:
        print(
            f"[indexnow][警告] key 文件内容({content})与文件名({key})不一致，以文件名为准",
            file=sys.stderr,
        )
    return key, key_file


def load_sitemap_urls() -> list:
    """解析 sitemap.xml，返回去重后的 URL 列表（保持文件内顺序）。

    Raises:
        FileNotFoundError: sitemap.xml 不存在。
        ValueError: sitemap.xml 中没有任何 URL。
    """
    if not SITEMAP_FILE.exists():
        raise FileNotFoundError(f"未找到 {SITEMAP_FILE.relative_to(ROOT)}")
    urls = LOC_RE.findall(SITEMAP_FILE.read_text(encoding="utf-8"))
    seen, unique = set(), []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    if not unique:
        raise ValueError("sitemap.xml 中未提取到任何 URL")
    return unique


def load_submitted() -> set:
    """读取已提交记录文件，返回 URL 集合；文件不存在或损坏时返回空集合。"""
    if not RECORD_FILE.exists():
        return set()
    try:
        data = json.loads(RECORD_FILE.read_text(encoding="utf-8"))
        return set(data.get("submitted", []))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[indexnow][警告] 记录文件损坏，按空处理: {exc}", file=sys.stderr)
        return set()


def save_submitted(urls: set) -> None:
    """把已提交 URL 集合写回记录文件（排序保证确定性输出）。"""
    payload = {
        "submitted": sorted(urls),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    RECORD_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def submit_to_indexnow(host: str, key: str, key_location: str, url_list: list) -> int:
    """POST 提交 URL 列表到 IndexNow API，返回 HTTP 状态码。

    Raises:
        urllib.error.URLError: 重试后仍网络失败。
    """
    payload = json.dumps(
        {
            "host": host,
            "key": key,
            "keyLocation": key_location,
            "urlList": url_list,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        INDEXNOW_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    last_exc: Exception | None = None
    for attempt in range(1, RETRY_TIMES + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as resp:
                return resp.status
        except urllib.error.HTTPError as exc:
            # HTTP 错误（如 400/403）不重试，直接返回状态码交由调用方判定
            return exc.code
        except urllib.error.URLError as exc:
            last_exc = exc
            print(
                f"[indexnow] 第 {attempt}/{RETRY_TIMES} 次请求失败: {exc}",
                file=sys.stderr,
            )
            if attempt < RETRY_TIMES:
                import time

                time.sleep(RETRY_DELAY)
    raise last_exc if last_exc else urllib.error.URLError("未知网络错误")


def main(argv: list) -> int:
    """入口：按模式提取 URL、提交并更新记录。"""
    parser = argparse.ArgumentParser(description="IndexNow URL 自动提交")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--all", action="store_true", help="全量提交 sitemap 全部 URL")
    mode.add_argument("--new", action="store_true", help="仅提交相对记录新增的 URL")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="--new 模式下最多提交的新 URL 条数（默认 10）",
    )
    args = parser.parse_args(argv)

    try:
        key, key_file = find_key()
        urls = load_sitemap_urls()
    except (FileNotFoundError, ValueError) as exc:
        print(f"[indexnow] 准备阶段失败: {exc}", file=sys.stderr)
        return 1

    host = re.sub(r"^https?://", "", urls[0]).split("/")[0]
    key_location = f"https://{host}/{key_file.name}"

    submitted = load_submitted()
    if args.all:
        pending = urls
        mode_desc = "全量"
    else:
        pending = [u for u in urls if u not in submitted]
        if not pending:
            print(f"[indexnow] 无新增 URL（sitemap 共 {len(urls)} 条，均已提交），跳过")
            return 0
        if len(pending) > args.limit:
            pending = pending[: args.limit]
        mode_desc = f"增量（上限 {args.limit} 条）"
        if not submitted:
            mode_desc += "，记录为空退化为全量"

    print(f"[indexnow] 模式: {mode_desc}；待提交 {len(pending)} 条 URL")
    for url in pending:
        print(f"  - {url}")

    try:
        status = submit_to_indexnow(host, key, key_location, pending)
    except urllib.error.URLError as exc:
        print(f"[indexnow] 提交失败（网络错误，已重试 {RETRY_TIMES} 次）: {exc}", file=sys.stderr)
        return 1

    if status in OK_STATUS:
        print(f"[indexnow] 提交成功，HTTP {status}（IndexNow API 已接收）")
        save_submitted(submitted | set(pending))
        print(f"[indexnow] 记录文件已更新: {RECORD_FILE.name}（累计 {len(submitted | set(pending))} 条）")
        return 0
    print(f"[indexnow] 提交失败，HTTP {status}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
