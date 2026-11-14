# teknik/ — Haftalık teknik analiz kodu (yöntem v2.4)

Haftalık akış: [`OTURUM.md`](OTURUM.md). Tek çalıştırıcı: `python3 teknik/haftalik.py {veri,puan,analiz,yayinla,alarm-sil}`.

| Klasör | İçerik |
|---|---|
| `kod/` | Hesap modülleri (lib, eng, ind/indb, struct_, run/runb, v1t, veri, puan, pine, yayinla). 14.11.2026'da Projeden (`claude/kod/`) taşındı; değişiklikler artık burada |
| `cfg/` | Haftaların referans noktaları (`abd_YYYYMMDD.py`, `bist_YYYYMMDD.py`) |
| `veri/` | **Tek doğru kaynak** (adetsiz): `bolgeler.csv`, `pencereler.csv` (eski), `cizgiler.csv`, `pano_seviyeler.json`, `pano_tahminler.json`, `karne_<pazar>.txt`, `alarmlar.json`, `defter_dizin.json`. Repo panosu: `docs/teknik/data/` |
| `is/` | Çalışma klasörü (git dışı): veri, loglar, plan, Pine, alarm listesi, adetli salınım, defter bölümü |

**Gizlilik:** repo herkese açık. Adet, nakit ve "gerçek durum" yalnız `is/` içinde ve Projedeki haftalık defter dosyasında (`claude/defter/`). Artifact pano repodaki adetsiz dosyaları kullanır.

`bt.py` (2 yıllık test) Projede (`claude/kod/bt.py`) duruyor; haftalık akışta gerekmez.

## Değişiklik günlüğü

- 14.11.2026: Kod Projeden repoya taşındı; `haftalik.py` (veri / puan / analiz + otomatik salınım önerisi / yayinla / alarm-sil) eklendi. Hesap modülleri değişmedi; `haftalik.py` öneri kuralları yöntem bölüm 10 ile aynı (sigorta 1,5 ATR kaydırması, Savunmada yalnız KRİTİK geri alım, çekirdek stop = geri alım bölgesinin altındaki KRİTİK destek − 0,15 ATR). 14.11 ABD analiziyle karşılaştırıldı: bölgeler, karne, sigorta ve stoplar aynı; B hedefleri otomatik seçimde ilk destek bölgesi.
- 15.11.2026: Tek kaynak: Projedeki pano JSON kopyaları kaldırıldı, artifact pano repodaki dosyaları asset olarak alır. `puan` birikimli karneyi `veri/karne_<pazar>.txt`'ye yazar. `yayinla` kısa `tahmin_defteri.md` ve `izleme_listesi.md` üretir (Proje); `veri/alarmlar.json`, `veri/defter_dizin.json` eklendi. `pozisyon` alt komutu (gh ile iş akışı günlükleri). `OTURUM.md` kural özetiyle 2 sayfalık kart oldu.
