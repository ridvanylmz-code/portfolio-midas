#!/usr/bin/env python3
"""Fiyatları çek -> docs/data/*.json yaz -> (opsiyonel) Telegram raporu / alarm gönder.

Kullanım:
  python scripts/monitor.py             # sadece yenile (piyasa kapalıysa atla)
  python scripts/monitor.py --report    # yenile + Telegram raporu
  python scripts/monitor.py --force     # piyasa kapalı olsa da yenile
Finnhub anahtarı sadece FINNHUB_API_KEY ortam değişkeninden okunur.
"""
import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

API = "https://finnhub.io/api/v1"
ET = ZoneInfo("America/New_York")
IST = ZoneInfo("Europe/Istanbul")
BIST = common.MARKET == "bist"
CUR = common.CUR
PRICE_DAYS = 30
SNAPSHOT_LIMIT = 400

# Telegram rapor saatleri ABD saatine (ET) bağlı: yaz/kış saati geçişinde kendiliğinden kayar.
# (saat, dakika, ET hafta günleri 0=Pzt). İstanbul karşılığı yazın: 03:01, 07:01, 11:01, 16:16, 16:31, 22:55, 23:01
# (kışın 1 saat sonra). 20:01 ET Pazar dahil: Pazartesi sabahı (İstanbul) yeni hafta ilk raporu.
WEEK = (0, 1, 2, 3, 4)
REPORT_SLOTS_ET = [(20, 1, (6,) + WEEK), (0, 1, WEEK), (4, 1, WEEK), (9, 16, WEEK), (9, 31, WEEK),
                   (15, 55, WEEK), (16, 1, WEEK)]
SLOT_WINDOW_MIN = 25  # GitHub zamanlanmış işleri geciktirebilir


def due_slots(now):
    """Şu an penceresinde olan rapor saatleri (kimlik: ET tarih + saat)."""
    t = now.astimezone(ET)
    out = []
    for h, m, days in REPORT_SLOTS_ET:
        s = t.replace(hour=h, minute=m, second=0, microsecond=0)
        if t.weekday() in days and s <= t < s + timedelta(minutes=SLOT_WINDOW_MIN):
            out.append(f"{s:%Y-%m-%dT%H%M}")
    return out


# ------------------------------------------------------------------ Finnhub
def fetch_quote(ticker, key, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(f"{API}/quote", params={"symbol": ticker, "token": key}, timeout=10)
            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            d = r.json()
            q = {k: d.get(k) for k in ("c", "d", "dp", "h", "l", "o", "pc", "t")}
            return q if common.valid_quote(q) else None
        except (requests.RequestException, ValueError) as ex:
            # İstisna metni token içeren URL taşıyabilir; yalnızca türünü yaz.
            print(f"[WARN] {ticker}: {type(ex).__name__}")
            time.sleep(1)
    return None


def backup_tv(tickers):
    import tvscan
    sc = tvscan.fetch(tickers, ["name", "close", "change", "change_abs", "open", "high", "low", "market_cap_basic"],
                      retries=2) or {}
    return {t: q for t, r in sc.items() if (q := tvscan.quote_from(r))}


def backup_alpaca(tickers):
    import alpaca
    return alpaca.snapshots(tickers)


def market_status(key):
    try:
        r = requests.get(f"{API}/stock/market-status", params={"exchange": "US", "token": key}, timeout=10)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError) as ex:
        print(f"[WARN] market-status: {type(ex).__name__}")
        return None


# ------------------------------------------------------------------ ön/sonrası
def attach_ext(quotes, tickers, now):
    """quotes.json'daki her kotasyona ön/kapanış sonrası fiyatını `ext` olarak ekler (TradingView).

    Finnhub alanları (c, pc, d, dp) DEĞİŞMEZ; ekranlar `ext`i görünce fiyatı onunla gösterir.
    Normal seans/seans dışında `ext` kaldırılır. Çekim başarısızsa önceki `ext` kalır (ekranda 3 saat yaş sınırı var).
    Dönüş: seans adı ('pre'|'post'|None).
    """
    if BIST:
        return None
    try:
        import extended
        sess = extended.session_name(now)
        got = extended.fetch(tickers)[0] if sess in ("pre", "post") else {}
    except Exception as ex:  # asla çalışmayı düşürme
        print(f"[WARN] attach_ext: {type(ex).__name__}")
        return None
    if sess not in ("pre", "post"):
        for q in quotes.values():
            q.pop("ext", None)
        return None
    if not got:
        return sess
    for t, q in quotes.items():
        x = got.get(t) or {}
        p = x.get(sess)
        if p and p > 0:
            q["ext"] = {"sess": sess, "p": p, "pct": x.get(sess + "_pct"), "close": x.get("close"),
                        "t": now.isoformat(timespec="seconds")}
        else:
            q.pop("ext", None)
    return sess


def refresh_ext_only(now):
    """Piyasa kapalıyken (ön/sonrası): yalnızca quotes.json'daki `ext` alanlarını yenile.
    Finnhub, prices.json, history.json ve alarmlara dokunmaz."""
    if BIST:
        return 0
    qj = common.load_json(f"{common.DATA_DIR}/quotes.json", {}) or {}
    quotes = qj.get("quotes") or {}
    if not quotes:
        print("quotes.json boş; ön/sonrası yenileme atlandı.")
        return 0
    sess = attach_ext(quotes, list(quotes), now)
    qj["quotes"] = quotes
    qj["ext_updated"] = now.isoformat(timespec="seconds")
    common.save_json(f"{common.DATA_DIR}/quotes.json", qj)
    n = sum(1 for q in quotes.values() if q.get("ext"))
    print(f"Ön/sonrası ({sess}): {n}/{len(quotes)} hisse güncellendi")
    return 0


def apply_extended(quotes, tickers, now):
    """Ön piyasa / kapanış sonrası seansında rapor için fiyatı TradingView'den al.

    Yalnızca rapor metni içindir; quotes.json, prices.json ve history.json Finnhub fiyatıyla kalır.
    Hata olursa sessizce Finnhub fiyatına döner. Dönüş: (quotes, 'pre'|'post'|None)
    """
    if BIST:
        return quotes, None
    try:
        import extended
        sess = extended.session_name(now)
        if sess not in ("pre", "post"):
            return quotes, None
        got, _ = extended.fetch(tickers)
    except Exception as ex:  # rapor hiçbir koşulda bundan dolayı düşmesin
        print(f"[WARN] extended: {type(ex).__name__}")
        return quotes, None
    if not got:
        return quotes, None
    out, n = dict(quotes), 0
    for t, q in quotes.items():
        x = got.get(t) or {}
        p = x.get(sess)
        if not p or p <= 0 or not common.valid_quote(q):
            continue
        nq = dict(q)
        if sess == "pre":  # Finnhub c = dünkü kapanış -> günlük değişim ona göre
            nq["pc"] = q["c"]
        pc = float(nq.get("pc") or q["c"])
        nq.update(c=p, d=p - pc, dp=(p / pc - 1) * 100 if pc else 0.0, ext=sess)
        out[t] = nq
        n += 1
    return (out, sess) if n else (quotes, None)


# ------------------------------------------------------------------ rapor
def _market():
    path = os.environ.get("MARKET_JSON", "")
    if BIST or not path or not os.path.exists(path):
        return None
    try:
        import json
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as ex:
        print(f"[WARN] market.json okunamadı: {type(ex).__name__}")
        return None


def earnings_alerts(portfolio, now):
    """Pozisyon ve izleme listesindeki hisselerin bilançosuna 3 gün (ve 0 gün) kala tek seferlik uyarı."""
    m = _market()
    if not m:
        return []
    today = now.astimezone(ET).date()
    held = set(portfolio["portfolio"])
    out = []
    for t in list(held) + [x for x in portfolio["watchlist"] if x not in held]:
        d = ((m.get("stocks") or {}).get(t) or {}).get("earn_next")
        if not d:
            continue
        try:
            days = (datetime.fromisoformat(d).date() - today).days
        except ValueError:
            continue
        if not 0 <= days <= 3:
            continue
        stage = "0" if days == 0 else "3"
        when = "BUGÜN" if days == 0 else f"{days} gün sonra"
        what = "pozisyonda: bilanço oynaklığına karşı stopu/boyutu gözden geçir" if t in held else \
               "izleme listesinde: girişi bilanço sonrasına bırakmak daha güvenli"
        out.append({"key": f"{t}:earn:{d}:{stage}", "once": True,
                    "text": f"📅 {t} bilançosu {d} ({when}) — {what}"})
    return out


def market_lines(summary):
    """market.json (market-data dalı; iş akışı MARKET_JSON ile verir) varsa rejim, nakit hedefi ve lider/zayıf sektörler."""
    m = _market()
    if not m:
        return []
    try:
        r = m.get("regime") or {}
        lo, hi = (r.get("cash_target") or [None, None])[:2]
        cp = summary["cash_pct"]
        gap = "" if lo is None else (" ⚠️ hedefin altında" if cp < lo else " ⚠️ hedefin üstünde" if cp > hi else " ✅")
        g = m.get("groups") or []
        lead = [x["sym"] for x in g if str(x.get("verdict", "")).startswith(("Ol", "Erken")) and not x.get("bank")][:5]
        weak = [x["sym"] for x in g if str(x.get("verdict", "")).startswith("Uzak")][-4:]
        out = [f"🧭 Rejim: {common.e(r.get('label', '–'))} ({r.get('score')}/{r.get('max')}) · önerilen nakit %{lo}–{hi}, şu an %{cp:.1f}{gap}"]
        if lead:
            out.append("📈 Güçlü: " + ", ".join(common.e(x) for x in lead) + (" · 📉 Zayıf: " + ", ".join(common.e(x) for x in weak) if weak else ""))
        return out
    except Exception as ex:
        print(f"[WARN] market.json okunamadı: {type(ex).__name__}")
        return []


def build_report(portfolio, quotes, fresh, summary, market_open, alerts, month, now, dashboard_url, ext_sess=None):
    e = common.e
    ist = now.astimezone(IST).strftime("%d.%m %H:%M")
    state = {True: "🟢 Piyasa açık", False: "🔴 Piyasa kapalı"}.get(market_open, "⚪ Piyasa durumu bilinmiyor")
    ico = lambda v: "🟢" if v >= 0 else "🔴"  # noqa: E731
    lines = [
        f"<b>{'🇹🇷 BIST Portföy Raporu' if BIST else '📊 Portföy Raporu'}</b> · {ist} (İstanbul)",
        state,
        *(["🌙 Kapanış sonrası fiyatlar (TradingView)"] if ext_sess == "post" else
          ["🌅 Ön piyasa fiyatları (TradingView)"] if ext_sess == "pre" else []),
        "",
        f"💼 Toplam: <b>{CUR}{summary['total_value']:,.2f}</b>",
        f"{ico(summary['day_pnl'])} Bugün: <b>{summary['day_pnl']:+,.2f}{CUR}</b> ({summary['day_pct']:+.2f}%)",
        f"{ico(summary['pnl'])} Toplam K/Z: <b>{summary['pnl']:+,.2f}{CUR}</b> ({summary['pnl_pct']:+.2f}%)",
        f"💵 Nakit: {CUR}{summary['cash']:,.2f} (%{summary['cash_pct']:.1f})",
    ]
    lines += market_lines(summary)
    if month:
        lines.append(f"🎯 Aylık hedef: {month['gain']:+,.0f}{CUR} / {month['target']:,.0f}{CUR} (%{max(month['pct'], 0):.0f})")
    lines += ["", "<b>Pozisyonlar</b>"]
    for m in sorted(summary["positions"], key=lambda x: -x["value"]):
        stale = " ⏱" if m["stale"] else ""
        if (quotes.get(m["ticker"]) or {}).get("ext"):
            stale += " 🌙" if ext_sess == "post" else " 🌅"
        lines.append(
            f"{ico(m['day_pct'])} <b>{e(m['ticker'])}</b> {CUR}{m['price']:.2f} ({m['day_pct']:+.2f}%){stale}\n"
            f"    K/Z {m['pnl']:+,.0f}{CUR} ({m['pnl_pct']:+.1f}%) · ağırlık %{m['weight']:.0f}"
        )
    if summary["missing"]:
        lines.append("⚠️ Fiyat alınamadı: " + ", ".join(e(t) for t in summary["missing"]))

    wl = [(t, quotes[t]) for t in portfolio["watchlist"] if common.valid_quote(quotes.get(t))]
    wl.sort(key=lambda x: -(x[1].get("dp") or 0))
    lines += ["", f"<b>İzleme listesi ({len(portfolio['watchlist'])})</b>"]
    for t, q in wl:
        z = common.zone_of(portfolio, t)
        tag = (" 🎯 alım bölgesi" if "below" in z and q["c"] <= z["below"] else "") + \
              (" 🚀 kırılım" if "above" in z and q["c"] >= z["above"] else "") + \
              (f" · alarm {'≤' + format(z['below'], '.2f') if 'below' in z else ''}{' ≥' + format(z['above'], '.2f') if 'above' in z else ''}" if z else "")
        lines.append(f"{ico(q.get('dp') or 0)} {e(t)} {CUR}{q['c']:.2f} ({(q.get('dp') or 0):+.2f}%){tag}")
    no_quote = [t for t in portfolio["watchlist"] if not common.valid_quote(quotes.get(t))]
    if no_quote:
        lines.append("⚠️ Fiyat alınamadı: " + ", ".join(e(t) for t in no_quote))

    if alerts:
        lines += ["", "<b>Alarmlar</b>"] + [e(a["text"]) for a in alerts]
    if dashboard_url:
        lines += ["", f'<a href="{e(dashboard_url)}">Dashboard</a>']
    return "\n".join(lines)


# --------------------------------------------------------------- ana akış
def update_prices(prices, fresh_quotes, et_date):
    for t, q in fresh_quotes.items():
        hist = prices.setdefault(t, {})
        hist[et_date] = round(float(q["c"]), 4)
        for d in sorted(hist)[:-PRICE_DAYS]:
            del hist[d]
    return prices


def upsert_snapshot(history, et_date, summary):
    snap = {"date": et_date, "value": round(summary["total_value"], 2),
            "cost": round(summary["cost"], 2), "cash": round(summary["cash"], 2)}
    snaps = [s for s in history["snapshots"] if s["date"] != et_date]
    snaps.append(snap)
    history["snapshots"] = sorted(snaps, key=lambda s: s["date"])[-SNAPSHOT_LIMIT:]


def run(report=False, force=False, key=None, fetch=fetch_quote, status_fn=market_status,
        now=None, dashboard_url=None):
    now = now or datetime.now(timezone.utc)
    et_date = now.astimezone(IST if BIST else ET).date().isoformat()
    due = []
    if report == "auto":  # zamanlanmış çalışma: rapor mu sessiz yenileme mi, ET saatine göre burada seçilir
        st0 = common.load_json(common.F_STATE, {}) or {}
        done = set(st0.get("reports", [])) if st0.get("date") == et_date else set()
        due = [x for x in due_slots(now) if x not in done]
        report = bool(due)
        if not report and not BIST:
            import extended
            if extended.session_name(now) in ("pre", "post") and now.astimezone(ET).minute % 30 >= 15:
                print("Ön/sonrası seansı: yarım saatte bir yenilenir; atlandı.")
                return 0
        print(f"Otomatik mod: {'rapor ' + ','.join(due) if report else 'sessiz yenileme'}")
    portfolio = common.load_portfolio()
    holdings = portfolio["portfolio"]
    tickers = list(dict.fromkeys(list(holdings) + list(portfolio["watchlist"])))

    status = status_fn(key)
    market_open = status.get("isOpen") if status else None
    if not report and not force and market_open is False:
        try:
            import extended
            if not BIST and extended.session_name(now) in ("pre", "post"):
                return refresh_ext_only(now)
        except Exception as ex:
            print(f"[WARN] ext yenileme: {type(ex).__name__}")
        print("Piyasa kapalı; yenileme atlandı.")
        return 0

    prev = (common.load_json(f"{common.DATA_DIR}/quotes.json", {}) or {}).get("quotes", {})
    quotes, fresh = {}, {}
    for t in tickers:
        q = fetch(t, key)
        if q:
            quotes[t] = q
            fresh[t] = q
    # Yedek zincir (yalnız ABD): Finnhub'dan gelmeyenler -> TradingView tarayıcısı (tek istek) -> Alpaca (anahtar varsa)
    missing = [t for t in tickers if t not in fresh]
    if missing and not BIST:
        for name, fn in (("TV scanner", backup_tv), ("Alpaca", backup_alpaca)):
            if not missing:
                break
            try:
                got = fn(missing)
            except Exception as ex:
                print(f"[WARN] {name} yedeği: {type(ex).__name__}")
                got = {}
            for t, q in got.items():
                if common.valid_quote(q):
                    quotes[t] = fresh[t] = q
            if got:
                print(f"{name} yedeği: {len(got)}/{len(missing)} fiyat")
            missing = [t for t in tickers if t not in fresh]
    for t in tickers:
        if t not in quotes and common.valid_quote(prev.get(t)):
            quotes[t] = {**prev[t], "stale": True}
    if not fresh:
        print("[ERROR] Hiç fiyat alınamadı (API anahtarı / limit?).")
        return 1

    summary = common.summarize(portfolio, quotes)
    history = common.load_history()

    attach_ext(quotes, tickers, now)
    common.save_json(f"{common.DATA_DIR}/quotes.json", {
        "updated": now.isoformat(timespec="seconds"),
        "market_open": market_open,
        "quotes": quotes,
    })
    common.save_json(f"{common.DATA_DIR}/prices.json",
                     update_prices(common.load_json(f"{common.DATA_DIR}/prices.json", {}) or {}, fresh, et_date))

    if all(t in fresh for t in holdings):
        upsert_snapshot(history, et_date, summary)
        common.save_json(common.F_HISTORY, history)
    common.sync_public()

    alerts = common.check_alerts(portfolio, fresh) + earnings_alerts(portfolio, now)
    state = common.load_json(common.F_STATE, {}) or {}
    once = list(state.get("once", []))[-300:]  # tek seferlik alarmlar (bilanço) gün değişse de tekrarlanmaz
    if state.get("date") != et_date:
        state = {"date": et_date, "sent": [], "reports": []}
    state.setdefault("reports", [])
    state["once"] = once
    alerts = [a for a in alerts if not (a.get("once") and a["key"] in once)]
    new_alerts = [a for a in alerts if a["key"] not in state["sent"]]

    if report:
        month = common.month_progress(history, portfolio["monthly_target"], summary["total_value"], et_date)
        rq, ext_sess = apply_extended(quotes, tickers, now)
        rsummary = common.summarize(portfolio, rq) if ext_sess else summary
        month = common.month_progress(history, portfolio["monthly_target"], rsummary["total_value"], et_date) if ext_sess else month
        text = build_report(portfolio, rq, fresh, rsummary, market_open, alerts, month, now, dashboard_url, ext_sess)
        if common.send_telegram(text):
            state["sent"] = sorted(set(state["sent"]) | {a["key"] for a in alerts})
            state["once"] = once + [a["key"] for a in alerts if a.get("once")]
            state["reports"] = sorted(set(state["reports"]) | set(due))
    elif new_alerts:
        if common.send_telegram("<b>🚨 Portföy Alarmı</b>\n" + "\n".join(common.e(a["text"]) for a in new_alerts)):
            state["sent"] = sorted(set(state["sent"]) | {a["key"] for a in new_alerts})
            state["once"] = once + [a["key"] for a in new_alerts if a.get("once")]
    common.save_json(common.F_STATE, state)
    print(f"Tamam: {len(fresh)}/{len(tickers)} fiyat güncel, toplam {CUR}{summary['total_value']:,.2f}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="Telegram raporu gönder")
    ap.add_argument("--force", action="store_true", help="Piyasa kapalıyken de çalış")
    ap.add_argument("--auto", action="store_true",
                    help="Zamanlanmış çalışma: rapor saatindeyse rapor, değilse sessiz yenileme (ET'ye göre)")
    args = ap.parse_args(argv)
    if args.auto and not args.report:
        args.report = "auto"
    if BIST:
        import bist_data
        pf = common.load_portfolio()
        tk = list(dict.fromkeys(list(pf["portfolio"]) + list(pf["watchlist"])))
        return run(report=args.report, force=args.force, key=None, fetch=bist_data.make_fetch(tk),
                   status_fn=bist_data.market_status, dashboard_url=os.environ.get("DASHBOARD_URL"))
    key = os.environ.get("FINNHUB_API_KEY")
    if not key:
        print("[ERROR] FINNHUB_API_KEY tanımlı değil (GitHub Secrets).")
        return 1
    return run(report=args.report, force=args.force, key=key,
               dashboard_url=os.environ.get("DASHBOARD_URL"))


if __name__ == "__main__":
    sys.exit(main())
