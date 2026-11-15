# Midas Dip-Tepe göstergesi

Kod: `tradingview/midas_dip_tepe.pine` (TradingView hesabında "Midas Dip-Tepe" adıyla kayıtlı).
Kapsam: ABD (RKLB, CRWV, SGML, WYFI, `NYSE:UAMY`) ve BIST (BIENY, SASA, SMRTG, MIATK, THYAO, TCELL, ALTIN, GMSTR); 15 dakikalık ve 4 saatlik grafik. Aynı gösterge ve aynı ayar hepsinde çalışır.

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

## Test — ABD (her hissede son 600 mum, 14.11.2026)

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

## Test — BIST (her hissede son 600 mum, 15.11.2026)

Aynı ölçüt, aynı ayar (4 / 0,5 / 3).

| Hisse | 4s: ok | 4s: büyük dönüş | 4s: yakalanan | 4s: isabetli ok | 15dk: ok | 15dk: büyük dönüş | 15dk: yakalanan | 15dk: isabetli ok |
|---|---|---|---|---|---|---|---|---|
| BIENY | 68 | 22 | %82 | %46 | 78 | 20 | %80 | %27 |
| SASA | 61 | 18 | %94 | %47 | 39 | 12 | %75 | %29 |
| SMRTG | 61 | 19 | %89 | %47 | 65 | 18 | %83 | %41 |
| MIATK | 60 | 22 | %82 | %54 | 58 | 22 | %73 | %46 |
| THYAO | 72 | 14 | %71 | %43 | 69 | 13 | %92 | %33 |
| TCELL | 61 | 18 | %89 | %47 | 55 | 17 | %88 | %47 |
| ALTIN | 70 | 25 | %76 | %45 | 64 | 27 | %67 | %41 |
| GMSTR | 74 | 23 | %74 | %35 | 65 | 16 | %88 | %45 |

- 4 saatlikte sonuç ABD ile aynı düzeyde. 15 dakikalıkta BIST daha zayıf; BIENY, SASA ve THYAO'da okların yalnız üçte biri isabetli.
- SASA 15 dakikalıkta ATR yalnız 1,5 fiyat adımı (ALTIN'da 2,3): fiyat basamaklı hareket ettiği için sinyal gürültülü. SASA için 4 saatlik kullanılmalı.
- Hisseye özel ayar BIST'te de ileriye dönük testte tutmadı (4s: özel 0,51, ortak 0,58; 15dk: özel 0,44, ortak 0,47 F1). 80'den fazla yöntem/ayar arasında en iyi çıkan yine bu gösterge; repodaki EMA kesişimleri ve Supertrend(10,2) dönüşten 7–26 mum sonra sinyal verdi (F1 0,06–0,26).

## Kullanım stratejisi

Okların yaklaşık yarısı erken gelir; bu yüzden plan "küçük gir, kutu bozulursa çık, yılan teyit edince tamamla" üzerine kuruludur. Bu kurallar göstergenin mantığından türetildi; bütün olarak geriye dönük test edilmedi.

Alım:
1. Yeşil ok + kesik yeşil kutu: 1 porsiyon al. Bozulma seviyesi kutunun alt kenarı.
2. Kutu silinirse (yeni dip): o porsiyonu sat, sonraki yeşil oku bekle. Aynı düşüşte 3 ok bozulduysa denemeyi bırak, yılanın yeşile dönmesini bekle.
3. Yılan yeşile dönerse (kutu düz çizgili olur): 1 porsiyon daha ekle, stopu teyitli kutunun altına al.

Satış:
1. Kırmızı ok + kesik kırmızı kutu: 1 porsiyon sat.
2. Kutu silinirse (yeni tepe): yükseliş sürüyor, elindekini tut; sonraki kırmızı okta yine 1 porsiyon sat.
3. Yılan kırmızıya dönerse: ticaret porsiyonlarının kalanını sat; yeni yeşil ok gelene kadar alım yok.

İki periyot birlikte: 4 saatlik yönü, 15 dakikalık giriş yerini verir. Köşedeki "4s ▲" iken 15 dakikalık yeşil oklar alım, kırmızı oklar yalnız kısmi kâr içindir. "4s ▼" iken 15 dakikalık yeşil oklar tepki alımıdır (yarım porsiyon). Ok ancak mum kapanışında kesinleşir.

## Ayarlar: ne zaman değiştirilir

Varsayılan (4 / 0,5 / 3 / ATR 14) test edilen 13 hissenin ortak en iyisidir; normalde değiştirme.

| Durum | Değişiklik | Testteki etkisi |
|---|---|---|
| Çok fazla ok, ekran kalabalık | "Erken ok dönüşü" 0,5 → 0,75 | BIST 4s: ok sayısı 66 → 57, isabetli ok %45 → %47, yakalanan dönüş aynı |
| Yalnız büyük salınımlar isteniyor | "Salınım eşiği" 4 → 5 | Yılan daha seyrek döner; BIST 4s: ok 66 → 54, yakalanan dönüş %82 → %69 |
| Küçük salınımlar da isteniyor | "Salınım eşiği" 4 → 3 | BIST 4s: ok 66 → 84, isabetli ok %45 → %40 |
| Yatay/dar bantta gereksiz ok | "En küçük bacak" 3 → 5 | BIST 4s: ok 66 → 57, yakalanan dönüş %82 → %73 |
| ATR uzunluğu | Değiştirme | 10, 14, 21 arasında fark yok |

Ayarı bir hissede geçmişe bakarak "en iyi görünen" değere çekmek işe yaramaz: testte geçmişte en iyi görünen hisseye özel ayar, sonraki 300 mumda ortak ayardan kötü çıktı.

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
