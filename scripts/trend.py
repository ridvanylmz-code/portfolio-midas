#!/usr/bin/env python3
"""Trend tarayıcı (elle tetiklenir): 30-50 hisse için tek sayfalık bullish/bearish durumu.

Hisse başına: 15dk EMA34/89, 4s EMA8/20, 15dk Supertrend (ATR 10, çarpan 3), Elliott (muhtemel).
Kaynak: Yahoo Finance chart API (anahtarsız, ön/sonrası dahil 15dk mum). Bir hisse Yahoo'dan
gelmezse ve TWELVEDATA_API_KEY varsa Twelve Data'ya düşer (yavaş: 8 istek/dk).
Hesaplar (EMA, 4s birleştirme, Elliott) scripts/intraday.py ile aynıdır; burada yalnızca Supertrend,
skor ve çıktı vardır.

Kullanım: python scripts/trend.py --tickers "AAPL,NVDA" --out trend.json
          python scripts/trend.py --file trend/tickers.txt [--include-portfolio]
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import intraday as ix  # noqa: E402

YF_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
YF_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
MAX_TICKERS = 80
ST_PERIOD, ST_MULT = 10, 3.0


def log(msg):
    ix.log(msg)


# ------------------------------------------------------------------ veri
def fetch_yahoo(sym, retries=1):
    """15dk mumlar [(epoch, o, h, l, c, v)] eskiden yeniye (ön/sonrası dahil) ya da None."""
    ysym = sym.replace(".", "-")  # BRK.B -> BRK-B
    params = {"interval": "15m", "range": "60d", "includePrePost": "true"}
    for attempt in range(retries):
        try:
            r = requests.get(YF_URL.format(sym=ysym), params=params, headers=YF_HEADERS, timeout=(6, 30))
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
            time.sleep(2)
    return None


# ------------------------------------------------------------------ Supertrend
def supertrend(rows, period=ST_PERIOD, mult=ST_MULT):
    """TradingView varsayılanı: kaynak hl2, ATR = Wilder RMA. rows: (ts,o,h,l,c,v)."""
    n = len(rows)
    if n < period + 5:
        return None
    tr = [rows[0][2] - rows[0][3]]
    for i in range(1, n):
        h, l, pc = rows[i][2], rows[i][3], rows[i - 1][4]
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr = [None] * n
    atr[period - 1] = sum(tr[:period]) / period
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    direction = 1  # 1 = yükseliş (çizgi fiyatın altında)
    fub = flb = None
    line = [None] * n
    dirs = [0] * n
    for i in range(period - 1, n):
        hl2 = (rows[i][2] + rows[i][3]) / 2
        ub, lb = hl2 + mult * atr[i], hl2 - mult * atr[i]
        pc = rows[i - 1][4] if i else rows[i][4]
        if fub is None:
            fub, flb = ub, lb
        else:
            fub = ub if (ub < fub or pc > fub) else fub
            flb = lb if (lb > flb or pc < flb) else flb
        c = rows[i][4]
        if i > period - 1:
            if direction == 1 and c < flb:
                direction = -1
            elif direction == -1 and c > fub:
                direction = 1
        line[i] = flb if direction == 1 else fub
        dirs[i] = direction
    since = 0
    for j in range(n - 2, period - 2, -1):
        if dirs[j] != dirs[-1]:
            break
        since += 1
    flipped = since < n - period  # yön hiç değişmediyse "son dönüş" yok
    price = rows[-1][4]
    return {"dir": "up" if dirs[-1] == 1 else "down", "line": round(line[-1], 4),
            "dist_pct": round((price - line[-1]) / price * 100, 2),
            "bars_since_flip": since if flipped else None}


# ------------------------------------------------------------------ skor
def classify(item):
    """Üç sinyalin yönüne göre durum: bullish / bearish / mixed (+ kısa not)."""
    votes = []
    for key in ("h4", "m15"):
        p = item.get(key)
        if p and p.get("dir") in ("up", "down"):
            votes.append(1 if p["dir"] == "up" else -1)
    st = item.get("st15")
    if st:
        votes.append(1 if st["dir"] == "up" else -1)
    if len(votes) < 3:
        return "n/a", 0
    s = sum(votes)
    if s == 3:
        return "bullish", 3
    if s == -3:
        return "bearish", -3
    return "mixed", s


def fresh_events(item):
    """Yeni sinyaller (kesişim / Supertrend dönüşü): 15dk için son 8 mum, 4s için son 2 mum."""
    ev = []
    m, h = item.get("m15") or {}, item.get("h4") or {}
    if m.get("cross") and m.get("cross_bars_ago") is not None and m["cross_bars_ago"] <= 8:
        ev.append("15dk EMA " + ("▲ kesişim" if m["cross"] == "up" else "▼ kesişim"))
    if h.get("cross") and h.get("cross_bars_ago") is not None and h["cross_bars_ago"] <= 2:
        ev.append("4s EMA " + ("▲ kesişim" if h["cross"] == "up" else "▼ kesişim"))
    st = item.get("st15") or {}
    if st.get("bars_since_flip") is not None and st["bars_since_flip"] <= 8:
        ev.append("Supertrend " + ("▲ döndü" if st["dir"] == "up" else "▼ döndü"))
    return ev


def compute(rows, now=None):
    now = now or datetime.now(timezone.utc)
    out = ix.compute(rows, now)
    closed = ix.closed_rows(rows, now) or rows[:-1]
    st = supertrend(closed)  # kapanmış mumlar: "Supertrend döndü" mum içinde gelip kaybolmasın
    if st:
        price = rows[-1][4]
        st["dist_pct"] = round((price - st["line"]) / price * 100, 2)
    out["st15"] = st
    out["state"], out["score"] = classify(out)
    out["events"] = fresh_events(out)
    # Gün %: son fiyat, önceki ET gününün NORMAL SEANS kapanışına (16:00) göre (kapanış sonrası mumu değil)
    try:
        last_day = datetime.fromtimestamp(rows[-1][0], ix.ET).date()
        prev = [r for r in rows if datetime.fromtimestamp(r[0], ix.ET).date() < last_day
                and (lambda t: t.hour * 60 + t.minute)(datetime.fromtimestamp(r[0], ix.ET)) < ix.REG_CLOSE]
        if prev:
            out["chg_pct"] = round((rows[-1][4] / prev[-1][4] - 1) * 100, 2)
    except Exception:
        pass
    return out


def overlay_extended(out):
    """Ön/kapanış sonrası seansında fiyatı ve 'Gün %'yi TradingView'in ön/sonrası fiyatıyla değiştirir.
    Sinyaller (EMA/Supertrend/Elliott) mum verisinden kalır; `ext` ve `close` alanları eklenir. Dönüş: seans ya da None."""
    try:
        import extended
        sess = extended.session_name(datetime.now(timezone.utc))
        if sess not in ("pre", "post"):
            return None
        got = extended.fetch(list(out))[0] or {}
    except Exception as ex:
        log(f"ön/sonrası fiyat alınamadı: {type(ex).__name__}")
        return None
    n = 0
    for t, v in out.items():
        x = got.get(t) or {}
        p = x.get(sess)
        if v.get("state") == "n/a" or not p or p <= 0:
            continue
        v["close"] = v.get("price")
        v["price"] = round(p, 4)
        if sess == "pre":
            pct = x.get("pre_pct")
        else:  # kapanış sonrası: bugünkü normal seans değişimi + sonrası hareketi
            ch, pp = x.get("change_pct"), x.get("post_pct")
            pct = round(((1 + ch / 100) * (1 + pp / 100) - 1) * 100, 2) if ch is not None and pp is not None else None
        if pct is not None:
            v["chg_pct"] = pct
        v["ext"] = sess
        n += 1
    log(f"ön/sonrası fiyat ({sess}) uygulandı: {n}/{len(out)}")
    return sess


# ------------------------------------------------------------------ ana akış
def parse_tickers(text):
    toks = [t.strip(".-") for t in re.split(r"[\s,;]+", (text or "").upper())]
    return [t for t in toks if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", t)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="", help="virgül/boşlukla ayrılmış semboller")
    ap.add_argument("--file", default="", help="satır/virgülle sembol listesi (# yorum)")
    ap.add_argument("--include-portfolio", action="store_true", help="portföy + izleme listesini de ekle")
    ap.add_argument("--out", default="trend.json")
    args = ap.parse_args(argv)

    tickers = parse_tickers(args.tickers)
    if not tickers and args.file and os.path.exists(args.file):
        with open(args.file, encoding="utf-8") as f:
            tickers = parse_tickers(re.sub(r"#.*", "", f.read()))
    if args.include_portfolio:
        tickers += parse_tickers(" ".join(ix.symbols()))
    tickers = list(dict.fromkeys(tickers))
    if not tickers:
        print("[ERROR] Sembol listesi boş.")
        return 1
    if len(tickers) > MAX_TICKERS:
        log(f"Liste {len(tickers)} sembol; ilk {MAX_TICKERS} alındı")
        tickers = tickers[:MAX_TICKERS]

    td_key = os.environ.get("TWELVEDATA_API_KEY", "").strip()
    out, src = {}, {}
    yahoo_on, yahoo_fail, prepost = True, 0, True
    for i, t in enumerate(tickers):
        rows, used = None, "Yahoo"
        if yahoo_on:
            rows = fetch_yahoo(t)
            if rows == "blocked" or rows is None:
                yahoo_fail += 1
                if yahoo_fail >= 2:
                    yahoo_on = False
                    log("Yahoo bu ortamda erişilemez/engelli; kalan semboller Twelve Data ile (yavaş)")
            else:
                yahoo_fail = 0
            if rows == "blocked":
                rows = None
        if not rows or len(rows) < 120:
            ar = ix.alpaca_rows(t)
            if ar:
                rows, used = ar, "Alpaca (ön/sonrası dahil)"
        if (not rows or len(rows) < 120) and td_key:
            time.sleep(ix.TD_PAUSE)
            rows, prepost = ix.fetch_15m(t, td_key, prepost)
            used = "TwelveData" + ("" if prepost else " (yalnız normal seans)")
        if rows and len(rows) >= 120:
            try:
                out[t] = compute(rows)
                src[t] = used
            except Exception as ex:
                log(f"{t}: hesap hatası {type(ex).__name__}: {str(ex)[:80]}")
        else:
            out[t] = {"state": "n/a", "error": "veri alınamadı"}
        if yahoo_on:
            time.sleep(0.4)

    ext_sess = overlay_extended(out)
    ok = [t for t, v in out.items() if v.get("state") != "n/a"]
    data = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
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
