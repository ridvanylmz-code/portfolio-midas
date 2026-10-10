# Aşama 2 — kontrol noktası (oturum kesilirse buradan devam)

Başlangıç: 2026-10-10 20:45 İstanbul. Kullanıcı isteği: veri kaynaklarını veri kaybı yaratmadan sadeleştir
(genişletilmiş saatler dahil, hafta içi sürekli, ücretsiz; ucuz ücretli öneriye açık), günlük/haftalık trend,
piyasa rejimi → nakit hedefi, göreli güç + sektör rotasyonu ("hangi sektör/hissede olmalıyım/olmamalıyım"),
pozisyon büyüklüğü ve risk.

## Plan ve durum
- [x] 1. TradingView scanner sütunlarını doğrula (Perf.*, SMA/EMA, RSI, ADX, ATR, premarket/postmarket, sector)
- [x] 2. scripts/market.py: rejim + sektör/tema ETF sıralaması + hisse günlük trend/RS/ATR → market.json (market-data dalı)
      Kaynak zinciri: TV scanner (toplu, anahtarsız) → Twelve Data günlük → önceki değer (stale)
- [x] 3. .github/workflows/market.yml (hafta içi saatlik + kapanış sonrası)
- [x] 4. monitor.py fiyat yedeği: Finnhub → TV scanner → (Alpaca, anahtar varsa) → stale
- [x] 5. intraday/trend 15dk mum yedeği: Alpaca (anahtar varsa, ön/sonrası dahil) → Twelve Data
- [ ] 6. Mini uygulama: Sektör sekmesi, rejim + hedef nakit, portföy risk/ısı, pozisyon büyüklüğü hesabı
- [ ] 7. docs/data/sector_notes.json: haber/momentum yorumu (güncelle bizi ile yenilenir) + ilk analiz
- [ ] 8. Test, push, canlı çalıştırma, rapor

## Notlar
- 1 ✔ Scanner sütunları MCP ile doğrulandı (|1W haftalık dahil). Not: IGV/ITA/PAVE CBOE'de listeli (scanner "name" filtresiyle sorun yok).
- 2 ✔ scripts/market.py + market/universe.json (37 sektör/tema ETF, hisse→tema eşlemesi). Gerçek veriyle test: rejim "Nötr / seçici" 4/7, nakit hedefi %20-25.
- 3 ✔ .github/workflows/market.yml → market-data dalı (market.json). Henüz canlı çalıştırılmadı.
- 4 ✔ monitor.py: Finnhub → TV scanner → Alpaca → stale. technicals.py: TV verisi artık scanner (tek istek), tradingview-ta yalnız yedek.
- 5 ✔ scripts/alpaca.py (isteğe bağlı; ALPACA_KEY_ID/ALPACA_SECRET_KEY): intraday/trend 15dk mumda Twelve Data'dan önce.
- Not: PORTFOLIO_KEY kullanıcı tarafından eklendi; repodaki portföy şifreli (17:24 UTC). Testlerde 0a46479'daki düz kopya kullanıldı.
- Sıradaki: 6 (mini uygulama Sektör sekmesi + risk), 7 (sector_notes + analiz), 8.
- 6 (kısmen) ✔ docs/sector.js + tg.html Sektör sekmesi, Portföy sekmesinde nakit/ısı şeridi. Test edilmedi, push edilmedi (yerelde). Sıradaki: Playwright testi, sector_notes.json.
