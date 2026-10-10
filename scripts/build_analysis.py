#!/usr/bin/env python3
"""BIST analysis.json üretici (Claude'un TradingView bağlayıcısından aldığı anlık veriyle).

Girdiler:
  bist/tv_snapshot.json  TradingView günlük teknik/temel/haber anlık görüntüsü (Claude 'güncelle bizi' ile yeniler)
  bist/research.json     Doğrulanmış sermaye artırımı notları
  --trend <dosya>        trend-bist.json (4S Trend / 15dk Trend / 15dk Tamam yada Devam / Elliott)
Çıktı: docs/bist/data/analysis.json (+ quotes.json'u TradingView kapanışından tohumlar, yoksa)
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASOF = ""
AY = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def n(x, d=2):
    """Türkçe sayı biçimi: 1.234,56"""
    s = f"{abs(x):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if x < 0 else "") + s


def pn(x, d=2):
    return ("+" if x >= 0 else "−") + "%" + n(abs(x), d)


def tl(x, d=2):
    return "₺" + n(x, d)


def big(x):
    if x is None:
        return None
    a, sg = abs(x), "−" if x < 0 else ""
    for lim, suf in ((1e12, " tr"), (1e9, " mlr"), (1e6, " mn")):
        if a >= lim:
            return f"{sg}₺{n(a / lim, 2 if a / lim < 10 else 1)}{suf}"
    return f"{sg}₺{n(a, 0)}"


def tr_date(ts, with_year=True):
    d = datetime.fromtimestamp(ts, timezone.utc)
    return f"{d.day} {AY[d.month - 1]}" + (f" {d.year}" if with_year else "")


def ell_detail(w, price):
    """docs/tg.html ellDetail'in Python karşılığı."""
    if not w or not w.get("wave") or w.get("start_price") is None:
        return ""
    s, l, dn, wv = float(w["start_price"]), float(w["last_price"]), w.get("bias") == "down", int(w["wave"])
    mv = abs(l - s)
    fb = lambda f: l + f * mv if dn else l - f * mv  # noqa: E731
    yn, ters = ("aşağı", "yukarı") if dn else ("yukarı", "aşağı")
    band = f"{tl(fb(0.382))} – {tl(fb(0.618))}"
    out = [f"{'Düşüş' if dn else 'Yükseliş'} sayımı {tl(s)} seviyesinden başlıyor; son uç {tl(l)} (%{n(mv / s * 100, 1)} {yn})."]
    if wv == 1:
        out.append(f"Bu ilk itki dalgası sayılıyor, hareket erken evrede olabilir. Sayım doğruysa önce Dalga 2 ile {ters} yönlü bir tepki ({band} bandı, hareketin %38–62'si) gelir, ardından genelde daha sert Dalga 3 başlar.")
    elif wv == 3:
        out.append(f"Dalga 3 genelde sayımın en sert ve en uzun dalgasıdır; bu yüzden {yn} yönün sürmesi daha olağan senaryodur. Geçici tepki (Dalga 4) bölgesi {band}.")
    elif wv == 5:
        out.append(f"Dalga 5 son itkidir: yorgunluk ve {ters} yönlü düzeltme riski yüksek. Düzeltme bölgesi {band}. Bu, dibin/tepenin geldiği anlamına gelmez.")
    else:
        out.append(f"Şu an düzeltme dalgası (Dalga {wv}) sürüyor; bugüne kadarki ucu {tl(l)}. Düzeltme bitince ana yön ({yn}) devam eder. Dalga 1'in ucu bu veride tutulmadığı için tepki hedefi hesaplanmıyor.")
    if price and wv in (1, 3, 5) and ((price < l) if dn else (price > l)):
        out.append(f"Fiyat ({tl(price)}) son ucu aştı: dalga uzuyor, yukarıdaki bölgeler {yn} kayar.")
    out.append(f"Sayım {tl(s)} {'üstünde' if dn else 'altında'} kapanışta geçersiz olur (dalga 2, dalga 1 başlangıcını aşamaz). Kural tabanlı, 4S mumlarda (eşik %{n(float(w.get('thr_pct', 0)), 1)}); kesin değildir.")
    return " ".join(out)


def rating(x):
    if x is None:
        return None
    return "Güçlü Al" if x >= 0.5 else "Al" if x >= 0.1 else "Nötr" if x > -0.1 else "Sat" if x > -0.5 else "Güçlü Sat"


def dirw(d):
    return {"up": "yukarı", "down": "aşağı"}.get(d, "yatay")


def momentum(t, tv, tr):
    close, chg = tv["close"], tv.get("change") or 0
    head = f"{ASOF} kapanışı {tl(close)} ({pn(chg)})."
    if not tr or tr.get("state") == "n/a":
        status = "Karışık"
        body = " Trend verisi bu hisse için alınamadı (4S Trend / 15dk Trend / 15dk Tamam yada Devam hesaplanamadı)."
    else:
        h, m, st, el = tr.get("h4") or {}, tr.get("m15") or {}, tr.get("st15") or {}, tr.get("elliott") or {}
        ups = [h.get("dir") == "up", m.get("dir") == "up", st.get("dir") == "up"]
        status = "Güçlü" if all(ups) else "Zayıf" if not any(ups) else "Karışık"
        body = (f" 4S Trend {dirw(h.get('dir'))}, 15dk Trend {dirw(m.get('dir'))}, 15dk Tamam yada Devam: "
                f"{'Devam' if st.get('dir') == 'up' else 'Tamam'}; Elliott {el.get('label', '–')}.")
    rsi = tv.get("RSI")
    if rsi is not None:
        body += f" Günlük RSI {n(rsi, 1)}" + (" (aşırı alım bölgesi)" if rsi >= 70 else " (aşırı satım bölgesi)" if rsi <= 30 else "") + "."
    ne = tv.get("earnings_release_next_date")
    if ne:
        body += f" Sonraki bilanço {tr_date(ne)}."
    return {"status": status, "text": head + body}


def technical(t, tv, tr):
    out, close = [], tv["close"]
    out.append(f"{ASOF} kapanışı {tl(close)} ({pn(tv.get('change') or 0)})" + (f"; trend verisi son fiyatı {tl(tr['price'])}" if tr and tr.get("price") else ""))
    if tr and tr.get("state") != "n/a":
        h, m, st, el = tr.get("h4") or {}, tr.get("m15") or {}, tr.get("st15") or {}, tr.get("elliott") or {}
        if h:
            out.append(f"4S Trend {dirw(h.get('dir'))}: kısa ortalama {n(h['ema8'])} {'>' if h['ema8'] > h['ema20'] else '<'} uzun ortalama {n(h['ema20'])}"
                       + (f"; son kesişim {h['cross_bars_ago']} mum önce" if h.get("cross_bars_ago") is not None else "")
                       + ". Kısa ortalama uzunun üstündeyse 4 saatlik görünüm yukarı, altındaysa aşağıdır")
        if m:
            out.append(f"15dk Trend {dirw(m.get('dir'))}: kısa {n(m['ema34'])} {'>' if m['ema34'] > m['ema89'] else '<'} uzun {n(m['ema89'])}"
                       + (f" ({m['cross_bars_ago']} mum önce kesişti)" if m.get("cross_bars_ago") is not None else ""))
        if st:
            out.append(f"15dk Tamam yada Devam: {'Devam (yukarı)' if st.get('dir') == 'up' else 'Tamam (aşağı)'}, çizgi {tl(st['line'])} (fiyata %{n(st['dist_pct'], 1)} uzak; {st['bars_since_flip']} mumdur bu yönde). "
                       "Fiyat çizginin ters tarafına geçince yön değişir: 'Devam' iken çizginin altı 'Tamam', 'Tamam' iken üstü 'Devam' demektir; ani sinyal ve geçici stop gibi okunur")
        e = ell_detail(el, tr.get("price") or close)
        if e:
            out.append(f"Elliott (4S, muhtemel sayım, {el.get('label', '')}): {e}")
    rsi = tv.get("RSI")
    if rsi is not None:
        z = "aşırı alım" if rsi >= 70 else "aşırı satım" if rsi <= 30 else "nötr" if 45 <= rsi <= 55 else "alıcı baskısı" if rsi > 55 else "satıcı baskısı"
        out.append(f"Günlük RSI {n(rsi, 1)}: {z}. RSI, aşırı alım/satım ve ivmeyi ölçer; 50 üstü alıcı, altı satıcı baskısı demektir")
    mc, sg = tv.get("MACD.macd"), tv.get("MACD.signal")
    if mc is not None and sg is not None:
        out.append(f"Günlük MACD {n(mc)} sinyalin ({n(sg)}) {'üstünde (boğa)' if mc >= sg else 'altında (ayı)'}; MACD iki hareketli ortalamanın farkıdır, sinyal çizgisini yukarı kesmesi ivme dönüşüdür")
    adx = tv.get("ADX")
    if adx is not None:
        g = "trend gücü zayıf (<20, belirgin trend yok)" if adx < 20 else "trend gücü orta" if adx < 25 else "güçlü trend" if adx < 40 else "çok güçlü trend"
        extra = "".join([f"; Stochastic %K {n(tv['Stoch.K'], 1)}" if tv.get("Stoch.K") is not None else "", f"; CCI {n(tv['CCI20'], 0)}" if tv.get("CCI20") is not None else ""])
        out.append(f"ADX {n(adx, 1)}: {g}; ADX yönü değil gücü gösterir{extra}")
    ma = []
    for k, lab in (("EMA20", "20 günlük ortalamanın"), ("SMA50", "SMA50'nin"), ("SMA200", "SMA200'ün")):
        v = tv.get(k)
        if v:
            ma.append(f"{lab} ({n(v)}) {'üstünde' if close >= v else 'altında'}")
    if ma:
        r = rating(tv.get("Recommend.All"))
        out.append("Fiyat günlük " + ", ".join(ma) + (f". TradingView günlük özeti: {r}" if r else ""))
    return out


def fundamental(t, tv, no_div=()):
    typ = tv.get("type")
    if typ != "stock" or t in no_div:
        return {"metrics": [["Tür", "Fon" if typ == "fund" else "Sertifika (altın)" if t == "ALTIN" else "Sertifika / fon"], ["Kapanış", tl(tv["close"])]],
                "fair_value": "Şirket değil (fon/sertifika): bilanço, analist hedefi ve sermaye artırımı verisi yok."}
    m = []
    add = lambda k, v: m.append([k, v]) if v else None  # noqa: E731
    add("Piyasa değeri", big(tv.get("market_cap_basic")))
    if tv.get("total_revenue_ttm"):
        g = tv.get("total_revenue_yoy_growth_ttm")
        add("Gelir (TTM)", big(tv["total_revenue_ttm"]) + (f" ({pn(g, 0)} y/y)" if g is not None else ""))
    add("Net sonuç (TTM)", big(tv.get("net_income_ttm")) if tv.get("net_income_ttm") is not None else None)
    add("Serbest nakit akışı", big(tv.get("free_cash_flow_ttm")) if tv.get("free_cash_flow_ttm") is not None else None)
    if tv.get("net_margin") is not None:
        add("Net marj", "%" + n(tv["net_margin"], 1))
    if tv.get("price_earnings_ttm"):
        add("F/K (TTM)", n(tv["price_earnings_ttm"], 1))
    if tv.get("price_book_ratio"):
        add("PD/DD", n(tv["price_book_ratio"], 2))
    if tv.get("debt_to_equity") is not None:
        add("Borç/Özsermaye", n(tv["debt_to_equity"], 2))
    if tv.get("dividends_yield"):
        add("Temettü verimi", "%" + n(tv["dividends_yield"], 1))
    ne = tv.get("earnings_release_next_date")
    add("Sonraki bilanço", f"{tr_date(ne)} (TradingView takvimi)" if ne else "Takvimde tarih yok")
    tg, close = tv.get("price_target_1y"), tv["close"]
    if tg and abs(tg / close - 1) < 1.5:
        fv = f"Analist ortalama hedefi {tl(tg)} (kapanışa göre {pn((tg / close - 1) * 100, 0)}; TradingView verisi). Adil değer = analist hedefi, kendi tahminim değil."
    elif tg:
        fv = f"Analist hedefi {tl(tg)} ({pn((tg / close - 1) * 100, 0)}) ama fiyatla tutarsız görünüyor (veri/birim hatası olabilir), güvenilir sayılmadı."
    else:
        fv = "Analist hedef fiyatı verisi yok (TradingView'de bu hisse için kapsam görünmüyor); adil değer hesaplanmadı."
    return {"metrics": m, "fair_value": fv}


NOTE = ("Fiyatlar 9 Ekim 2026 (Cuma) seans kapanışı, TradingView; trend verisi (4S Trend / 15dk Trend / 15dk Tamam yada Devam / Elliott) "
        "Yahoo Finance 15dk mumlarından (gecikmeli). Günlük göstergeler TradingView 1D. Adil değer = analist ortalama hedefi, kendi tahminim değil. "
        "Kısa sözlük: 4S Trend = 4 saatlik mumlarda kısa/uzun hareketli ortalama ilişkisi (yukarı = kısa üstte); "
        "15dk Trend = 15 dakikalık mumlarda aynı mantık, daha kısa vade; "
        "15dk Tamam yada Devam = 15 dakikalık ATR tabanlı trend çizgisi (yukarı = Devam, aşağı = Tamam); "
        "RSI = ivme (30 altı aşırı satım, 70 üstü aşırı alım); MACD = ivme/trend dönüşü; ADX = trend gücü; "
        "Elliott = fiyatın 5 itki + 3 düzeltme dalgası yaptığı varsayımı, kural tabanlı ve kesin değildir. "
        "Sermaye artırımı notları otomatik haber/KAP taramasıdır: yatırım kararından önce KAP'tan doğrulayın (bedelli sermaye artırımı kontrolü zorunlu). "
        "BIST: yalnızca spot (T+2), günlük ±%10 fiyat sınırı. Yazılı notlar sabittir; trend satırları canlı güncellenir. Yatırım tavsiyesi değildir.")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--trend", default=os.path.join(ROOT, "bist", "trend_seed.json"))
    ap.add_argument("--snapshot", default=os.path.join(ROOT, "bist", "tv_snapshot.json"))
    ap.add_argument("--research", default=os.path.join(ROOT, "bist", "research.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "bist", "data", "analysis.json"))
    a = ap.parse_args(argv)
    snap = json.load(open(a.snapshot, encoding="utf-8"))
    rs = json.load(open(a.research, encoding="utf-8"))
    global ASOF
    y, mo, dd = (int(x) for x in snap["asof"].split("-"))
    ASOF = f"{dd} {AY[mo - 1]}"
    trd = (json.load(open(a.trend, encoding="utf-8")) or {}).get("tickers", {})
    out = {}
    for t, tv in snap["symbols"].items():
        item = {"name": tv.get("description") or t,
                "momentum": momentum(t, tv, trd.get(t)),
                "technical": technical(t, tv, trd.get(t)),
                "fundamental": fundamental(t, tv, rs.get("no_dilution", []))}
        dl = rs["dilution"].get(t)
        if dl:
            item["dilution"] = dl
        item["news"] = [{"date": tr_date(x["ts"]), "title": x["title"], "src": x["src"], "url": x["url"]}
                        for x in snap["news"].get(t, [])]
        out[t] = item
    data = {"updated": snap["asof"], "note": NOTE, "tickers": out}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    # quotes.json tohumu (yoksa): izleme listesi ilk açılışta fiyat göstersin
    qp = os.path.join(os.path.dirname(a.out), "quotes.json")
    if not os.path.exists(qp):
        qs = {}
        for t, tv in snap["symbols"].items():
            c, d = tv["close"], tv.get("change_abs") or 0
            qs[t] = {"c": c, "d": round(d, 4), "dp": round(tv.get("change") or 0, 4), "h": tv.get("high") or c,
                     "l": tv.get("low") or c, "o": tv.get("open") or c, "pc": round(c - d, 4), "t": 0}
        json.dump({"updated": "2026-10-09T15:00:00+00:00", "market_open": False, "quotes": qs},
                  open(qp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{len(out)} hisse yazıldı -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
