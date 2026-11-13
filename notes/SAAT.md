# Saat - zamanlayıcı

## Nedir
GitHub'ın `schedule` olayları bu depoda ~8 saat geç geliyor ve çoğu düşüyor (denetim B1); `workflow_dispatch` ise saniyeler içinde başlıyor. `.github/workflows/saat.yml` tek uzun çalışmadır: `scripts/saat.py` her dakika hangi işin zamanı geldiğine bakar ve diğer iş akışlarını `gh workflow run <dosya> --ref <dal> -f mode=auto` ile tetikler. Tablo betiğin başındaki `ENTRIES` listesindedir (piyasanın kendi saat diliminde; tatil takvimi yok, borsa tatilinde iş akışları kendi kontrolüyle sessiz kalır). Diğer iş akışlarındaki `schedule:` satırları şimdilik yedek olarak duruyor.

## Başlatma
Dalı main'e birleştirdikten sonra bir kez: GitHub -> Actions -> "Saat - zamanlayıcı" -> Run workflow. Sonrası kendi kendine sürer: 5 sa 30 dk sonra kendini yeniden tetikleyip çıkar; saatlik yedek cron (dakika 7) takılırsa yeniden başlatır.

## Çalıştığını görmek
- Actions -> "Saat - zamanlayıcı": çalışan bir kayıt olmalı; günlükte her tetikleme için bir satır (`tetiklendi: monitor.yml`) ve 15 dakikada bir `çalışıyor` satırı vardır.
- Diğer iş akışlarında olay türü "workflow_dispatch" görünür ve seans saatlerinde 15/30/60 dk aralıkla başlar.
- Yerelde deneme (gh çağrılmaz): `python scripts/saat.py --dry-run --now 2026-11-13T15:00:00Z`.

## Durdurma
Çalışan "Saat - zamanlayıcı" kaydını Cancel edin ve `saat.yml` dosyasındaki `schedule:` bloğunu silin ya da Actions'ta iş akışını Disable edin (yoksa saatlik cron yeniden başlatır). Beklemedeki kaydı da iptal edin.

## Bilinen sınırlar
- Bir çalıştırıcı sürekli meşgul. Herkese açık depoda dakika kotası sorun değil; depo özel yapılırsa saat sürekli çalıştığı için kotayı tüketir, o durumda dış zamanlayıcıya geçin.
- GitHub kendi yeniden tetiklememizi de geciktirirse saatlik cron devralır; arada boşluk kalabilir.
- Devir anında yeni saat o anki ızgara noktasını yeniden tetikler (bellekte durum yok): bir kez çift çalışma olur; concurrency grupları ve rapor tekilleştirmesi (state.json) bunu zararsız kılar. Günlük işler (IBKR, trend 03:15, Excel) saatinden 90 dakikadan sonra yeniden başlayan saatte o gün atlanır.
- Üretimde denenmedi: `gh workflow run` ve `GITHUB_TOKEN` ile dispatch yetkisi birleştirmeden sonra ilk çalışmada doğrulanmalı.

## Alternatif: dış zamanlayıcı
Aynı tetikleme dışarıdan da yapılabilir (ör. Cloudflare Workers Cron): `POST https://api.github.com/repos/<sahip>/<depo>/actions/workflows/<dosya>/dispatches` gövde `{"ref":"main","inputs":{"mode":"auto"}}`, başlıkta `Authorization: Bearer <actions:write yetkili token>`. İş akışı kodu aynı kalır; zaman tablosu zamanlayıcıya taşınır ve `saat.yml` kapatılır.
