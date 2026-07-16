#!/usr/bin/env python3
"""低频发现 pay.ldxp.cn 公开店铺；候选 Token 严格限制为 3～8 位。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
import re
import string
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

BASE = "https://pay.ldxp.cn"
API = f"{BASE}/shopApi/Shop/info"
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{3,8}$")
MAX_ATTEMPTS = 300
MIN_DELAY = 2.0

KNOWN = [
    "xdstore", "doge", "OAGQN77Z", "XRE84N7M", "CodexBro", "wckj",
    "caitou", "chaoji", "3YYTXC5R", "282D9KDL", "superman", "3KU925G2",
    "E0AJV9HG", "Lucoo", "LSSZLMUY", "aigpt", "7DQD04V0", "1490777",
    "JZ9CUHL0", "6YQL25Q0", "2E2KPQD1", "xcursor", "RBWM95T3",
]
WORDS = [
    "ai", "gpt", "openai", "claude", "gemini", "cursor", "codex", "store",
    "shop", "mall", "cloud", "api", "card", "vip", "pro",
]


@dataclass(frozen=True)
class Shop:
    token: str
    url: str
    nickname: str
    description: str
    goods_count: int | None
    card_count: int | None
    checked_at: str


def valid(token: str) -> bool:
    return bool(TOKEN_RE.fullmatch(token))


def fit(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]", "", value)[:8]
    if len(value) < 3:
        value += "".join(random.choices(string.ascii_letters + string.digits, k=3 - len(value)))
    if not valid(value):
        raise ValueError(f"无效 Token：{value!r}")
    return value


def candidate() -> str:
    mode = random.choices(
        ["upper", "lower", "number", "word", "mutate"],
        weights=[30, 20, 5, 25, 20],
        k=1,
    )[0]
    if mode == "upper":
        return "".join(random.choices(string.ascii_uppercase + string.digits, k=random.randint(3, 8)))
    if mode == "lower":
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(3, 8)))
    if mode == "number":
        return "".join(random.choices(string.digits, k=random.randint(3, 8)))
    if mode == "word":
        return fit(random.choice([
            random.choice(WORDS),
            random.choice(WORDS) + str(random.randint(1, 99)),
            random.choice(["ai", "gpt", "api", "vip", "pro"]) + str(random.randint(1, 999)),
        ]))
    seed = random.choice(KNOWN)
    return fit(random.choice([
        seed.lower(), seed.upper(), seed.capitalize(),
        f"{seed}{random.randint(1, 99)}", f"{seed}_{random.randint(1, 9)}",
        f"{seed}{random.choice(['ai', 'vip', 'pro'])}",
    ]))


def clean(value: object, limit: int = 300) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def integer(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def session() -> requests.Session:
    visitor = hashlib.sha256(f"{uuid.uuid4()}:{time.time_ns()}".encode()).hexdigest()[:32]
    client = requests.Session()
    client.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": BASE,
        "Referer": f"{BASE}/",
        "Visitorid": visitor,
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
    })
    return client


def inspect(client: requests.Session, token: str, timeout: float) -> tuple[str, Shop | None]:
    if not valid(token):
        raise ValueError(f"拒绝请求不符合 3～8 位规则的 Token：{token!r}")
    try:
        response = client.post(API, json={"token": token, "category_key": ""}, timeout=timeout)
    except requests.RequestException as exc:
        print(f"[网络错误] {token}: {exc}")
        return "error", None
    if response.status_code in (403, 429):
        print(f"[停止] HTTP {response.status_code}，可能触发限流或风控。")
        return "blocked", None
    head = response.text[:500].lower()
    if "application/json" not in response.headers.get("content-type", "").lower() and any(
        marker in head for marker in ("acw_sc__v2", "captcha", "<html")
    ):
        print("[停止] 返回了风控或 HTML 页面。")
        return "blocked", None
    try:
        payload = response.json()
    except ValueError:
        print(f"[解析错误] {token}: 非 JSON，HTTP {response.status_code}")
        return "error", None
    if payload.get("code") != 1 or not isinstance(payload.get("data"), dict):
        return "invalid", None
    data = payload["data"]
    nickname = clean(data.get("nickname"), 120)
    returned = clean(data.get("token"), 32)
    if not nickname and not returned:
        return "invalid", None
    result_token = returned if valid(returned) else token
    return "valid", Shop(
        token=result_token,
        url=f"{BASE}/shop/{result_token}",
        nickname=nickname,
        description=clean(data.get("description")),
        goods_count=integer(data.get("goods_count")),
        card_count=integer(data.get("card_count")),
        checked_at=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    )


def load_seen(paths: list[Path]) -> set[str]:
    seen = {token for token in KNOWN if valid(token)}
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            match = re.search(r"/shop/([^/?#\s]+)", line)
            value = match.group(1) if match else line
            if valid(value):
                seen.add(value)
    return seen


def append_shop(csv_path: Path, txt_path: Path, shop: Shop) -> None:
    new_file = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(shop)))
        if new_file:
            writer.writeheader()
        writer.writerow(asdict(shop))
    with txt_path.open("a", encoding="utf-8") as handle:
        handle.write(shop.url + "\n")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempts", type=int, default=100)
    parser.add_argument("--min-delay", type=float, default=2.0)
    parser.add_argument("--max-delay", type=float, default=5.0)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--output-dir", default="data/ldxp_results")
    parser.add_argument("--seed-file", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if not 1 <= args.attempts <= MAX_ATTEMPTS:
        print(f"--attempts 必须在 1～{MAX_ATTEMPTS} 之间")
        return 2
    if args.min_delay < MIN_DELAY or args.max_delay < args.min_delay:
        print("延迟参数无效：最小延迟不得低于 2 秒，最大延迟必须不小于最小延迟")
        return 2

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "valid_shops.csv"
    txt_path = output / "valid_shop_urls.txt"
    checked_path = output / "checked_tokens.txt"
    seen = load_seen([*(Path(p) for p in args.seed_file), txt_path, checked_path])
    client = session()
    checked = hits = 0

    print(f"开始低频验证：最多 {args.attempts} 次，Token 规则 {TOKEN_RE.pattern}")
    with checked_path.open("a", encoding="utf-8") as history:
        while checked < args.attempts:
            token = candidate()
            if token in seen:
                continue
            assert 3 <= len(token) <= 8 and valid(token)
            seen.add(token)
            checked += 1
            history.write(token + "\n")
            history.flush()
            status, shop = inspect(client, token, args.timeout)
            if status == "blocked":
                break
            if status == "valid" and shop:
                hits += 1
                append_shop(csv_path, txt_path, shop)
                print(f"[命中 #{hits}] {shop.url} | {shop.nickname or '-'} | goods={shop.goods_count}")
            elif status == "invalid":
                print(f"[{checked}/{args.attempts}] 未命中：{token}")
            time.sleep(random.uniform(args.min_delay, args.max_delay))

    print(f"完成：检查 {checked} 个，发现 {hits} 个有效店铺。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
