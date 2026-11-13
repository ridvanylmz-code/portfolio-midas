---
name: "portfoy-guncelle"
description: "ABD hisse güncellemesi: yalnız Portföy_Midas projesinde ya da açıkça \"ABD güncelle\" dendiğinde kullan. Bist_Takip projesinde \"güncelle\" BIST demektir; orada bist-guncelle kullanılır."
---

# ABD Analiz Güncellemesi

Önce proje kontrolü: oturum Bist_Takip projesine bağlıysa ve kullanıcı açıkça "ABD" demediyse bu beceriyi kullanma; `bist-guncelle` kullan.

Dil: Türkçe, kısa, uygulanabilir. Basit tablolar. Sade Türkçe terimler ("yükselen hisse oranı", "taranan hisseler").

## Kapsam
- Yalnızca ABD piyasası. BIST bu skill'in kapsamında değil.
- Portföy tutarları (adet, maliyet, K/Z, nakit oranı) okunmaz ve hesaplanmaz. portfolio.json şifrelidir; K/Z ve nakit mini uygulamada kullanıcının kendi şifresiyle hesaplanır.
- Eldeki pozisyonların **yalnızca sembolleri** `docs/data/holdings.json` dosyasından okunur (`{"updated", "holdings": [...]}`). Dosya yoksa veya 7 günden eskiyse pozisyon hatırlatmasını atla ve bunu veri eksikliği olarak yaz. Pozisyon uydurma.
- Kesin kısıtlar: yalnız spot; short, kaldıraç, opsiyon yok; banka hisseleri ve alkol üreticisi şirketler yok.

## Dil (zorunlu, haftalik-teknik-analiz ile ortak)
Kullanıcıyla ortak gibi doğrudan konuş; kaçamak ifade ve "yatırım tavsiyesi değildir" satırı kullanma. Al-sat önerileri **porsiyon dilinde** yazılır: tam pozisyon = 4 porsiyon, 1 porsiyon = 1/4. Kalıplar: "1 porsiyon al", "1 porsiyon sat", "1 porsiyon daha sat", "sattığını geri al", "1 porsiyon çekirdek sat", "kenardaki porsiyonu al", "yarım porsiyon". Adet ve tutar yazılmaz; porsiyon göreli bir birimdir.

## 0. Repo bağlantısı
1. Oturumda repo yoksa `add_repo` ile `ridvanylmz-code/portfolio-midas` ekle (`access: push`). Ardından çalışma dizinine clone et.
2. Push izni reddedilirse okuma için herkese açık clone yeterlidir. Bu durumda yazma adımlarını yapma; değişiklikleri yalnız değişen kısım olarak ver ve raporun ilk satırına "repo güncellenmedi: push izni yok" yaz.

## Veri kaynağı
1. `git fetch origin market-data` ve `git show FETCH_HEAD:market.json`. Rejim, sektör puanları ve picks buradan gelir.
2. market.json'un `updated` alanını oku. 24 saatten eskiyse raporun ilk satırında açıkça yaz; eski veriyle "al" önerme.
3. Haber ve momentum yorumu için TradingView connector'ı tek toplu çağrıyla kullan. Her fiyatın tarihini ve seansını yaz.

## Adımlar
1. Rejim ve nakit: rejim etiketini ve puanı yaz. Direktifi "nakit %X-Y bandında olmalı" biçiminde ver. Düşüş rejiminde üst banda, yükselişte alt banda yaklaş.
2. Sektör yorumu: `docs/data/sector_notes.json` içinde lider ve zayıf sektörleri haber ve momentum gerekçesiyle güncelle. Her not tarihli olsun.
3. Aday seçimi ve takip listesi: `takip-listesi-tarama` skill'ini Skill aracıyla yükle ve uygula.
4. Hisse yorumu: `docs/data/analysis.json` içinde yalnızca güncellenen hisseler için adil değer, teknik yorum ve `dilution` alanını yaz.
5. Pozisyon kontrolü: `holdings.json` içindeki her sembol için günlük kapanışı EMA20/EMA50 ve picks/technicals içindeki stop ile karşılaştır. Momentumu kırılanı porsiyon diliyle tek satırda yaz (örn. "SGML: kapanış EMA50 altında, 1 porsiyon sat; 9,10 üstüne dönerse sattığını geri al").
6. Değişiklikleri commit edip push et. Commit mesajı Türkçe ve kısa.
7. Yazma başarısızsa bunu raporun başında yaz ve kalan yazma adımlarını atla.

## Çıktı
En fazla 5 içerik maddesi:
1. Veri tazeliği ve eksikler
2. Rejim ve nakit bandı
3. Öne çıkan ve zayıf sektörler
4. Takip listesinin son hali ve bu güncellemede değişen hisseler (gerekçesiyle)
5. Momentumu kırılan pozisyonlar, porsiyon diliyle (yoksa "yok")

Madde sayısına girmeyen ek satırlar: Kaynaklar ve DEVAM.md için tek satır.

## Yasak
- Pozisyon, adet, tutar uydurmak
- Veri eskiyken "al" önermek
- Porsiyon dili dışında belirsiz al-sat ifadesi ("düşünülebilir", "değerlendirilebilir")