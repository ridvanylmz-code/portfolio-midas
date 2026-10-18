# BIST devir belgesi — ABD tarafında yapılan aşama 1–4 iyileştirmelerinin BIST'e uyarlanması

Bu belge başka bir Claude oturumu (Proje: "Bist Takip") içindir. Kullanıcı (Rıdvan, Türkçe) teknik ayrıntıyı bilmek
istemiyor; kararları sen ver, kısa ve uygulanabilir raporla. Yazım: 2026-10-11, ABD oturumu (Opus).

## 0. Önce oku (sırayla)
1. `notes/BIST-PARITE.md` — BIST oturumunun 10 Eki gecesi zaten yaptıkları (commit 4c9bed7). TEKRAR YAPMA.
2. `notes/ASAMA2.md`, `notes/ASAMA3.md`, `notes/ASAMA4.md` — ABD tarafının ayrıntılı kayıtları.
3. `git log --oneline -40` — iki oturum aynı repoda çalışıyor; başlamadan `git pull --rebase`.
4. Kontrol noktası: işe başlarken `notes/BIST-ASAMA.md` aç (plan + [ ] kutuları), her adım bitince güncelle,
   commit + push et. Oturum kesilirse yeni oturum oradan devam eder. Kullanıcı bunu özellikle istedi.

## 1. Değişmez kurallar
- Repo: `ridvanylmz-code/portfolio-midas` (public; GitHub Pages /docs). Push yetkisi `add_repo(access:"push")`.
- Yalnız spot, banka ve alkol üreticisi hisse ÖNERİLMEZ (BIST: AKBNK, GARAN, YKBNK, ISCTR, HALKB, VAKBN, TSKB, SKBNK,
  ALBRK, QNBTR… ve AEFES). TradingView industry "Major Banks"/"Regional Banks"/"Beverages: Alcoholic" dışla.
- ABD'yi BOZMA. Ortak dosyalar: `scripts/common.py, monitor.py, update_position.py, intraday.py, trend.py,
  tvscan.py, flush_outbox.py`, `docs/vault.js, sector.js, techview.js, perf.js, theme.css`. Bunlara yalnız
  geriye uyumlu parametre ekle (varsayılan = ABD davranışı). Değiştirdiysen ABD regresyon testini çalıştır (bkz. §6).
- Portföy verisi şifreli (PORTFOLIO_KEY, AES-256-GCM, `common.py` kasası; tarayıcıda `docs/vault.js`).
  `MARKET=bist` iken SECRET_FILES otomatik `bist/*.json` ve `docs/bist/data/{portfolio,history}.json` olur.
  Parolayı sen bilmiyorsun; test için SENTETİK düz portföy kullan (git geçmişi 10 Eki'de temizlendi, eski düz kopya yok).
- Hiçbir zaman gerçek işlem kaydeden "Pozisyon Güncelle" iş akışını test için çalıştırma.
- Commit mesajlarının sonuna kendi oturumunun Co-Authored-By / Claude-Session satırlarını ekle.

## 2. BIST'te ZATEN çalışanlar (ortak koddan geliyor ya da BIST oturumu yaptı)
| Konu | Durum |
|---|---|
| Şifreleme | `monitor-bist.yml`, `update-position-bist.yml` PORTFOLIO_KEY alıyor. **Ama** `bist/*.json` şu an hâlâ düz: ilk BIST izleme çalışmasında (Pzt) şifrelenecek. Kontrol et: `git show HEAD:bist/portfolio.json` → `"vault":1` olmalı. Değilse "BIST Portföy İzleme"yi `report=false` ile bir kez elle çalıştır. |
| Telegram kayıttan sonra + push yeniden deneme | `monitor-bist.yml` ve `update-position-bist.yml` yeni döngüde (outbox + flush_outbox.py). |
| Fiyat sapma kontrolü (%15), undo, zone_below/zone_above/zone_clear | `update_position.py` ortak; BIST quotes yolu `docs/bist/data/quotes.json`. |
| Alım bölgesi alarmı | `common.check_alerts` ortak; BIST monitor'da çalışır. |
| Telegram dönem satırı (📆 Hafta/Ay/Yıl) | `common.perf_summary` ortak. |
| Performans paneli, stop–hedef çubuğu, koyu tema, mobil trend kartları, günlük mum grafiği | BIST oturumu yaptı (perf.js `cur`, techview.js `chartOnly/plainLegend/noBarsMsg`, `scripts/bist_bars.py` → `trend-bist-data/bars-bist.json`). |
| Repaint (oluşan 15dk mum) | `trend_bist.compute` kapanmış 15dk mumları kullanıyor. |
| Trend sayfası `?src=` izin listesi, durum sınıfı beyaz liste | `docs/trend/bist/index.html` içinde var. |
| Geçmiş temizliği | 10 Eki'de BIST yolları da dahil yapıldı. Tekrar gerekmez. |
| Yaz/kış saati | Türkiye'de yok; `monitor-bist.yml`'deki cron eşleşmesi güvenli. |

## 3. YAPILACAKLAR (öncelik sırasıyla)

### 3.1 Aşama 1 kalanları (küçük)
- `scripts/trend_bist.py::aggregate_4h_bist`: bitmemiş son 4s mumu (10:00–14:00 / 14:00–18:00) sinyalden çıkar
  (ABD'deki `intraday.aggregate_4h(..., complete_only=True)` mantığı; dilim bitişi İstanbul saati 14:00/18:10).
- `bist_data.py` / `bist_bars.py` / `trend_bist.py` loglarında anahtar sızıntısı olmasın: log'a yalnız hata türü
  ya da `technicals.scrub()` ile maskelenmiş metin yaz (Twelve Data XIST isteğinde `apikey` URL'de).
- BIST iş akışlarında `${{ inputs.* }}` artık yalnız `env:` üzerinden veriliyor (11 Eki kontrol edildi); yeni iş akışı
  yazarsan aynı kuralı uygula.
- `docs/bist/data/analysis.json` (build_analysis.py üretir): pozisyon girilirse maliyet/stop rakamı yazma;
  ABD'deki gibi `{cost:T}` `{stop:T}` `{target:T}` yer tutucu kullan (`docs/bist/tg.html` içindeki `tok()` doldurur; mevcut).

### 3.2 Aşama 2: BIST piyasa rejimi + sektör rotasyonu + 3 aday hisse (ANA İŞ)
ABD karşılığı: `scripts/market.py`, `market/universe.json`, `.github/workflows/market.yml`, `docs/sector.js`.
BIST için ayrı dosyalar yaz: `scripts/market_bist.py`, `market/universe_bist.json`, `.github/workflows/market-bist.yml`
(çıktı `market-bist-data` dalı → `market-bist.json`; ABD'nin `market-data` dalına dokunma).

Doğrulanmış veri gerçekleri (TradingView MCP, 2026-10-11):
- TradingView tarayıcısı Türkiye: `https://scanner.tradingview.com/turkey/scan` (bist_data.py zaten kullanıyor),
  `"markets":["turkey"]`. `scripts/tvscan.py` ABD'ye sabit (`america`); ona `market="america"` parametresi ekle
  (varsayılan ABD), BIST'te `turkey` geç.
- `BIST:XU100` endeks verisi geliyor (close, Perf.1M/3M, SMA50/200, EMA20|1W). Sektör endeksleri (ör. `BIST:XUSIN`)
  tarayıcıda YOK → sektör performansını hisselerden topla: TradingView `sector` (ör. "Transportation",
  "Process Industries") ya da `industry` alanına göre grupla, grup değeri = piyasa değeri ağırlıklı ya da medyan
  Perf.W/1M/3M/6M.
- `FX_IDC:USDTRY` veriliyor (Perf.1M/3M, SMA50/200) → TL enflasyonunu ayırmak için rejim kartına ekle
  (XU100'ün dolar bazlı 1A/3A getirisi = (1+XU100)/(1+USDTRY)−1).
- `earnings_release_next_date` bazı BIST hisselerinde dolu (THYAO var, SASA boş) → bilanço uyarısı kısmen mümkün.
- `average_volume_10d_calc` BIST'te adet; likidite = adet × fiyat (TL). Eşik öner: ≥ 50 mn TL/gün.

Yapılacak hesaplar (ABD'deki ile aynı mantık, `market.py`'den fonksiyonları içe aktar ya da kopyala):
- Göreli güç (RS) = hisse/grup performansı − XU100 performansı (puan). Bileşik 0.15·1H+0.35·1A+0.35·3A+0.15·6A.
- Trend 0–7 (5 günlük + 2 haftalık koşul), çeyrek (Lider/Zayıflayan/Toparlanan/Geride), karar (Ol/Erken giriş/Tut/
  Azalt/Uzak dur) — `market.trend_points`, `rel`, `quadrant`, `verdict` aynen kullanılabilir.
- Rejim: XU100 > SMA50, > SMA200, SMA50 > SMA200, XU030 > SMA50 (varsa), genişlik (BIST hisselerinin % kaçı SMA50
  üstünde; tarama tüm likit BIST hisseleri), USDTRY trendi (TL hızlı değer kaybediyorsa risk-off puanı).
  Nakit hedefi bandı ABD ile aynı: risk-on %10–15, nötr %20–25, risk-off %35–40.
- Sektör başına 3 aday: tarama (piyasa değeri > ~10 mlr TL ve likidite eşiği, banka/alkol hariç), grup içinde
  trend ≥ 5 ve RS > 0 olan ilk 3 (`market.build_picks` mantığı; `tvscan.screen(market="turkey")`).
- Çıktıya pozisyon/izleme hisseleri için günlük/haftalık trend, RS, ATR, ATR stop (`market.atr_stop`), `earn_next`.

Arayüz:
- `docs/bist/tg.html`'e "Sektör" sekmesi: `docs/sector.js`'i yeniden kullan. sector.js şu an ABD'ye bağlı yazılar içeriyor
  ("SPY", "$"); ona `ctx.bench` (ör. "XU100") ve `ctx.cur` ("₺") parametresi ekle (varsayılan "SPY"/"$"), BIST'ten geç.
  Portföy sekmesine nakit hedefi/ısı şeridi (`SectorView.strip`), "Risk & Boyut" (pozisyon büyüklüğü hesaplayıcı).
- Teknik sekmesinde zaman dilimi sinyal tablosu (`TechView.render`, `chartOnly` kapalı) — 15dk/4s `trend-bist.json`'dan,
  günlük/haftalık `market-bist.json`'dan.
- `docs/bist/data/sector_notes.json`: haber + momentum yorumu (BIST'e özgü: faiz/TCMB, enflasyon, kur, sektör haberleri).
  İlk sürümü güncel haberlerle sen yaz; "güncelle bizi"de yenilenir.
- Dashboard (`docs/bist/index.html`) izleme listesi sıralaması RS'e göre + rejim kartı (ABD `docs/index.html` örneği).

### 3.3 Aşama 3 kalanları
- `monitor.market_lines` BIST'te boş döner (BIST kontrolü var). BIST için `MARKET_JSON` → market-bist.json okuyup
  rejim/nakit/güçlü-zayıf sektör satırını Telegram raporuna ekle; `monitor-bist.yml`'de market-bist-data dalından
  `$RUNNER_TEMP/market.json` çek (ABD monitor.yml'deki adım gibi).
- Takip sekmesi satırı: trend etiketi + RS + karar + bilanço günü + EMA20 giriş notu (ABD `renderWatch`).

### 3.4 Aşama 4 kalanları
- Bilanço uyarısı: `monitor.earnings_alerts` şu an `BIST` ise boş döner (`_market()` BIST'te None). market-bist.json'da
  `stocks[T].earn_next` olunca BIST'te de çalışacak şekilde aç (tarihi olmayan hisseler sessizce atlanır).
- Performans, alım bölgesi, geçmiş temizliği: tamam (bkz. §2).

## 4. Veri kaynakları (BIST'te sürekli ücretsiz veri)
- Fiyat: Yahoo/yfinance → TradingView turkey scanner (bist_data.py'de var). Alpaca BIST vermez.
- 15dk mumlar: Yahoo (ham) → yfinance → Twelve Data XIST. BIST'te ön/sonrası seans yok.
- Günlük göstergeler + sektör + rejim: TradingView turkey scanner (TEK istek, anahtarsız) → eksikler yfinance günlük
  → önceki değer "stale". Veri boşluğu yaratma: her adımda önceki dosyayı yedek olarak koru (ABD market.yml deseni).
- Sandbox'tan scanner/Yahoo'ya doğrudan erişilemiyor: yerel test için TradingView MCP
  (`mcp-tv-get-symbol-data-batch`, BIST:SEMBOL) ile fixture oluştur, script'teki `tvscan.fetch/screen`'i stub'la.
  Canlı doğrulama için iş akışını `gh api -X POST .../actions/workflows/<dosya>/dispatches -f ref=main` ile tetikle.

## 5. Bilinen tuzaklar
- `gh workflow run` çalışmıyor (GraphQL engelli); REST dispatch kullan. Yeni iş akışı dosyası push'tan ~20 sn sonra
  dispatch edilebilir (önce 404 verir).
- Bot her ~15 dk main'e veri commit'i atabilir (BIST seans saatlerinde): push öncesi daima `git fetch && git rebase origin/main`.
- `pkill -f "http.server"` kendi kabuğunu öldürebilir; test sunucusunu `setsid python3 -m http.server PORT` ile aç, port değiştir.
- Playwright: Chromium hazır (`playwright install` çalıştırma). raw.githubusercontent isteklerini `page.route` ile yerel
  JSON'a yönlendir. Telegram webview script'i (telegram.org) sandbox'ta yüklenmez; hata sayma.
- `docs/bist/*.html` ortak JS'leri `../vault.js`, `../sector.js` gibi göreli yolla yükler; sürüm parametresini (`?v=`)
  değiştirince önbellek yenilenir.

## 6. Test ve teslim
- Python: `python3 -m py_compile scripts/*.py`; sentetik veriyle `market_bist.main()` çalıştır; rejim/sektör/aday çıktısını yazdır.
- Arayüz: `docs`'u geçici bir klasöre kopyala, `docs/bist/data/portfolio.json` + `history.json` yerine SENTETİK düz
  portföy koy, Playwright ile `bist/tg.html` (tüm sekmeler), `bist/index.html`, `trend/bist/index.html` 390 ve 1280 px;
  sayfa hatası 0, yatay kaydırma yok, ekran görüntülerine bak.
- ABD regresyonu (ortak dosyaya dokunduysan): aynı yöntemle `tg.html`, `index.html`, `trend/index.html` açılmalı, hata 0.
- Canlı: `market-bist.yml`'i dispatch et, `market-bist-data` dalındaki dosyayı `gh api .../contents/market-bist.json?ref=market-bist-data`
  ile oku; kaç sembol geldiğini ve kaynak dağılımını kullanıcıya bildir.
- Son yanıt: ne değişti (tablo), kullanıcının yapması gereken bir şey varsa (secret vb.) tek satır, DEVAM.md satırı.
