# Denetim düzeltme planı

Kaynak: `notes/DENETIM.md` (B1–B39). Uygulayan: Sonnet alt ajanları. Denetleyen: Fable (her paketin farkı okunur, testler yeniden çalıştırılır).
Dal: `claude/zen-hypatia-d79gk9`. Main'e birleştirme kullanıcıda.

## Kurallar (tüm paketler)

- Otomatik üretilen ve şifreli veri dosyaları dalda **elle değiştirilmez** (main'de botlar sürekli yazıyor, birleştirmede çakışır). Temizlik ve taşıma işleri çalışma anında kod tarafından yapılır.
- `PORTFOLIO_KEY` yok: her değişiklik sentetik veriyle test edilir (`tests/`), şifreli yol test anahtarıyla denenir.
- Haftalık teknik analiz yöntemi ve salınım stratejisi kapsam dışı; dokunulmaz.
- Şifre biçimi (kasa) değiştirilmez: gerçek anahtarla denenemeyen bir biçim değişikliği veriyi kilitleme riski taşır.

## Kararlar (peşin onaya dayanarak)

| Konu | Karar |
|---|---|
| Stop kuralı (B5) | `stop_atr = kapanış − 2×ATR`. 1×ATR kıskacı kalkar; "tepeden 3×ATR" bacağı 2× kıskaçla hiçbir zaman devreye girmediği için kaldırılır. Takip eden stop yalnız piyasa kapalıyken (günlük kapanış fiyatıyla) yükselir; böylece zamanla "en yüksek kapanış − 2×ATR" olur. |
| Zamanlayıcı (B1) | Depo içi "saat" iş akışı: tek uzun çalışma 5 dk'da bir hangi işin zamanı geldiğine bakıp `workflow_dispatch` ile tetikler, bitmeden kendini yeniden başlatır. Mevcut `schedule` satırları ilk hafta yedek olarak kalır. Dış zamanlayıcı (Cloudflare) isteğe bağlı ikinci adım. |
| Rapor sayısı (B23) | Piyasa başına 2 rapor: açılış öncesi, kapanış sonrası. Alarm yalnız olay olunca. |
| Tek kopya (B7) | Portföy/geçmiş yalnız `docs/…/data` altında; kökteki kopya ilk çalışmada kod tarafından taşınır. |
| Defter şişmesi (B6) | İçerik değişmediyse yazılmaz; işlem listesi ayrı küçük dosyaya alınır. |
| BIST fiyatı (B36) | Mum tarihi son seans değilse TradingView tarayıcısı kullanılır; yine eskiyse `stale`, günlük kayıt yazılmaz. |
| Parola saklama (B26) | Biçim değişmez. CDN Excel betiği ve Google Fonts kaldırılır. Parolanın düz saklanması açık kalan risk olarak not edilir. |
| Sayfalar (B16) | Dashboard sayfaları kaldırılır; ABD/BIST mini uygulaması tek şablondan üretilir. Tek uygulamaya (PWA) tam geçiş ayrı adım. |

## Paketler

| Paket | Bulgular | Dosyalar | Sıra |
|---|---|---|---|
| P1 Çekirdek | B5, B11, B12, B13, B24, B36, B31, B32 (sınırda notu), B18 (girinti), B7, B14, B25, B28, B3, B4, B23, B39 | `scripts/common.py, monitor.py, bist_data.py, market*.py, update_position.py, trend.py`, izleme/pozisyon iş akışları, `tests/` | 1 |
| P3 Mini uygulama | B17, B19, B20, B27, B35, B37 (ekran), B38, Haberler sekmesi | `docs/tg.html, docs/bist/tg.html, docs/*.js` | 1 (P1 ile paralel) |
| P2 Defter | B8, B9, B10, B6, B21, B22, B29, B26 (CDN/font) | `scripts/defter.py, docs/defter/index.html, defter*.yml, info-pozisyon.yml` | 2 |
| P4 Yapı | B1 (saat), B15, B16, B34, B33 | `.github/workflows/*`, `scripts/saat.py`, sayfa şablonu | 3 |
| P5 Belgeler | B30, B37 (skill), B14 (skill), B28 (skill) | `notes/` altında skill değişiklik önerileri (asıl skill'ler Claude hesabında, buradan değiştirilemez) | 4 |

## Kullanıcıda kalanlar

- Dalı main'e birleştirmek; birleştirince "saat" iş akışını bir kez elle başlatmak.
- Skill metinlerini (Claude hesabında) P5 önerilerine göre güncellemek.
- Depoyu özel yapma kararı (B25'in kalan kısmı) ve parolayı yenileme.
- TradingView'de stop/alım alarmları (B2): seviyeler şifreli portföyde olduğu için buradan kurulamaz.
