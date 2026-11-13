---
name: "takip-listesi-tarama"
description: "market.json picks listesinden 5 hisselik ABD takip listesini seçip repoda güncellemek istendiğinde kullan. Her güncellemede mevcut listeyi yeniden kontrol eder."
---

# ABD Takip Listesi Seçimi

Dil: Türkçe, kısa, basit tablo. Al-sat dili porsiyon dilidir (`portfoy-guncelle` ile aynı): "1 porsiyon al", "kenardaki porsiyonu al" vb.

## Kesin kısıtlar
- Yalnız ABD, yalnız spot; short, kaldıraç, opsiyon yok.
- Banka hisseleri ve alkol üreticisi şirketler alınmaz (aday listesinde olsa bile).

## Girdi
- `market.json` içindeki `picks` (sektör başına adaylar), `regime` ve aday alanları: `rs`, `rs_m1`, `rs_m3`, `trend`, `label`, `rsi`, `atr_pct`, `stop_atr`. Kendi taraman yok; sayılar koddan gelir, Claude seçer ve yorumlar.
- Adil değer: `docs/data/analysis.json` → `fundamental.fair_value` (analist ortalama hedefi). Yoksa "adil değer yok" yaz, kendi tahminini uydurma.
- Stop: adayın `stop_atr` değeri (`günlük kapanış − 2×ATR`). Teknik bir dip daha yakınsa onu kullan ve kaynağını yaz.
- Aday dışı hisse önerirsen "aday dışı" diye etiketle ve nedenini yaz.

## Dilüsyon kontrolü (her hisse, zorunlu)
Kaynaklar:
1. TradingView `get-financials`: nakit, serbest nakit akışı (son çeyrek ve TTM). Nakit ömrü = nakit / çeyreklik nakit yakımı.
2. SEC EDGAR (WebFetch ile; shell sec.gov'a erişemez): son 12 ayda S-3 / S-3ASR (shelf), 424B5 (shelf'ten satış), ATM / "equity distribution agreement" duyurusu.
3. Son 30 günün haber başlıkları (TradingView `get-news`).

Seviye:
| Seviye | Koşul | Karar |
|---|---|---|
| Yüksek | Serbest nakit akışı negatif ve nakit ömrü < 4 çeyrek; **veya** aktif ATM/424B5 satışı var ve nakit akışı negatif | Listeye alma |
| Orta | Etkin shelf var ama nakit ömrü ≥ 4 çeyrek ya da nakit akışı pozitif; veya ATM tamamlanmış | Alınabilir, tabloda "dilüsyon: orta" ve gerekçe |
| Düşük | Serbest nakit akışı pozitif, etkin shelf/ATM yok | Not gerekmez |
| Doğrulanamadı | Kaynaklardan biri okunamadı | Listeye alırsan "doğrulanamadı" etiketiyle |

Sonucu `analysis.json` → `dilution` alanına `{"risk", "text"}` olarak, tarih ve kaynakla yaz.

## Seçim
- Adaylar arasından en fazla 5 hisse; yalnızca önümüzdeki günlerde yükseliş beklenenler. Düşüş rejiminde 5'i doldurmak zorunlu değil.
- Korelasyonu makro sürücüye göre kontrol et (faiz hassasiyeti, risk iştahı), yalnızca sektör etiketine göre değil.
- En güçlü 1-2 fikre gerçek boyutla girmeyi öncele.

## Değiştirme kuralı (rotasyonu sınırlar)
Listedeki bir hisse yalnızca şu durumlardan biri olursa çıkarılır:
1. Günlük kapanış stop altında.
2. Dilüsyon seviyesi "Yüksek"e döndü.
3. Artık picks içinde değil **ve** `trend` puanı düştü ya da `label` yükseliş değil.
4. Yeni bir aday mevcut en zayıf hisseden belirgin güçlü: `rs` en az 5 puan yüksek **ve** `trend` puanı eşit ya da yüksek.

Bunlar dışında liste korunur. Stop ve dilüsyon kaynaklı çıkışlar hariç, bir güncellemede en fazla 2 hisse değişir. Her değişikliği tek satır gerekçeyle yaz.

## Tablo (her hisse)
`Hisse | Giriş tarihi ve fiyatı | Güncel fiyat (tarih, seans) | Adil değer | Momentum (rs, trend) | Giriş tetikleyicisi | Stop | Dilüsyon`

Giriş fiyatı TradingView'den tarihli alınır.

## Repo yazma
- Portföy dosyası şifrelidir; betik yerelde çalıştırılamaz. Takip listesini "Portföy Güncelle - Midas-USD" iş akışını **tek sefer** çalıştırarak güncelle: `batch` alanına her satıra bir işlem yaz (örn. `watch_remove INTC` / `watch_add AMD` / `zone_below AMD 95`). Hepsi tek commit ve tek Telegram mesajı olur; bir satır hatalıysa hiçbiri uygulanmaz.
- Her girişi ve çıkışı `docs/data/picks_log.json` dosyasına ekle ve commit et: `{"ticker", "in_date", "in_price", "stop", "out_date", "out_price", "reason"}` (açık seçimlerde `out_*` boş).
- Push başarısızsa listeyi repoda güncel sayma; hatayı raporun başında yaz ve yapılacak eylemleri liste olarak ver.

## Performans
Performansı yalnızca `docs/data/picks_log.json`'daki tarihli giriş ve çıkış fiyatlarıyla ölç. Raporun sonuna tek satır ekle: kapanan seçim sayısı, kazananların oranı, aynı dönemde SPY'a göre ortalama fark. İzlenimle karşılaştırma yapma.