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


def expected_session(now=None):
    """Beklenen son seans günü (İstanbul): bugün hafta içiyse ve saat >= 10:00 ise bugün, değilse önceki iş günü.
    Resmî tatiller modellenmez (tatil günü her mumun "eski" görünmesi beklenen davranıştır)."""
    n = (now or datetime.now(timezone.utc)).astimezone(IST)
    d = n.date()
    if n.weekday() < 5 and (n.hour, n.minute) >= (10, 0):
        return d
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _stamp(now=None):
    """TradingView kotasyonunun zaman damgası: seans açıksa şimdi; kapalıysa son tamamlanan seansın kapanışı
    (18:10 İstanbul). Kapalıyken "şimdi" damgası hafta sonu/gece yarısı sonrası yanlış tarih üretir."""
    now = now or datetime.now(timezone.utc)
    if session_open(now):
        return now.timestamp()
    d = expected_session(now)
    return datetime(d.year, d.month, d.day, 18, 10, tzinfo=IST).timestamp()


def _quote(c, pc, o, h, l, ts):
    c, pc = float(c), float(pc or c)
    return {"c": round(c, 4), "d": round(c - pc, 4), "dp": round((c / pc - 1) * 100, 4) if pc else 0.0,
            "h": round(float(h), 4), "l": round(float(l), 4), "o": round(float(o), 4),
            "pc": round(pc, 4), "t": int(ts)}


def yahoo_batch(tickers, now=None, stale_out=None):
    """yfinance ile günlük bar: son bar = c, bir önceki = pc. Başarısız hisse sözlükte yer almaz.
    Son barın tarihi beklenen son seanstan (expected_session) eskiyse hisse sonuçta YER ALMAZ (TradingView'e düşer);
    bu bayat kotasyonlar stale_out sözlüğüne (verilmişse) yazılır."""
    out = {}
    expected = expected_session(now)
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
            q = _quote(last["Close"], prev["Close"], last["Open"], last["High"], last["Low"],
                       d.index[-1].to_pydatetime().replace(tzinfo=timezone.utc).timestamp())
            if d.index[-1].date() < expected:
                if stale_out is not None:
                    stale_out[t] = {**q, "stale": True}
                continue
            out[t] = q
        except Exception:
            continue
    return out


def tradingview_batch(tickers, now=None):
    """Yahoo'da olmayan ya da bayat semboller (ör. ALTIN) için TradingView scanner (gecikmeli, anahtarsız).
    Zaman damgası _stamp(): seans kapalıyken son tamamlanan seansın kapanışı (tarayıcının zaman kolonu istenmiyor)."""
    try:
        r = requests.post(TV_URL, json={
            "symbols": {"tickers": [f"BIST:{t}" for t in tickers]},
            "columns": ["close", "change", "open", "high", "low"]}, timeout=15)
        r.raise_for_status()
        out = {}
        ts = _stamp(now)
        for row in r.json().get("data", []):
            t = row["s"].split(":")[1]
            c, chg, o, h, l = row["d"]
            if c:
                pc = c / (1 + chg / 100) if chg is not None else c
                out[t] = _quote(c, pc, o or c, h or c, l or c, ts)
        return out
    except Exception as ex:
        print(f"[WARN] tradingview scanner: {type(ex).__name__}")
        return {}


def make_fetch(tickers, now=None):
    stale_y = {}
    got = yahoo_batch(tickers, now=now, stale_out=stale_y)
    missing = [t for t in tickers if t not in got]
    if missing:
        tv = tradingview_batch(missing, now)
        # Yeni seans verisi var mı? Bayat Yahoo mumlarıyla karşılaştırılan hisselerin en az %10'unda (en az 1) TradingView
        # kapanışı farklıysa yeni seans vardır: TradingView yetkilidir, kapanışı değişmeyen hisse de günceldir.
        # Hiçbiri (ya da neredeyse hiçbiri) farklı değilse tatil / veri henüz yok demektir: kotasyonlar bayattır ve
        # tarihleri mumun kendi tarihidir, "şimdi" değil.
        both = [t for t in tv if t in stale_y]
        diff = sum(1 for t in both if abs(tv[t]["c"] - stale_y[t]["c"]) >= 1e-9)
        new_session = bool(both) and diff >= max(1, -(-len(both) // 10))
        for t, q in tv.items():
            got[t] = q if (new_session or t not in stale_y) else stale_y[t]
        for t, q in stale_y.items():
            got.setdefault(t, q)  # TradingView'de hiç yoksa bayat Yahoo kotasyonu (stale=True) kalır
    print(f"BIST fiyat: {len(got)}/{len(tickers)}" + (f" (eksik: {', '.join(t for t in tickers if t not in got)})"
                                                         if len(got) < len(tickers) else ""))
    return lambda t, key=None: got.get(t)
