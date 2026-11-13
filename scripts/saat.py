"""Depo içi saat: GitHub `schedule` olayları saatlerce gecikip düştüğü için (denetim B1) iş akışlarını kendimiz tetikleriz.

Tek uzun çalışma (saat.yml): her dakika hangi işin zamanı geldiğine bakar, `gh workflow run ... -f mode=auto` ile
`workflow_dispatch` tetikler (dispatch saniyeler içinde başlar). Süre dolunca kendini yeniden başlatıp çıkar.
Yalnız stdlib + `gh` CLI (Actions çalıştırıcısında hazır; GH_TOKEN ile yetkili). Tatil takvimi yok: borsa tatilinde
iş akışının kendisi (monitor.py piyasa durumu) sessiz kalır.

Kullanım: python scripts/saat.py [--minutes 330] [--branch main] [--dry-run] [--now 2026-11-13T15:00:00Z]
"""
import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
IST = ZoneInfo("Europe/Istanbul")
SELF = "saat.yml"
LATE_RESTART_MIN = 90  # günlük işler: saatinden bu kadar sonra yeniden başlayan saat o günü atlar (çift çalışma yerine eksik)
HEARTBEAT_MIN = 15
TICK_SEC = 60

MON_FRI = (0, 1, 2, 3, 4)
TUE_SAT = (1, 2, 3, 4, 5)


def hm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def every(wf, tz, start, end, minutes, days=MON_FRI):
    """Pencere içinde (yerel saat, uçlar dahil) `start`tan başlayarak her `minutes` dakikada bir."""
    return {"key": wf, "wf": wf, "tz": tz, "days": days, "start": hm(start), "end": hm(end), "every": minutes}


def once(wf, tz, at, days=MON_FRI, komut=None, idempotent=False):
    """Yerel günde bir kez, `at` saatinden sonraki ilk turda. idempotent: geç yeniden başlatmada da (aynı gün) çalışır."""
    key = f"{wf}:{komut}@{at}" if komut else f"{wf}@{at}"
    return {"key": key, "wf": wf, "tz": tz, "days": days, "at": hm(at), "komut": komut, "idempotent": idempotent}


ENTRIES = [
    every("monitor.yml", ET, "04:00", "20:45", 15),        # seans içi yalnız kotasyon/fiyat yazılır (küçük, düz dosyalar)
    every("monitor-bist.yml", IST, "09:45", "18:30", 15),
    every("market.yml", ET, "04:00", "20:00", 60),
    every("market-bist.yml", IST, "09:15", "18:45", 60),
    every("intraday.yml", ET, "04:00", "20:30", 30),
    every("trend.yml", ET, "08:00", "17:00", 120),
    once("trend.yml", IST, "03:15", TUE_SAT),
    every("trend-bist.yml", IST, "10:15", "18:30", 120),
    once("technicals.yml", ET, "17:30", idempotent=True),
    once("technicals-bist.yml", IST, "18:35", idempotent=True),
    once("defter.yml", ET, "18:30", komut="oto", idempotent=True),   # iki piyasa da kapalı
    once("defter.yml", ET, "23:40", komut="oto", idempotent=True),   # yeniden deneme
    once("defter.yml", IST, "09:15", TUE_SAT, komut="ibkr"),
    once("defter.yml", IST, "10:10", (5,), komut="excel"),
]


def _grid_point(e, t):
    """`t` yerel zamanında (aware) `every` girdisinin son ızgara noktası (aware, yerel) ya da None (pencere dışı)."""
    m = t.hour * 60 + t.minute
    if t.weekday() not in e["days"] or m < e["start"] or m > e["end"]:
        return None
    g = e["start"] + (m - e["start"]) // e["every"] * e["every"]
    return t.replace(hour=g // 60, minute=g % 60, second=0, microsecond=0)


def due(entries, state, now):
    """Şimdi tetiklenmesi gereken girdiler. Saf fonksiyon (saat ve ağ yok).
    state = {"start": clock'un başlangıç anı (aware), "last": {key: son tetikleme anı (aware)}}."""
    out = []
    last = state.get("last", {})
    for e in entries:
        t = now.astimezone(e["tz"])
        prev = last.get(e["key"])
        if "every" in e:
            g = _grid_point(e, t)
            if g is not None and (prev is None or prev < g):
                out.append(e)
            continue
        target = t.replace(hour=e["at"] // 60, minute=e["at"] % 60, second=0, microsecond=0)
        if t.weekday() not in e["days"] or t < target:
            continue
        if prev is not None and prev >= target:  # bugün (yerel tarih) zaten tetiklendi
            continue
        if not e["idempotent"] and state["start"] > target + timedelta(minutes=LATE_RESTART_MIN):
            continue  # saatten çok sonra yeniden başladık: kopya yerine eksik tercih edilir
        out.append(e)
    return out


def gh_args(e, branch):
    a = ["gh", "workflow", "run", e["wf"], "--ref", branch]
    if e["wf"] != SELF:
        a += ["-f", "mode=auto"]
    if e.get("komut"):
        a += ["-f", f"komut={e['komut']}"]
    return a


def dispatch(e, branch):
    """(ok, mesaj). Hata ölümcül değil: bir sonraki turda yeniden denenir."""
    try:
        r = subprocess.run(gh_args(e, branch), capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as ex:
        return False, str(ex)
    return r.returncode == 0, (r.stderr or r.stdout).strip()


def log(msg, now):
    print(f"[{now:%Y-%m-%d %H:%M:%S}Z] {msg}", flush=True)


def run(entries, branch, minutes, dry_run=False, now_fn=None, sleep_fn=time.sleep, dispatch_fn=dispatch):
    now_fn = now_fn or (lambda: datetime.now(timezone.utc))
    start = now_fn()
    deadline = start + timedelta(minutes=minutes)
    state = {"start": start, "last": {}}
    next_beat = start
    log(f"saat başladı: dal={branch}, süre={minutes} dk, {len(entries)} girdi" + (" (kuru çalışma)" if dry_run else ""), start)
    while True:
        now = now_fn()
        if now >= deadline:
            break
        for e in due(entries, state, now):
            if dry_run:
                log("tetiklenirdi: " + " ".join(gh_args(e, branch)), now)
                state["last"][e["key"]] = now
                continue
            ok, msg = dispatch_fn(e, branch)
            if ok:
                state["last"][e["key"]] = now
                log(f"tetiklendi: {e['key']}", now)
            else:
                log(f"HATA {e['key']}: {msg[:200]} (sonraki turda yeniden)", now)
        if dry_run:
            return state
        if now >= next_beat:
            log(f"çalışıyor; bitiş {deadline:%H:%M}Z", now)
            next_beat = now + timedelta(minutes=HEARTBEAT_MIN)
        sleep_fn(max(1, TICK_SEC - (now_fn() - now).total_seconds()))
    # süre doldu: yeni çalışma devralsın (concurrency grubunda sıraya girer, bu çalışma bitince başlar)
    ok, msg = dispatch_fn({"wf": SELF, "key": SELF}, branch)
    log("devir: saat.yml yeniden tetiklendi" if ok else f"UYARI devir tetiklenemedi: {msg[:200]} (saatlik yedek cron başlatır)", now_fn())
    return state


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--minutes", type=float, default=330, help="çalışma süresi (varsayılan 5 sa 30 dk)")
    ap.add_argument("--branch", default=os.environ.get("BRANCH") or "main")
    ap.add_argument("--dry-run", action="store_true", help="tek tur: ne tetikleneceğini yaz, gh çağırma")
    ap.add_argument("--now", help="kuru çalışma için sahte an (ISO, UTC), ör. 2026-11-13T15:00:00Z")
    a = ap.parse_args(argv)
    now_fn = None
    if a.now:
        fixed = datetime.fromisoformat(a.now.replace("Z", "+00:00"))
        now_fn = lambda: fixed
    run(ENTRIES, a.branch, a.minutes, dry_run=a.dry_run, now_fn=now_fn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
