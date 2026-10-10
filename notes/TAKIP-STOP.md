# Takip eden stop (tam otomatik, ABD + BIST) — 2026-10-11

Kural: eldeki her hisse için `stop = max(kayıtlı stop, ATR stop)`. **Yalnızca yukarı**; stop asla aşağı inmez.
- ATR stop: market.json (ABD) / market-bist.json (BIST) içindeki `stop_atr` (fiyattan 2×ATR ya da 3A tepeden 3×ATR).
- Çalıştığı yer: `monitor.py` her çalışmada (`common.trail_stops`), `sync_public`'ten önce portföyü kaydeder; dashboard/mini uygulama yeni stopu görür.
- Kayıtlı stop yoksa varsayılan (maliyet −%15) esas alınır.
- Korumalar: piyasa verisi 5 günden eskiyse ya da satır `stale` ise dokunulmaz; güncel fiyat yoksa dokunulmaz;
  yeni stop fiyatın en az %0,5 altında ve hedefin altında olmalı; en az fiyatın %0,5'i kadar yükselmiyorsa taşınmaz.
- Telegram: her yükselişte tek seferlik "🔼 stop yükseltildi" alarmı (key: `T:trail:<yeni stop>`).
- Kapatma/açma: update-position iş akışı `trail_off` / `trail_on` (hisse bazlı; `position_levels[T].trail=false`). Geri alınabilir (undo).
- Kayıt: `position_levels[T].stop_auto` = son otomatik yükseltme tarihi.
- Dikkat: pozisyon kapanıp yeniden alınırsa saklı (yüksek) stop geri gelir; alışta mevcut uyarı çıkar.
Test: birim (21 durum) + monitor.run uçtan uca (ABD/BIST, şifreli yol dahil), sentetik veri.
