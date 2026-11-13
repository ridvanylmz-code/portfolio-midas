# Takip eden stop (tam otomatik, ABD + BIST) — 2026-10-11

Kural: eldeki her hisse için `stop = max(kayıtlı stop, ATR stop)`. **Yalnızca yukarı**; stop asla aşağı inmez.
- ATR stop: market.json (ABD) / market-bist.json (BIST) içindeki `stop_atr` = **kapanış − 2×ATR** (başka kıskaç ya da tepe bacağı yok; 2026-11-13 denetimi B5).
- Yalnız **piyasa kapalıyken** ve tamamlanmış günlük kapanış fiyatıyla yükselir (`trail_stops(..., market_open=False)`): seans içinde ya da piyasa durumu bilinmiyorsa stop taşınmaz. Böylece stop zamanla "en yüksek kapanış − 2×ATR" olur; gün içi tepe stopu yukarı kilitlemez.
- Çalıştığı yer: `monitor.py` kapanış sonrası ve açılış öncesi rapor çalışmalarında (`common.trail_stops`), `sync_public`'ten önce portföyü kaydeder; dashboard/mini uygulama yeni stopu görür.
- Kayıtlı stop yoksa varsayılan (maliyet −%15) esas alınır.
- Korumalar: piyasa verisi 5 günden eskiyse ya da satır `stale` ise dokunulmaz; güncel fiyat yoksa dokunulmaz;
  yeni stop fiyatın en az %0,5 altında ve hedefin altında olmalı; en az fiyatın %0,5'i kadar yükselmiyorsa taşınmaz.
- Telegram: her yükselişte tek seferlik "🔼 stop yükseltildi" alarmı (key: `T:trail:<yeni stop>`).
- Kapatma/açma: update-position iş akışı `trail_off` / `trail_on` (hisse bazlı; `position_levels[T].trail=false`). Geri alınabilir (undo).
- Kayıt: `position_levels[T].stop_auto` = son otomatik yükseltme tarihi.
- Dikkat: pozisyon kapanıp yeniden alınırsa saklı (yüksek) stop geri gelir; alışta mevcut uyarı çıkar.
Test: `tests/` (sentetik veri; `python -m pytest -q`).
