#!/usr/bin/env python3
"""Gün içi teknik sinyaller: 4s EMA8/EMA20, 15dk EMA34/EMA89, Elliott (kural tabanlı, muhtemel).

Kaynak: Yahoo Finance chart API (gayriresmi, anahtarsız), ön/sonrası mumlar dahil (15dk, 60 gün).
4 saatlik mumlar 15dk mumlardan ABD saatiyle (ET) 04-08 / 08-12 / 12-16 / 16-20 dilimlerinde birleştirilir.

Çıktı: --out (varsayılan intraday.json). Workflow bunu `data` dalına yazar; main'e dokunmaz.
Hisse listesi docs/data/portfolio.json'dan okunur (pozisyonlar + izleme listesi).

Çalışma kuralı (ET seansı): normal seans -> her çalışmada; ön/kapanış sonrası -> son güncellemeden
en az 50 dk geçmişse; seans dışı -> atla. --force hepsini atlar.
Bir hisse için istek başarısız olursa önceki veri korunur (stale=true).
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PORTFOLIO = "docs/data/portfolio.json"
ET = ZoneInfo("America/New_York")
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
EXT_MIN_AGE_MIN = 50
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


# ------------------------------------------------------------------ seans
def session_name(now):
    """ET: ön piyasa 04:00-09:30, normal 09:30-16:00, kapanış sonrası 16:00-20:00."""
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


# ------------------------------------------------------------------ veri
def fetch_15m(sym, retries=2):
    """[(epoch, o, h, l, c, v), ...] eskiden yeniye; None = başarısız."""
    params = {"interval": "15m", "range": "60d", "includePrePost": "true"}
    for attempt in range(retries):
        try:
            r = requests.get(YAHOO.format(sym=sym), params=params, headers=HEADERS, timeout=(6, 15))
            if r.status_code == 429:
                log(f"{sym}: HTTP 429 (deneme {attempt + 1})")
                time.sleep(3 * (attempt + 1))
                continue
            if r.status_code != 200:
                log(f"{sym}: HTTP {r.status_code} {r.text[:120]!r}")
                return None
            r.raise_for_status()
            res = r.json()["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            rows = []
            for i, ts in enumerate(res.get("timestamp") or []):
                o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
                if None in (o, h, l, c):
                    continue
                rows.append((int(ts), float(o), float(h), float(l), float(c), q["volume"][i] or 0))
            return rows or None
        except Exception as ex:  # ağ/JSON/anahtar hatası: yalnızca türünü yaz
            log(f"{sym}: {type(ex).__name__}")
            time.sleep(1.5)
    return None


def aggregate_4h(rows):
    """15dk mumları ET'de 04/08/12/16 saat dilimlerine birleştir. Dönüş: [(epoch0, o, h, l, c), ...]."""
    out, cur_key = [], None
    for ts, o, h, l, c, _v in rows:
        t = datetime.fromtimestamp(ts, ET)
        hh = t.hour // 4 * 4
        if hh < 4 or hh > 16:
            continue  # 04:00-20:00 ET dışı (olmamalı)
        key = (t.date(), hh)
        if key != cur_key:
            out.append([ts, o, h, l, c])
            cur_key = key
        else:
            b = out[-1]
            b[2] = max(b[2], h)
            b[3] = min(b[3], l)
            b[4] = c
    return [tuple(b) for b in out]


# ------------------------------------------------------------------ EMA
def ema_series(v, n):
    if len(v) < n:
        return []
    k = 2 / (n + 1)
    out = [sum(v[:n]) / n]
    for x in v[n:]:
        out.append(x * k + out[-1] * (1 - k))
    return out


def ema_pair(closes, fast, slow):
    """Hızlı/yavaş EMA son değerleri, yön ve son kesişimin kaç mum önce olduğu."""
    ef, es = ema_series(closes, fast), ema_series(closes, slow)
    if not es or not ef:
        return None
    L = len(es)
    ef = ef[-L:]
    diffs = [a - b for a, b in zip(ef, es)]
    sign = lambda x: 1 if x > 0 else (-1 if x < 0 else 0)  # noqa: E731
    cur = sign(diffs[-1])
    cross_ago, cross_type = None, None
    for j in range(len(diffs) - 2, -1, -1):
        if sign(diffs[j]) != 0 and sign(diffs[j]) != cur and cur != 0:
            cross_ago = len(diffs) - 1 - (j + 1)  # kesişimin gerçekleştiği muma göre
            cross_type = "up" if cur > 0 else "down"
            break
    return {
        f"ema{fast}": round(ef[-1], 4), f"ema{slow}": round(es[-1], 4),
        "diff": round(diffs[-1], 4), "dir": "up" if cur > 0 else ("down" if cur < 0 else "flat"),
        "cross": cross_type, "cross_bars_ago": cross_ago, "bars": len(closes),
    }


# ------------------------------------------------------------------ Elliott (kural tabanlı)
def atr(bars, n=14):
    trs = []
    for i in range(1, len(bars)):
        _, _, h, l, _ = bars[i]
        pc = bars[i - 1][4]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs[-n:]) / n if len(trs) >= n else None


def zigzag(bars, thr):
    """Onaylı pivotlar [(idx, fiyat, 'H'|'L')] + son (onaysız) uç nokta."""
    piv, trend = [], None
    hi = lo = None
    for i, (_t, _o, h, l, _c) in enumerate(bars):
        if trend is None:
            if hi is None:
                hi, lo = (i, h), (i, l)
            if h > hi[1]:
                hi = (i, h)
            if l < lo[1]:
                lo = (i, l)
            if hi[1] >= lo[1] * (1 + thr) and hi[0] > lo[0]:
                piv.append((lo[0], lo[1], "L")); trend = "up"
            elif lo[1] <= hi[1] * (1 - thr) and lo[0] > hi[0]:
                piv.append((hi[0], hi[1], "H")); trend = "down"
        elif trend == "up":
            if h > hi[1]:
                hi = (i, h)
            elif l <= hi[1] * (1 - thr):
                piv.append((hi[0], hi[1], "H")); trend = "down"; lo = (i, l)
        else:
            if l < lo[1]:
                lo = (i, l)
            elif h >= lo[1] * (1 + thr):
                piv.append((lo[0], lo[1], "L")); trend = "up"; hi = (i, h)
    if trend == "up":
        piv.append((hi[0], hi[1], "H"))
    elif trend == "down":
        piv.append((lo[0], lo[1], "L"))
    return piv


def _valid_prefix(p):
    """p: yükseliş yönüne normalize fiyatlar. Geçerli itki kuralı sağlanan en uzun nokta sayısı (<=6)."""
    m = min(len(p), 6)
    for k in range(2, m + 1):
        if k == 2 and not p[1] > p[0]:
            return 1
        if k == 3 and not p[2] > p[0]:          # dalga 2, dalga 1 başlangıcının altına inemez
            return 2
        if k == 4 and not p[3] > p[1]:          # dalga 3, dalga 1 sonunu aşmalı
            return 3
        if k == 5 and not p[4] > p[1]:          # dalga 4, dalga 1 bölgesine girmez
            return 4
        if k == 6:
            w1, w3, w5 = p[1] - p[0], p[3] - p[2], p[5] - p[4]
            if not (p[5] > p[3] and w3 >= min(w1, w5)):  # dalga 5 yeni uç yapar; dalga 3 en kısa olamaz
                return 5
    return m


WAVE_TR = {1: "Dalga 1 oluşuyor", 2: "Dalga 2 (düzeltme)", 3: "Dalga 3 (güçlü itki)",
           4: "Dalga 4 (düzeltme)", 5: "Dalga 5 (olgun, düzeltme riski)"}


def elliott(bars):
    """Son pivotlara göre muhtemel itki dalgası. Kesin sayım değildir."""
    if len(bars) < 40:
        return None
    a = atr(bars)
    price = bars[-1][4]
    if not a or not price:
        return None
    thr = min(max(1.5 * a / price, 0.02), 0.12)
    piv = zigzag(bars, thr)
    best = None  # (m, dir, start)
    for direction in ("up", "down"):
        want = "L" if direction == "up" else "H"
        n = len(piv)
        for s in range(max(0, n - 7), n):
            if piv[s][2] != want:
                continue
            seg = piv[s:]
            p = [x[1] if direction == "up" else -x[1] for x in seg]
            m = _valid_prefix(p)
            if s + m == n and m >= 2 and (best is None or m > best[0]):
                best = (m, direction, s)
    out = {"thr_pct": round(thr * 100, 1), "pivots": len(piv)}
    if not best:
        out.update(bias="unclear", wave=None, label="Belirsiz (geçerli itki dizisi yok)")
        return out
    m, direction, s = best
    wave = m - 1  # son nokta dalga (m-1)'in ucu; o dalga şu an oluşuyor/yeni bitti
    out.update(bias=direction, wave=wave,
               label=("Yükseliş · " if direction == "up" else "Düşüş · ") + WAVE_TR.get(wave, f"Dalga {wave}"),
               start_price=round(piv[s][1], 4), last_price=round(piv[-1][1], 4))
    return out


# ------------------------------------------------------------------ ana akış
def compute(rows):
    b4 = aggregate_4h(rows)
    c15 = [r[4] for r in rows]
    c4 = [b[4] for b in b4]
    return {
        "price": round(rows[-1][4], 4),
        "bar_time": datetime.fromtimestamp(rows[-1][0], timezone.utc).isoformat(timespec="minutes"),
        "h4": ema_pair(c4, 8, 20),
        "m15": ema_pair(c15, 34, 89),
        "elliott": elliott(b4),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="intraday.json")
    ap.add_argument("--force", action="store_true", help="Seans/yaş kontrolünü atla")
    args = ap.parse_args(argv)

    now = datetime.now(timezone.utc)
    sess = session_name(now)
    prev = load_json(args.out, {}) or {}
    if not args.force:
        if sess == "kapali":
            print("Seans dışı; atlandı.")
            return 0
        if sess in ("pre", "post") and prev.get("updated"):
            try:
                age = (now - datetime.fromisoformat(prev["updated"])).total_seconds() / 60
                if age < EXT_MIN_AGE_MIN and prev.get("session") == sess:
                    print(f"Ön/sonrası seansı, son güncelleme {age:.0f} dk önce; atlandı.")
                    return 0
            except ValueError:
                pass

    pf = load_json(PORTFOLIO, {})
    tickers = list(dict.fromkeys(list(pf.get("portfolio", {})) + list(pf.get("watchlist", []))))
    if not tickers:
        print("[ERROR] Hisse listesi okunamadı (docs/data/portfolio.json).")
        return 1
    out, fails = {}, 0
    for t in tickers:
        if fails >= 3 and not out:  # ilk 3 hisse hiç gelmediyse kaynak erişilemez: boşuna bekleme
            log("Üst üste 3 hisse alınamadı; kaynak erişilemez sayıldı, durduruldu")
            break
        rows = fetch_15m(t)
        fails = 0 if rows else fails + 1
        if rows and len(rows) >= 120:
            try:
                out[t] = compute(rows)
            except Exception as ex:
                log(f"{t}: hesap hatası {type(ex).__name__}")
        elif rows:
            log(f"{t}: yetersiz mum ({len(rows)})")
        if t not in out and (prev.get("tickers") or {}).get(t):
            out[t] = {**prev["tickers"][t], "stale": True}
        time.sleep(0.4)
    fresh = sum(1 for v in out.values() if not v.get("stale"))
    # Başarısız olsa da yaz: log (hata sebebi) data dalında okunabilsin; önceki veri stale olarak korunur.
    data = {"updated": now.isoformat(timespec="seconds") if fresh else prev.get("updated"),
            "checked": now.isoformat(timespec="seconds"), "session": sess,
            "source": "Yahoo Finance (gayriresmi)", "log": LOG, "tickers": out}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"{fresh}/{len(tickers)} hisse güncel, seans={sess}")
    if not fresh:
        print("[ERROR] Hiç hisse alınamadı (log alanına bak).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
