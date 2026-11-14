# Midas Dip-Tepe göstergesi

Kod: `tradingview/midas_dip_tepe.pine` (TradingView hesabında "Midas Dip-Tepe" adıyla kayıtlı).
Kapsam: RKLB, CRWV, SGML, WYFI, UAMY (TradingView'de `NYSE:UAMY`); 15 dakikalık ve 4 saatlik grafik. Aynı ayar hepsinde çalışır.

## Ekranda ne var

| Öğe | Anlamı |
|---|---|
| Yeşil ▲ / kırmızı ▼ ok | Erken dip / tepe adayı. Mum kapanışında kesinleşir, sonradan silinmez. |
| Kesik çizgili kutu | Canlı aday bölge. Fiyat yeni dip/tepe yaparsa kutu silinir (aday bozuldu). |
| Düz çizgili kutu | Teyit edilmiş dip/tepe (yılan renk değiştirdiğinde geriye dönük çizilir). |
| Yılan (yeşil/kırmızı çizgi) | Salınım yönü. Renk değişimi = fiyat uçtan 4 ATR döndü, dönüş teyitli. |
| Köşedeki "4s ▲/▼" | 15 dakikalık grafikte 4 saatlik salınımın yönü. |

## Kural

Fiyat son uçtan 0,5 ATR dönünce ok çıkar; koşul, önceki dönüş noktasından en az 3 ATR uzaklaşılmış olması.
Her yeni dip/tepe oku yeniden kurar. Fiyat uçtan 4 ATR dönünce yılan renk değiştirir.
Okun bozulma seviyesi kutunun dış kenarıdır (dipte kutunun altı, tepede üstü).

## Test (her hissede son 600 mum, 14.11.2026)

Ölçüt: "büyük dönüş" = en az 4 ATR'lik salınımın dibi/tepesi. "İsabetli ok" = sonraki bacağın ilk üçte birinde gelen ok.

| Periyot | Hisse | Ok | Büyük dönüş | Yakalanan | İsabetli ok |
|---|---|---|---|---|---|
| 4s | RKLB | 66 | 18 | %100 | %52 |
| 4s | CRWV | 84 | 27 | %96 | %48 |
| 4s | SGML | 79 | 18 | %94 | %56 |
| 4s | WYFI | 75 | 24 | %92 | %38 |
| 4s | UAMY | 75 | 22 | %82 | %39 |
| 15dk | RKLB | 67 | 21 | %90 | %48 |
| 15dk | CRWV | 64 | 23 | %83 | %42 |
| 15dk | SGML | 76 | 29 | %83 | %45 |
| 15dk | WYFI | 75 | 23 | %87 | %51 |
| 15dk | UAMY | 57 | 21 | %86 | %52 |

İlk isabetli ok ortalama olarak dönüş mumunda veya bir mum sonra gelir ve sonraki bacağın yaklaşık %80'ini bırakır.

## Sınırlar

- Okların yaklaşık yarısı erkendir: ardından yeni dip/tepe gelir. Ok tek başına emir değildir; kutu bozulursa aday geçersizdir.
- 2 ATR kazanç / 1 ATR zarar ölçüsüyle okların tek başına bir üstünlüğü yok (%34–37; rastgele beklenti %33).
- Hisseye özel ayar denendi, ileriye dönük testte tutmadı (4s: hisseye özel 0,56, ortak ayar 0,63 F1). Bu yüzden tek ayar kullanılıyor.
- Test TradingView'in normal seans verisiyle yapıldı. Grafikte seans dışı mumlar açıksa ATR ve ok yerleri biraz farklı olur.

## Denenen diğer yöntemler (aynı ölçüt)

Repodaki trend yöntemleri dip/tepe yakalamada en zayıf çıktı: EMA 34/89, EMA 8/20 ve Supertrend(10,2) dönüşten 4–22 mum sonra sinyal veriyor (F1 0,01–0,25). Bunlar yön teyidi için uygun, dip/tepe için değil.
Aşırılıktan dönüş yöntemleri (dip süpürme-geri alma, Williams %R, RSI, Bollinger, z-skoru, StochRSI, CCI, WaveTrend, TD9, RSI uyumsuzluğu) 0,40–0,62 arasında kaldı; birkaçını birleştirmek isabeti artırmadı.

## Alarm

Grafikte göstergeyi aç → Alarm → Koşul: "Midas Dip-Tepe" → "Herhangi bir alert() fonksiyon çağrısı". Hisse ve periyot başına bir alarm; dip adayı, tepe adayı ve iki teyit mesajı aynı alarmdan gelir.
