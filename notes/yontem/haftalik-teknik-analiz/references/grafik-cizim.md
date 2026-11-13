# Grafiğe çizim (haftalik-teknik-analiz, bölüm 5)

## 5. Grafiğe çizim (Claude in Chrome + TradingView)

Kullanıcının açık TradingView sekmesinde çalış (layout "Günlük_2"). Yeni sekme açma. Chrome uzantısı bağlı değilse çizimi atla, izleme listesindeki "Grafik durumu" bölümüne not düş.

### 5.1 Sadelik kuralları (grafik kalabalık olmasın)

- **Grafiğe yalnızca şunlar çizilir:** (a) kesişim bölgeleri (hisse başına en fazla 3 fiyat bölgesi), (b) en fazla 1 zaman bandı, (c) ana senaryo yolu (tek `path`, alternatif senaryo yalnızca olasılığı %40 ve üzeriyse), (d) al tetiği ve stop/kritik destek çizgileri, (e) Elliott sayımı ana dereceyle sınırlı.
- **Çizilmez:** tek başına EMA, tek Fibonacci veya Gann seviyesi, bütün Fibonacci ızgarası, Gann yelpazesi, yay ve daireler, uyumsuzluk çizgileri (bunlar yalnızca analiz metninde ve tabloda kalır). İstisna: kullanıcı özellikle isterse.
- Hisse başına toplam çizim nesnesi hedefi **~10'u geçmesin**. Geçecekse önce en az önemli olanı çıkar.
- Bölge içindeki bileşenleri grafiğe tek tek yazma. Bölgede yalnızca kısa bir etiket olsun (örn. "KRİTİK 61,0–62,5", "ÖNEMLİ"); bileşenlerin ayrıntısı analiz metninde.

### 5.2 Yazıların mumları kapatmaması

- Bölge dikdörtgenlerini son mumun **sağındaki boş alana** çiz (yarından ~5 hafta ileriye). Etiketler böylece mumların üstüne gelmez.
- Bölge etiketini kutunun **içine** koy: `vertLabelsAlign: 'middle'`, `horzLabelsAlign: 'right'`. (Kutunun dışına koymak gerekirse: TradingView'de `'bottom'` etiketi kutunun **üstüne**, `'top'` **altına** koyar.) Zaman bandının etiketi için `'bottom'` kullan (bandın üstünde görünür).
- Etiket mümkün olduğunca kısa olsun (en çok 2–4 kelime, ~20 karakter). Uzun açıklamalar çizime değil, analiz metnine yazılır.
- Dikdörtgenlerin dolgu şeffaflığını yüksek tut (~%85–90) ki mumlar görünsün; kenar çizgisi ince olsun.
- Çizimden sonra fiyat ölçeğini bölgeleri kapsayacak şekilde ayarla ve ekran görüntüsü al; herhangi bir yazı mumu veya analizi kapatıyorsa şeklin noktalarını `setPoints` ile kaydır, gerekirse etiketi sil ve metne taşı.

### 5.3 Teknik adımlar

1. Önce durumu oku: `TradingViewApi.chartsCount()`, `activeChartIndex()`, her grafik için `chart(i).symbol()`, `chart(i).resolution()`, `getAllShapes()` ve `document.hidden`.
2. **Kullanıcının mevcut çizimlerine asla dokunma.** Kendi eski çizimlerini şu işaretlerle tanı: Türkçe açıklama metni olan `horizontal_ray`/`rectangle`, renkler `#fb8c00`, `#2e7d32`, `#e53935`, `#1e88e5`, `#8e24aa`, `#00bcd4`, `#26a69a`, `#ef5350`, `#ff9800`, `#fbc02d`, `#5c6bc0` ve son haftalara ait senaryo `path`'leri. `fib_retracement`, `signpost`, `text_note`, `price_label`, `price_note`, `info_line`, metinsiz sarı/beyaz `trend_line` kullanıcınındır. Şekil ID'leri sayfa yenilenince değişir; ID'ye değil içeriğe bak. Emin olmadığın şekle dokunma. Elliott sayımı (mavi `elliott_*` ve mor etiketler) hâlâ geçerliyse silme.
3. `setSymbol(sembol)` ile hisseye geç, ~3 sn bekle. Grafiği önce `setResolution('1D')` yap. Çizimden sonra `getPoints()` ile zamanları doğrula; kayan noktaları `setPoints` ile düzelt. `path` nokta sayısı `setPoints` ile değiştirilemez; farklı sayıda nokta gerekiyorsa eski yolu sil, yenisini oluştur.
4. Zaman değeri olarak günün 00:00 UTC unix saniyesini kullan.
5. Kullanılacak şekiller ve renkler:
   - `rectangle`: **Kesişim bölgeleri.** Kritik = turuncu dolgu `#ff9800` (yazı `#e65100`), önemli = sarı dolgu `#fbc02d` (yazı `#b28704`); destek rolündeki bölge yeşil `#26a69a`, direnç rolündeki kırmızı `#ef5350` kenar. Zaman bandı `#5c6bc0`, şeffaflık 90, geniş fiyat aralığıyla.
   - `horizontal_ray`: Yalnızca al tetiği (turuncu) ve stop (yeşil, kesikli `linestyle: 2`). Başlangıç noktası ~2 ay önce.
   - `elliott_correction`: 4 nokta (başlangıç, A, B, C). Mavi. `elliott_impulse_wave`: 6 nokta.
   - `text`: Elliott etiketleri (mor) ve kısa bölge etiketleri; konum kuralları için 5.2'ye bak.
   - `trend_line` (`extendRight: true`): Yalnızca üçgenin ana kenarları (analizin dayandığı).
   - `path` (`lineStyle: 2`, `rightEnd: 1`): Ana senaryo yeşil, alternatif senaryo (gerekirse) kırmızı. Ana senaryo düşüş olsa da yeşil kalır; bunu kullanıcıya tek satırla söyle.
6. `createShape` ve `createMultipointShape` sonucunu `await` ile al. Fiyat ölçeğini `chart.getPanes()[0].getMainSourcePriceScale().setVisiblePriceRange({from, to})` ile ayarla (`setVisibleRange` çalışmıyor).
7. Sayfa yenilenince yardımcı fonksiyonlar kaybolur; her oturumda `window.__draw` ve `window.__list` yardımcılarını yeniden tanımla. Uzun süren (birden çok sembol gezen) betikleri arka planda başlatıp bir bayrakla bitişini kontrol et; tek çağrıda beklemek araç zaman aşımına düşer.
8. Ekran görüntüsüyle kontrol et (5.2'deki çakışma kontrolü dahil). `document.hidden === true` ise grafik ekrana çizilmez; bu durumda kodla doğrula ve kullanıcıya "sekmeye dönünce görünecek" de.
9. İş bitince grafiği kullanıcının başta açık olduğu sembole ve zaman dilimine geri getir.
10. Kullanıcıya kısa bir renk/çizim tablosu ver, grafiğe **neyin çizilmediğini** de tek satırla belirt ("Fibonacci/Gann tekil seviyeleri analizde, grafikte yok") ve "Kaydet" butonuna basmasını hatırlat.
