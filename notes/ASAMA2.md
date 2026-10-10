# Aşama 2 — kontrol noktası (oturum kesilirse buradan devam)

Başlangıç: 2026-10-10 20:45 İstanbul. Kullanıcı isteği: veri kaynaklarını veri kaybı yaratmadan sadeleştir
(genişletilmiş saatler dahil, hafta içi sürekli, ücretsiz; ucuz ücretli öneriye açık), günlük/haftalık trend,
piyasa rejimi → nakit hedefi, göreli güç + sektör rotasyonu ("hangi sektör/hissede olmalıyım/olmamalıyım"),
pozisyon büyüklüğü ve risk.

## Plan ve durum
- [ ] 1. TradingView scanner sütunlarını doğrula (Perf.*, SMA/EMA, RSI, ADX, ATR, premarket/postmarket, sector)
- [ ] 2. scripts/market.py: rejim + sektör/tema ETF sıralaması + hisse günlük trend/RS/ATR → market.json (market-data dalı)
      Kaynak zinciri: TV scanner (toplu, anahtarsız) → Twelve Data günlük → önceki değer (stale)
- [ ] 3. .github/workflows/market.yml (hafta içi saatlik + kapanış sonrası)
- [ ] 4. monitor.py fiyat yedeği: Finnhub → TV scanner → (Alpaca, anahtar varsa) → stale
- [ ] 5. intraday/trend 15dk mum yedeği: Alpaca (anahtar varsa, ön/sonrası dahil) → Twelve Data
- [ ] 6. Mini uygulama: Sektör sekmesi, rejim + hedef nakit, portföy risk/ısı, pozisyon büyüklüğü hesabı
- [ ] 7. docs/data/sector_notes.json: haber/momentum yorumu (güncelle bizi ile yenilenir) + ilk analiz
- [ ] 8. Test, push, canlı çalıştırma, rapor

## Notlar
