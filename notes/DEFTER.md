# Portföy Defteri — devir notu

4 hesabın günlük kaydı. Sayfa: `docs/defter/index.html` (mini uygulamalarda "📒 Portföy Defteri" butonu).
Veri: `docs/defter/data/defter.json` (PORTFOLIO_KEY ile şifreli). Tutarsız durum: `docs/defter/data/status.json`.
Kod: `scripts/defter.py`, iş akışı: `.github/workflows/defter.yml`.

| Hesap | Para | Kaynak | Not |
|---|---|---|---|
| Midas-TR | ₺ | otomatik: `bist/history.json` snapshot | v = toplam − yedek (90.000) |
| Info-TR | ₺ | otomatik: `defter/info_portfolio.json` pozisyonları × BIST fiyatı | yedek 25.000; işlem: Info-TR Pozisyon Güncelle |
| Midas-USD | $ | otomatik: `history.json` snapshot | seri 2025-10-14'te başlar |
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
