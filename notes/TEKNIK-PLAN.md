# Teknik Plan panosu ve bildirimleri

- Sayfa: `docs/teknik/index.html` → https://ridvanylmz-code.github.io/portfolio-midas/teknik/ (Telegram mini uygulamasında "📐 Teknik Plan").
- Veri: `docs/teknik/data/salinim.json` (emirler, **adet ve nakit yok**), `meta.json` (hisse başına pazar, ATR, plan tarihi, mod). Claude haftalık analiz ve ara güncellemeden sonra yazar.
- Bildirim: `scripts/teknik_bildirim.py us|bist`, izleme iş akışları (`monitor.yml`, `monitor-bist.yml`) her çalışmada çağırır. Mesajlar mevcut Telegram botlarına (ABD / BIST) giden kutusu üzerinden gider.
  - 🔔 fiyat bir emre 0,5 ATR yaklaştı (emir başına günde bir) · ✅ seviye geçildi · ⚠️ fiyat emir haritası dışında (günde bir) · ⏳ plan 14 günden eski.
  - Yeni plan yüklenince ilk çalışma yalnız durumu kaydeder (eski geçişler için toplu bildirim gitmez).
  - Durum: `docs/teknik/data/bildirim_durum_<pazar>.json`.
- Kapatmak için: iş akışlarındaki `teknik_bildirim.py` satırını silmek yeterli.
- Öncelik: haftalık plan bağlayıcı; repo günlük analizi ve 15 dk Pine alarmı bilgi amaçlı.
