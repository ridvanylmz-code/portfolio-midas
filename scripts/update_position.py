#!/usr/bin/env python3
"""Pozisyon / nakit / izleme listesi güncelleme.

Girdiler ortam değişkenlerinden (workflow inputs) ya da CLI argümanlarından gelir.
Örnek:
  python scripts/update_position.py --action buy --ticker MU --shares 10 --price 95.5
  python scripts/update_position.py --action sell --ticker UAMY --shares 200 --price 8.1
  python scripts/update_position.py --action buy --ticker MU --shares 10 --price 95.5 --commission 1.25
Komisyon ($) isteğe bağlıdır; boşsa 0 sayılır. Alışta toplam maliyete eklenir (ortalama maliyet buna göre),
satışta net tutardan düşer (gerçekleşen K/Z ve nakit buna göre).
  python scripts/update_position.py --action deposit --amount 1000
  python scripts/update_position.py --action watch_add --ticker AMD
"""
import argparse
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

ET = ZoneInfo("America/New_York")
ACTIONS = ("buy", "sell", "deposit", "withdraw", "watch_add", "watch_remove")
EPS = 1e-9


def _num(x):
    x = round(float(x), 6)
    return int(x) if x.is_integer() else x


def _commission(x):
    """İsteğe bağlı komisyon ($). Boş/None -> 0. Negatif veya geçersiz -> ValueError."""
    if x in (None, ""):
        return 0.0
    try:
        v = float(x)
    except (TypeError, ValueError):
        raise ValueError(f"commission sayı olmalı: {x!r}")
    if v != v or v in (float("inf"), float("-inf")) or v < 0:
        raise ValueError(f"commission 0 veya pozitif olmalı: {x!r}")
    return round(v, 4)


def apply(portfolio, history, action, ticker=None, shares=None, price=None, amount=None,
          note="", date=None, update_cash=True, now=None, commission=None):
    """portfolio/history'yi yerinde günceller, kullanıcıya mesaj döndürür. Hata -> ValueError."""
    now = now or datetime.now(timezone.utc)
    date = date or now.astimezone(ET).date().isoformat()
    if action not in ACTIONS:
        raise ValueError(f"Geçersiz işlem: {action}")

    tx = {"date": date, "time": now.isoformat(timespec="seconds"), "action": action, "note": note or ""}

    if action in ("buy", "sell", "watch_add", "watch_remove"):
        ticker = (ticker or "").strip().upper()
        if not common.TICKER_RE.match(ticker):
            raise ValueError(f"Geçersiz ticker: {ticker!r}")
        tx["ticker"] = ticker

    if action in ("watch_add", "watch_remove"):
        wl = portfolio["watchlist"]
        if action == "watch_add":
            if ticker in wl:
                raise ValueError(f"{ticker} zaten izleme listesinde")
            wl.append(ticker)
            msg = f"👀 {ticker} izleme listesine eklendi ({len(wl)} hisse)"
        else:
            if ticker not in wl:
                raise ValueError(f"{ticker} izleme listesinde yok")
            wl.remove(ticker)
            portfolio["buy_zones"].pop(ticker, None)
            msg = f"🗑 {ticker} izleme listesinden çıkarıldı ({len(wl)} hisse)"
        history["transactions"].append(tx)
        return msg

    if action in ("deposit", "withdraw"):
        amt = common.finite_positive(amount, "amount")
        if action == "withdraw" and amt > portfolio["cash"] + EPS:
            raise ValueError(f"Yetersiz nakit: ${portfolio['cash']:,.2f} < ${amt:,.2f}")
        portfolio["cash"] = round(portfolio["cash"] + (amt if action == "deposit" else -amt), 2)
        tx.update(amount=round(amt, 2), cash_after=portfolio["cash"])
        history["transactions"].append(tx)
        verb = "yatırıldı" if action == "deposit" else "çekildi"
        return f"💵 ${amt:,.2f} {verb}. Nakit: ${portfolio['cash']:,.2f}"

    # buy / sell
    qty = common.finite_positive(shares, "shares")
    px = common.finite_positive(price, "price")
    pos = portfolio["portfolio"].get(ticker)
    fee = _commission(commission)
    gross = qty * px
    # Alış: nakit çıkışı = tutar + komisyon. Satış: nakit girişi = tutar - komisyon.
    total = gross + fee if action == "buy" else gross - fee
    fee_txt = f" (komisyon ${fee:,.2f})" if fee else ""

    if action == "buy":
        if update_cash and total > portfolio["cash"] + EPS:
            raise ValueError(
                f"Yetersiz nakit: ${portfolio['cash']:,.2f} < ${total:,.2f}. "
                "Önce deposit yapın ya da update_cash=false seçin.")
        if pos:
            new_shares = pos["shares"] + qty
            new_cost = (pos["shares"] * pos["cost_basis"] + total) / new_shares
        else:
            new_shares, new_cost = qty, total / qty  # komisyon dahil birim maliyet
        portfolio["portfolio"][ticker] = {"shares": _num(new_shares), "cost_basis": round(new_cost, 4)}
        tx.update(shares=_num(qty), price=px, cost_basis_after=round(new_cost, 4), realized_pnl=0.0)
        if fee:
            tx["commission"] = fee
        msg = (f"🟢 ALIŞ {ticker}: {_num(qty)} adet @ ${px:,.2f}{fee_txt}\n"
               f"Yeni pozisyon: {_num(new_shares)} adet, ort. maliyet ${new_cost:,.4f}")
        if ticker in portfolio["watchlist"]:  # artık pozisyonda; listede iki kez görünmesin
            portfolio["watchlist"].remove(ticker)
            portfolio["buy_zones"].pop(ticker, None)
            msg += f"\n👀 {ticker} izleme listesinden çıkarıldı (artık pozisyonda)"
    else:
        if not pos:
            raise ValueError(f"{ticker} portföyde yok")
        if qty > pos["shares"] + EPS:
            raise ValueError(f"{ticker}: eldeki {pos['shares']} adetten fazlası satılamaz ({_num(qty)})")
        realized = total - qty * pos["cost_basis"]  # net tutar (komisyon düşülmüş) - maliyet
        remaining = pos["shares"] - qty
        if remaining < EPS:
            del portfolio["portfolio"][ticker]
            portfolio["position_levels"].pop(ticker, None)
            rest = "Pozisyon kapandı."
        else:
            portfolio["portfolio"][ticker] = {"shares": _num(remaining), "cost_basis": pos["cost_basis"]}
            rest = f"Kalan: {_num(remaining)} adet (maliyet ${pos['cost_basis']:,.4f})"
        tx.update(shares=_num(qty), price=px, cost_basis_after=pos["cost_basis"],
                  realized_pnl=round(realized, 2))
        if fee:
            tx["commission"] = fee
        msg = f"🔴 SATIŞ {ticker}: {_num(qty)} adet @ ${px:,.2f}{fee_txt}\nGerçekleşen K/Z: {realized:+,.2f}$ · {rest}"

    if update_cash:
        portfolio["cash"] = round(portfolio["cash"] + (-total if action == "buy" else total), 2)
        msg += f"\nNakit: ${portfolio['cash']:,.2f}"
    else:
        msg += "\n(Nakit güncellenmedi)"
    tx["cash_after"] = portfolio["cash"]
    history["transactions"].append(tx)
    return msg


def _env_or(args, name, env):
    v = getattr(args, name)
    return v if v not in (None, "") else os.environ.get(env, "")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--action")
    ap.add_argument("--ticker")
    ap.add_argument("--shares")
    ap.add_argument("--price")
    ap.add_argument("--amount")
    ap.add_argument("--commission")
    ap.add_argument("--note")
    ap.add_argument("--date")
    ap.add_argument("--no-cash-update", action="store_true")
    args = ap.parse_args(argv)

    action = _env_or(args, "action", "IN_ACTION")
    update_cash = not (args.no_cash_update or os.environ.get("IN_UPDATE_CASH", "true").lower() == "false")
    portfolio = common.load_portfolio()
    history = common.load_history()
    try:
        msg = apply(portfolio, history, action,
                    ticker=_env_or(args, "ticker", "IN_TICKER"),
                    shares=_env_or(args, "shares", "IN_SHARES") or None,
                    price=_env_or(args, "price", "IN_PRICE") or None,
                    amount=_env_or(args, "amount", "IN_AMOUNT") or None,
                    note=_env_or(args, "note", "IN_NOTE"),
                    date=_env_or(args, "date", "IN_DATE") or None,
                    update_cash=update_cash,
                    commission=_env_or(args, "commission", "IN_COMMISSION") or None)
    except ValueError as ex:
        print(f"[ERROR] {ex}")
        common.send_telegram(f"⚠️ Pozisyon güncellemesi reddedildi: {common.e(ex)}")
        return 1

    common.save_json("portfolio.json", portfolio)
    common.save_json("history.json", history)
    common.sync_public()
    print(msg)
    common.send_telegram("<b>✅ Portföy güncellendi</b>\n" + common.e(msg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
