#!/usr/bin/env python3
"""Piyasa rejimi + sektör/tema rotasyonu + hisse günlük/haftalık trend ve göreli güç.

Çıktı: market.json (iş akışı 'market-data' dalına yazar; mini uygulama raw adresinden okur).
Kaynak zinciri (veri kaybı olmasın diye):
  1) TradingView tarayıcısı: tüm semboller TEK istekte (günlük + haftalık göstergeler, 1H/1A/3A/6A performans,
     ön/sonrası fiyat). Anahtarsız.
  2) Eksik kalan semboller: Twelve Data günlük mumlarından aynı göstergeler hesaplanır (TWELVEDATA_API_KEY,
     dakikada 8 istek; çalışma başına en çok TD_MAX sembol).
  3) Hâlâ eksikse: önceki market.json'daki değer 'stale' işaretiyle korunur.

Göreli güç (RS) = sembolün performansı − SPY performansı (yüzde puan). Bileşik RS = 0.15·1H + 0.35·1A + 0.35·3A + 0.15·6A.
Trend puanı (0-7): fiyat>EMA20, EMA20>EMA50, fiyat>SMA50, SMA50>SMA200, fiyat>SMA200 (günlük) +
                   fiyat>EMA20(haftalık), EMA20(haftalık)>SMA50(haftalık).
Çeyrek (RRG benzeri): uzun vade = 3A RS, kısa vade = 1A RS → Lider / Zayıflayan / Toparlanan / Geride.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import tvscan  # noqa: E402
import technicals as tk  # noqa: E402  (saf Python göstergeler: rsi, atr, ema_series, sma)

UNIVERSE = "market/universe.json"
TD_MAX = 12
LOG = []
W = {"w": 0.15, "m1": 0.35, "m3": 0.35, "m6": 0.15}


def log(msg):
    msg = tk.scrub(msg)
    print(msg, flush=True)
    LOG.append(msg)


def num(x):
    return float(x) if isinstance(x, (int, float)) else None


def rnd(x, d=2):
    return None if x is None else round(x, d)


# ------------------------------------------------------------------ kaynak 2: Twelve Data günlük
def from_twelvedata(sym, key):
    """Twelve Data günlük mumlarından tarayıcı sütunlarıyla aynı alanlar."""
    r = requests.get("https://api.twelvedata.com/time_series",
                     params={"symbol": sym, "interval": "1day", "outputsize": 300, "apikey": key}, timeout=30)
    d = r.json()
    if d.get("status") == "error" or "values" not in d:
        raise RuntimeError(str(d.get("message", d))[:160])
    rows = list(reversed(d["values"]))
    c = [float(x["close"]) for x in rows]
    h = [float(x["high"]) for x in rows]
    lo = [float(x["low"]) for x in rows]
    if len(c) < 60:
        raise RuntimeError(f"yetersiz mum ({len(c)})")

    def perf(n):
        return (c[-1] / c[-1 - n] - 1) * 100 if len(c) > n else None

    def ema_last(v, n):
        s = tk.ema_series(v, n)
        return s[-1] if s else None
    wk = c[::-1][::5][::-1]  # ~haftalık kapanış (5 işlem günü)
    return {"name": sym, "close": c[-1], "change": (c[-1] / c[-2] - 1) * 100, "change_abs": c[-1] - c[-2],
            "high": h[-1], "low": lo[-1], "Perf.W": perf(5), "Perf.1M": perf(21), "Perf.3M": perf(63),
            "Perf.6M": perf(126), "EMA20": ema_last(c, 20), "EMA50": ema_last(c, 50), "SMA50": tk.sma(c, 50),
            "SMA200": tk.sma(c, 200), "RSI": tk.rsi(c), "ATR": tk.atr(h, lo, c), "EMA20|1W": ema_last(wk, 20),
            "SMA50|1W": tk.sma(wk, 50), "RSI|1W": tk.rsi(wk), "High.3M": max(h[-63:]), "_src": "twelvedata"}


# ------------------------------------------------------------------ hesaplar
def trend_points(x):
    c, e20, e50, s50, s200 = (num(x.get(k)) for k in ("close", "EMA20", "EMA50", "SMA50", "SMA200"))
    w20, w50 = num(x.get("EMA20|1W")), num(x.get("SMA50|1W"))
    checks = [("Fiyat > EMA20 (günlük)", c, e20), ("EMA20 > EMA50", e20, e50), ("Fiyat > SMA50", c, s50),
              ("SMA50 > SMA200", s50, s200), ("Fiyat > SMA200", c, s200),
              ("Fiyat > EMA20 (haftalık)", c, w20), ("EMA20 > SMA50 (haftalık)", w20, w50)]
    pts, known, det = 0, 0, []
    for label, a, b in checks:
        if a is None or b is None:
            continue
        known += 1
        ok = a > b
        pts += ok
        det.append([label, ok])
    if known < 4:
        return None
    pts = round(pts * 7 / known)  # eksik sütun varsa 7'lik ölçeğe oranla
    lab = ("Güçlü yükseliş" if pts >= 6 else "Yükseliş" if pts >= 4 else "Kararsız" if pts == 3
           else "Düşüş" if pts >= 1 else "Güçlü düşüş")
    return {"points": pts, "label": lab, "checks": det,
            "daily_up": (c is not None and s50 is not None and c > s50),
            "weekly_up": (c is not None and w20 is not None and c > w20)}


def perf_of(x):
    return {"w": num(x.get("Perf.W")), "m1": num(x.get("Perf.1M")), "m3": num(x.get("Perf.3M")),
            "m6": num(x.get("Perf.6M"))}


def rel(p, base):
    out = {k: (None if p[k] is None or base.get(k) is None else p[k] - base[k]) for k in W}
    parts = [(W[k], v) for k, v in out.items() if v is not None]
    out["score"] = sum(w * v for w, v in parts) / sum(w for w, _ in parts) if parts else None
    return {k: rnd(v, 2) for k, v in out.items()}


def quadrant(rs):
    lo, sh = rs.get("m3"), rs.get("m1")
    if lo is None or sh is None:
        return None
    if lo >= 0 and sh >= 0:
        return "Lider"
    if lo >= 0:
        return "Zayıflayan"
    if sh >= 0:
        return "Toparlanan"
    return "Geride"


def verdict(q, tr, bank=False):
    if not q or not tr:
        return "Veri yetersiz"
    p = tr["points"]
    if q == "Lider" and p >= 5:
        v = "Ol"
    elif q == "Lider":
        v = "İzle (trend zayıfladı)"
    elif q == "Toparlanan" and p >= 3:
        v = "Erken giriş adayı"
    elif q == "Zayıflayan" and p >= 6:
        v = "Tut, yeni alım yok"
    elif q == "Zayıflayan":
        v = "Azalt / kâr al"
    elif q == "Geride" and p <= 3:
        v = "Uzak dur"
    else:
        v = "İzle"
    return v + (" · banka kuralı: yatırım yok" if bank else "")


def compact(x, src):
    c = num(x.get("close"))
    atr = num(x.get("ATR"))
    return {"close": rnd(c, 4), "chg": rnd(num(x.get("change")), 2), "perf": {k: rnd(v, 2) for k, v in perf_of(x).items()},
            "rsi": rnd(num(x.get("RSI")), 1), "rsi_w": rnd(num(x.get("RSI|1W")), 1), "adx": rnd(num(x.get("ADX")), 1),
            "atr": rnd(atr, 4), "atr_pct": rnd(atr / c * 100, 2) if atr and c else None,
            "ema20": rnd(num(x.get("EMA20")), 4), "sma50": rnd(num(x.get("SMA50")), 4), "sma200": rnd(num(x.get("SMA200")), 4),
            "macd": rnd(num(x.get("MACD.macd")), 4), "macd_sig": rnd(num(x.get("MACD.signal")), 4),
            "rec": tvscan.rec_label(x.get("Recommend.All")), "rvol": rnd(num(x.get("relative_volume_10d_calc")), 2),
            "high3m": rnd(num(x.get("High.3M")), 4),
            "earn_next": (datetime.fromtimestamp(x["earnings_release_next_date"], timezone.utc).date().isoformat()
                          if isinstance(x.get("earnings_release_next_date"), (int, float)) else None),
            "pre": rnd(num(x.get("premarket_close")), 4), "pre_pct": rnd(num(x.get("premarket_change")), 2),
            "post": rnd(num(x.get("postmarket_close")), 4), "post_pct": rnd(num(x.get("postmarket_change")), 2),
            "src": src}


def atr_stop(c):
    """Fiyattan 2×ATR ya da 3A tepeden 3×ATR (yüksek olan; fiyatın en az 1×ATR altında)."""
    if not (c.get("atr") and c.get("close")):
        return None
    ref = max(v for v in (c["close"], c.get("high3m") or 0) if v)
    return rnd(max(c["close"] - 2 * c["atr"], min(ref - 3 * c["atr"], c["close"] - 1 * c["atr"])), 2)


def build_picks(uni, gmap, spy_p, held):  # held: izlenen semboller (pozisyon + izleme listesi)
    """Sektör/tema başına en çok N hisse: trend >= min_trend, SPY'ye göre RS > 0, yeterli işlem hacmi.
    Aday havuzu: büyük tarama (piyasa değeri > min_mcap, TEK istek) + tema aday listeleri (TEK istek)."""
    cfg = uni.get("picks") or {}
    if not cfg:
        return {}, 0
    ind_g, sec_g, themes = cfg.get("industry_group", {}), uni.get("sector_group", {}), cfg.get("theme_candidates", {})
    excl = set(cfg.get("exclude_industries", []))
    big = tvscan.screen([{"left": "market_cap_basic", "operation": "greater", "right": cfg.get("min_mcap", 3e9)},
                         {"left": "exchange", "operation": "in_range", "right": ["NASDAQ", "NYSE", "AMEX"]}],
                        log=log) or []
    curated = sorted({t for v in themes.values() for t in v})
    cur = tvscan.fetch(curated, log=log) or {}
    log(f"Hisse seçimi: büyük tarama {len(big)} hisse, tema adayları {len(cur)}/{len(curated)}")
    pool = {}
    for rec in big:
        g = ind_g.get(rec.get("industry") or "") or sec_g.get(rec.get("sector") or "")
        if g:
            pool.setdefault(g, {})[rec["name"]] = rec
    for g, names in themes.items():
        for t in names:
            rec = cur.get(t) or next((x for x in big if x["name"] == t), None)
            if rec:
                pool.setdefault(g, {})[t] = rec
    bank = {x["sym"] for x in gmap.values() if x.get("bank")}
    out = {}
    for g, recs in pool.items():
        if g in bank or g not in gmap:
            continue
        gperf = gmap[g].get("perf") or {}
        cands = []
        for t, x in recs.items():
            if (x.get("industry") or "") in excl or "/" in t:  # banka/alkol ve tercihli hisse (ör. HPE/PC) hariç
                continue
            c = compact(x, "tv")
            dv = (num(x.get("average_volume_10d_calc")) or 0) * (c["close"] or 0)
            if dv < cfg.get("min_dollar_vol", 2e7):
                continue
            tr = trend_points(x)
            rs = rel(perf_of(x), spy_p)
            if not tr or tr["points"] < cfg.get("min_trend", 5) or (rs.get("score") or -1) <= 0:
                continue
            rg = rel(perf_of(x), gperf) if gperf else {}
            cands.append({"t": t, "name": x.get("description") or t, "close": c["close"], "chg": c["chg"],
                          "rs": rs.get("score"), "rs_m1": rs.get("m1"), "rs_m3": rs.get("m3"), "rs_group": rg.get("score"),
                          "trend": tr["points"], "label": tr["label"], "rsi": c["rsi"], "atr_pct": c["atr_pct"],
                          "stop_atr": atr_stop(c), "mcap_bn": rnd((num(x.get("market_cap_basic")) or 0) / 1e9, 1),
                          "industry": x.get("industry"), "tracked": t in held,
                          "_k": (rs.get("score") or 0) + 0.5 * (rg.get("score") or 0)})
        cands.sort(key=lambda z: z["_k"], reverse=True)
        for z in cands:
            z.pop("_k")
        out[g] = cands[:cfg.get("per_group", 3)]
    return out, len(big)


def write_bars(path, stocks, sout):
    """Mini uygulama grafiği: hisse başına ~180 işlem günü [gün, o, y, d, k]. Alpaca yoksa/başarısızsa dosya
    yazılmaz (önceki dosya iş akışında korunur)."""
    try:
        import alpaca
        if not alpaca.keys():
            log("Grafik mumları: Alpaca anahtarı yok, atlandı")
            return
        got = alpaca.bars_daily(stocks, log=log)
    except Exception as ex:
        log(f"Grafik mumları hatası: {type(ex).__name__}")
        return
    if not got:
        log("Grafik mumları alınamadı (önceki dosya korunur)")
        return
    def r4(v):
        return round(float(v), 4 if v < 10 else 2)
    out = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": "Alpaca günlük", "bars": {}}
    for t, rows in got.items():
        out["bars"][t] = [[datetime.fromtimestamp(b[0], timezone.utc).strftime("%Y-%m-%d"), r4(b[1]), r4(b[2]), r4(b[3]), r4(b[4])]
                          for b in rows[-180:]]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    log(f"Grafik mumları: {len(out['bars'])}/{len(stocks)} hisse")


def regime(data, groups_out, stocks_out):
    """0-7 puan: SPY/QQQ/IWM trendi, piyasa genişliği, eşit ağırlık katılımı."""
    def g(s, k):
        return num((data.get(s) or {}).get(k))
    checks = []

    def add(label, a, b):
        if a is not None and b is not None:
            checks.append([label, a > b])
    add("SPY > SMA50", g("SPY", "close"), g("SPY", "SMA50"))
    add("SPY > SMA200", g("SPY", "close"), g("SPY", "SMA200"))
    add("SPY SMA50 > SMA200", g("SPY", "SMA50"), g("SPY", "SMA200"))
    add("QQQ > SMA50", g("QQQ", "close"), g("QQQ", "SMA50"))
    add("IWM (küçük şirket) > SMA50", g("IWM", "close"), g("IWM", "SMA50"))
    rsp, spy = g("RSP", "Perf.1M"), g("SPY", "Perf.1M")
    if rsp is not None and spy is not None:
        checks.append(["Eşit ağırlık (RSP) SPY'den en çok 2 puan geride (katılım)", rsp - spy > -2])
    above = [x for x in list(groups_out) + list(stocks_out.values()) if x.get("close") and x.get("sma50")]
    br50 = round(sum(1 for x in above if x["close"] > x["sma50"]) / len(above) * 100) if above else None
    if br50 is not None:
        checks.append([f"Genişlik: evrenin %{br50}'i SMA50 üstünde (>%50)", br50 > 50])
    if not checks:
        return None
    score = sum(1 for _, ok in checks if ok)
    mx = len(checks)
    ratio = score / mx
    if ratio >= 0.8:
        label, cash = "Risk-on (yükseliş)", [10, 15]
    elif ratio >= 0.45:
        label, cash = "Nötr / seçici", [20, 25]
    else:
        label, cash = "Risk-off (savunma)", [35, 40]
    return {"score": score, "max": mx, "label": label, "cash_target": cash, "breadth50": br50, "checks": checks}


# ------------------------------------------------------------------ ana akış
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="market.json")
    ap.add_argument("--tickers-file", default="trend/tickers.txt")
    ap.add_argument("--bars-out", default="", help="Grafik için günlük mumlar (Alpaca anahtarı varsa)")
    args = ap.parse_args(argv)

    uni = common.load_json(UNIVERSE)
    bench = list(uni["benchmarks"])
    groups = uni["groups"]
    stocks = list(dict.fromkeys(common.public_symbols("docs/data") + tk.read_tickers_file(args.tickers_file)))
    allsyms = list(dict.fromkeys(bench + [g["sym"] for g in groups] + stocks))
    prev = common.load_json(args.out, {}) or {}
    now = datetime.now(timezone.utc)

    data, src = {}, {}
    sc = tvscan.fetch(allsyms, log=log)
    if sc:
        for s in allsyms:
            if s in sc:
                data[s], src[s] = sc[s], "tv"
        log(f"TV scanner: {len(data)}/{len(allsyms)} sembol")
    else:
        log("TV scanner erişilemedi; Twelve Data / önceki değerlere düşülüyor")
    missing = [s for s in allsyms if s not in data]
    key = os.environ.get("TWELVEDATA_API_KEY", "").strip()
    if missing and key:
        # öncelik: kıyas (SPY...) > pozisyon/izleme hisseleri > ETF'ler
        order = [s for s in bench if s in missing] + [s for s in stocks if s in missing] + \
                [s for s in missing if s not in bench and s not in stocks]
        for i, s in enumerate(order[:TD_MAX]):
            if i:
                time.sleep(8)
            try:
                data[s], src[s] = from_twelvedata(s, key), "twelvedata"
            except Exception as ex:
                log(f"TD {s}: {type(ex).__name__}: {tk.scrub(ex)[:100]}")
        if len(order) > TD_MAX:
            log(f"Twelve Data sınırı: {len(order) - TD_MAX} sembol bu çalışmada alınamadı")

    if "SPY" not in data:
        log("[ERROR] SPY verisi yok; göreli güç hesaplanamaz. Önceki dosya korunuyor.")
        if prev:
            prev["checked"] = now.isoformat(timespec="seconds")
            prev["log"] = LOG
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(prev, f, ensure_ascii=False, indent=1)
        return 1

    spy_p = perf_of(data["SPY"])
    pgroups = {g["sym"]: g for g in prev.get("groups", [])}
    pstocks = prev.get("stocks", {})

    gout = []
    for g in groups:
        s = g["sym"]
        if s not in data:
            if s in pgroups:
                gout.append({**pgroups[s], "stale": True})
            continue
        x = data[s]
        rs = rel(perf_of(x), spy_p)
        tr = trend_points(x)
        q = quadrant(rs)
        gout.append({"sym": s, "name": g["name"], "kind": g["kind"], "bank": bool(g.get("bank")),
                     **compact(x, src[s]), "rs": rs, "trend": tr, "quadrant": q,
                     "verdict": verdict(q, tr, g.get("bank"))})
    ranked = sorted([x for x in gout if (x.get("rs") or {}).get("score") is not None],
                    key=lambda x: x["rs"]["score"], reverse=True)
    for i, x in enumerate(ranked, 1):
        x["rank"] = i
    gout.sort(key=lambda x: x.get("rank") or 999)

    gmap = {x["sym"]: x for x in gout}
    sout = {}
    for s in stocks:
        if s not in data:
            if s in pstocks:
                sout[s] = {**pstocks[s], "stale": True}
            continue
        x = data[s]
        grp = uni["stock_group"].get(s) or uni["sector_group"].get(x.get("sector") or "")
        gp = perf_of(data[grp]) if grp in data else None
        rs = rel(perf_of(x), spy_p)
        tr = trend_points(x)
        q = quadrant(rs)
        c = compact(x, src[s])
        stop = atr_stop(c)
        sout[s] = {"name": x.get("description") or s, "sector": x.get("sector"), "industry": x.get("industry"),
                   "group": grp, "group_name": (gmap.get(grp) or {}).get("name"),
                   **c, "rs": rs, "rs_group": rel(perf_of(x), gp) if gp else None, "trend": tr, "quadrant": q,
                   "verdict": verdict(q, tr), "stop_atr": stop}

    try:
        picks, pool_n = build_picks(uni, gmap, spy_p, set(common.public_symbols("docs/data")))
    except Exception as ex:  # seçim hatası ana çıktıyı düşürmesin
        log(f"Hisse seçimi hatası: {type(ex).__name__}: {tk.scrub(ex)[:100]}")
        picks, pool_n = (prev.get("picks") or {}), 0
    reg = regime(data, [x for x in gout if not x.get("stale")] + [{"close": num(data[b].get("close")),
                 "sma50": num(data[b].get("SMA50"))} for b in bench if b in data], sout)
    out = {
        "updated": now.isoformat(timespec="seconds"), "checked": now.isoformat(timespec="seconds"),
        "session": __import__("extended").session_name(now),
        "sources": {k: sum(1 for v in src.values() if v == k) for k in set(src.values())},
        "missing": [s for s in allsyms if s not in data],
        "benchmarks": {b: {"name": uni["benchmarks"][b], **compact(data[b], src[b]), "trend": trend_points(data[b])}
                       for b in bench if b in data},
        "regime": reg, "groups": gout, "stocks": sout, "picks": picks, "picks_pool": pool_n, "log": LOG,
        "method": "RS = performans − SPY (puan). Bileşik: 0.15·1H+0.35·1A+0.35·3A+0.15·6A. Trend 0-7 (5 günlük + 2 haftalık koşul). "
                  "Çeyrek: 3A RS (uzun) ve 1A RS (kısa). Stop önerisi: fiyattan 2×ATR ya da 3A tepeden 3×ATR (yüksek olan).",
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    if args.bars_out:
        write_bars(args.bars_out, stocks, sout)
    top = ", ".join(f"{x['sym']}({x['verdict']})" for x in gout[:5])
    print(f"Rejim: {reg and reg['label']} · ilk 5: {top} · hisse {len(sout)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
