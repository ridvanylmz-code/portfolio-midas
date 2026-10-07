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
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

API = "https://finnhub.io/api/v1"
ET = ZoneInfo("America/New_York")
IST = ZoneInfo("Europe/Istanbul")
PRICE_DAYS = 30
SNAPSHOT_LIMIT = 400


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
    qj = common.load_json("docs/data/quotes.json", {}) or {}
    quotes = qj.get("quotes") or {}
    if not quotes:
        print("quotes.json boş; ön/sonrası yenileme atlandı.")
        return 0
    sess = attach_ext(quotes, list(quotes), now)
    qj["quotes"] = quotes
    qj["ext_updated"] = now.isoformat(timespec="seconds")
    common.save_json("docs/data/quotes.json", qj)
    n = sum(1 for q in quotes.values() if q.get("ext"))
    print(f"Ön/sonrası ({sess}): {n}/{len(quotes)} hisse güncellendi")
    return 0


def apply_extended(quotes, tickers, now):
    """Ön piyasa / kapanış sonrası seansında rapor için fiyatı TradingView'den al.

    Yalnızca rapor metni içindir; quotes.json, prices.json ve history.json Finnhub fiyatıyla kalır.
    Hata olursa sessizce Finnhub fiyatına döner. Dönüş: (quotes, 'pre'|'post'|None)
    """
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
def build_report(portfolio, quotes, fresh, summary, market_open, alerts, month, now, dashboard_url, ext_sess=None):
    e = common.e
    ist = now.astimezone(IST).strftime("%d.%m %H:%M")
    state = {True: "🟢 Piyasa açık", False: "🔴 Piyasa kapalı"}.get(market_open, "⚪ Piyasa durumu bilinmiyor")
    ico = lambda v: "🟢" if v >= 0 else "🔴"  # noqa: E731
    lines = [
        f"<b>📊 Portföy Raporu</b> · {ist} (İstanbul)",
        state,
        *(["🌙 Kapanış sonrası fiyatlar (TradingView)"] if ext_sess == "post" else
          ["🌅 Ön piyasa fiyatları (TradingView)"] if ext_sess == "pre" else []),
        "",
        f"💼 Toplam: <b>${summary['total_value']:,.2f}</b>",
        f"{ico(summary['day_pnl'])} Bugün: <b>{summary['day_pnl']:+,.2f}$</b> ({summary['day_pct']:+.2f}%)",
        f"{ico(summary['pnl'])} Toplam K/Z: <b>{summary['pnl']:+,.2f}$</b> ({summary['pnl_pct']:+.2f}%)",
        f"💵 Nakit: ${summary['cash']:,.2f} (%{summary['cash_pct']:.1f})",
    ]
    if month:
        lines.append(f"🎯 Aylık hedef: {month['gain']:+,.0f}$ / {month['target']:,.0f}$ (%{max(month['pct'], 0):.0f})")
    lines += ["", "<b>Pozisyonlar</b>"]
    for m in sorted(summary["positions"], key=lambda x: -x["value"]):
        stale = " ⏱" if m["stale"] else ""
        if (quotes.get(m["ticker"]) or {}).get("ext"):
            stale += " 🌙" if ext_sess == "post" else " 🌅"
        lines.append(
            f"{ico(m['day_pct'])} <b>{e(m['ticker'])}</b> ${m['price']:.2f} ({m['day_pct']:+.2f}%){stale}\n"
            f"    K/Z {m['pnl']:+,.0f}$ ({m['pnl_pct']:+.1f}%) · ağırlık %{m['weight']:.0f}"
        )
    if summary["missing"]:
        lines.append("⚠️ Fiyat alınamadı: " + ", ".join(e(t) for t in summary["missing"]))

    wl = [(t, quotes[t]) for t in portfolio["watchlist"] if common.valid_quote(quotes.get(t))]
    wl.sort(key=lambda x: -(x[1].get("dp") or 0))
    lines += ["", f"<b>İzleme listesi ({len(portfolio['watchlist'])})</b>"]
    for t, q in wl:
        zone = portfolio["buy_zones"].get(t)
        tag = " 🎯 alım bölgesi" if zone and q["c"] <= zone else ""
        lines.append(f"{ico(q.get('dp') or 0)} {e(t)} ${q['c']:.2f} ({(q.get('dp') or 0):+.2f}%){tag}")
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
    portfolio = common.load_portfolio()
    holdings = portfolio["portfolio"]
    tickers = list(dict.fromkeys(list(holdings) + list(portfolio["watchlist"])))

    status = status_fn(key)
    market_open = status.get("isOpen") if status else None
    if not report and not force and market_open is False:
        try:
            import extended
            if extended.session_name(now) in ("pre", "post"):
                return refresh_ext_only(now)
        except Exception as ex:
            print(f"[WARN] ext yenileme: {type(ex).__name__}")
        print("Piyasa kapalı; yenileme atlandı.")
        return 0

    prev = (common.load_json("docs/data/quotes.json", {}) or {}).get("quotes", {})
    quotes, fresh = {}, {}
    for t in tickers:
        q = fetch(t, key)
        if q:
            quotes[t] = q
            fresh[t] = q
        elif common.valid_quote(prev.get(t)):
            quotes[t] = {**prev[t], "stale": True}
    if not fresh:
        print("[ERROR] Hiç fiyat alınamadı (API anahtarı / limit?).")
        return 1

    et_date = now.astimezone(ET).date().isoformat()
    summary = common.summarize(portfolio, quotes)
    history = common.load_history()

    attach_ext(quotes, tickers, now)
    common.save_json("docs/data/quotes.json", {
        "updated": now.isoformat(timespec="seconds"),
        "market_open": market_open,
        "quotes": quotes,
    })
    common.save_json("docs/data/prices.json",
                     update_prices(common.load_json("docs/data/prices.json", {}) or {}, fresh, et_date))

    if all(t in fresh for t in holdings):
        upsert_snapshot(history, et_date, summary)
        common.save_json("history.json", history)
    common.sync_public()

    alerts = common.check_alerts(portfolio, fresh)
    state = common.load_json("state.json", {}) or {}
    if state.get("date") != et_date:
        state = {"date": et_date, "sent": []}
    new_alerts = [a for a in alerts if a["key"] not in state["sent"]]

    if report:
        month = common.month_progress(history, portfolio["monthly_target"], summary["total_value"], et_date)
        rq, ext_sess = apply_extended(quotes, tickers, now)
        rsummary = common.summarize(portfolio, rq) if ext_sess else summary
        month = common.month_progress(history, portfolio["monthly_target"], rsummary["total_value"], et_date) if ext_sess else month
        text = build_report(portfolio, rq, fresh, rsummary, market_open, alerts, month, now, dashboard_url, ext_sess)
        if common.send_telegram(text):
            state["sent"] = sorted(set(state["sent"]) | {a["key"] for a in alerts})
    elif new_alerts:
        if common.send_telegram("<b>🚨 Portföy Alarmı</b>\n" + "\n".join(common.e(a["text"]) for a in new_alerts)):
            state["sent"] = sorted(set(state["sent"]) | {a["key"] for a in new_alerts})
    common.save_json("state.json", state)
    print(f"Tamam: {len(fresh)}/{len(tickers)} fiyat güncel, toplam ${summary['total_value']:,.2f}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="Telegram raporu gönder")
    ap.add_argument("--force", action="store_true", help="Piyasa kapalıyken de çalış")
    args = ap.parse_args(argv)
    key = os.environ.get("FINNHUB_API_KEY")
    if not key:
        print("[ERROR] FINNHUB_API_KEY tanımlı değil (GitHub Secrets).")
        return 1
    return run(report=args.report, force=args.force, key=key,
               dashboard_url=os.environ.get("DASHBOARD_URL"))


if __name__ == "__main__":
    sys.exit(main())
