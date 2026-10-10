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

ET = ZoneInfo("Europe/Istanbul" if common.MARKET == "bist" else "America/New_York")
C = common.CUR
ACTIONS = ("buy", "sell", "deposit", "withdraw", "watch_add", "watch_remove", "undo",
           "zone_below", "zone_above", "zone_clear")
PRICE_TOL = 0.15  # girilen fiyat son kapanıştan bu orandan fazla saparsa onaysız kabul edilmez
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


def ref_price(ticker, quotes=None):
    """Son bilinen fiyat (docs/data/quotes.json, herkese açık dosya). Yoksa None."""
    q = (quotes if quotes is not None else
         (common.load_json(f"{common.DATA_DIR}/quotes.json", {}) or {}).get("quotes", {})).get(ticker) or {}
    try:
        c = float(q.get("c"))
        return c if c > 0 else None
    except (TypeError, ValueError):
        return None


def check_price(ticker, px, confirm, quotes=None):
    """Yazım hatası koruması (ör. '82 adet @16' yerine '16 adet @82'). Dönüş: mesaja eklenecek not."""
    ref = ref_price(ticker, quotes)
    if ref is None:
        return "\nℹ️ Referans fiyat yok; fiyat kontrolü yapılamadı"
    dev = px / ref - 1
    if abs(dev) > PRICE_TOL and not confirm:
        raise ValueError(
            f"{ticker} fiyatı {C}{px:,.2f}, son fiyattan ({C}{ref:,.2f}) %{dev * 100:+.1f} sapıyor. "
            "Adet ve fiyat yer değiştirmiş olabilir. Doğruysa 'confirm' kutusunu işaretleyip tekrar çalıştır.")
    return f"\n⚠️ Fiyat son fiyattan %{dev * 100:+.1f} sapıyor (onaylandı)" if abs(dev) > PRICE_TOL else ""


def undo_last(portfolio, history, now):
    """Son (geri alınmamış) işlemi geri alır. Yalnızca 'before' kaydı olan işlemler geri alınabilir."""
    txs = history["transactions"]
    for tx in reversed(txs):
        if tx.get("action") == "undo" or tx.get("undone"):
            continue
        b = tx.get("before")
        if not b:
            raise ValueError("Son işlem bu sürümden önce kaydedilmiş; otomatik geri alınamaz (elle düzeltilmeli)")
        t = tx.get("ticker")
        if "position" in b:
            if b["position"] is None:
                portfolio["portfolio"].pop(t, None)
            else:
                portfolio["portfolio"][t] = b["position"]
        if "cash" in b:
            portfolio["cash"] = b["cash"]
        if "watchlist" in b:
            portfolio["watchlist"] = b["watchlist"]
        if "buy_zones" in b:
            portfolio["buy_zones"] = b["buy_zones"]
        tx["undone"] = True
        desc = " ".join(str(x) for x in (tx["action"], t, tx.get("shares", tx.get("amount"))) if x not in (None, ""))
        if tx.get("price"):
            desc += f" @ {C}{tx['price']:,.2f}"
        txs.append({"date": now.astimezone(ET).date().isoformat(), "time": now.isoformat(timespec="seconds"),
                    "action": "undo", "note": f"Geri alındı: {desc} ({tx['time']})", "ticker": t,
                    "undo_of": tx["time"], "cash_after": portfolio["cash"]})
        return f"↩️ Geri alındı: {desc}\nNakit: {C}{portfolio['cash']:,.2f}"
    raise ValueError("Geri alınacak işlem yok")


def apply(portfolio, history, action, ticker=None, shares=None, price=None, amount=None,
          note="", date=None, update_cash=True, now=None, commission=None, confirm=False, quotes=None):
    """portfolio/history'yi yerinde günceller, kullanıcıya mesaj döndürür. Hata -> ValueError."""
    now = now or datetime.now(timezone.utc)
    date = date or now.astimezone(ET).date().isoformat()
    if action not in ACTIONS:
        raise ValueError(f"Geçersiz işlem: {action}")
    if action == "undo":
        return undo_last(portfolio, history, now)

    tx = {"date": date, "time": now.isoformat(timespec="seconds"), "action": action, "note": note or ""}
    # Geri alma için işlem öncesi durum (yalnızca değişen alanlar)
    t0 = (ticker or "").strip().upper()
    tx["before"] = {"cash": portfolio["cash"], "watchlist": list(portfolio["watchlist"])}
    if action in ("buy", "sell"):
        p0 = portfolio["portfolio"].get(t0)
        tx["before"]["position"] = dict(p0) if p0 else None

    if action in ("buy", "sell", "watch_add", "watch_remove", "zone_below", "zone_above", "zone_clear"):
        ticker = (ticker or "").strip().upper()
        if not common.TICKER_RE.match(ticker):
            raise ValueError(f"Geçersiz ticker: {ticker!r}")
        tx["ticker"] = ticker

    if action in ("zone_below", "zone_above", "zone_clear"):
        z = common.zone_of(portfolio, ticker)
        tx["before"] = {"buy_zones": dict(portfolio["buy_zones"])}
        if action == "zone_clear":
            portfolio["buy_zones"].pop(ticker, None)
            msg = f"🧹 {ticker} alım bölgesi silindi"
        else:
            lvl = common.finite_positive(price, "price")
            check_price(ticker, lvl, True, quotes)  # sapma bilgisi için (alarm seviyesi uzak olabilir; reddetmez)
            z["below" if action == "zone_below" else "above"] = round(lvl, 4)
            portfolio["buy_zones"][ticker] = z
            kind = "geri çekilme (fiyat ≤)" if action == "zone_below" else "kırılım (fiyat ≥)"
            msg = f"🎯 {ticker} alım alarmı: {kind} {C}{lvl:,.2f}"
            if ticker not in portfolio["watchlist"] and ticker not in portfolio["portfolio"]:
                portfolio["watchlist"].append(ticker)
                msg += f"\n👀 {ticker} izleme listesine de eklendi"
                tx["before"]["watchlist"] = [x for x in portfolio["watchlist"] if x != ticker]
        tx["zone"] = portfolio["buy_zones"].get(ticker)
        history["transactions"].append(tx)
        return msg

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
            raise ValueError(f"Yetersiz nakit: {C}{portfolio['cash']:,.2f} < {C}{amt:,.2f}")
        portfolio["cash"] = round(portfolio["cash"] + (amt if action == "deposit" else -amt), 2)
        tx.update(amount=round(amt, 2), cash_after=portfolio["cash"])
        history["transactions"].append(tx)
        verb = "yatırıldı" if action == "deposit" else "çekildi"
        return f"💵 {C}{amt:,.2f} {verb}. Nakit: {C}{portfolio['cash']:,.2f}"

    # buy / sell
    qty = common.finite_positive(shares, "shares")
    px = common.finite_positive(price, "price")
    warn = check_price(ticker, px, confirm, quotes)
    pos = portfolio["portfolio"].get(ticker)
    fee = _commission(commission)
    gross = qty * px
    # Alış: nakit çıkışı = tutar + komisyon. Satış: nakit girişi = tutar - komisyon.
    total = gross + fee if action == "buy" else gross - fee
    fee_txt = f" (komisyon {C}{fee:,.2f})" if fee else ""

    if action == "buy":
        if update_cash and total > portfolio["cash"] + EPS:
            raise ValueError(
                f"Yetersiz nakit: {C}{portfolio['cash']:,.2f} < {C}{total:,.2f}. "
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
        msg = (f"🟢 ALIŞ {ticker}: {_num(qty)} adet @ {C}{px:,.2f}{fee_txt}\n"
               f"Yeni pozisyon: {_num(new_shares)} adet, ort. maliyet {C}{new_cost:,.4f}")
        lv = portfolio["position_levels"].get(ticker)
        if lv and not pos:  # kapatılmış pozisyon yeniden açıldı: saklı seviyeler geri geçerli
            msg += f"\n🎯 Kayıtlı seviyeler geri yüklendi ({_lv_txt(lv)})"
            if lv.get("stop_loss") is not None and px <= float(lv["stop_loss"]):
                msg += "\n⚠️ Kayıtlı stop alış fiyatına eşit/üstünde: ilk alarmda hemen tetiklenir, seviyeyi güncelle"
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
            # Stop/hedef silinmez: yeniden alımda geçerli olur (alarmlar yalnız eldeki hisselere bakar).
            lv = portfolio["position_levels"].get(ticker)
            rest = "Pozisyon kapandı." + (f" Seviyeler saklandı ({_lv_txt(lv)}), yeniden alımda geçerli olur." if lv else "")
        else:
            portfolio["portfolio"][ticker] = {"shares": _num(remaining), "cost_basis": pos["cost_basis"]}
            rest = f"Kalan: {_num(remaining)} adet (maliyet {C}{pos['cost_basis']:,.4f})"
        tx.update(shares=_num(qty), price=px, cost_basis_after=pos["cost_basis"],
                  realized_pnl=round(realized, 2))
        if fee:
            tx["commission"] = fee
        msg = f"🔴 SATIŞ {ticker}: {_num(qty)} adet @ {C}{px:,.2f}{fee_txt}\nGerçekleşen K/Z: {realized:+,.2f}{C} · {rest}"

    if update_cash:
        portfolio["cash"] = round(portfolio["cash"] + (-total if action == "buy" else total), 2)
        msg += f"\nNakit: {C}{portfolio['cash']:,.2f}"
    else:
        msg += "\n(Nakit güncellenmedi)"
    tx["cash_after"] = portfolio["cash"]
    history["transactions"].append(tx)
    return msg + warn


def _lv_txt(lv):
    st, tg = lv.get("stop_loss"), lv.get("target")
    return ", ".join(x for x in (f"stop {C}{float(st):,.2f}" if st is not None else "",
                                 f"hedef {C}{float(tg):,.2f}" if tg is not None else "") if x) or "boş"


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
    ap.add_argument("--confirm", action="store_true", help="Fiyat sapma kontrolünü onayla")
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
                    commission=_env_or(args, "commission", "IN_COMMISSION") or None,
                    confirm=args.confirm or os.environ.get("IN_CONFIRM", "").lower() == "true")
    except ValueError as ex:
        print(f"[ERROR] {ex}")
        common.send_telegram(f"⚠️ Pozisyon güncellemesi reddedildi: {common.e(ex)}")
        return 1

    common.save_json(common.F_PORTFOLIO, portfolio)
    common.save_json(common.F_HISTORY, history)
    common.sync_public()
    print(msg)
    head = "<b>✅ BIST portföyü güncellendi</b>" if common.MARKET == "bist" else "<b>✅ Portföy güncellendi</b>"
    common.send_telegram(head + "\n" + common.e(msg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
