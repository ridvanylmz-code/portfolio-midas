"""Ortak yardımcılar: dosya I/O, hesaplamalar, uyarılar, Telegram."""
import html
import json
import math
import os
import re
import tempfile
from pathlib import Path

import requests

ROOT = Path(os.environ.get("PORTFOLIO_ROOT") or Path(__file__).resolve().parent.parent)
TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")

# Piyasa seçimi: MARKET=bist -> BIST kopyası (ayrı portföy/geçmiş/durum dosyaları, ₺, docs/bist/data).
# Varsayılan (MARKET boş/us) ABD yapısıdır ve davranışı değişmez.
MARKET = (os.environ.get("MARKET") or "us").strip().lower()
if MARKET == "bist":
    F_PORTFOLIO, F_HISTORY, F_STATE = "bist/portfolio.json", "bist/history.json", "bist/state.json"
    DATA_DIR, CUR = "docs/bist/data", "₺"
else:
    F_PORTFOLIO, F_HISTORY, F_STATE = "portfolio.json", "history.json", "state.json"
    DATA_DIR, CUR = "docs/data", "$"


# ---------------------------------------------------------------- dosya I/O
def path(name):
    return ROOT / name


def load_json(name, default=None):
    p = path(name)
    if not p.exists():
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_json(name, data):
    """Atomik yazım: yarım dosya kalmasın."""
    p = path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, p)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load_portfolio():
    data = load_json(F_PORTFOLIO)
    if data is None:
        raise FileNotFoundError(f"{F_PORTFOLIO} bulunamadı")
    # Eski şema: "cash_reserve". Tek anahtara ("cash") taşı ki bayat kopya kalmasın.
    data["cash"] = float(data.get("cash", data.get("cash_reserve", 0)))
    data.pop("cash_reserve", None)
    data.setdefault("portfolio", {})
    data.setdefault("watchlist", [])
    data.setdefault("alerts", {})
    data.setdefault("position_levels", {})
    data.setdefault("buy_zones", {})
    data.setdefault("monthly_target", 0)
    for t, pos in data["portfolio"].items():
        if not TICKER_RE.match(t):
            raise ValueError(f"Geçersiz ticker: {t}")
        if not (pos["shares"] > 0 and pos["cost_basis"] > 0):
            raise ValueError(f"{t}: shares ve cost_basis > 0 olmalı")
    return data


def load_history():
    h = load_json(F_HISTORY, {}) or {}
    h.setdefault("transactions", [])
    h.setdefault("snapshots", [])
    return h


def sync_public():
    """Dashboard (GitHub Pages /docs) sadece docs/ altını görür; kopyala."""
    for name, src in (("portfolio.json", F_PORTFOLIO), ("history.json", F_HISTORY)):
        data = load_json(src)
        if data is not None:
            save_json(f"{DATA_DIR}/{name}", data)


# ------------------------------------------------------------- hesaplamalar
def pct(a, b):
    return (a / b * 100) if b else 0.0


def valid_quote(q):
    try:
        return bool(q) and float(q.get("c") or 0) > 0
    except (TypeError, ValueError):
        return False


def position_metrics(shares, cost_basis, quote):
    price = float(quote["c"])
    prev = float(quote.get("pc") or price)
    value = shares * price
    cost = shares * cost_basis
    return {
        "price": price,
        "prev_close": prev,
        "value": value,
        "cost": cost,
        "pnl": value - cost,
        "pnl_pct": pct(value - cost, cost),
        "day_pnl": shares * (price - prev),
        "day_pct": pct(price - prev, prev),
    }


def summarize(portfolio, quotes):
    positions, missing = [], []
    value = cost = day_pnl = prev_value = 0.0
    for t, pos in portfolio["portfolio"].items():
        q = quotes.get(t)
        if not valid_quote(q):
            missing.append(t)
            continue
        m = position_metrics(pos["shares"], pos["cost_basis"], q)
        m.update(ticker=t, shares=pos["shares"], cost_basis=pos["cost_basis"],
                 stale=bool(q.get("stale")))
        positions.append(m)
        value += m["value"]
        cost += m["cost"]
        day_pnl += m["day_pnl"]
        prev_value += pos["shares"] * m["prev_close"]
    cash = portfolio["cash"]
    total = value + cash
    for m in positions:
        m["weight"] = pct(m["value"], total)
    return {
        "positions": positions,
        "positions_value": value,
        "cost": cost,
        "cash": cash,
        "total_value": total,
        "pnl": value - cost,
        "pnl_pct": pct(value - cost, cost),
        "day_pnl": day_pnl,
        "day_pct": pct(day_pnl, prev_value),
        "cash_pct": pct(cash, total),
        "missing": missing,
    }


def levels_for(portfolio, ticker):
    """Stop / hedef fiyatı: pozisyona özel seviye varsa o, yoksa maliyet ± yüzde."""
    pos = portfolio["portfolio"][ticker]
    custom = portfolio["position_levels"].get(ticker, {})
    a = portfolio["alerts"]
    stop = custom.get("stop_loss")
    target = custom.get("target")
    if stop is None and a.get("stop_loss_pct") is not None:
        stop = pos["cost_basis"] * (1 + a["stop_loss_pct"] / 100)
    if target is None and a.get("target_pct") is not None:
        target = pos["cost_basis"] * (1 + a["target_pct"] / 100)
    return stop, target


def check_alerts(portfolio, fresh_quotes):
    out = []
    move = portfolio["alerts"].get("daily_move_pct")
    for t in portfolio["portfolio"]:
        q = fresh_quotes.get(t)
        if not valid_quote(q):
            continue
        price = float(q["c"])
        stop, target = levels_for(portfolio, t)
        if stop is not None and price <= stop:
            out.append({"key": f"{t}:stop", "text": f"🛑 {t} stop seviyesinde: {CUR}{price:.2f} (stop {CUR}{stop:.2f})"})
        if target is not None and price >= target:
            out.append({"key": f"{t}:target", "text": f"🎯 {t} hedefe ulaştı: {CUR}{price:.2f} (hedef {CUR}{target:.2f})"})
        dp = q.get("dp")
        if move and dp is not None and abs(dp) >= move:
            side = "up" if dp > 0 else "down"
            out.append({"key": f"{t}:move_{side}", "text": f"⚡ {t} günlük %{dp:+.2f} hareket ({CUR}{price:.2f})"})
    return out


def month_progress(history, target, total_value, today_iso):
    """Ay başı ilk snapshot'a göre kazanç; para yatırma/çekmeyi düzeltir."""
    if not target:
        return None
    month = today_iso[:7]
    snaps = sorted((s for s in history["snapshots"] if s["date"].startswith(month)),
                   key=lambda s: s["date"])
    if not snaps:
        return None
    start = snaps[0]
    flows = 0.0
    for tx in history["transactions"]:
        if tx["date"] > start["date"] and tx["date"].startswith(month):
            if tx["action"] == "deposit":
                flows += tx["amount"]
            elif tx["action"] == "withdraw":
                flows -= tx["amount"]
    gain = total_value - start["value"] - flows
    return {"start": start["value"], "start_date": start["date"], "gain": gain,
            "target": target, "pct": pct(gain, target)}


# ----------------------------------------------------------------- Telegram
def send_telegram(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[WARN] Telegram bilgileri yok; mesaj gönderilmedi.")
        return False
    if len(text) > 4000:
        text = text[:3990] + "\n…"
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=15,
        )
        if r.status_code != 200:
            # URL token içerir; sadece durum kodunu yaz
            print(f"[WARN] Telegram HTTP {r.status_code}")
            return False
        return True
    except requests.RequestException as e:
        print(f"[WARN] Telegram hatası: {type(e).__name__}")
        return False


def e(s):
    return html.escape(str(s))


def finite_positive(x, name):
    try:
        x = float(x)
    except (TypeError, ValueError):
        raise ValueError(f"{name} sayı olmalı")
    if not math.isfinite(x) or x <= 0:
        raise ValueError(f"{name} > 0 olmalı")
    return x
