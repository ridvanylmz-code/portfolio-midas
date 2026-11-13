# Görsel pano (haftalik-teknik-analiz, bölüm 8)

## 8. Görsel pano (Dashboard)

Pano: https://claude.ai/artifact/C8y3d13PSUJEjAopPQEuuK (ArtifactData ile güncellenir; sayfa dosyasına dokunmadan yalnızca veriler değişir). Bağlantı çalışmazsa Artifact `list` ile "pano" adlı artifact'ı bul.

- **fiyat** (canlı sorgu, Tradingview → `mcp-tv-get-symbol-data-batch`): İzleme listesi değişince `datasets/fiyat` içindeki `source.args.symbols` listesini güncelle.
- **seviyeler** (dosya): Her analizde yeni haftanın seviyelerini ekle. Satır alanları: `id` (`HİSSE-YYYYMMDD-NN`), `hisse`, `sembol`, `sira`, `seviye`, `etiket`, `tur`, `hafta` (YYYY-AA-GG). `tur` değerleri: hedef, tetik, ara, donus, destek, stop, asagi, taban. Kesişim bölgeleri için yeni bir `tur` icat etme; bölgenin rolüne göre `donus`, `destek` veya `ara` kullan, `etiket` alanını "Konfluens (güç): kısa açıklama" biçiminde yaz ve bölgenin alt ve üst sınırını ayrı iki satır olarak gir. Pano her hisse için yalnızca en son haftayı gösterir. Aynı gün aynı hisse için yeniden analiz yapılırsa o günün eski satırlarını sil, yenilerini yaz.
- **tahminler** (dosya): Önceki satırların `sonuc` ve `isabet` alanlarını doldur, yeni haftanın satırlarını ekle. Alanlar: id, hafta, surum, sembol, hisse, para, analiz_fiyati, ana_senaryo, olasilik ("A %55 / B %45" biçiminde metin), alt_senaryo, donus_bolgesi, tetik, stop, hedef1, hedef2 (metin), zaman, momentum, sonuc, isabet.
- **Güncelleme adımları (onay sayısını azaltmak için panoyu okuma):**
  1. Mevcut verileri panodan değil, **proje kopyasından** oku: `claude/pano_seviyeler.json` ve `claude/pano_tahminler.json` (`project_read`). Artifact `read` ve `ArtifactData list` çağrısı yapma.
  2. Satırları Python ile ekle/güncelle ve iki JSON dosyasını yerelde yaz.
  3. Yeni dosyaları panoya asset olarak yükle (Artifact `publish`, `asset: true`).
  4. `datasets/seviyeler` ve `datasets/tahminler` dokümanlarında `source.url` ve `updated` alanlarını tek bir `ArtifactData batch` çağrısıyla güncelle. `if_version` değerini ezbere yazma: önce tahmini bir değerle dene, çakışma hatası gelince hata mesajındaki güncel sürümle bir kez tekrarla.
  5. Aynı iki JSON dosyasını `project_write` ile proje kopyasına geri yaz; proje kopyası her zaman panodakiyle aynı olmalı.
- Proje belgesi `claude/tahmin_defteri.md` ile panodaki veriler aynı kalmalı.
