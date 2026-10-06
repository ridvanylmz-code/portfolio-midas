#!/usr/bin/env python3
"""Ön piyasa / kapanış sonrası fiyatları (TradingView tarayıcısı, gayriresmi, anahtarsız).

Çıktı: docs/data/extended.json   (+ opsiyonel Telegram özeti: --telegram)
- Mevcut sistem (monitor.py, update_position.py, dashboard) bu dosyayı kullanmaz; hata olursa hiçbir şeyi bozmaz.
- Bir istek başarısız olursa önceki başarılı veri korunur (stale=true) ve 'log' alanına yazılır.
- Hisse listesi docs/data/portfolio.json'dan okunur (pozisyonlar + izleme listesi).
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

OUT = "docs/data/extended.json"
PORTFOLIO = "docs/data/portfolio.json"
URL = "https://scanner.tradingview.com/america/scan"
ET = ZoneInfo("America/New_York")
IST = ZoneInfo("Europe/Istanbul")
COLS = ["name", "exchange", "close", "change", "premarket_close", "premarket_change",
        "postmarket_close", "postmarket_change", "market_cap_basic"]
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
           "Content-Type": "application/json", "Origin": "https://www.tradingview.com",
           "Referer": "https://www.tradingview.com/"}
LOG = []


def log(msg):
    print(msg, flush=True)
    LOG.append(msg)


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def session_name(now):
    """ABD seans dilimi (ET): ön piyasa 04:00-09:30, normal 09:30-16:00, kapanış sonrası 16:00-20:00."""
    t = now.astimezone(ET)
    if t.weekday() >= 5:
        return "kapali"
    m = t.hour * 60 + t.minute
    if 4 * 60 <= m < 9 * 60 + 30:
        return "pre"
    if 9 * 60 + 30 <= m < 16 * 60:
        return "regular"
    if 16 * 60 <= m < 20 * 60:
        return "post"
    return "kapali"


def build_payload(tickers, cols):
    return {
        "filter": [{"left": "name", "operation": "in_range", "right": tickers}],
        "options": {"lang": "en"},
        "markets": ["america"],
        "symbols": {"query": {"types": ["stock", "dr", "fund"]}, "tickers": []},
        "columns": cols,
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
        "range": [0, 500],
    }


def parse(rows, cols):
    """Satırlar market cap'e göre azalan geliyor; aynı ticker için ilk satırı al."""
    idx = {c: i for i, c in enumerate(cols)}
    out = {}
    for row in rows or []:
        d = row.get("d") or []
        name = d[idx["name"]] if "name" in idx and len(d) > idx["name"] else None
        if not name or name in out:
            continue

        def g(k):
            i = idx.get(k)
            v = d[i] if i is not None and i < len(d) else None
            return round(float(v), 4) if isinstance(v, (int, float)) else None

        out[name] = {
            "exchange": d[idx["exchange"]] if "exchange" in idx else None,
            "close": g("close"), "change_pct": g("change"),
            "pre": g("premarket_close"), "pre_pct": g("premarket_change"),
            "post": g("postmarket_close"), "post_pct": g("postmarket_change"),
        }
    return out


def fetch(tickers):
    cols = list(COLS)
    for attempt in range(2):
        r = requests.post(URL, json=build_payload(tickers, cols), headers=HEADERS, timeout=20)
        if r.status_code == 200:
            return parse(r.json().get("data"), cols), cols
        log(f"TradingView HTTP {r.status_code} (deneme {attempt + 1}): {r.text[:200]!r}")
        if r.status_code == 400 and attempt == 0:
            # bilinmeyen kolon olabilir: temel alanlara düş
            cols = [c for c in cols if c in ("name", "exchange", "close", "change", "market_cap_basic")]
            log("Genişletilmiş kolonlar reddedildi; yalnızca temel kolonlarla denendi")
            continue
        break
    return None, cols


def fmt(v, pct=None):
    if v is None:
        return "—"
    return f"${v:,.2f}" + (f" ({pct:+.2f}%)" if pct is not None else "")


def telegram_text(data):
    now = datetime.fromisoformat(data["updated"]).astimezone(IST)
    sess = {"pre": "Ön piyasa", "post": "Kapanış sonrası", "regular": "Normal seans",
            "kapali": "Seans dışı"}[data["session"]]
    lines = [f"<b>🧪 Genişletilmiş saat testi</b> · {now:%d.%m %H:%M} (İstanbul)", f"Seans: {sess}", ""]
    pf = load_json(PORTFOLIO, {})
    for title, names in (("Pozisyonlar", list(pf.get("portfolio", {}))), ("İzleme", pf.get("watchlist", []))):
        lines.append(f"<b>{title}</b>")
        for t in names:
            q = data["quotes"].get(t)
            if not q:
                lines.append(f"• {common.e(t)}: veri yok")
                continue
            lines.append(f"• <b>{common.e(t)}</b> kapanış {fmt(q['close'])} · ön {fmt(q['pre'], q['pre_pct'])} · sonrası {fmt(q['post'], q['post_pct'])}")
        lines.append("")
    n_ext = sum(1 for q in data["quotes"].values() if q["pre"] is not None or q["post"] is not None)
    lines.append(f"Ön/sonrası verisi gelen hisse: {n_ext}/{len(data['quotes'])}")
    if data.get("log"):
        lines.append("⚠️ " + common.e("; ".join(data["log"])[:300]))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--telegram", action="store_true", help="Özet mesajı Telegram'a gönder")
    args = ap.parse_args()

    pf = load_json(PORTFOLIO, {})
    tickers = sorted(set(list(pf.get("portfolio", {})) + list(pf.get("watchlist", []))))
    prev = load_json(OUT, {}) or {}
    now = datetime.now(timezone.utc)
    quotes, stale = {}, False
    try:
        got, cols = fetch(tickers)
    except Exception as ex:  # ağ hatası vb.; tüm çalışmayı düşürme
        log(f"İstek hatası: {type(ex).__name__}")
        got = None
    if got is None:
        stale = True
        quotes = {t: {**q, "stale": True} for t, q in (prev.get("quotes") or {}).items()}
    else:
        quotes = got
        missing = [t for t in tickers if t not in quotes]
        if missing:
            log("Veri gelmeyen: " + ", ".join(missing))

    data = {"updated": now.isoformat(timespec="seconds"), "session": session_name(now),
            "source": "TradingView scanner (gayriresmi)", "stale": stale, "quotes": quotes, "log": LOG}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"{len(quotes)} hisse yazıldı, seans={data['session']}, stale={stale}")
    if args.telegram:
        common.send_telegram(telegram_text(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
