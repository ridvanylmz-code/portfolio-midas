# Aşama 4 — kontrol noktası (oturum kesilirse buradan devam)

Başlangıç: 2026-10-10 23:02 İstanbul. İstek: (1) alım bölgesi Telegram alarmı, (2) bilançoya 3 gün kala uyarı,
(3) portföyün kendi performans takibi (günlük/aylık/yıllık; değer, kazanç/kayıp oranları, nakit/hisse oranı),
(4) repo geçmişindeki şifresiz portföy kopyalarını temizle — ana kayıtlar (güncel şifreli history.json) kalacak.

## Plan ve durum
- [x] 1. Alım bölgesi: update-position'a zone_below / zone_above / zone_clear; monitor alarmı
- [x] 2. Bilanço uyarısı: market.py'ye earnings_release_next_date; monitor'da 0-3 gün kala tek seferlik alarm
- [x] 3. Performans: docs/perf.js (mini uygulama + dashboard), Telegram raporuna dönem satırı
- [x] 4. Geçmiş temizliği: önce kayıt bütünlüğü kontrolü, sonra git filter-repo + force push
- [x] 5. Test, push, rapor

## Notlar
- 1-2 ✔ zone_below/zone_above/zone_clear (update_position + workflow seçenekleri, undo destekli); common.check_alerts alım bölgesi; monitor.earnings_alerts (market.json earn_next, 3 ve 0 gün, tek seferlik state['once']). Yerel test ok.
- 3 ✔ docs/perf.js (Özet/Aylık/İşlemler + değer/nakit grafiği) mini uygulama Portföy sekmesi ve dashboard; common.perf_summary → Telegram '📆 Hafta/Ay/Yıl' satırı; SNAPSHOT_LIMIT 4000. Test ok.
- Sıradaki: 4 (geçmiş temizliği).
- 4 ✔ Bütünlük: eski düz sürümlerdeki 9 işlemin hepsi güncel kayıtta; eksik yok. git filter-repo ile 11 hassas dosyanın eski sürümleri tüm geçmişten silindi, güncel (şifreli) sürümleri 1fb0516'da geri eklendi; son ağaç birebir aynı (a7c3301). Force push (lease ile) yapıldı. Yeni geçmişte main 274 commit.
- Not: GitHub eski commit'leri SHA ile bir süre daha önbellekte tutuyor (ör. 0a46479 API'de hâlâ açılıyor). Tam silme için GitHub Support'a "sensitive data / cached views" talebi gerekir.
- Not: Yerel tam yedek (eski geçmiş dahil) yalnız bu oturumun geçici alanında: scratchpad/rewrite/yedek-tam-gecmis.bundle (oturum bitince silinir).
- 5 ✔ Rewrite sonrası monitor.yml başarılı (1fb0516).
## Aşama 4 bitti.
