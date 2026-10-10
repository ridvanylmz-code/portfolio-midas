"""BIST günlük mumları (Teknik sekmesindeki grafik için): yfinance (.IS) -> bars-bist.json.

Biçim ABD'deki bars.json ile aynıdır: {"updated", "source", "bars": {SEMBOL: [[YYYY-MM-DD, o, h, l, c], ...]}}.
Veri alınamayan hisse önceki dosyadaki mumlarıyla kalır (--prev). Kaynağı çalışmazsa çıkış kodu 0 döner (grafik
yalnızca eski veriyle kalır; iş akışı bozulmaz).
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone


def parse_tickers(text):
    return [t for t in re.split(r"[\s,;]+", text.upper()) if t]


def fetch(sym, days):
    import yfinance as yf
    df = yf.Ticker(sym + ".IS").history(period=f"{days}d", interval="1d", auto_adjust=False)
    if df is None or df.empty:
        return None
    out = []
    for ts, r in df.iterrows():
        o, h, l, c = (float(r[k]) for k in ("Open", "High", "Low", "Close"))
        if c > 0 and h >= l > 0:
            out.append([ts.strftime("%Y-%m-%d"), round(o, 4), round(h, 4), round(l, 4), round(c, 4)])
    return out or None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="trend/bist_tickers.txt")
    ap.add_argument("--prev", default="")
    ap.add_argument("--out", default="bars-bist.json")
    ap.add_argument("--days", type=int, default=270)
    a = ap.parse_args(argv)

    with open(a.file, encoding="utf-8") as f:
        tickers = list(dict.fromkeys(parse_tickers(re.sub(r"#.*", "", f.read()))))
    prev = {}
    if a.prev and os.path.exists(a.prev):
        try:
            prev = (json.load(open(a.prev, encoding="utf-8")) or {}).get("bars") or {}
        except (OSError, ValueError):
            prev = {}

    bars, ok = {}, 0
    for t in tickers:
        try:
            rows = fetch(t, a.days)
        except Exception as ex:  # ağ/kütüphane hatası tek hisseyi düşürür
            print(f"{t}: {type(ex).__name__}: {str(ex)[:60]}")
            rows = None
        if rows:
            bars[t] = rows[-200:]
            ok += 1
        elif t in prev:
            bars[t] = prev[t]
    print(f"BIST günlük mum: {ok}/{len(tickers)} hisse güncellendi, toplam {len(bars)}")
    if not bars:
        return 0
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "source": "Yahoo Finance günlük (yfinance)", "bars": bars}, f, ensure_ascii=False, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
