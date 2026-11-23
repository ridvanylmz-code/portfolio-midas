"""Kesişim bölgelerini çizen Pine v6 göstergesinin kodunu üretir (Chrome gerektirmez).

Kullanım: python3 pine.py bolgeler.csv cizgiler.csv > bolgeler.pine
  bolgeler.csv  analiz,ref,hisse,alt,ust,guc[,rol]   (her hissenin en son analizi kullanılır)
  cizgiler.csv  hisse,fiyat,tur                      (tur: SIG = sigorta, STP = çekirdek stop)
Üretilen kod TradingView'e MCP ile yazılır: ilk kez create-pine-script, sonra update-pine-script.
Gösterge grafiğe bir kez eklenir; her haftalık analizde yalnız kod (veri bloğu) güncellenir.
"""
import sys
import pandas as pd

G = {"KRİTİK": "K", "ÖNEMLİ": "O", "İzleme": "I"}


def veri(bolgeler, cizgiler):
    b = pd.read_csv(bolgeler)
    son = b.groupby("hisse").analiz.transform("max")
    b = b[b.analiz == son]
    parca = [f"{r.hisse}|{r.alt:g}|{r.ust:g}|{G.get(r.guc, 'I')}" for r in b.itertuples()]
    c = pd.read_csv(cizgiler)
    parca += [f"{r.hisse}|{r.fiyat:g}|{r.fiyat:g}|{r.tur}" for r in c.itertuples()]
    tarih = ", ".join(f"{h} {a[8:10]}.{a[5:7]}" for h, a in b.groupby("hisse").analiz.max().items())
    # Uzun vadeli analizler (haftalık akıştan bağımsız; ör. SGO): veri/uzun_vade.csv  analiz,hisse,alt,ust,tur
    # tur: K/O/I bölge · AT al tetiği · BT B tetiği · US uzun vade stop · ZO/ZU zaman penceresi (alt/ust = başlangıç/bitiş YYYY-MM-DD)
    import os
    uv = os.path.join(os.path.dirname(os.path.abspath(bolgeler)), "uzun_vade.csv")
    if os.path.exists(uv):
        u = pd.read_csv(uv, dtype=str)
        u = u[u.analiz == u.groupby("hisse").analiz.transform("max")]
        for r in u.itertuples():
            if r.tur in ("ZO", "ZU"):
                a1 = int(pd.Timestamp(r.alt, tz="UTC").timestamp() * 1000)
                a2 = int(pd.Timestamp(r.ust, tz="UTC").timestamp() * 1000)
                parca.append(f"{r.hisse}|{a1}|{a2}|{r.tur}")
            else:
                parca.append(f"{r.hisse}|{float(r.alt):g}|{float(r.ust):g}|{r.tur}")
        ek = ", ".join(f"{h} {a[8:10]}.{a[5:7]} (uzun vade)" for h, a in u.groupby("hisse").analiz.max().items())
        tarih = ", ".join(x for x in (tarih, ek) if x)
    return ";".join(parca), tarih


SABLON = r'''//@version=6
indicator("Claude Kesişim Bölgeleri", "Claude Bölgeler", overlay = true, max_boxes_count = 200, max_lines_count = 60, max_labels_count = 60)
// Haftalık analizde Claude tarafından otomatik güncellenir; elle düzenleme bir sonraki güncellemede silinir.
// Satır biçimi: SEMBOL|alt|üst|tür  (tür: K = KRİTİK, O = ÖNEMLİ, I = izleme/düşürülmüş, SIG = sigorta, STP = çekirdek stop,
//   AT = al tetiği, BT = B tetiği, US = uzun vade stop (aylık kapanış), ZO/ZU = orta/uzun vade zaman penceresi: alt/üst = başlangıç/bitiş zamanı, ms)
VERI = "__VERI__"
ANALIZ = "__TARIH__"

uzat = input.int(25, "Bölgeleri sağa uzat (bar)", minval = 5)
geri = input.int(20, "Bölge başlangıcı (bar geri)", minval = 1)
etiket = input.bool(true, "Kısa etiketler")

var array<box> kutular = array.new<box>()
var array<line> cizgiler = array.new<line>()
var array<label> etiketler = array.new<label>()

fmt(float v) => str.tostring(v, v < 10 ? "#.###" : "#.##")

if barstate.islast
    for k in kutular
        box.delete(k)
    array.clear(kutular)
    for c in cizgiler
        line.delete(c)
    array.clear(cizgiler)
    for e in etiketler
        label.delete(e)
    array.clear(etiketler)
    sat = str.split(VERI, ";")
    for s in sat
        p = str.split(s, "|")
        if array.size(p) == 4 and array.get(p, 0) == syminfo.ticker
            alt = str.tonumber(array.get(p, 1))
            ust = str.tonumber(array.get(p, 2))
            tur = array.get(p, 3)
            if tur == "ZO" or tur == "ZU"
                t1 = int(alt)
                t2 = int(ust)
                zr = color.new(#5c6bc0, 0)
                // Pine en fazla ~500 bar ileriye çizer; uzak pencere küçük zaman diliminde atlanır (haftalıkta görünür)
                sinir = time + 450 * timeframe.in_seconds() * 1000
                if t1 <= sinir
                    array.push(cizgiler, line.new(t1, close, t1, close * 1.01, xloc = xloc.bar_time, extend = extend.both, color = zr, style = line.style_dashed, width = 1))
                if t2 <= sinir
                    array.push(cizgiler, line.new(t2, close, t2, close * 1.01, xloc = xloc.bar_time, extend = extend.both, color = zr, style = line.style_dashed, width = 1))
                if etiket and t1 <= sinir
                    array.push(etiketler, label.new(t1, high, (tur == "ZO" ? "Orta vade zaman " : "Uzun vade zaman ") + str.format_time(t1, "dd.MM.yy") + "–" + str.format_time(t2, "dd.MM.yy"), xloc = xloc.bar_time, style = label.style_label_left, color = color.new(color.white, 100), textcolor = zr, size = size.small))
            else if tur == "SIG" or tur == "STP" or tur == "AT" or tur == "BT" or tur == "US"
                renk = tur == "SIG" or tur == "AT" ? color.new(#26a69a, 0) : tur == "BT" ? color.new(#ff9800, 0) : color.new(#e53935, 0)
                ad = tur == "SIG" ? "Sigorta " : tur == "STP" ? "Ç.stop " : tur == "AT" ? "Al tetiği (ay kap.) " : tur == "BT" ? "B tetiği (ay kap.) " : "Uzun stop (ay kap.) "
                l = line.new(bar_index - geri, alt, bar_index + uzat, alt, color = renk, style = line.style_dashed, width = 2)
                array.push(cizgiler, l)
                if etiket
                    array.push(etiketler, label.new(bar_index + uzat, alt, ad + fmt(alt), style = label.style_label_left, color = color.new(color.white, 100), textcolor = renk, size = size.tiny))
            else
                dolgu = tur == "K" ? color.new(#ff9800, 85) : tur == "O" ? color.new(#fbc02d, 88) : color.new(#9e9e9e, 90)
                yazi = tur == "K" ? #e65100 : tur == "O" ? #b28704 : #616161
                kenar = (alt + ust) / 2 > close ? #ef5350 : #26a69a
                stil = tur == "I" ? line.style_dotted : line.style_dashed
                ad = tur == "K" ? "KRİTİK" : tur == "O" ? "ÖNEMLİ" : "İzleme"
                b = box.new(bar_index - geri, ust, bar_index + uzat, alt, border_color = kenar, border_style = stil, bgcolor = dolgu, text = etiket ? ad + " " + fmt(alt) + "–" + fmt(ust) : "", text_color = yazi, text_size = size.small, text_halign = text.align_right, text_valign = text.align_center)
                array.push(kutular, b)
    if etiket
        array.push(etiketler, label.new(bar_index + uzat, high, "Analiz: " + ANALIZ, style = label.style_label_left, color = color.new(color.white, 100), textcolor = color.gray, size = size.small))
'''


if __name__ == "__main__":
    v, t = veri(sys.argv[1], sys.argv[2])
    print(SABLON.replace("__VERI__", v).replace("__TARIH__", t))
