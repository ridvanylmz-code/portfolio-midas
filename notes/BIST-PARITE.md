# BIST — ABD aşama 2-4 iyileştirmelerinin uyarlanması (2026-10-10 gece)

Yapılanlar (ABD'ye dokunulmadı):
- docs/perf.js: para birimi parametresi (`cur`); BIST'te ₺.
- docs/bist/index.html: koyu tema varsayılan, tr-TR sayı biçimi, kart rengi yalnız stop kırılınca, stop–hedef çubuğu, stop çizgili grafik, performans paneli, duvar yazısı en altta.
- docs/trend/bist/index.html: mobil kart görünümü, sıralama oku/erişilebilirlik, tr-TR yüzde biçimi, boş değer sıralaması.
- docs/bist/tg.html: performans paneli, trend etiketi (Bullish/Karışık/Bearish), ağırlık, stop–hedef çubuğu, stop kırılınca kırmızı çerçeve, Takip'te trend etiketi, Teknik sekmesinde günlük mum grafiği.
- scripts/bist_bars.py + trend-bist.yml: günlük mumlar -> trend-bist-data/bars-bist.json (yfinance, hata trend taramasını bozmaz).
- docs/techview.js: `chartOnly`, `plainLegend`, `noBarsMsg` seçenekleri (BIST'te EMA/Supertrend adı geçmez).

Zaten ortak arka planda çalışanlar (MARKET=bist): alım bölgesi alarmı, Telegram dönem satırı (perf_summary), update-position zone_* girişleri.
Yapılmayanlar / BIST'e uymaz: sektör-rejim-RS (ABD ETF/SPY'ye bağlı), Alpaca (ABD verisi), bilanço uyarısı (BIST'te earn_next verisi yok).
Test: sentetik pozisyon/mum verisiyle Playwright, 390 ve 1024 px, hata yok. Canlı doğrulama: BIST Trend Tara'yı bir kez elle çalıştır (bars-bist.json oluşsun).
