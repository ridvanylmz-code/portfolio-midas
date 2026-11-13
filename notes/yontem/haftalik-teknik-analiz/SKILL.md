---
name: "haftalik-teknik-analiz"
description: "Rıdvan'ın haftalık detaylı teknik analizi (yöntem v2.3: Fibonacci ailesi, Elliott, rejim filtresi, göreli güç, çapalı VWAP, EMA21/34/89/144/233, momentum, zaman, puanlı kesişim bölgeleri, puan.py ile nesnel puanlama) istendiğinde: veriyi çek, analiz et, Pine göstergesiyle bölgeleri çiz, alarm kur, tahmin defterini ve panoyu güncelle."
---

# Haftalık Teknik Analiz — Yöntem v2.3

Son güncelleme: 13.11.2026 (v2.3). Önceki: 07.11.2026 v2.2, 30.10.2026 v2.1, 29.10.2026 v2, 21.10.2026 v1.

**Kural dondurma:** 13.11.2026 – 08.01.2027 arası kurallar değiştirilmez; değişiklik ancak en az 20 puanlanmış örnek ve puan.py şans karşılaştırmasıyla.

## Tek kaynak kuralı (zorunlu)

Yöntemin tam ve güncel metni Projedeki **`claude/haftalik-teknik-analiz-yontemi.md`** dosyasıdır. Her analizin başında bu dosyayı `project_read` ile oku ve **bölüm 0–11 ile kontrol listesini aynen uygula**. Bu SKILL.md yalnız giriş noktasıdır; **çelişki olursa her zaman proje dosyası geçerlidir** (13.11.2026 itibarıyla v2.3).

- `references/` klasöründeki `grafik-cizim.md`, `pano.md`, `salinim.md` **v1 dönemine aittir, kullanma**. Çizim, pano ve salınım kuralları yöntem dosyasının 5, 8 ve 10. bölümlerindedir.
- Hesaplar Projedeki `claude/kod/` betikleriyle yapılır (kurulum ve sıra: `claude/kod/README.md`). Kodu yeniden yazma; kural değişirse ilgili dosyayı düzeltip Projeye geri yaz, README değişiklik günlüğüne satır ekle.
- v1 kuralları (EMA20/50/200, ölçekli dokuzun karesi, Gann açıları, 3 aile eşiği, en fazla 3 bölge) yalnız karşılaştırma için `claude/kod/v1t.py` içinde yaşar.
- Proje bağlı değilse (Projects aracı yoksa) kullanıcıya bunu tek satırla söyle ve aşağıdaki özet kurallarla çalış; kayıtları sona bırakıp kullanıcıya ver.

## Başlangıç sırası

1. Projeden oku: `claude/haftalik-teknik-analiz-yontemi.md`, `claude/izleme_listesi.md`, `claude/tahmin_defteri.md`, `claude/salinim_stratejisi.md`.
2. Önce geçen haftanın tahminlerini `claude/kod/puan.py` ile nesnel puanla (bölge tepkisi/kırılımı ve zaman pencereleri, 500 tekrarlı şans karşılaştırması; elle ✓/½ yok), kullanıcıya 3–5 satırlık karne göster.
3. Sonra yöntem dosyasındaki sırayla analiz, çizim, alarm, kayıt ve pano.

## Genel tarz

Türkçe, kısa, uygulanabilir; takip için basit tablolar. "Yatırım tavsiyesi değildir" satırı ekleme; riskleri analizin içinde yaz. Doğrudan, porsiyon diliyle konuş ("1 porsiyon sat", "sattığını geri al"); bu dil `portfoy-guncelle` ve `takip-listesi-tarama` ile ortaktır. Zamanlanmış görev kurma; kullanıcı her çalışmayı kendisi başlatır. Gereksiz onay doğuracak araç çağrısı yapma; panoyu okuma, veriyi proje kopyasından al.

## v2.3 farkları (13.11.2026)

- Puanlama nesnel: `puan.py` (yöntem 7a). Olasılık yüzdesi yazılmaz; B seviyeleri önce yazılır (4c).
- Çizim önce Pine göstergesi "Claude Kesişim Bölgeleri" (`claude/kod/pine.py` → MCP update-pine-script); Chrome yalnız Elliott etiketi ve yol için yedek (bölüm 5).
- Salınım satırlarında `tip` alanı zorunlu (sat/al/sigorta/stop/yedek/uyari/not); B hedefi `uyari`.
- S2 ertelemesi en fazla bir kez, 5 işlem günü son sınır.
- Haftalık plan bağlayıcı; repo günlük analizi ve 15 dk Pine alarmı bilgi amaçlı (bölüm 12).
- Plan dışı alım ve bilanço kuralı kullanıcı kararıdır; Claude yalnız kaydeder ve önerir.

## v2.2 özet kuralları (07.11.2026, v2.3'te de geçerli)

**Kesişim bölgesi oluşturma:**

- Seviyeler fiyata göre sıralanır; birbirine **0,3 × ATR(14)** veya %1,5 (hangisi büyükse) mesafedekiler kümelenir.
- Bölge genişliği **en fazla 0,4 ATR** (v2.1: 0,6). Aşarsa en yüksek puanlı 0,4 ATR'lik alt gruba bölünür; kalanlar ayrı gruplar olarak yeniden değerlendirilir. Bölgeler kuralın ürettiği sınırlarla yazılır, elle daraltma yok. Kodda: `eng.py` → `cluster(..., wmax=0.4)`.
- Puanlama v2 aynen: geometri tavanı 3 puan; uzatma + B aynı seviyede 2 puan; aynı pivot tek aile; ÖNEMLİ ≥ 3 puan ve ≥ 1 bağımsız aile; KRİTİK ≥ 4 puan ve ≥ 2 bağımsız aile; KRİTİK küme 0,3 ATR'den darsa kritik nokta; zaman bonusu +0,5; rejim düzeltmesi puanlamadan sonra.
- Stop, dayandığı bölge sınırının en az 0,15 ATR ötesinde.

**v1 karşılaştırması sürüyor:** Her analizde v1 bölgeleri de üretilir (kullanıcıya gösterilmez), tahmin defterine hisse başına tek satır yazılır ve karnede "v1 / v2.2 bölge isabeti" satırında karşılaştırılır. Kullanıcı bırak diyene kadar devam eder; v2.2'ye geçişten sonraki ilk 3 analizin sonunda kısa sonuç verilir. Tahmin defterinde ve panoda `surum` alanına "v2.2" yazılır; karne isabeti sürüme göre ayrı gösterir.

**Grafik çizimi (TradingView, layout Günlük_2) — v2.3'te birincil yol Pine göstergesidir; aşağıdaki stil hem Pine hem Chrome yedeği için geçerli:**

| Nesne | Kenar çizgisi |
|---|---|
| KRİTİK bölge, kritik nokta, ÖNEMLİ bölge | **kesikli** (`linestyle: 2`) |
| İzleme bölgesi, rejimle düşürülmüş bölge | **noktalı** (`linestyle: 1`) |
| Zaman bandı | kesikli, `#5c6bc0`, şeffaflık 90 |

Renkler: KRİTİK turuncu dolgu `#ff9800`, ÖNEMLİ sarı `#fbc02d`; destek rolü yeşil `#26a69a`, direnç rolü kırmızı `#ef5350` kenar; dolgu şeffaflığı ~%85–90. Hisse başına en fazla 5 bölge ve ~12 nesne. Kullanıcının mevcut çizimlerine asla dokunma; iş bitince grafiği başlangıç sembol/zaman dilimine geri getir ve "Kaydet" hatırlat. Ayrıntılar yöntem dosyası bölüm 5.

## Kayıt

Analiz sonunda `claude/tahmin_defteri.md`, `claude/izleme_listesi.md` ve pano JSON kopyalarını Projeye doğrudan yaz, panoyu güncelle (yöntem dosyası bölüm 7–8). Kullanıcıdan dosya yüklemesini isteme.