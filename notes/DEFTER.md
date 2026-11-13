# Portföy Defteri — devir notu

4 hesabın günlük kaydı. Sayfa: `docs/defter/index.html` (mini uygulamalarda "📒 Portföy Defteri" butonu).
Veri: `docs/defter/data/defter.json` (PORTFOLIO_KEY ile şifreli). İşlem listesi: `docs/defter/data/islem.json` (şifreli, ayrı; sayfa İşlemler sekmesi açılınca yükler, dosya yoksa eski `islem` anahtarına döner). Durum: `docs/defter/data/status.json`.
Kod: `scripts/defter.py`, iş akışı: `.github/workflows/defter.yml`.

| Hesap | Para | Kaynak | Not |
|---|---|---|---|
| Midas-TR | ₺ | otomatik: `docs/bist/data/history.json` snapshot | v = toplam − yedek (90.000) |
| Info-TR | ₺ | otomatik: `defter/info_portfolio.json` pozisyonları × `bars-bist.json` tarihli günlük kapanış (`BIST_BARS_JSON`; yoksa yalnız kapalı piyasada ve hedef gün beklenen son seans ise canlı kotasyon, aksi hâlde yazılmaz + `status.json` diag) | yedek 25.000; işlem: Info-TR Pozisyon Güncelle |
| Midas-USD | $ | otomatik: `docs/data/history.json` snapshot | seri 2025-10-14'te başlar |
| IBKR | $ | IBKR Flex (secret: IBKR_FLEX_TOKEN, IBKR_FLEX_QUERY_ID), 09:15 İst.; yoksa elle | seri 2026-04-17; Excel günlerinin üstüne yazmaz |

- Alanlar: v performans tabanı, h hisse değeri, c günlük değişim (akış ayıklanmış), f para akışı, r yedek, s kaynak (x Excel, a oto, m elle), n not.
- Excel geçmişi 2020-10-01 → 2026-10-16 aktarıldı (Excel'deki c değerleri aynen korunur; sonraki günler c = Δtoplam − akış).
- Endeksler: XU100 (Excel + Yahoo/TradingView), S&P kıyası **SPY** (Twelve Data). Yahoo GitHub'dan sık 429 veriyor.
- Zaman: hafta içi 22:20 UTC oto kayıt; Cumartesi 07:10 UTC Excel + haftalık özet (ana Telegram botu).
- Claude → repo şifreli veri: `defter/box_pub.pem` ile `scripts/defter.py:box_seal` → `defter/inbox/*.box.json`, sonra iş akışı `ice_aktar`.
  Özel anahtar `defter/box_key.json` (PORTFOLIO_KEY ile şifreli). Düz tutar asla commit edilmez.
- 2026-10-18: 16.09.2026 Midas-TR değişimi −41.063 → −21.063 (yedek 70k→90k iç ayrım). Diğer yedek değişim günleri gerçek para hareketi; dokunulmadı.
- 2026-10-18: Info-TR pozisyonları repoda (defter/info_portfolio.json, şifreli; 6 hisse + nakit). Değer her gece `oto` içinde
  BIST fiyatlarıyla hesaplanır (v = toplam − 25.000 yedek). İşlem girişi: `.github/workflows/info-pozisyon.yml` (buy/sell/deposit/withdraw/undo).

## Davranış kuralları (P2)

- **Tamamlanmış seans:** `oto` her piyasa için son tamamlanmış seans gününe yazar (BIST İst. 18:15, ABD New York 16:15 sonrası; `last_session`/`target_day`, tatil modellenmez). Seans ortasında gelen çalışma bitmemiş güne yazmaz, "snapshot yok" uyarısı göndermez. `--date` geçmişi doldurur; Info-TR yalnız hedef güne yazılır (pozisyonlar bugünküdür).
- **Akış:** `flows_on` geri alınan (`undone`) hareketi saymaz; her `oto` son 60 günün otomatik (s=a) Midas kayıtlarında `f`'yi geçmişten yeniden türetir (`fm` korunur), Excel/elle kayda dokunmaz.
- **Grup toplamı:** kaydı olmayan hesap son bilinen değeriyle toplanır (başlangıcından sonra); günlük değişim/% yalnız gerçek kayıtlardan. Kural Python `carry_group` ile sayfa `build()` içinde aynıdır; sayfada "IBKR: 11.11 değeri" ve ↺ işareti, Excel/Telegram aynı rakam.
- **Yazma:** `save` içerik (`updated` hariç) değişmediyse defter.json ve status.json yazmaz; `islem.json` yalnız içerik (`at` hariç) değişince yazılır; `defter.py islemler` yalnız islem.json'a dokunur.
- **USD/TRY:** günlük kapanış gün kaydında `fx` (Yahoo `USDTRY=X`; yedek TradingView yalnız son tamamlanmış BIST seansı; günlerin yarısından azında fx varsa tüm geçmiş bir kez çekilir). Sayfa: "TOPLAM SERVET" kartı (₺ ve $), TL grafiğinde "TL hesaplar ($ bazında)" çizgisi; eksik gün son kurla, hiç kur yoksa gizli. Excel Günlük sayfasında "USD/TRY" sütunu.
- Tarayıcıda Excel dışa aktarma ve Google Fonts kaldırıldı; sayfa yalnız `telegram.org/js/telegram-web-app.js` yükler (Dağılım modu repodaki `defter/info_portfolio.json`'ı raw.githubusercontent.com'dan veri olarak çeker).
