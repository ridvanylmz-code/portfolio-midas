"""TradingView tarayıcısı (scanner.tradingview.com): anahtarsız, TEK istekte çok sembol.

Gayriresmi bir uç noktadır; bu yüzden her kullanan script bunu yalnızca bir kaynak olarak görür ve
başarısızlıkta kendi yedeğine (Twelve Data / önceki değer) düşer. tradingview-ta paketinin aksine sembol
başına istek atmaz, bu yüzden 429 (istek sınırı) riski çok düşüktür.
"""
import time

import requests

URL = "https://scanner.tradingview.com/america/scan"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
           "Content-Type": "application/json", "Origin": "https://www.tradingview.com",
           "Referer": "https://www.tradingview.com/"}

# Günlük teknik + haftalık trend + performans + seans dışı fiyat (MCP ile 2026-10-10'da doğrulandı)
MARKET_COLS = ["name", "exchange", "description", "type", "sector", "industry", "close", "change", "change_abs",
               "open", "high", "low", "volume", "average_volume_10d_calc", "relative_volume_10d_calc",
               "Perf.W", "Perf.1M", "Perf.3M", "Perf.6M", "Perf.YTD",
               "EMA20", "EMA50", "SMA50", "SMA200", "RSI", "ADX", "ATR", "MACD.macd", "MACD.signal",
               "Stoch.K", "CCI20", "Recommend.All", "Recommend.MA", "Recommend.Other",
               "EMA20|1W", "SMA50|1W", "RSI|1W", "High.3M", "price_52_week_high",
               "premarket_close", "premarket_change", "postmarket_close", "postmarket_change", "market_cap_basic"]


def _payload(tickers, cols):
    return {
        "filter": [{"left": "name", "operation": "in_range", "right": list(tickers)}],
        "options": {"lang": "en"},
        "markets": ["america"],
        "symbols": {"query": {"types": ["stock", "dr", "fund"]}, "tickers": []},
        "columns": cols,
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
        "range": [0, 1000],
    }


def fetch(tickers, cols=None, retries=3, log=print, timeout=25):
    """{TICKER: {kolon: değer}} ya da None (kaynak erişilemez). Bulunamayan semboller sonuçta yer almaz.
    Aynı isimde birden çok borsa varsa piyasa değeri en büyük olan alınır."""
    cols = list(cols or MARKET_COLS)
    if "name" not in cols:
        cols.insert(0, "name")
    tickers = list(dict.fromkeys(tickers))
    for attempt in range(retries):
        try:
            r = requests.post(URL, json=_payload(tickers, cols), headers=HEADERS, timeout=timeout)
        except requests.RequestException as ex:
            log(f"TV scanner {type(ex).__name__} (deneme {attempt + 1})")
            time.sleep(3 * (attempt + 1))
            continue
        if r.status_code == 200:
            out = {}
            for row in r.json().get("data") or []:
                d = row.get("d") or []
                rec = {c: (d[i] if i < len(d) else None) for i, c in enumerate(cols)}
                name = rec.get("name")
                if name and name not in out:
                    rec["symbol"] = row.get("s")
                    out[name] = rec
            return out
        log(f"TV scanner HTTP {r.status_code} (deneme {attempt + 1}): {r.text[:160]!r}")
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(10 * (attempt + 1))
            continue
        break
    return None


def screen(filters, cols=None, limit=1500, log=print, retries=2, timeout=40):
    """Filtreli tarama (ör. piyasa değeri > 3 mlr $): [kayıt, ...] piyasa değerine göre azalan, ya da None."""
    cols = list(cols or MARKET_COLS)
    if "name" not in cols:
        cols.insert(0, "name")
    payload = {"filter": filters, "options": {"lang": "en"}, "markets": ["america"],
               "symbols": {"query": {"types": ["stock", "dr"]}, "tickers": []}, "columns": cols,
               "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"}, "range": [0, limit]}
    for attempt in range(retries):
        try:
            r = requests.post(URL, json=payload, headers=HEADERS, timeout=timeout)
        except requests.RequestException as ex:
            log(f"TV tarama {type(ex).__name__} (deneme {attempt + 1})")
            time.sleep(5)
            continue
        if r.status_code == 200:
            out, seen = [], set()
            for row in r.json().get("data") or []:
                d = row.get("d") or []
                rec = {c: (d[i] if i < len(d) else None) for i, c in enumerate(cols)}
                if rec.get("name") and rec["name"] not in seen:
                    seen.add(rec["name"])
                    rec["symbol"] = row.get("s")
                    out.append(rec)
            return out
        log(f"TV tarama HTTP {r.status_code}: {r.text[:160]!r}")
        time.sleep(10)
    return None


def rec_label(v):
    """TradingView 'Recommend.*' değeri -> etiket (TradingView eşikleri)."""
    if not isinstance(v, (int, float)):
        return None
    if v >= 0.5:
        return "STRONG_BUY"
    if v >= 0.1:
        return "BUY"
    if v > -0.1:
        return "NEUTRAL"
    if v > -0.5:
        return "SELL"
    return "STRONG_SELL"


def quote_from(rec):
    """Finnhub /quote biçiminde fiyat (monitor.py yedeği)."""
    c, ch = rec.get("close"), rec.get("change_abs")
    if not isinstance(c, (int, float)) or c <= 0:
        return None
    pc = c - ch if isinstance(ch, (int, float)) else None
    return {"c": c, "d": ch, "dp": rec.get("change"), "h": rec.get("high"), "l": rec.get("low"),
            "o": rec.get("open"), "pc": pc, "t": int(time.time()), "src": "tv"}
