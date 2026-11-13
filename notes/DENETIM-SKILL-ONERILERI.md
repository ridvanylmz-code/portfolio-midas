# Skill metinleri için değişiklik önerileri (P5)

Asıl skill'ler Claude hesabında durur; bu depodan değiştirilemez. Aşağıdaki değişiklikleri hesaptaki metinlere elle uygula. `notes/yontem/` kopyası bilerek olduğu gibi bırakıldı.

## `portfoy-guncelle`

| Bölüm | Şimdi | Olması gereken | Bulgu |
|---|---|---|---|
| Kapsam, 3. madde | `docs/data/holdings.json` okunur; yoksa atla | Aynı. Dosya artık her izleme çalışmasında üretiliyor (`{"updated","holdings":[…]}`); "yoksa atla" kuralı kalabilir, artık tetiklenmemeli. | B14 |
| Adım 4 (hisse yorumu) | "yalnızca güncellenen hisseler için" yaz | Her hissede bloğun tarihini yaz: `technical_date`, `momentum_date` (YYYY-AA-GG). Elde ya da takipte olan her hissenin teknik bloğu **her güncellemede** yenilenir; yenilenemeyen blok silinir. | B37 |
| Adım 4 (adil değer) | Metin: "Analist ortalama hedefi $129,51 (+%179)" | Yüzdeyi metne yazma. Sayıyı ayrı alana koy: `fundamental.target_price: 129.51`. Bilanço tarihi: `fundamental.earn_date: "2026-11-20"`. Yüzdeyi ekran canlı fiyattan hesaplar. | B35, B37 |
| Adım 4 (kapsam) | — | `analysis.json`'da yalnız `symbols.json`'daki hisseler kalır; listeden çıkan hissenin kaydı silinir. | B19 |
| Adım 5 (stop) | "picks/technicals içindeki stop" | Stop kuralı artık `kapanış − 2×ATR`; takip eden stop yalnız günlük kapanışla yükselir. Metindeki "2×ATR ya da tepeden 3×ATR" ifadesi varsa düzelt. | B5 |

## `takip-listesi-tarama`

| Bölüm | Şimdi | Olması gereken | Bulgu |
|---|---|---|---|
| Repo yazma | `update_position.py --action watch_add / watch_remove`, her hisse ayrı | Tek işlem: "Portföy Güncelle" iş akışını `batch` alanıyla çalıştır (her satır bir işlem) ya da `watch_set` ile listeyi tek seferde ayarla. Betik yerelde çalıştırılamaz (portföy şifreli); yazma iş akışı üzerinden yapılır. | B28 |
| Performans | "tarihli giriş fiyatlarıyla ölç" | Her giriş/çıkışı `docs/data/picks_log.json`'a yaz: `{"ticker","in_date","in_price","stop","out_date","out_price","reason"}`. Rapor sonunda: kapanan seçimlerin isabet oranı ve aynı dönemde SPY'a göre ortalama fark. | B30 |
| Girdi (stop) | `stop_atr` | Aynı alan, yeni tanım: `kapanış − 2×ATR`. | B5 |

## BIST (`bist-guncelle`, depoda kopyası yok)

- Takip listesi 32 hisse; ABD'deki "en fazla 5" disiplini yok. Aynı değiştirme kuralını ve üst sınırı (öneri: 8–10) uygula.
- `bist/tv_snapshot.json` ve `analysis.json` için yukarıdaki tarih ve sayısal alan kuralları aynen geçerli.
- Skill metninin kopyasını `notes/yontem/bist-guncelle/` altına ekle; bir sonraki denetimde yöntem de incelenebilsin.
