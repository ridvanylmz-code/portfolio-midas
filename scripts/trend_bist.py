#!/usr/bin/env python3
"""BIST trend tarayıcı (elle tetiklenir). ABD tarafındaki scripts/trend.py'nin BIST karşılığı.

Hisse başına: 4S Trend (4 saatlik mumlarda 8/20), 15dk Trend (34/89), 15dk Tamam yada Devam
(15dk Supertrend, ATR 10, çarpan 3), Elliott (muhtemel).
Hesap fonksiyonları (EMA, Supertrend, Elliott) ABD tarafındaki scripts/intraday.py ve scripts/trend.py'den
aynen kullanılır; burada yalnızca BIST'e özgü kısımlar vardır:
  - Kaynak: Yahoo Finance chart API, sembol soneki .IS (BIST'te ön/sonrası seans yok)
  - 4S mumlar İstanbul saatiyle 10:00-14:00 ve 14:00-18:00 dilimlerinde 15dk mumlardan birleştirilir
  - Yedek kaynak yok (Twelve Data ABD seansına göre yazılmış)

Kullanım: python scripts/trend_bist.py --file trend/bist_tickers.txt --out trend-bist.json
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import intraday as ix  # noqa: E402
import trend as tr  # noqa: E402

TRT = ZoneInfo("Europe/Istanbul")
YF_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
MAX_TICKERS = 80
MIN_BARS = 120


def log(msg):
    ix.log(msg)


def fetch_yahoo_bist(sym):
    """15dk mumlar [(epoch, o, h, l, c, v)] eskiden yeniye ya da None / 'blocked'."""
    params = {"interval": "15m", "range": "60d", "includePrePost": "false"}
    try:
        r = requests.get(YF_URL.format(sym=sym + ".IS"), params=params, headers=tr.YF_HEADERS, timeout=(6, 30))
        if r.status_code == 429:
            log(f"{sym}: Yahoo 429")
            return "blocked"
        d = r.json()
        res = (d.get("chart") or {}).get("result")
        if not res:
            err = ((d.get("chart") or {}).get("error") or {}).get("description", f"HTTP {r.status_code}")
            log(f"{sym}: Yahoo veri yok ({str(err)[:80]})")
            return None
        res = res[0]
        ts = res.get("timestamp") or []
        q = res["indicators"]["quote"][0]
        rows = []
        for i, t in enumerate(ts):
            o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
            if None in (o, h, l, c):
                continue
            rows.append((int(t), float(o), float(h), float(l), float(c), float(q["volume"][i] or 0)))
        return rows or None
    except Exception as ex:
        log(f"{sym}: Yahoo {type(ex).__name__}")
        return None


def aggregate_4h_bist(rows):
    """15dk mumları İstanbul saatiyle 10:00-14:00 / 14:00-18:00 dilimlerine birleştirir.
    Açılış öncesi (10:00'dan önce) mumlar ilk dilime, 18:00 ve sonrası ikinci dilime katılır."""
    out, cur_key = [], None
    for ts, o, h, l, c, _v in rows:
        t = datetime.fromtimestamp(ts, TRT)
        slot = 0 if t.hour < 14 else 1
        key = (t.date(), slot)
        if key != cur_key:
            out.append([ts, o, h, l, c])
            cur_key = key
        else:
            b = out[-1]
            b[2] = max(b[2], h)
            b[3] = min(b[3], l)
            b[4] = c
    return [tuple(b) for b in out]


def fresh_events(item):
    """Yeni sinyaller. Açıklamalarda yalnızca sütun adları kullanılır."""
    ev = []
    m, h = item.get("m15") or {}, item.get("h4") or {}
    if m.get("cross") and m.get("cross_bars_ago") is not None and m["cross_bars_ago"] <= 8:
        ev.append("15dk Trend " + ("▲ döndü" if m["cross"] == "up" else "▼ döndü"))
    if h.get("cross") and h.get("cross_bars_ago") is not None and h["cross_bars_ago"] <= 2:
        ev.append("4S Trend " + ("▲ döndü" if h["cross"] == "up" else "▼ döndü"))
    st = item.get("st15") or {}
    if st.get("bars_since_flip") is not None and st["bars_since_flip"] <= 8:
        ev.append("15dk Tamam yada Devam " + ("▲ Devam" if st["dir"] == "up" else "▼ Tamam"))
    return ev


def compute(rows):
    b4 = aggregate_4h_bist(rows)
    out = {
        "price": round(rows[-1][4], 4),
        "bar_time": datetime.fromtimestamp(rows[-1][0], timezone.utc).isoformat(timespec="minutes"),
        "h4": ix.ema_pair([b[4] for b in b4], 8, 20),
        "m15": ix.ema_pair([r[4] for r in rows], 34, 89),
        "elliott": ix.elliott(b4),
        "st15": tr.supertrend(rows),
    }
    out["state"], out["score"] = tr.classify(out)
    out["events"] = fresh_events(out)
    try:  # günlük değişim: önceki İstanbul günü kapanışına göre
        last_day = datetime.fromtimestamp(rows[-1][0], TRT).date()
        prev = [r for r in rows if datetime.fromtimestamp(r[0], TRT).date() < last_day]
        if prev:
            out["chg_pct"] = round((rows[-1][4] / prev[-1][4] - 1) * 100, 2)
    except Exception:
        pass
    return out


def parse_tickers(text):
    toks = [t.strip(".-") for t in re.split(r"[\s,;]+", (text or "").upper())]
    return [t for t in toks if re.fullmatch(r"[A-Z][A-Z0-9]{0,9}", t)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="", help="virgül/boşlukla ayrılmış semboller (.IS yazma)")
    ap.add_argument("--file", default="", help="satır/virgülle sembol listesi (# yorum)")
    ap.add_argument("--out", default="trend-bist.json")
    args = ap.parse_args(argv)

    tickers = parse_tickers(args.tickers)
    if not tickers and args.file and os.path.exists(args.file):
        with open(args.file, encoding="utf-8") as f:
            tickers = parse_tickers(re.sub(r"#.*", "", f.read()))
    tickers = list(dict.fromkeys(tickers))[:MAX_TICKERS]
    if not tickers:
        print("[ERROR] Sembol listesi boş.")
        return 1

    out, src = {}, {}
    for t in tickers:
        rows = fetch_yahoo_bist(t)
        if rows == "blocked":
            time.sleep(3)
            rows = fetch_yahoo_bist(t)
        if isinstance(rows, list) and len(rows) >= MIN_BARS:
            try:
                out[t] = compute(rows)
                src[t] = "Yahoo"
            except Exception as ex:
                log(f"{t}: hesap hatası {type(ex).__name__}: {str(ex)[:80]}")
                out[t] = {"state": "n/a", "error": "hesap hatası"}
        else:
            n = len(rows) if isinstance(rows, list) else 0
            log(f"{t}: yetersiz veri ({n} mum, en az {MIN_BARS} gerekli)")
            out[t] = {"state": "n/a", "error": "veri alınamadı"}
        time.sleep(0.4)

    ok = [t for t, v in out.items() if v.get("state") != "n/a"]
    data = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "market": "BIST",
            "count": len(tickers), "ok": len(ok), "sources": src, "log": ix.LOG, "tickers": out}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"{len(ok)}/{len(tickers)} hisse hesaplandı")
    if not ok:
        print("[ERROR] Hiç hisse alınamadı (log alanına bak).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
