"""Alpaca Market Data (ücretsiz 'Basic' plan) — İSTEĞE BAĞLI kaynak.

ALPACA_KEY_ID ve ALPACA_SECRET_KEY secret'ları tanımlıysa devreye girer; yoksa hiçbir şey yapmaz.
Ücretsiz planda: IEX borsası gerçek zamanlı; tüm borsaların (SIP) geçmiş verisi son 15 dk hariç;
dakikada 200 istek; tek istekte çok sembol. Mumlar ön/sonrası seansı da kapsar (04:00-20:00 ET).
Kullanım:
  snapshots(["AAPL","MSFT"]) -> {T: Finnhub /quote biçiminde fiyat}
  bars_15m("AAPL", days=30)  -> [(epoch, o, h, l, c, v), ...]  (SIP, 15 dk gecikmeli; olmazsa IEX)
"""
import os
import time
from datetime import datetime, timedelta, timezone

import requests

BASE = "https://data.alpaca.markets/v2/stocks"


def keys():
    k, s = os.environ.get("ALPACA_KEY_ID", "").strip(), os.environ.get("ALPACA_SECRET_KEY", "").strip()
    return (k, s) if k and s else None


def _get(path, params, log=print):
    ks = keys()
    if not ks:
        return None
    h = {"APCA-API-KEY-ID": ks[0], "APCA-API-SECRET-KEY": ks[1]}
    for attempt in range(3):
        try:
            r = requests.get(f"{BASE}{path}", params=params, headers=h, timeout=20)
        except requests.RequestException as ex:
            log(f"Alpaca {type(ex).__name__}")
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            time.sleep(5 * (attempt + 1))
            continue
        log(f"Alpaca HTTP {r.status_code}: {r.text[:120]!r}")
        return {"_error": r.status_code, "_text": r.text[:200]}
    return None


def snapshots(tickers, log=print):
    """Son işlem fiyatı + günlük mum (IEX gerçek zamanlı). Bulunamayan sembol sonuçta yok."""
    if not keys() or not tickers:
        return {}
    d = _get("/snapshots", {"symbols": ",".join(tickers), "feed": "iex"}, log) or {}
    out = {}
    for t, s in d.items():
        if t.startswith("_") or not isinstance(s, dict):
            continue
        lt, db, pb = s.get("latestTrade") or {}, s.get("dailyBar") or {}, s.get("prevDailyBar") or {}
        c, pc = lt.get("p") or db.get("c"), pb.get("c")
        if not c or c <= 0:
            continue
        out[t] = {"c": c, "d": (c - pc) if pc else None, "dp": ((c / pc - 1) * 100) if pc else None,
                  "h": db.get("h"), "l": db.get("l"), "o": db.get("o"), "pc": pc, "t": int(time.time()), "src": "alpaca"}
    return out


def bars_15m(sym, days=30, log=print):
    """15 dk mumlar (eskiden yeniye). Önce SIP (tüm borsalar, son 15 dk hariç), izin yoksa IEX."""
    if not keys():
        return None
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).isoformat(timespec="seconds").replace("+00:00", "Z")
    for feed, end in (("sip", now - timedelta(minutes=16)), ("iex", now)):
        rows, token = [], None
        while True:
            p = {"timeframe": "15Min", "start": start, "end": end.isoformat(timespec="seconds").replace("+00:00", "Z"),
                 "limit": 10000, "feed": feed, "adjustment": "split"}
            if token:
                p["page_token"] = token
            d = _get(f"/{sym}/bars", p, log)
            if not d or d.get("_error"):
                rows = None
                break
            for b in d.get("bars") or []:
                ts = int(datetime.fromisoformat(b["t"].replace("Z", "+00:00")).timestamp())
                rows.append((ts, float(b["o"]), float(b["h"]), float(b["l"]), float(b["c"]), float(b.get("v") or 0)))
            token = d.get("next_page_token")
            if not token:
                break
        if rows:
            return rows
    return None
