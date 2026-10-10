# Aşama 3 — kontrol noktası (oturum kesilirse buradan devam)

Başlangıç: 2026-10-10 22:33 İstanbul. İstek: 3. aşamayı tamamla + sektör analizine "o sektörde alınabilecek 3 hisse".
Önceki aşamalar: notes/ASAMA2.md (bitti). Portföy şifreli (PORTFOLIO_KEY); testlerde 0a46479'daki düz kopya kullanılır.

## Plan ve durum
- [ ] 1. Sektör başına 3 hisse: market.py büyük tarama (piyasa değeri > 3 mlr $, tek istek) + tema aday listeleri; banka/alkol hariç; UI'da göster
- [ ] 2. Günlük mumlar (bars.json, market-data dalı; Alpaca → Twelve Data) — Teknik sekmesindeki grafik için
- [ ] 3. Teknik sekmesi: tek sinyal matrisi (Günlük/Haftalık/4s/15dk) + grafik (EMA20/SMA50, stop/hedef, ATR stop) + kısa yorum, sözlük açılır
- [ ] 4. Portföy kartları: trend etiketi, ağırlık, stop–fiyat–hedef çubuğu; alt bilgi menü arkasında kalmasın; Takip sekmesi zenginleşsin
- [ ] 5. Dashboard (index.html): koyu tema varsayılan, Türkçe sayı biçimi, kart renklendirme sadece stop kırılınca, "momentuma göre" = RS, duvar yazısı en alta  [alt ajan]
- [ ] 6. Trend sayfası: mobil kart görünümü, Türkçe etiketler, sıralama, Günlük trend + RS sütunu, Yeni sütunu kesilmesin  [alt ajan]
- [ ] 7. Telegram raporu: rejim + nakit hedefi + lider sektörler satırı
- [ ] 8. Test, push, canlı çalıştırma, rapor

## Notlar
- 1 (veri) ✔ market.py build_picks + tvscan.screen + universe.json picks (yerel test ok). Canlı tarama doğrulanacak; UI henüz yok.
- 5-6 ✔ alt ajan bitirdi (docs/index.html, docs/trend/index.html) — gözden geçirme bekliyor.
