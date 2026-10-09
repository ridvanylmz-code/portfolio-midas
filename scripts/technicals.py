#!/usr/bin/env python3
"""Teknik veri: TradingView özeti (tradingview-ta, gayriresmi) + Twelve Data'dan hesaplanan indikatörler.

Çıktı: docs/data/technicals.json
- Hiçbir adım tüm çalışmayı düşürmez; hata olursa 'log' alanına yazılır.
- TWELVEDATA_API_KEY yoksa Twelve Data adımı atlanır.
- Bir kaynak başarısız olursa o hissenin önceki başarılı verisi korunur (stale=true).
Mevcut sistem (monitor.py, update_position.py) bu dosyayı kullanmaz.
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

OUT = "docs/data/technicals.json"
PORTFOLIO = "docs/data/portfolio.json"
TICKERS_FILE = "trend/tickers.txt"  # portföy + takip listesine ek olarak bu dosyadaki semboller de alınır
MAX_TICKERS = 40
TIME_BUDGET = 15 * 60  # sn; aşılırsa kalan hisselerde önceki veri korunur, dosya yine yazılır
EXCHANGES = ["NASDAQ", "NYSE", "AMEX"]
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


# ---------- indikatör hesapları (saf Python) ----------
def sma(v, n):
    return sum(v[-n:]) / n if len(v) >= n else None


def ema_series(v, n):
    if len(v) < n:
        return []
    k = 2 / (n + 1)
    out = [sum(v[:n]) / n]
    for x in v[n:]:
        out.append(x * k + out[-1] * (1 - k))
    return out


def rsi(c, n=14):
    if len(c) <= n:
        return None
    gains = [max(c[i] - c[i - 1], 0) for i in range(1, len(c))]
    losses = [max(c[i - 1] - c[i], 0) for i in range(1, len(c))]
    ag, al = sum(gains[:n]) / n, sum(losses[:n]) / n
    for i in range(n, len(gains)):
        ag = (ag * (n - 1) + gains[i]) / n
        al = (al * (n - 1) + losses[i]) / n
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def macd(c):
    e12, e26 = ema_series(c, 12), ema_series(c, 26)
    if not e26:
        return None
    off = len(e12) - len(e26)
    line = [e12[off + i] - e26[i] for i in range(len(e26))]
    sig = ema_series(line, 9)
    if not sig:
        return None
    return {"macd": line[-1], "signal": sig[-1], "hist": line[-1] - sig[-1]}


def atr(h, l, c, n=14):
    if len(c) <= n:
        return None
    tr = [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(c))]
    a = sum(tr[:n]) / n
    for x in tr[n:]:
        a = (a * (n - 1) + x) / n
    return a


def r(x, d=2):
    return None if x is None else round(x, d)


def compute(rows):
    """rows: eskiden yeniye [{datetime,open,high,low,close,volume}]"""
    c = [float(x["close"]) for x in rows]
    h = [float(x["high"]) for x in rows]
    l = [float(x["low"]) for x in rows]
    v = [float(x.get("volume") or 0) for x in rows]
    last = c[-1]
    s20, s50, s200 = sma(c, 20), sma(c, 50), sma(c, 200)
    m = macd(c)
    avgv = sma(v, 20)
    return {
        "date": rows[-1]["datetime"],
        "close": r(last),
        "rsi14": r(rsi(c), 1),
        "sma20": r(s20), "sma50": r(s50), "sma200": r(s200),
        "above_sma20": None if s20 is None else last > s20,
        "above_sma50": None if s50 is None else last > s50,
        "above_sma200": None if s200 is None else last > s200,
        "macd": None if not m else {k: r(x, 3) for k, x in m.items()},
        "atr14": r(atr(h, l, c)),
        "support20": r(min(l[-20:])) if len(l) >= 20 else None,
        "resistance20": r(max(h[-20:])) if len(h) >= 20 else None,
        "vol_ratio": r(v[-1] / avgv) if avgv else None,
        "bars": len(c),
    }


# ---------- kaynaklar ----------
def fetch_td(symbol, key):
    resp = requests.get(
        "https://api.twelvedata.com/time_series",
        params={"symbol": symbol, "interval": "1day", "outputsize": 250, "apikey": key},
        timeout=30,
    )
    data = resp.json()
    if data.get("status") == "error" or "values" not in data:
        raise RuntimeError(str(data.get("message", data))[:200])
    return compute(list(reversed(data["values"])))


def fetch_tv(symbol):
    from tradingview_ta import TA_Handler, Interval  # noqa

    last_err = None
    for ex in EXCHANGES:
        try:
            a = TA_Handler(symbol=symbol, screener="america", exchange=ex,
                           interval=Interval.INTERVAL_1_DAY).get_analysis()
            ind = a.indicators or {}
            pick = ["RSI", "MACD.macd", "MACD.signal", "SMA20", "SMA50", "SMA200", "EMA20", "ADX", "close"]
            return {
                "exchange": ex,
                "recommendation": a.summary.get("RECOMMENDATION"),
                "buy": a.summary.get("BUY"), "sell": a.summary.get("SELL"), "neutral": a.summary.get("NEUTRAL"),
                "oscillators": (a.oscillators or {}).get("RECOMMENDATION"),
                "moving_averages": (a.moving_averages or {}).get("RECOMMENDATION"),
                "indicators": {k: r(ind.get(k), 3) for k in pick if ind.get(k) is not None},
            }
        except Exception as e:  # borsa yanlışsa sıradakini dene
            last_err = e
    raise RuntimeError(f"{type(last_err).__name__}: {str(last_err)[:160]}")


def fetch_tv_retry(symbol):
    """TradingView 429 (istek sınırı) verirse bekleyip en çok 2 kez yeniden dener."""
    for attempt in range(3):
        try:
            return fetch_tv(symbol)
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                wait = 20 * (attempt + 1)
                log(f"TV  {symbol}: 429, {wait} sn beklenip yeniden denenecek")
                time.sleep(wait)
                continue
            raise


def read_tickers_file(path):
    """trend/tickers.txt: virgül/boşluk/satır ayrımlı, # yorum satırları atlanır."""
    try:
        with open(path, encoding="utf-8") as f:
            text = re.sub(r"#.*", "", f.read())
    except OSError:
        return []
    toks = [t.strip(".-") for t in re.split(r"[\s,;]+", text.upper())]
    return [t for t in toks if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", t)]


def main():
    t0 = time.time()
    pf = load_json(PORTFOLIO, {})
    tickers = list(dict.fromkeys(list((pf.get("portfolio") or {}).keys()) + list(pf.get("watchlist") or [])
                                 + read_tickers_file(TICKERS_FILE)))
    if len(tickers) > MAX_TICKERS:
        log(f"Liste {len(tickers)} sembol; ilk {MAX_TICKERS} alındı")
        tickers = tickers[:MAX_TICKERS]
    old = load_json(OUT, {}).get("tickers", {})
    key = os.environ.get("TWELVEDATA_API_KEY", "").strip()
    try:
        import tradingview_ta  # noqa
        tv_ok = True
    except Exception as e:
        tv_ok = False
        log(f"tradingview-ta yüklenemedi: {e}")
    if not key:
        log("TWELVEDATA_API_KEY yok: Twelve Data adımı atlandı")

    result, n_td, n_tv = {}, 0, 0
    tv_429 = 0  # art arda TradingView 429 sayısı
    for i, t in enumerate(tickers):
        prev = old.get(t, {})
        entry = {"tv": None, "td": None}
        if time.time() - t0 > TIME_BUDGET:
            if not any("Süre bütçesi" in m for m in LOG):
                log(f"Süre bütçesi doldu: {t} ve sonrası atlandı, önceki veri korundu")
            for k in ("tv", "td"):
                if prev.get(k):
                    entry[k] = dict(prev[k], stale=True)
            result[t] = entry
            continue
        if tv_ok:
            try:
                entry["tv"] = fetch_tv_retry(t)
                n_tv += 1
                tv_429 = 0
                log(f"TV  {t}: {entry['tv']['recommendation']} (RSI {entry['tv']['indicators'].get('RSI')})")
            except Exception as e:
                log(f"TV  {t}: HATA {e}")
                if prev.get("tv"):
                    entry["tv"] = dict(prev["tv"], stale=True)
                tv_429 = tv_429 + 1 if "429" in str(e) else 0
                if tv_429 >= 2:
                    tv_ok = False
                    log("TV: art arda 2 kez 429, bu çalışmada kalan hisselerde TradingView atlandı (önceki değer korunur)")
            time.sleep(2.5)
        elif prev.get("tv"):
            entry["tv"] = dict(prev["tv"], stale=True)
        if key:
            try:
                entry["td"] = fetch_td(t, key)
                n_td += 1
                log(f"TD  {t}: RSI {entry['td']['rsi14']} SMA50 {entry['td']['sma50']} ({entry['td']['bars']} bar)")
            except Exception as e:
                log(f"TD  {t}: HATA {e}")
                if prev.get("td"):
                    entry["td"] = dict(prev["td"], stale=True)
            if i < len(tickers) - 1:
                time.sleep(8)  # ücretsiz plan: dakikada 8 istek
        result[t] = entry

    log(f"Özet: {len(tickers)} hisse, TV başarılı {n_tv}, TD başarılı {n_td}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_note": "TV = tradingview-ta (gayriresmi), TD = Twelve Data günlük mumlardan hesaplandı",
            "log": LOG[-60:],
            "tickers": result,
        }, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # asla workflow'u kırma
        print(f"BEKLENMEYEN HATA: {e}")
        sys.exit(0)
