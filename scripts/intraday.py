#!/usr/bin/env python3
"""Gün içi teknik sinyaller: 4s EMA8/EMA20, 15dk EMA34/EMA89, Elliott (kural tabanlı, muhtemel).

Kaynak: Twelve Data 15dk mumlar (TWELVEDATA_API_KEY). Önce ön/sonrası mumlar (prepost) denenir;
planda yoksa normal seans mumlarına düşülür ve bu `prepost: false` olarak dosyaya yazılır.
4 saatlik mumlar 15dk mumlardan ABD saatiyle (ET) 04-08 / 08-12 / 12-16 / 16-20 dilimlerinde birleştirilir
(yalnızca normal seans verisiyle günde 2 mum: 09:30-12:00 ve 12:00-16:00).

Çıktı: --out (varsayılan intraday.json). Workflow bunu `data` dalına yazar; main'e dokunmaz.
Hisse listesi docs/data/portfolio.json'dan okunur (pozisyonlar + izleme listesi).

Çalışma kuralı (ET seansı): normal seans -> her çalışmada; ön/kapanış sonrası -> son güncellemeden
en az 50 dk geçmişse; seans dışı -> atla. --force hepsini atlar.
Bir hisse için istek başarısız olursa önceki veri korunur (stale=true).
"""
import argparse
import json
import re
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PORTFOLIO = "docs/data/portfolio.json"
ET = ZoneInfo("America/New_York")
TD_URL = "https://api.twelvedata.com/time_series"
TD_PAUSE = 8.0  # ücretsiz plan: dakikada 8 istek
OUTPUTSIZE = 2000
EXT_MIN_AGE_MIN = 50
LOG = []


_SECRET_RE = re.compile(r"(apikey|api_key|token|key)=[^&\s'\"]+", re.I)


def log(msg):
    msg = _SECRET_RE.sub(r"\1=***", str(msg))  # log data dalına (herkese açık) yazılır
    print(msg, flush=True)
    LOG.append(msg)


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def symbols():
    """Pozisyon + izleme listesi sembolleri (şifre gerektirmez: docs/data/symbols.json)."""
    import common
    return common.public_symbols("docs/data")


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
def alpaca_on():
    try:
        import alpaca
        return bool(alpaca.keys())
    except Exception:
        return False


def alpaca_rows(sym):
    """Alpaca 15dk mumları (ALPACA_KEY_ID/ALPACA_SECRET_KEY varsa), yoksa None."""
    try:
        import alpaca
        if not alpaca.keys():
            return None
        rows = alpaca.bars_15m(sym, days=45, log=log)
        return rows if rows and len(rows) >= 120 else None
    except Exception as ex:
        log(f"{sym}: Alpaca {type(ex).__name__}")
        return None


def fetch_15m(sym, key, prepost, retries=2):
    """([(epoch, o, h, l, c, v), ...] eskiden yeniye, prepost_ok) ; başarısızsa (None, prepost)."""
    for attempt in range(retries):
        params = {"symbol": sym, "interval": "15min", "outputsize": OUTPUTSIZE,
                  "timezone": "America/New_York", "order": "ASC", "apikey": key}
        if prepost:
            params["prepost"] = "true"
        try:
            r = requests.get(TD_URL, params=params, timeout=(6, 30))
            d = r.json()
        except Exception as ex:  # ağ/JSON hatası: yalnızca türünü yaz
            log(f"{sym}: {type(ex).__name__}")
            time.sleep(2)
            continue
        if d.get("status") == "error" or "values" not in d:
            code, msg = d.get("code"), str(d.get("message", d))[:160]
            if code == 429:
                log(f"{sym}: 429 hız sınırı (deneme {attempt + 1})")
                time.sleep(20)
                continue
            if prepost:  # plan ön/sonrası mumu desteklemiyor olabilir -> normal seansla yeniden dene
                log(f"{sym}: prepost reddedildi ({code}: {msg}); normal seans mumlarıyla denenecek")
                prepost = False
                continue
            log(f"{sym}: Twelve Data hata {code}: {msg}")
            return None, prepost
        rows = []
        for v in d["values"]:
            try:
                dt = v["datetime"]
                t = datetime.strptime(dt[:19] if len(dt) > 10 else dt + " 00:00:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=ET)
                rows.append((int(t.timestamp()), float(v["open"]), float(v["high"]), float(v["low"]),
                             float(v["close"]), float(v.get("volume") or 0)))
            except (KeyError, ValueError):
                continue
        rows.sort(key=lambda x: x[0])
        return (rows or None), prepost
    return None, prepost


REG_OPEN, REG_MID, REG_CLOSE = 9 * 60 + 30, 13 * 60 + 30, 16 * 60  # ET dakika


def closed_rows(rows, now=None):
    """Yalnızca kapanmış 15dk mumlar (zaman damgası mum başlangıcı). Oluşan mum sinyale girmez (repaint olmasın)."""
    now_ts = (now or datetime.now(timezone.utc)).timestamp()
    return [r for r in rows if r[0] + 15 * 60 <= now_ts]


def is_regular_only(rows):
    """Tüm mumlar 09:30-16:00 ET içindeyse veri yalnız normal seanstır."""
    for r in rows[-400:]:
        t = datetime.fromtimestamp(r[0], ET)
        m = t.hour * 60 + t.minute
        if m < REG_OPEN or m >= REG_CLOSE:
            return False
    return True


def aggregate_4h(rows, regular=None, now=None, complete_only=False):
    """15dk mumları TradingView 4s mumlarıyla aynı dilimlerde birleştir. Dönüş: [(epoch0, o, h, l, c), ...].
    Normal seans verisi: 09:30-13:30 ve 13:30-16:00 ET (TradingView 'yalnız normal seans' 4s mumu).
    Ön/sonrası dahil veri: 04/08/12/16 ET dilimleri. complete_only: bitmemiş son 4s mum atılır."""
    if regular is None:
        regular = is_regular_only(rows)
    out, ends, cur_key = [], [], None
    for ts, o, h, l, c, _v in rows:
        t = datetime.fromtimestamp(ts, ET)
        m = t.hour * 60 + t.minute
        if regular:
            if m < REG_OPEN or m >= REG_CLOSE:
                continue
            part = 0 if m < REG_MID else 1
            key = (t.date(), part)
            end_m = REG_MID if part == 0 else REG_CLOSE
        else:
            hh = t.hour // 4 * 4
            if hh < 4 or hh > 16:
                continue  # 04:00-20:00 ET dışı (olmamalı)
            key = (t.date(), hh)
            end_m = (hh + 4) * 60
        if key != cur_key:
            out.append([ts, o, h, l, c])
            day0 = t.replace(hour=0, minute=0, second=0, microsecond=0)
            ends.append((day0 + timedelta(minutes=end_m)).timestamp())
            cur_key = key
        else:
            b = out[-1]
            b[2] = max(b[2], h)
            b[3] = min(b[3], l)
            b[4] = c
    if complete_only and out:
        now_ts = (now or datetime.now(timezone.utc)).timestamp()
        while out and ends[len(out) - 1] > now_ts:
            out.pop()
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
def compute(rows, now=None):
    """Sinyaller (EMA, kesişim, Elliott) yalnızca KAPANMIŞ mumlardan; fiyat en son mumdan (canlı)."""
    now = now or datetime.now(timezone.utc)
    closed = closed_rows(rows, now) or rows[:-1]
    regular = is_regular_only(rows)
    b4 = aggregate_4h(closed, regular=regular, now=now, complete_only=True)
    c15 = [r[4] for r in closed]
    c4 = [b[4] for b in b4]
    return {
        "price": round(rows[-1][4], 4),
        "bar_time": datetime.fromtimestamp(rows[-1][0], timezone.utc).isoformat(timespec="minutes"),
        "signal_bar": datetime.fromtimestamp(closed[-1][0], timezone.utc).isoformat(timespec="minutes"),
        "h4_bar": datetime.fromtimestamp(b4[-1][0], timezone.utc).isoformat(timespec="minutes") if b4 else None,
        "session_data": "regular" if regular else "extended",
        "h4": ema_pair(c4, 8, 20),
        "m15": ema_pair(c15, 34, 89),
        "elliott": elliott(b4),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="intraday.json")
    ap.add_argument("--force", action="store_true", help="Seans/yaş kontrolünü atla")
    args = ap.parse_args(argv)

    key = os.environ.get("TWELVEDATA_API_KEY", "").strip()
    if not key and not alpaca_on():
        print("[ERROR] TWELVEDATA_API_KEY (ya da ALPACA_KEY_ID/ALPACA_SECRET_KEY) tanımlı değil (GitHub Secrets).")
        return 1
    now = datetime.now(timezone.utc)
    sess = session_name(now)
    prev = load_json(args.out, {}) or {}
    prepost_known_off = prev.get("prepost") is False
    if not args.force:
        if sess == "kapali":
            print("Seans dışı; atlandı.")
            return 0
        if sess in ("pre", "post") and prepost_known_off and not alpaca_on():
            print("Plan ön/sonrası mum vermiyor (prepost=false); bu seansta kredi harcanmadı, atlandı.")
            return 0
        if sess in ("pre", "post") and prev.get("updated"):
            try:
                age = (now - datetime.fromisoformat(prev["updated"])).total_seconds() / 60
                if age < EXT_MIN_AGE_MIN and prev.get("session") == sess:
                    print(f"Ön/sonrası seansı, son güncelleme {age:.0f} dk önce; atlandı.")
                    return 0
            except ValueError:
                pass

    tickers = symbols()
    if not tickers:
        print("[ERROR] Hisse listesi okunamadı (docs/data/symbols.json / portfolio.json).")
        return 1
    out, fails, used = {}, 0, {}
    prepost = args.force or not prepost_known_off  # kapalı biliniyorsa boşuna deneme (kredi); --force yeniden dener
    for i, t in enumerate(tickers):
        if fails >= 3 and not out:  # ilk 3 hisse hiç gelmediyse kaynak erişilemez: boşuna bekleme
            log("Üst üste 3 hisse alınamadı; kaynak erişilemez sayıldı, durduruldu")
            break
        rows = alpaca_rows(t)  # anahtar varsa: ön/sonrası dahil, Twelve Data kredisi harcamaz
        if rows:
            used["Alpaca"] = used.get("Alpaca", 0) + 1
        else:
            if i:
                time.sleep(TD_PAUSE)
            rows, prepost = fetch_15m(t, key, prepost)
            if rows:
                used["TwelveData"] = used.get("TwelveData", 0) + 1
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
    fresh = sum(1 for v in out.values() if not v.get("stale"))
    # Başarısız olsa da yaz: log (hata sebebi) data dalında okunabilsin; önceki veri stale olarak korunur.
    data = {"updated": now.isoformat(timespec="seconds") if fresh else prev.get("updated"),
            "checked": now.isoformat(timespec="seconds"), "session": sess,
            "source": " + ".join(f"{k} {v}" for k, v in used.items()) or "Twelve Data 15dk", "prepost": (bool(prepost) or bool(used.get("Alpaca"))) if fresh else prev.get("prepost"),
            "log": LOG, "tickers": out}
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
