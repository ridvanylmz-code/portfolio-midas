# Haftalık analiz — oturum kartı (yöntem v2.4)

Her analizde okunacak **tek** belge budur. Tam kural metni (Proje `claude/haftalik-teknik-analiz-yontemi.md`, `claude/salinim_stratejisi.md`) yalnız aşağıdaki özetin cevaplamadığı bir kural sorusunda açılır. Kural dondurma: 08.01.2027'ye kadar kural değişmez.

## A. Akış (komutlar)

```bash
git clone https://github.com/ridvanylmz-code/portfolio-midas.git && cd portfolio-midas     # tek kurulum
```
1. **Veri (MCP, ≤5 paralel, rows + büyük count → dosyaya düşer):** ABD RKLB/SGML 1D 1600 + 1h 1500 · CRWV/WYFI 1h 3500 · SPY/UFO/SMH/LIT/WGMI 1D 1500. BIST 4 hisse 4h 5000 · XU100/XTAST/XKMYA/XUSIN/XBLSM 1D 1500. Sonra batch (close, change, high, low, ATR, pre/postmarket), earnings, gerekirse news (limit 8). → `python3 teknik/haftalik.py veri`
2. **Karne:** `python3 teknik/haftalik.py puan --pazar abd` (son analiz + birikimli → `teknik/veri/karne_abd.txt`)
3. **Pozisyon:** `python3 teknik/haftalik.py pozisyon --pazar abd --since <son analiz tarihi>` (gh ile iş akışı günlükleri → işlemler + son adet + nakit)
4. **Analiz:** önceki `teknik/cfg/<pazar>_*.py` kopyala, yalnız yeni pivotları Edit ile düzelt → `python3 teknik/haftalik.py analiz --pazar abd --cfg teknik/cfg/abd_<YYYYMMDD>.py --tarih <YYYY-MM-DD>` → kısa özet + `teknik/is/plan_<pazar>_<tarih>.json`
5. **Plan düzeltme (küçük Python düzenlemesi, dosya baştan yazılmaz):** `rejim` sonucu; hisse başına `gercek`, `gercek_kosul`, `bilanco`, `notlar`; emirlerde `adet`; istisnalar (S2 ertelemesi, S3 taşıma, fazla porsiyon); `onceki_sonuclar` (geçen haftanın B/A seviyeleri: `{"<tarih>-<HİSSE>": ["sonuç", "isabet"]}`).
6. **Yayınla:** `python3 teknik/haftalik.py yayinla --plan teknik/is/plan_<pazar>_<tarih>.json` → `git add teknik docs/teknik && git commit -m "teknik: <PAZAR> haftalık <tarih>" && git push`
7. **Dış sistemler:**

| İş | Nasıl |
|---|---|
| Pine | `teknik/is/bolgeler.pine` → `update-pine-script` (`USER;1a93bd48668a4240a5176742bd31f615`). Grafik eski sürümde kalırsa göstergeyi yeniden ekle |
| Alarmlar | `list-alerts` (dosyaya düşer) → `haftalik.py alarm-sil --liste <dosya> --pazar abd` → `delete-alert` → `teknik/is/alarmlar_<pazar>.json` ile `create-alert` (`resolution 120`, `auto_deactivate true`). BIST: Chrome, `currency-id TRY` |
| Artifact pano | Veri repodadır; artifact dış URL okuyamadığı için repodaki **aynı dosyalar** asset olarak yüklenir (`docs/teknik/data/salinim.json`, `teknik/veri/pano_seviyeler.json`, `pano_tahminler.json`) → `ArtifactData batch` ile `datasets/{salinim,seviyeler,tahminler}` `source.url` + `updated`. Projede JSON kopyası tutulmaz |
| Proje (`project_write local_path`) | `teknik/is/defter_<pazar>_<tarih>.md` → `claude/defter/<tarih>_<pazar>.md` (yeni dosya) · `teknik/is/tahmin_defteri.md` → `claude/tahmin_defteri.md` · `teknik/is/izleme_listesi.md` → `claude/izleme_listesi.md` (ikisi de betikle baştan üretilir, kısa) |

8. **Kullanıcıya:** karne 3–5 satır · seviye haritası (B önce) · salınım emirleri · yapılanlar · riskler · kalite kuralları tek satır.

**Yapılmaz:** Proje kodunu okuyup yeniden yazmak · büyük belgeleri bağlama okumak · defteri elle yeniden yazmak · Chrome ile çizim (yalnız eski Claude çizimi temizliği) · hisse başına 5'ten fazla alarm.

## B. Kural özeti (v2.4)

**Rejim (önce):** ABD risk-on = SPY > EMA89 > EMA233 ve VIX < 20 · risk-off = SPY < EMA89 < EMA233 veya VIX > 25 · diğer nötr. BIST: XU100 aynı EMA kuralı; risk-off'a ek olarak ADX > 40 ve −DI baskın.
**Hisse modu:** Trend = kapanış > EMA21 > 34 > 89, ADX > 25, +DI baskın · Savunma = tersi (−DI baskın) · diğer Bant. **Göreli güç:** güçlü = RS > EMA21(RS) ve 63g RS > 0; zayıf = ikisi de ters.
**Rejim düzeltmesi:** Savunma veya risk-off → destekler bir kademe düşer (KRİTİK→ÖNEMLİ→izleme). Trend + risk-on → dirençler düşer.
**Kesişim puanı (kodda):** Fib düzeltme 1 · uzatma 1,5 · kanal/yelpaze 1 (geometri tavanı 3) · EMA 1 · yapı (tepe/dip, Darvas, boşluk) 1 · hacim/ÇVWAP 1. ÖNEMLİ ≥ 3 ve ≥ 1 bağımsız aile; KRİTİK ≥ 4 ve ≥ 2 bağımsız. Kümeleme 0,3 ATR / %1,5, genişlik ≤ 0,4 ATR. Elliott, Gann, zaman penceresi **yok**. En yakın 5 bölge ana tablo.
**Senaryo yazımı:** olasılık yazılmaz. B (aşağı) önce: tetik = son 3 günün dibi altında kapanış; A: son 3 günün tepesi üstünde kapanış; hedefler bölgelerden. B hedef 1'e her zaman alarm.
**Puanlama (`puan.py`):** dokunma 7 bar; dokunduktan sonra 4 barda 1 ATR beklenen tepki ✓, 0,15 ATR öte kapanış ✗, ikisi yok ½; şans 500 tekrar. Elle ✓/½ yok.

**Salınım (porsiyon dili; tam yemek = 4 porsiyon: 2 çekirdek + 2 ticaret, kenarda 1 nakit):**
- **Sat:** en yakın direnç bölgesi alt = "1 porsiyon sat", ortası = "1 porsiyon daha". Teyit: bölgede 1s RSI 70 / CCI +100 aşağı; 4s çift tepe ikinci porsiyon. Trend modunda hedefte satılmaz, 4s Supertrend(10,2) iz süren stop.
- **Geri al:** limit yok; destek bölgesinde 1s RSI 30 üstüne → yarım, 4s çift dip / EMA34 yukarı / ST yeşil → kalan yarım. Savunmada yalnız KRİTİK destekte ve yarım; yoksa "Yok". Teyit gelmeden bölge altı − 0,15 ATR kapanış → bir alt desteğe taşınır.
- **Sigorta:** satılan bölge üstü + 0,15 ATR kapanış → satılanların yarısını geri al; 1,5 ATR içinde KRİTİK direnç varsa sigorta onun üstüne taşınır.
- **Çekirdek stop:** son KRİTİK destek alt − 0,15 ATR altında kapanış → 1 porsiyon çekirdek sat. **S2:** o gün RSI ≤ 25 veya z ≤ −2,5 ise bir kez ertelenir, ilk direnç altına limit; 5 işlem günü son sınır. Bilanço boşluğunda erteleme yok.
- **S1** satış yalnız dirençte · **S3** kaçırılan emir kovalanmaz, sonraki bölgeye taşınır · **S5** plan gerçek pozisyondan kurulur; plan dışı alım yalnız kaydedilir, fazla porsiyon için dirençte satış önerilir.
- **Filtreler:** R/Ö ≥ 2; bir sonraki dirence 1,5 ATR'den yakın kırılım tetiği yok; bilançodan 2 işlem günü önce 1 ticaret porsiyonu nakde; porsiyon riski ≤ portföyün %1'i; açılışın ilk 15–30 dk kovalama yok; 15 dk sinyal üretmez.
- **Kenardaki porsiyon:** bir alt KRİTİK destekte (ÖNEMLİ ise yarım); Savunma ve risk-off'ta kullanılmaz.

**Öncelik:** haftalık plan bağlayıcı; repo günlük analizi ve 15 dk Pine alarmı bilgi amaçlı (çelişki tek satırla yazılır).
**Tarz:** Türkçe, kısa, tablolar, porsiyon dili; "yatırım tavsiyesi değildir" satırı yok; riskler metnin içinde.
