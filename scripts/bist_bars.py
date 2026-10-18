"""BIST günlük mumları (Teknik sekmesindeki grafik için): yfinance (.IS), olmazsa TradingView yedeği -> bars-bist.json.

Biçim ABD'deki bars.json ile aynıdır: {"updated", "source", "bars": {SEMBOL: [[YYYY-MM-DD, o, h, l, c], ...]}}.
Veri alınamayan hisse önceki dosyadaki mumlarıyla kalır (--prev). Kaynağı çalışmazsa çıkış kodu 0 döner (grafik
yalnızca eski veriyle kalır; iş akışı bozulmaz).
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from technicals import scrub  # noqa: E402  (log'a anahtar sızmasın)


def parse_tickers(text):
    return [t for t in re.split(r"[\s,;]+", text.upper()) if t]


def fetch(sym, days):
    import yfinance as yf
    df = yf.Ticker(sym + ".IS").history(period=f"{days}d", interval="1d", auto_adjust=False)
    if df is None or df.empty:
        return None
    out = []
    for ts, r in df.iterrows():
        o, h, l, c = (float(r[k]) for k in ("Open", "High", "Low", "Close"))
        if c > 0 and h >= l > 0:
            out.append([ts.strftime("%Y-%m-%d"), round(o, 4), round(h, 4), round(l, 4), round(c, 4)])
    return out or None


def tv_fetch(sym, days, exchange="BIST", timeout=25):
    """Yedek: TradingView websocket'inden günlük mum (Yahoo'nun vermediği ALTIN, GMSTR gibi semboller için).
    Gayriresmi, anahtarsız; çalışmazsa istisna fırlatır (çağıran yakalar)."""
    import websocket  # websocket-client
    ws = websocket.create_connection("wss://data.tradingview.com/socket.io/websocket",
                                     origin="https://www.tradingview.com", timeout=timeout)
    try:
        def send(m, p):
            body = json.dumps({"m": m, "p": p}, separators=(",", ":"))
            ws.send(f"~m~{len(body)}~m~{body}")
        send("set_auth_token", ["unauthorized_user_token"])
        send("chart_create_session", ["cs", ""])
        send("resolve_symbol", ["cs", "sds_sym_1", "=" + json.dumps({"symbol": f"{exchange}:{sym}", "adjustment": "splits"})])
        send("create_series", ["cs", "s1", "s1", "sds_sym_1", "1D", min(days, 300), ""])
        raw, rows = "", []
        for _ in range(60):
            raw = ws.recv()
            if raw.startswith("~h~") or re.fullmatch(r"~m~\d+~m~~h~\d+", raw):
                ws.send(raw)  # kalp atışını aynen geri yolla
                continue
            rows = parse_tv_series(raw) or rows
            if "series_completed" in raw or "symbol_error" in raw or "critical_error" in raw:
                break
        if not rows:
            raise RuntimeError("TradingView mum vermedi")
        return rows
    finally:
        try:
            ws.close()
        except Exception:
            pass


def parse_tv_series(raw):
    """Websocket çerçevelerinden timescale_update mumlarını çıkar -> [[tarih,o,h,l,c,v?]]."""
    out = []
    for body in re.split(r"~m~\d+~m~", raw):
        if not body.startswith("{"):
            continue
        try:
            msg = json.loads(body)
        except ValueError:
            continue
        if msg.get("m") != "timescale_update":
            continue
        for b in (((msg.get("p") or [None, {}])[1] or {}).get("s1") or {}).get("s") or []:
            t, o, h, l, c = b["v"][:5]
            if c and c > 0 and h >= l > 0:
                day = datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")
                out.append([day, round(o, 4), round(h, 4), round(l, 4), round(c, 4)])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="trend/bist_tickers.txt")
    ap.add_argument("--prev", default="")
    ap.add_argument("--out", default="bars-bist.json")
    ap.add_argument("--days", type=int, default=270)
    a = ap.parse_args(argv)

    with open(a.file, encoding="utf-8") as f:
        tickers = list(dict.fromkeys(parse_tickers(re.sub(r"#.*", "", f.read()))))
    prev = {}
    if a.prev and os.path.exists(a.prev):
        try:
            prev = (json.load(open(a.prev, encoding="utf-8")) or {}).get("bars") or {}
        except (OSError, ValueError):
            prev = {}

    bars, ok = {}, 0
    for t in tickers:
        try:
            rows = fetch(t, a.days)
        except Exception as ex:  # ağ/kütüphane hatası tek hisseyi düşürür
            print(scrub(f"{t}: {type(ex).__name__}: {str(ex)[:60]}"))
            rows = None
        if not rows:  # Yahoo vermediyse TradingView yedeği
            try:
                rows = tv_fetch(t, a.days)
                print(f"{t}: TradingView yedeğinden {len(rows)} mum")
            except Exception as ex:
                print(scrub(f"{t}: TV yedeği: {type(ex).__name__}: {str(ex)[:60]}"))
                rows = None
        if rows:
            bars[t] = rows[-200:]
            ok += 1
        elif t in prev:
            bars[t] = prev[t]
    print(f"BIST günlük mum: {ok}/{len(tickers)} hisse güncellendi, toplam {len(bars)}")
    if not bars:
        return 0
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "source": "Yahoo Finance günlük (yfinance)", "bars": bars}, f, ensure_ascii=False, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
