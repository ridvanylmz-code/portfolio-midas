"""BIST fiyat kaynağı: Yahoo Finance (yfinance, günlük) + TradingView scanner yedeği.

monitor.run() ile uyumlu arayüz: make_fetch(tickers) -> fetch(ticker, key) ve market_status(key).
Kotasyon biçimi Finnhub ile aynıdır: {c, d, dp, h, l, o, pc, t}.
"""
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import requests

IST = ZoneInfo("Europe/Istanbul")
TV_URL = "https://scanner.tradingview.com/turkey/scan"


def session_open(now=None):
    """BIST sürekli işlem: Pzt-Cum 10:00-18:00 (İstanbul). Kapanış seansı 18:10'a kadar sürer."""
    now = (now or datetime.now(timezone.utc)).astimezone(IST)
    return now.weekday() < 5 and (10, 0) <= (now.hour, now.minute) < (18, 10)


def market_status(key=None, now=None):
    return {"isOpen": session_open(now)}


def _quote(c, pc, o, h, l, ts):
    c, pc = float(c), float(pc or c)
    return {"c": round(c, 4), "d": round(c - pc, 4), "dp": round((c / pc - 1) * 100, 4) if pc else 0.0,
            "h": round(float(h), 4), "l": round(float(l), 4), "o": round(float(o), 4),
            "pc": round(pc, 4), "t": int(ts)}


def yahoo_batch(tickers):
    """yfinance ile günlük bar: son bar = c, bir önceki = pc. Başarısız hisse sözlükte yer almaz."""
    out = {}
    try:
        import yfinance as yf
        df = yf.download([t + ".IS" for t in tickers], period="10d", interval="1d", group_by="ticker",
                         auto_adjust=False, progress=False, threads=True)
    except Exception as ex:
        print(f"[WARN] yfinance: {type(ex).__name__}")
        return out
    for t in tickers:
        try:
            d = df[t + ".IS"].dropna(subset=["Close"])
            if len(d) < 2:
                continue
            last, prev = d.iloc[-1], d.iloc[-2]
            out[t] = _quote(last["Close"], prev["Close"], last["Open"], last["High"], last["Low"],
                            d.index[-1].to_pydatetime().replace(tzinfo=timezone.utc).timestamp())
        except Exception:
            continue
    return out


def tradingview_batch(tickers):
    """Yahoo'da olmayan semboller (ör. ALTIN) için TradingView scanner (gecikmeli, anahtarsız)."""
    try:
        r = requests.post(TV_URL, json={
            "symbols": {"tickers": [f"BIST:{t}" for t in tickers]},
            "columns": ["close", "change", "open", "high", "low"]}, timeout=15)
        r.raise_for_status()
        out = {}
        now = datetime.now(timezone.utc).timestamp()
        for row in r.json().get("data", []):
            t = row["s"].split(":")[1]
            c, chg, o, h, l = row["d"]
            if c:
                pc = c / (1 + chg / 100) if chg is not None else c
                out[t] = _quote(c, pc, o or c, h or c, l or c, now)
        return out
    except Exception as ex:
        print(f"[WARN] tradingview scanner: {type(ex).__name__}")
        return {}


def make_fetch(tickers):
    got = yahoo_batch(tickers)
    missing = [t for t in tickers if t not in got]
    if missing:
        got.update(tradingview_batch(missing))
    print(f"BIST fiyat: {len(got)}/{len(tickers)}" + (f" (eksik: {', '.join(t for t in tickers if t not in got)})"
                                                         if len(got) < len(tickers) else ""))
    return lambda t, key=None: got.get(t)
