#!/usr/bin/env python3
"""Haftalık teknik analiz emir planı için Telegram bildirimi (docs/teknik/data).

Kullanım: python scripts/teknik_bildirim.py us|bist [--dry]
- Plan: docs/teknik/data/salinim.json (Claude haftalık analizden sonra yazar; adet içermez).
- ATR ve plan tarihi: docs/teknik/data/meta.json.
- Fiyat: izleme iş akışının yeni yazdığı quotes.json (us: docs/data, bist: docs/bist/data).
- Durum: docs/teknik/data/bildirim_durum_<pazar>.json (aynı bildirim tekrar gitmesin).

Bildirimler (common.send_telegram; iş akışında giden kutusuna yazılır, push sonrası gönderilir):
  🔔 yaklaştı  : fiyat bir emre 0,5 ATR'den yakın (emir başına günde bir kez)
  ✅ geçti     : fiyat seviyeyi geçti (satış/sigorta yukarı, alış/stop/uyarı aşağı; yön değişince bir kez)
  Kapanış koşullu emirlerde (sigorta, çekirdek stop) mesaj "karar günlük kapanışta" der.
Plan 14 günden eskiyse bildirim gönderilmez; günde bir kez "plan eski" notu gider.
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

D = common.ROOT / "docs" / "teknik" / "data"
QUOTES = {"us": common.ROOT / "docs" / "data" / "quotes.json", "bist": common.ROOT / "docs" / "bist" / "data" / "quotes.json"}
CUR = {"us": "$", "bist": "₺"}
YUKARI = {"sat", "sigorta"}           # fiyat yukarı geçince tetiklenir
KAPANIS = {"sigorta", "stop"}
AD = {"sat": "Sat", "al": "Geri al", "sigorta": "Sigorta", "stop": "Çekirdek stop", "yedek": "Kenardaki", "uyari": "Uyarı"}
ESKI_GUN = 14


def oku(p, varsayilan):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return varsayilan


def fiyat_al(q):
    if not q:
        return None
    ext = q.get("ext") or {}
    p = ext.get("p") if ext.get("sess") in ("pre", "post") else None
    p = p or q.get("c")
    try:
        p = float(p)
    except (TypeError, ValueError):
        return None
    return p if p > 0 else None


def f2(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("pazar", choices=["us", "bist"])
    ap.add_argument("--dry", action="store_true", help="göndermeden yazdır, durumu kaydetme")
    a = ap.parse_args(argv)
    plan = oku(D / "salinim.json", [])
    meta = oku(D / "meta.json", {}).get("hisseler", {})
    quotes = oku(QUOTES[a.pazar], {}).get("quotes", {})
    durum = oku(D / f"bildirim_durum_{a.pazar}.json", {})
    bugun = date.today().isoformat()
    satir, eski = [], []
    for h, m in sorted(meta.items()):
        if m.get("pazar") != a.pazar:
            continue
        p = fiyat_al(quotes.get(h))
        atr = float(m.get("atr") or 0)
        if p is None or atr <= 0:
            continue
        yas = (date.today() - date.fromisoformat(m.get("plan", bugun))).days
        if yas > ESKI_GUN:
            eski.append(f"{h} ({yas} gün)")
            continue
        fy = [float(r["fiyat"]) for r in plan if r.get("hisse") == h and r.get("fiyat") is not None]
        if fy and (p > max(fy) or p < min(fy)) and durum.get(f"_harita_{h}") != bugun:
            durum[f"_harita_{h}"] = bugun
            satir.append(f"⚠️ <b>{h}</b> {CUR[a.pazar]}{f2(p)} emir haritasının dışında ({f2(min(fy))}–{f2(max(fy))}) — ara güncelleme gerekli")
        for r in plan:
            if r.get("hisse") != h or r.get("fiyat") is None or r.get("tip") in (None, "not"):
                continue
            f, t, rid = float(r["fiyat"]), r["tip"], r["id"]
            st = durum.setdefault(rid, {})
            if st.get("hafta") != r.get("hafta"):          # yeni plan: durumu sıfırla, ilk görüşte gönderme
                st.clear(); st["hafta"] = r.get("hafta"); st["taraf"] = "ust" if p >= f else "alt"
                continue
            taraf = "ust" if p >= f else "alt"
            uzak = abs(p - f) / atr
            ek = " · karar günlük kapanışta" if t in KAPANIS else ""
            ad = f"{AD.get(t, t)} — {common.e(r.get('emir', ''))}"
            hedef_taraf = "ust" if t in YUKARI else "alt"
            if taraf != st.get("taraf"):
                st["taraf"] = taraf
                if taraf == hedef_taraf:
                    satir.append(f"✅ <b>{h}</b> {CUR[a.pazar]}{f2(p)} · {ad} {f2(f)} geçildi{ek}")
                    st["gecti"] = bugun
                    continue
            if uzak <= 0.5 and taraf != hedef_taraf and st.get("yakin") != bugun:
                st["yakin"] = bugun
                satir.append(f"🔔 <b>{h}</b> {CUR[a.pazar]}{f2(p)} · {ad} {f2(f)} seviyesine {str(round(uzak, 1)).replace(".", ",")} ATR{ek}")
    if eski and durum.get("_eski") != bugun:
        durum["_eski"] = bugun
        satir.append("⏳ Plan eski, bildirim durdu: " + ", ".join(eski) + " — haftalık analiz gerekli")
    if satir:
        url = os.environ.get("TEKNIK_URL", "")
        msg = "📐 <b>Teknik plan</b>\n" + "\n".join(satir) + (f"\n<a href=\"{url}\">Pano</a>" if url else "")
        if a.dry:
            print(msg)
        else:
            common.send_telegram(msg)
    durum["_son"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not a.dry:
        with open(D / f"bildirim_durum_{a.pazar}.json", "w", encoding="utf-8") as f:
            json.dump(durum, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"teknik_bildirim {a.pazar}: {len(satir)} satır")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as ex:  # izleme iş akışını asla düşürmesin
        print(f"[WARN] teknik_bildirim: {type(ex).__name__}: {ex}")
        sys.exit(0)
