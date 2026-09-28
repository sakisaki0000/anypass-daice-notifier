"""
AnyPASS STORE リセール監視 → LINE 通知

https://store.anypass.jp/resale-list を定期的に確認し、
指定アーティスト(既定: Da-iCE)の新しい出品があれば LINE に通知します。

使い方:
  python notifier.py              # 1回だけチェック (GitHub Actions 用)
  python notifier.py --loop 120   # 120秒ごとにチェックし続ける (PC 常駐用)
  python notifier.py --test       # LINE にテスト通知を送るだけ

必要な環境変数 (または同じフォルダの .env ファイル):
  LINE_CHANNEL_ACCESS_TOKEN  Messaging API のチャネルアクセストークン(長期)
  LINE_USER_ID               通知先の自分のユーザーID (U から始まる)
  ARTIST_KEYWORDS            任意。カンマ区切り。既定 "Da-iCE"
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://store.anypass.jp"
LIST_URL = f"{BASE_URL}/resale-list"
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
HERE = Path(__file__).resolve().parent
STATE_FILE = HERE / "seen.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.8",
}


# ---------- 設定 ----------
def load_dotenv():
    env = HERE / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def norm(s: str) -> str:
    """全角/半角・大文字小文字・記号ゆれを吸収 (Da-iCE / DA-ICE / da ice など)"""
    s = unicodedata.normalize("NFKC", s).lower()
    return re.sub(r"[\s\-‐‑–—ー_・]", "", s)


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s)).strip()


# ---------- 取得・解析 ----------
def fetch_listings():
    r = requests.get(LIST_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return parse_listings(r.text)


def parse_listings(html: str):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for a in soup.select("a.resale-list-item"):
        href = a.get("href", "")
        m = re.search(r"/resale/(\d+)", href)
        if not m:
            continue
        details = a.select_one(".item__details")
        artist_el = details.select_one("p > span") if details else None
        seat = a.select_one(".seat-icon")
        qty = a.select_one("span.ticket-info")
        price_el = a.select_one("p.ticket-info")
        items.append({
            "id": m.group(1),
            "url": BASE_URL + href if href.startswith("/") else href,
            "artist": clean(artist_el.get_text()) if artist_el else "",
            "title": clean(a.select_one(".title").get_text()) if a.select_one(".title") else "",
            "location": clean(a.select_one(".location").get_text()) if a.select_one(".location") else "",
            "date": clean(a.select_one(".date").get_text()) if a.select_one(".date") else "",
            "seat": clean(seat.get_text()) if seat else "",
            "qty": clean(qty.get_text()) if qty else "",
            "price": clean(price_el.get_text()) if price_el else "",
        })
    return items


def matches(item, keywords):
    text = norm(item["artist"] + " " + item["title"])
    return any(norm(k) in text for k in keywords)


# ---------- LINE ----------
def build_message(item, label):
    lines = [
        f"[{label}] {item['artist'] or label} のチケットが見つかりました。",
        "",
        f"タイトル: {item['title']}",
        f"場所: {item['location']}",
        f"時間: {item['date']}",
    ]
    if item["seat"]:
        lines.append(f"席種: {item['seat']} × {item['qty']}枚")
    if item["price"]:
        lines.append(f"価格: {item['price']}")
    lines += ["", item["url"]]
    return "\n".join(lines)


def send_line(texts):
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if not token or not user_id:
        sys.exit("LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID が設定されていません")
    # 1回のpushで最大5メッセージまで
    for i in range(0, len(texts), 5):
        body = {"to": user_id, "messages": [{"type": "text", "text": t[:5000]} for t in texts[i:i + 5]]}
        r = requests.post(
            LINE_PUSH_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            data=json.dumps(body),
            timeout=30,
        )
        if r.status_code != 200:
            raise RuntimeError(f"LINE送信エラー {r.status_code}: {r.text}")


# ---------- 状態 ----------
def load_seen():
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()


def save_seen(seen):
    # 古いIDが溜まりすぎないよう新しい順に最大2000件だけ保持
    ids = sorted(seen, key=int, reverse=True)[:2000]
    STATE_FILE.write_text(json.dumps(ids, indent=0), encoding="utf-8")


# ---------- メイン ----------
def check_once(keywords, label):
    items = fetch_listings()
    seen = load_seen()
    hits = [it for it in items if matches(it, keywords)]
    new = [it for it in hits if it["id"] not in seen]
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] 出品 {len(items)}件 / 対象 {len(hits)}件 / 新規 {len(new)}件", flush=True)
    if new:
        send_line([build_message(it, label) for it in reversed(new)])  # 古い順に送る
        seen.update(it["id"] for it in new)
        save_seen(seen)
    return len(new)


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0, help="この秒数ごとに繰り返す (最低60秒)")
    ap.add_argument("--test", action="store_true", help="LINEにテスト通知を送る")
    args = ap.parse_args()

    keywords = [k.strip() for k in os.environ.get("ARTIST_KEYWORDS", "Da-iCE").split(",") if k.strip()]
    label = keywords[0]

    if args.test:
        send_line([f"[{label}] テスト通知です。この通知が届けば設定OKです。\n{LIST_URL}"])
        print("テスト通知を送信しました")
        return

    if not args.loop:
        check_once(keywords, label)
        return

    interval = max(60, args.loop)  # サイトに負荷をかけないよう最低60秒
    print(f"{interval}秒ごとに監視します (Ctrl+C で終了)  対象: {keywords}")
    while True:
        try:
            check_once(keywords, label)
        except Exception as e:
            print(f"エラー: {e}", flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
