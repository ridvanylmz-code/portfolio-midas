# BIST aşama 1–4 uyarlaması — kontrol noktası (2026-10-11)

Oturum kesilirse buradan devam et. Plan kaynağı: notes/BIST-DEVIR.md. Yapılmışlar: notes/BIST-PARITE.md (tekrarlama).

- [x] 0. Hazırlık: repo klonlandı, devir + parite okundu, `bist/portfolio.json` şifre durumu kontrol edildi
- [x] 1. §3.1 küçük kalanlar: aggregate_4h_bist tamamlanmamış mum, log anahtar sızıntısı, analysis.json yer tutucu
- [x] 2. §3.2 veri (canlı dispatch bekliyor): tvscan `market=` parametresi, market_bist.py, universe_bist.json, market-bist.yml
- [x] 3. §3.2 arayüz: sector.js bench/cur, tg.html Sektör/Risk/Teknik sekmeleri, dashboard rejim kartı, sector_notes.json
- [x] 4. §3.3/3.4: monitor market_lines + earnings_alerts BIST, monitor-bist.yml market-bist-data çekme
- [ ] 5. Test: yerel testler TAMAM (py_compile, market_bist fixture, monitor BIST+ABD, Playwright 390/1280 BIST+ABD, hata 0); KALAN: canlı dispatch market-bist.yml + monitor-bist (şifreleme), market-bist-data dalı doğrulama
- [ ] 6. Teslim: tablo + DEVAM.md satırı

## Notlar
- Başlangıç: HEAD 611623b; `bist/portfolio.json` hâlâ düz (vault yok) → ilk BIST izleme çalışmasında şifrelenecek.

- 1 ✔ aggregate_4h_bist(complete_only=True) + bist_bars log maskesi; build_analysis.py pozisyon verisi okumuyor, yer tutucu gerekmiyor.
- 2 ✔ tvscan `market=`/`exact=`/`types=` (varsayılan ABD), scripts/market_bist.py, market/universe_bist.json, market-bist.yml. Gerçek TV verisiyle (MCP fixture) yerel test: rejim Risk-off 2/7, 18 grup, 17 gruba aday.
- Sıradaki: 3 (arayüz: sector.js bench/cur, tg.html Sektör + Teknik sinyal tablosu, dashboard rejim kartı, sector_notes.json).
- 3 ✔ sector.js (cfg.bench/cur, verdict chip taşması düzeltildi), techview.js (plain/bench, mobil sinyal tablosu), docs/bist/tg.html (Sektör sekmesi, Risk şeridi, Takip RS/karar/bilanço, Teknik tablo), docs/bist/index.html (rejim kartı + RS sıralama), docs/bist/data/sector_notes.json (10 Eki haber+veri).
- 4 ✔ monitor.py: _market() BIST'te de MARKET_JSON okur, bilanço uyarısı İstanbul tarihiyle, rejim satırı grup adıyla; monitor-bist.yml market-bist-data'dan market.json çeker.
- Sıradaki: 5 (canlı dispatch: market-bist.yml, sonra monitor-bist report=false), 6 teslim.
