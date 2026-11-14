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
    return ";".join(parca), tarih


SABLON = r'''//@version=6
indicator("Claude Kesişim Bölgeleri", "Claude Bölgeler", overlay = true, max_boxes_count = 200, max_lines_count = 60, max_labels_count = 60)
// Haftalık analizde Claude tarafından otomatik güncellenir; elle düzenleme bir sonraki güncellemede silinir.
// Satır biçimi: SEMBOL|alt|üst|tür  (tür: K = KRİTİK, O = ÖNEMLİ, I = izleme/düşürülmüş, SIG = sigorta, STP = çekirdek stop)
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
            if tur == "SIG" or tur == "STP"
                renk = tur == "SIG" ? color.new(#26a69a, 0) : color.new(#e53935, 0)
                l = line.new(bar_index - geri, alt, bar_index + uzat, alt, color = renk, style = line.style_dashed, width = 2)
                array.push(cizgiler, l)
                if etiket
                    array.push(etiketler, label.new(bar_index + uzat, alt, (tur == "SIG" ? "Sigorta " : "Ç.stop ") + fmt(alt), style = label.style_label_left, color = color.new(color.white, 100), textcolor = renk, size = size.small))
            else
                dolgu = tur == "K" ? color.new(#ff9800, 85) : tur == "O" ? color.new(#fbc02d, 88) : color.new(#9e9e9e, 90)
                yazi = tur == "K" ? #e65100 : tur == "O" ? #b28704 : #616161
                kenar = (alt + ust) / 2 > close ? #ef5350 : #26a69a
                stil = tur == "I" ? line.style_dotted : line.style_dashed
                ad = tur == "K" ? "KRİTİK" : tur == "O" ? "ÖNEMLİ" : "İzleme"
                b = box.new(bar_index - geri, ust, bar_index + uzat, alt, border_color = kenar, border_style = stil, bgcolor = dolgu, text = etiket ? ad + " " + fmt(alt) + "–" + fmt(ust) : "", text_color = yazi, text_size = size.small, text_halign = text.align_right, text_valign = text.align_center)
                array.push(kutular, b)
    if etiket
        array.push(etiketler, label.new(bar_index + uzat, high, "Analiz: " + ANALIZ, style = label.style_label_left, color = color.new(color.white, 100), textcolor = color.gray, size = size.tiny))
'''


if __name__ == "__main__":
    v, t = veri(sys.argv[1], sys.argv[2])
    print(SABLON.replace("__VERI__", v).replace("__TARIH__", t))
