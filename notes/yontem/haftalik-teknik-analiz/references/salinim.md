# Salınım planı (haftalik-teknik-analiz, bölüm 10)

## 10. Salınım planı (porsiyon dili)

Ayrıntılı kurallar: `claude/salinim_stratejisi.md`. Her analizin sonunda bu dosyayı oku ve aşağıdaki tabloyu üret.

**Dil (zorunlu, üç skill'de ortak):** Emirler porsiyonla yazılır: tam yemek = 4 porsiyon (planlanan pozisyon), 1 porsiyon = 1/4. Kalıplar: "1 porsiyon sat", "1 porsiyon daha sat", "sattığını geri al", "1 porsiyon çekirdek sat", "kenardaki porsiyonu al", "yarım porsiyon".

- **Pozisyon yapısı:** 2 porsiyon çekirdek (yalnız yapı bozulunca satılır), 2 porsiyon ticaret; kenarda ayrıca 1 porsiyon nakit.
- **Mod** (günlük kapanışa göre): Bant (ADX < 25 veya son dip korunuyor), Trend (kapanış > EMA20 > EMA50, ADX > 25, +DI baskın), Savunma (kapanış < EMA20 < EMA50, ADX > 25, −DI baskın).
- **Seviyeler kesişim bölgelerinden alınır:**
  - "1 porsiyon sat" = en yakın direnç bölgesinin alt sınırı; "1 porsiyon daha sat" = aynı bölgenin ortası. Trend modunda hedefte satılmaz, 4 saatlik Supertrend(10,2) iz süren stop olarak kullanılır (`salinim_stratejisi.md` bölüm 7); tabloya 4 saatlik ve günlük Supertrend yönü ve dönüş çizgisi eklenir. 15 dakikalık ve 1 saatlik grafikte iz süren stop kullanılmaz (testte kârlılık faktörü < 1).
  - "Sattığını geri al" = en yakın destek bölgesinin üst sınırı. Bant modunda 4 saatlik Supertrend kırmızıyken yarım porsiyon, yeşile dönünce tamamlanır. Savunma modunda yalnız KRİTİK destekte ve yarım porsiyon; altta KRİTİK destek yoksa "Yok" yazılır.
  - Sigorta = direnç bölgesinin üst sınırı + 0,15 ATR; bunun üstünde günlük kapanış olursa sattığın porsiyonlar ertesi gün geri alınır.
  - "1 porsiyon çekirdek sat" = son KRİTİK destek bölgesinin alt sınırı − 0,15 ATR altında günlük kapanış.
  - "Kenardaki porsiyonu al" = bir alt KRİTİK destek bölgesi (ÖNEMLİ bölgedeyse yarım porsiyon; Savunma modunda kullanılmaz).
- **Filtreler:** risk/ödül ≥ 2; bir sonraki dirence 1,5 ATR'den yakın kırılım tetiği kullanılmaz; bilançodan 2 işlem günü önce ticaret porsiyonları nakde çekilir; porsiyon başına risk portföyün %1'ini geçmez.
- **Tablo biçimi:** `Hisse | Kapanış | Mod | 1 porsiyon sat / 1 porsiyon daha | Sattığını geri al | Sigorta (kapanış üstü) | 1 porsiyon çekirdek sat (kapanış altı) | Kenardaki porsiyonu al | 4s / günlük Supertrend | Bilanço`.
- Bugünkü fiyattan yeni alımın risk/ödül oranı 2'nin altındaysa "yeni alım yok, X–Y bekle" yazılır.
- **Pano:** Aynı emirler panonun "Salınım emirleri" bölümüne yazılır (`datasets/salinim`, proje kopyası `claude/pano_salinim.json`). Satır alanları: `id` (`HİSSE-NN`), `hisse`, `sira`, `mod`, `emir` (porsiyon dili), `fiyat` (sayı; yoksa null), `fiyat_metin` (bölge ise "43,6–45,7"), `kosul`, `kaynak` (hangi kesişim bölgesinden geldiği), `hafta`. Güncelleme: JSON'u üret → asset yükle → `datasets/salinim` içinde `source.url` ve `updated` alanlarını güncelle → `project_write`. Panodaki seviye merdiveni yalnız bölge sınırlarını gösterir; bölge ortası gibi türetilmiş fiyatlar yalnız salınım tablosunda yer alır.
- **Alarmlar:** "1 porsiyon sat", "1 porsiyon daha sat", sigorta, "sattığını geri al" ve "kenardaki porsiyonu al" seviyelerine kurulur (ABD için MCP ile; BIST için kullanıcıya liste). Alarm adı emrin kendisidir (ör. "CRWV 65,6 — 1 porsiyon sat"). Süre, bilançodan 2 işlem günü öncesine ayarlanır. Yerini alan eski alarmlar "silme önerisi" olarak listelenir; kullanıcı kendisi siler.
