#!/usr/bin/env python3
"""BIST trend tarayıcı (elle tetiklenir). ABD tarafındaki scripts/trend.py'nin BIST karşılığı.

Hisse başına: 4S Trend (4 saatlik mumlarda 8/20), 15dk Trend (34/89), 15dk Tamam yada Devam
(15dk Supertrend, ATR 10, çarpan 3), Elliott (muhtemel).
Hesap fonksiyonları (EMA, Supertrend, Elliott) ABD tarafındaki scripts/intraday.py ve scripts/trend.py'den
aynen kullanılır; burada yalnızca BIST'e özgü kısımlar vardır:
  - Kaynak: Yahoo Finance chart API, sembol soneki .IS (BIST'te ön/sonrası seans yok)
  - 4S mumlar İstanbul saatiyle 10:00-14:00 ve 14:00-18:00 dilimlerinde 15dk mumlardan birleştirilir
  - Kaynak sırası: ham Yahoo -> yfinance -> Twelve Data (XIST, yalnız TWELVEDATA_API_KEY varsa)

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
import bist_data  # noqa: E402
import intraday as ix  # noqa: E402
import trend as tr  # noqa: E402

TRT = ZoneInfo("Europe/Istanbul")
YF_URL = "https://{host}.finance.yahoo.com/v8/finance/chart/{sym}"
MAX_TICKERS = 80
MIN_BARS = 120


def log(msg):
    ix.log(msg)


def _yahoo_raw(sym):
    """Ham Yahoo chart API (query1, olmazsa query2). Liste ya da None."""
    params = {"interval": "15m", "range": "60d", "includePrePost": "false"}
    for host in ("query1", "query2"):
        try:
            r = requests.get(YF_URL.format(host=host, sym=sym + ".IS"), params=params,
                             headers=tr.YF_HEADERS, timeout=(6, 30))
            if r.status_code == 429:
                log(f"{sym}: Yahoo {host} 429")
                time.sleep(2)
                continue
            d = r.json()
            res = (d.get("chart") or {}).get("result")
            if not res:
                err = ((d.get("chart") or {}).get("error") or {}).get("description", f"HTTP {r.status_code}")
                log(f"{sym}: Yahoo {host} veri yok ({str(err)[:80]})")
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
            log(f"{sym}: Yahoo {host} {type(ex).__name__}")
    return None


def _yahoo_lib(sym):
    """yfinance kütüphanesi (çerez/crumb ile; ham istek 429 alırken çoğu zaman çalışır). Liste ya da None."""
    try:
        import yfinance as yf
        df = yf.Ticker(sym + ".IS").history(period="60d", interval="15m", auto_adjust=False)
        if df is None or df.empty:
            log(f"{sym}: yfinance boş döndü")
            return None
        rows = []
        for t, r in df.iterrows():
            o, h, l, c = r["Open"], r["High"], r["Low"], r["Close"]
            if o != o or h != h or l != l or c != c:  # NaN
                continue
            rows.append((int(t.timestamp()), float(o), float(h), float(l), float(c), float(r.get("Volume") or 0)))
        return rows or None
    except Exception as ex:
        log(f"{sym}: yfinance {type(ex).__name__}: {str(ex)[:60]}")
        return None


def _twelvedata(sym, key):
    """Twelve Data, borsa XIST (BIST). Ücretsiz planda BIST kapalı olabilir; hata mesajı loga yazılır."""
    try:
        params = {"symbol": sym, "exchange": "XIST", "interval": "15min", "outputsize": ix.OUTPUTSIZE,
                  "timezone": "Europe/Istanbul", "order": "ASC", "apikey": key}
        d = requests.get(ix.TD_URL, params=params, timeout=(6, 30)).json()
        if d.get("status") == "error" or "values" not in d:
            log(f"{sym}: Twelve Data {d.get('code')}: {str(d.get('message', d))[:120]}")
            return None
        rows = []
        for v in d["values"]:
            dt = v["datetime"]
            t = datetime.strptime(dt[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TRT)
            rows.append((int(t.timestamp()), float(v["open"]), float(v["high"]), float(v["low"]),
                         float(v["close"]), float(v.get("volume") or 0)))
        rows.sort(key=lambda x: x[0])
        return rows or None
    except Exception as ex:
        log(f"{sym}: Twelve Data {type(ex).__name__}")
        return None


def fetch_bars(sym, td_key, state):
    """Sırayla: ham Yahoo -> yfinance -> Twelve Data. (rows, kaynak). Çalışmayan kaynak 2 hisse üst üste
    başarısız olursa atlanır (state['off'])."""
    chain = [("Yahoo", _yahoo_raw), ("yfinance", _yahoo_lib)]
    if td_key:
        chain.append(("TwelveData", lambda s: _twelvedata(s, td_key)))
    for name, fn in chain:
        if state["fail"].get(name, 0) >= 2 and name != chain[-1][0]:
            continue
        rows = fn(sym)
        if isinstance(rows, list) and len(rows) >= MIN_BARS:
            state["fail"][name] = 0
            return rows, name
        state["fail"][name] = state["fail"].get(name, 0) + 1
        if name == "TwelveData":
            time.sleep(ix.TD_PAUSE)  # dakikada 8 istek sınırı
    return None, None


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
    ap.add_argument("--prev", default="", help="önceki trend-bist.json; veri alınamayan hisse eski değeriyle (stale) kalır")
    args = ap.parse_args(argv)

    tickers = parse_tickers(args.tickers)
    if not tickers and args.file and os.path.exists(args.file):
        with open(args.file, encoding="utf-8") as f:
            tickers = parse_tickers(re.sub(r"#.*", "", f.read()))
    tickers = list(dict.fromkeys(tickers))[:MAX_TICKERS]
    if not tickers:
        print("[ERROR] Sembol listesi boş.")
        return 1

    prev = {}
    if args.prev and os.path.exists(args.prev):
        try:
            with open(args.prev, encoding="utf-8") as f:
                prev = (json.load(f) or {}).get("tickers") or {}
        except Exception:
            prev = {}
    td_key = os.environ.get("TWELVEDATA_API_KEY", "").strip()
    out, src, state = {}, {}, {"fail": {}}
    for t in tickers:
        rows, used = fetch_bars(t, td_key, state)
        if rows:
            try:
                out[t] = compute(rows)
                src[t] = used
            except Exception as ex:
                log(f"{t}: hesap hatası {type(ex).__name__}: {str(ex)[:80]}")
                out[t] = {"state": "n/a", "error": "hesap hatası"}
        else:
            log(f"{t}: hiçbir kaynaktan yeterli veri gelmedi")
            p = prev.get(t)
            if p and p.get("state") != "n/a":
                out[t] = {**p, "stale": True}
            else:
                out[t] = {"state": "n/a", "error": "veri alınamadı"}
        time.sleep(0.4)

    ok = [t for t, v in out.items() if v.get("state") != "n/a" and not v.get("stale")]
    data = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "market": "BIST",
            "session": "regular" if bist_data.session_open() else "kapali", "prepost": False,
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
