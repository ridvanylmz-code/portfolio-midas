#!/usr/bin/env python3
"""BIST piyasa rejimi + sektör rotasyonu + hisse günlük/haftalık trend, göreli güç ve sektör başına 3 aday.

ABD karşılığı: scripts/market.py. Hesap fonksiyonları (trend puanı, RS, çeyrek, karar, ATR stop) oradan
aynen kullanılır; burada yalnızca BIST'e özgü kısımlar vardır. Çıktı: market-bist.json (iş akışı 'market-bist-data'
dalına yazar; ABD'nin 'market-data' dalına dokunmaz).

Kaynak zinciri (veri kaybı olmasın diye):
  1) TradingView Türkiye tarayıcısı (scanner.tradingview.com/turkey/scan): endeks, izlenen hisseler ve piyasa değeri
     eşiğini geçen tüm hisseler, anahtarsız. Kur (USDTRY) forex tarayıcısından.
  2) Eksik kalan izleme hisseleri: yfinance günlük mumlarından aynı göstergeler hesaplanır.
  3) Hâlâ eksikse: önceki market-bist.json'daki değer 'stale' işaretiyle korunur.

Sektör endeksleri tarayıcıda yok: sektör/grup performansı üye hisselerin MEDYANIdır (TradingView 'sector' ve
'industry' alanlarına göre). Göreli güç (RS) = performans − XU100 performansı (puan); bileşik 0.15·1H+0.35·1A+0.35·3A+0.15·6A.
"""
import argparse
import json
import os
import statistics
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import market as mk  # noqa: E402  (trend_points, rel, quadrant, verdict, compact, atr_stop ... ABD ile ortak)
import technicals as tk  # noqa: E402
import tvscan  # noqa: E402

UNIVERSE = "market/universe_bist.json"
TICKERS_FILE = "trend/bist_tickers.txt"
YF_MAX = 30
LOG = []
COLS = ["name", "description", "type", "sector", "industry", "close", "change", "change_abs", "high", "low", "volume",
        "average_volume_10d_calc", "relative_volume_10d_calc", "Perf.W", "Perf.1M", "Perf.3M", "Perf.6M",
        "EMA20", "EMA50", "SMA50", "SMA200", "RSI", "ADX", "ATR", "MACD.macd", "MACD.signal", "Recommend.All",
        "EMA20|1W", "SMA50|1W", "RSI|1W", "High.3M", "market_cap_basic", "earnings_release_next_date"]
num, rnd, perf_of = mk.num, mk.rnd, mk.perf_of


def log(msg):
    msg = tk.scrub(msg)
    print(msg, flush=True)
    LOG.append(msg)


def med(vals, d=2):
    v = [x for x in vals if isinstance(x, (int, float))]
    return round(statistics.median(v), d) if v else None


# ------------------------------------------------------------------ kaynak 2: yfinance günlük
def from_yfinance(sym):
    """yfinance günlük mumlarından tarayıcı sütunlarıyla aynı alanlar (izleme hissesi tarayıcıda yoksa)."""
    import yfinance as yf
    df = yf.Ticker(sym + ".IS").history(period="500d", interval="1d", auto_adjust=False)
    if df is None or df.empty:
        raise RuntimeError("veri yok")
    df = df.dropna(subset=["Close"])
    c = [float(x) for x in df["Close"]]
    h = [float(x) for x in df["High"]]
    lo = [float(x) for x in df["Low"]]
    if len(c) < 60:
        raise RuntimeError(f"yetersiz mum ({len(c)})")

    def perf(n):
        return (c[-1] / c[-1 - n] - 1) * 100 if len(c) > n else None

    def ema_last(v, n):
        s = tk.ema_series(v, n)
        return s[-1] if s else None
    wk = c[::-1][::5][::-1]
    return {"name": sym, "close": c[-1], "change": (c[-1] / c[-2] - 1) * 100, "change_abs": c[-1] - c[-2],
            "high": h[-1], "low": lo[-1], "Perf.W": perf(5), "Perf.1M": perf(21), "Perf.3M": perf(63),
            "Perf.6M": perf(126), "EMA20": ema_last(c, 20), "EMA50": ema_last(c, 50), "SMA50": tk.sma(c, 50),
            "SMA200": tk.sma(c, 200), "RSI": tk.rsi(c), "ATR": tk.atr(h, lo, c), "EMA20|1W": ema_last(wk, 20),
            "SMA50|1W": tk.sma(wk, 50), "RSI|1W": tk.rsi(wk), "High.3M": max(h[-63:]), "_src": "yfinance"}


# ------------------------------------------------------------------ sektör grupları
def group_of(uni, x):
    return (uni["stock_group"].get(x.get("name")) or uni["industry_group"].get(x.get("industry") or "")
            or uni["sector_group"].get(x.get("sector") or ""))


def trend_label(p):
    return ("Güçlü yükseliş" if p >= 6 else "Yükseliş" if p >= 4 else "Kararsız" if p == 3
            else "Düşüş" if p >= 1 else "Güçlü düşüş")


def build_groups(uni, pool, bench_p):
    """Grup başına üye hisselerin medyanı: performans, RS, trend (üye trend puanı ortalaması + katılım koşulları)."""
    members = {}
    for x in pool:
        g = group_of(uni, x)
        if g:
            members.setdefault(g, []).append(x)
    out = []
    for g in uni["groups"]:
        ms = members.get(g["sym"], [])
        if not ms:
            continue
        perfs = [perf_of(x) for x in ms]
        gp = {k: med([p[k] for p in perfs]) for k in ("w", "m1", "m3", "m6")}
        rs = mk.rel(gp, bench_p)
        trs = [t for t in (mk.trend_points(x) for x in ms) if t]
        pts = round(sum(t["points"] for t in trs) / len(trs)) if trs else None

        def share(pred):
            ok = [pred(x) for x in ms]
            ok = [v for v in ok if v is not None]
            return round(sum(ok) / len(ok) * 100) if ok else None
        above50 = share(lambda x: None if num(x.get("close")) is None or num(x.get("SMA50")) is None else x["close"] > x["SMA50"])
        above200 = share(lambda x: None if num(x.get("close")) is None or num(x.get("SMA200")) is None else x["close"] > x["SMA200"])
        abovew = share(lambda x: None if num(x.get("close")) is None or num(x.get("EMA20|1W")) is None else x["close"] > x["EMA20|1W"])
        tr = None
        if pts is not None:
            tr = {"points": pts, "label": trend_label(pts),
                  "checks": [[f"Üyelerin %{above50}'i SMA50 üstünde (>%50)", above50 is not None and above50 > 50],
                             [f"Üyelerin %{above200}'i SMA200 üstünde (>%50)", above200 is not None and above200 > 50],
                             [f"Üyelerin %{abovew}'i haftalık EMA20 üstünde (>%50)", abovew is not None and abovew > 50],
                             [f"Üye trend puanı ortalaması {pts}/7 (≥4)", pts >= 4]],
                  "daily_up": above50 is not None and above50 > 50, "weekly_up": abovew is not None and abovew > 50}
        q = mk.quadrant(rs)
        atrp = med([num(x.get("ATR")) / num(x.get("close")) * 100 for x in ms if num(x.get("ATR")) and num(x.get("close"))], 2)
        out.append({"sym": g["sym"], "name": g["name"], "kind": g["kind"], "bank": bool(g.get("bank")), "n": len(ms),
                    "members": sorted(x["name"] for x in ms)[:40], "close": None,
                    "chg": med([num(x.get("change")) for x in ms]), "perf": {k: rnd(v, 2) for k, v in gp.items()},
                    "rsi": med([num(x.get("RSI")) for x in ms], 1), "rsi_w": med([num(x.get("RSI|1W")) for x in ms], 1),
                    "atr_pct": atrp, "breadth50": above50, "rs": rs, "trend": tr, "quadrant": q,
                    "verdict": mk.verdict(q, tr, g.get("bank")), "src": "tv"})
    ranked = sorted([x for x in out if (x.get("rs") or {}).get("score") is not None],
                    key=lambda x: x["rs"]["score"], reverse=True)
    for i, x in enumerate(ranked, 1):
        x["rank"] = i
    out.sort(key=lambda x: x.get("rank") or 999)
    return out


def build_picks(uni, pool, gmap, bench_p, held):
    """Sektör başına en çok N hisse: trend >= min_trend, XU100'e göre RS > 0, yeterli TL hacmi. Banka/alkol hariç."""
    cfg = uni["picks"]
    excl_ind, excl_t = set(cfg["exclude_industries"]), set(cfg["exclude_tickers"])
    by_g = {}
    for x in pool:
        g = group_of(uni, x)
        if g and not gmap.get(g, {}).get("bank") and g in gmap:
            by_g.setdefault(g, []).append(x)
    out = {}
    for g, recs in by_g.items():
        gperf = gmap[g].get("perf") or {}
        cands = []
        for x in recs:
            t = x["name"]
            if t in excl_t or (x.get("industry") or "") in excl_ind or (x.get("mcap") or num(x.get("market_cap_basic")) or 0) < cfg["min_mcap"]:
                continue
            c = mk.compact(x, "tv")
            dv = (num(x.get("average_volume_10d_calc")) or 0) * (c["close"] or 0)  # adet × fiyat = TL
            if dv < cfg["min_tl_vol"]:
                continue
            tr = mk.trend_points(x)
            rs = mk.rel(perf_of(x), bench_p)
            if not tr or tr["points"] < cfg["min_trend"] or (rs.get("score") or -1) <= 0:
                continue
            rg = mk.rel(perf_of(x), gperf) if gperf else {}
            cands.append({"t": t, "name": x.get("description") or t, "close": c["close"], "chg": c["chg"],
                          "rs": rs.get("score"), "rs_m1": rs.get("m1"), "rs_m3": rs.get("m3"), "rs_group": rg.get("score"),
                          "trend": tr["points"], "label": tr["label"], "rsi": c["rsi"], "atr_pct": c["atr_pct"],
                          "stop_atr": mk.atr_stop(c), "mcap_bn": rnd((num(x.get("market_cap_basic")) or 0) / 1e9, 1),
                          "dvol_mn": rnd(dv / 1e6, 0), "earn_next": c["earn_next"], "industry": x.get("industry"),
                          "tracked": t in held, "_k": (rs.get("score") or 0) + 0.5 * (rg.get("score") or 0)})
        cands.sort(key=lambda z: z["_k"], reverse=True)
        for z in cands:
            z.pop("_k")
        out[g] = cands[:cfg["per_group"]]
    return out


# ------------------------------------------------------------------ rejim
def regime(bench, fx, pool):
    """0-7 puan: XU100/XU030 trendi, piyasa genişliği, TL değer kaybı (kur) ve dolar bazlı getiri."""
    def g(s, k):
        return num((bench.get(s) or {}).get(k))
    checks = []

    def add(label, a, b):
        if a is not None and b is not None:
            checks.append([label, a > b])
    add("XU100 > SMA50", g("XU100", "close"), g("XU100", "SMA50"))
    add("XU100 > SMA200", g("XU100", "close"), g("XU100", "SMA200"))
    add("XU100 SMA50 > SMA200", g("XU100", "SMA50"), g("XU100", "SMA200"))
    add("XU030 (büyükler) > SMA50", g("XU030", "close"), g("XU030", "SMA50"))
    with_sma = [x for x in pool if num(x.get("close")) and num(x.get("SMA50"))]
    br50 = round(sum(1 for x in with_sma if x["close"] > x["SMA50"]) / len(with_sma) * 100) if with_sma else None
    if br50 is not None:
        checks.append([f"Genişlik: evrenin %{br50}'i SMA50 üstünde (>%50)", br50 > 50])
    usd = {}
    if fx:
        fm1, fm3 = num(fx.get("Perf.1M")), num(fx.get("Perf.3M"))
        if fm1 is not None:
            checks.append([f"TL sakin: USD/TRY son 1A %{fm1:.1f} (< %3)", fm1 < 3])
        for k, fk in (("m1", "Perf.1M"), ("m3", "Perf.3M")):
            xp, fp = num(bench.get("XU100", {}).get(fk)), num(fx.get(fk))
            usd[k] = rnd(((1 + xp / 100) / (1 + fp / 100) - 1) * 100, 2) if xp is not None and fp is not None else None
        if usd.get("m3") is not None:
            checks.append([f"XU100 dolar bazında 3A getirisi pozitif (%{usd['m3']:.1f})", usd["m3"] > 0])
    if not checks:
        return None, usd
    score = sum(1 for _, ok in checks if ok)
    mxp = len(checks)
    ratio = score / mxp
    if ratio >= 0.8:
        label, cash = "Risk-on (yükseliş)", [10, 15]
    elif ratio >= 0.45:
        label, cash = "Nötr / seçici", [20, 25]
    else:
        label, cash = "Risk-off (savunma)", [35, 40]
    return {"score": score, "max": mxp, "label": label, "cash_target": cash, "breadth50": br50, "checks": checks}, usd


# ------------------------------------------------------------------ ana akış
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="market-bist.json")
    ap.add_argument("--tickers-file", default=TICKERS_FILE)
    args = ap.parse_args(argv)

    uni = common.load_json(UNIVERSE)
    cfg = uni["picks"]
    stocks = list(dict.fromkeys(common.public_symbols("docs/bist/data") + tk.read_tickers_file(args.tickers_file)))
    prev = common.load_json(args.out, {}) or {}
    now = datetime.now(timezone.utc)

    def keep_prev(msg):
        log(msg)
        if prev:
            prev["checked"] = now.isoformat(timespec="seconds")
            prev["log"] = LOG
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(prev, f, ensure_ascii=False, indent=1)
        return 1

    bsyms = [f"BIST:{b}" for b in uni["benchmarks"]]
    bench = tvscan.fetch(bsyms, cols=COLS, log=log, market="turkey", exact=True) or {}
    fxd = (tvscan.fetch([uni["fx"]["tv"]], cols=COLS, log=log, market=uni["fx"]["market"], exact=True) or {}).get(uni["fx"]["sym"])
    if "XU100" not in bench:
        return keep_prev("[ERROR] XU100 verisi yok (TV scanner erişilemedi); göreli güç hesaplanamaz. Önceki dosya korunuyor.")
    bench_p = perf_of(bench["XU100"])

    pool = tvscan.screen([{"left": "market_cap_basic", "operation": "greater", "right": cfg["min_mcap"]}],
                         cols=COLS, log=log, market="turkey", types=["stock"]) or []
    log(f"TV scanner: endeks {len(bench)}/{len(bsyms)}, kur {'var' if fxd else 'yok'}, hisse havuzu {len(pool)}")
    for x in pool:
        x["mcap"] = num(x.get("market_cap_basic"))
    pmap = {x["name"]: x for x in pool}

    data, src = {}, {}
    sc = tvscan.fetch([f"BIST:{s}" for s in stocks], cols=COLS, log=log, market="turkey", exact=True) or {}
    for s in stocks:
        if s in sc:
            data[s], src[s] = sc[s], "tv"
        elif s in pmap:
            data[s], src[s] = pmap[s], "tv"
    missing = [s for s in stocks if s not in data]
    for s in missing[:YF_MAX]:
        try:
            data[s], src[s] = from_yfinance(s), "yfinance"
        except Exception as ex:
            log(f"yfinance {s}: {type(ex).__name__}: {tk.scrub(ex)[:80]}")

    gout = build_groups(uni, pool, bench_p)
    pg = {g["sym"]: g for g in prev.get("groups", [])}
    have = {g["sym"] for g in gout}
    gout += [{**v, "stale": True} for k, v in pg.items() if k not in have]
    gmap = {x["sym"]: x for x in gout}

    pstocks = prev.get("stocks", {})
    sout = {}
    for s in stocks:
        if s not in data:
            if s in pstocks:
                sout[s] = {**pstocks[s], "stale": True}
            continue
        x = data[s]
        grp = group_of(uni, x)
        gp = (gmap.get(grp) or {}).get("perf")
        rs = mk.rel(perf_of(x), bench_p)
        tr = mk.trend_points(x)
        q = mk.quadrant(rs)
        c = mk.compact(x, src[s])
        sout[s] = {"name": x.get("description") or s, "sector": x.get("sector"), "industry": x.get("industry"),
                   "group": grp, "group_name": (gmap.get(grp) or {}).get("name"), **c, "rs": rs,
                   "rs_group": mk.rel(perf_of(x), gp) if gp else None, "trend": tr, "quadrant": q,
                   "verdict": mk.verdict(q, tr, bool((gmap.get(grp) or {}).get("bank"))), "stop_atr": mk.atr_stop(c)}

    try:
        picks = build_picks(uni, pool, gmap, bench_p, set(stocks))
    except Exception as ex:  # seçim hatası ana çıktıyı düşürmesin
        log(f"Hisse seçimi hatası: {type(ex).__name__}: {tk.scrub(ex)[:100]}")
        picks = prev.get("picks") or {}
    reg, usd = regime(bench, fxd, pool)
    out = {
        "market": "BIST", "bench": "XU100", "cur": "₺",
        "updated": now.isoformat(timespec="seconds"), "checked": now.isoformat(timespec="seconds"),
        "sources": {k: sum(1 for v in src.values() if v == k) for k in set(src.values())},
        "missing": [s for s in stocks if s not in data],
        "benchmarks": {b: {"name": uni["benchmarks"][b], **mk.compact(bench[b], "tv"), "trend": mk.trend_points(bench[b])}
                       for b in uni["benchmarks"] if b in bench},
        "fx": ({"usdtry": rnd(num(fxd.get("close")), 4), "perf": {k: rnd(v, 2) for k, v in perf_of(fxd).items()},
                "xu100_usd": usd} if fxd else None),
        "regime": reg, "groups": gout, "stocks": sout, "picks": picks, "picks_pool": len(pool), "log": LOG,
        "method": "RS = performans − XU100 (puan). Sektör = üye hisselerin medyanı. Bileşik: 0.15·1H+0.35·1A+0.35·3A+0.15·6A. "
                  "Trend 0-7 (5 günlük + 2 haftalık koşul). Çeyrek: 3A RS (uzun) ve 1A RS (kısa). "
                  "Stop önerisi: fiyattan 2×ATR ya da 3A tepeden 3×ATR (yüksek olan). Banka ve alkol önerilmez.",
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    top = ", ".join(f"{x['sym']}({x['verdict']})" for x in gout[:5])
    print(f"Rejim: {reg and reg['label']} · ilk 5: {top} · izlenen hisse {len(sout)} · aday grubu {len(picks)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
