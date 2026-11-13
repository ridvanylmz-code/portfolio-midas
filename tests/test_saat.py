"""scripts/saat.py: due() saf mantığı (saat dilimleri, yaz/kış saati, hafta sonu, günlük işler) ve iş akışı dosyaları."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

import saat
from conftest import ET, IST, at

ROOT = Path(__file__).resolve().parent.parent
E = {e["key"]: e for e in saat.ENTRIES}


def keys(now, start=None, last=None):
    state = {"start": start or now - timedelta(hours=1), "last": last or {}}
    return {e["key"] for e in saat.due(saat.ENTRIES, state, now)}


def utc(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


def test_interval_inside_and_outside_window_us():
    mon = (2026, 11, 2)  # Pazartesi, kış saati (EST)
    assert "monitor.yml" in keys(at(*mon, 4, 0))
    assert "monitor.yml" in keys(at(*mon, 20, 45))
    assert "monitor.yml" not in keys(at(*mon, 3, 59))
    assert "monitor.yml" not in keys(at(*mon, 20, 46))
    assert "intraday.yml" in keys(at(*mon, 20, 30)) and "intraday.yml" not in keys(at(*mon, 20, 31))
    assert "market.yml" in keys(at(*mon, 20, 0)) and "market.yml" not in keys(at(*mon, 20, 1))


def test_interval_inside_and_outside_window_bist():
    mon = (2026, 11, 2)
    assert "monitor-bist.yml" in keys(at(*mon, 9, 45, IST))
    assert "monitor-bist.yml" in keys(at(*mon, 18, 30, IST))
    assert "monitor-bist.yml" not in keys(at(*mon, 9, 44, IST))
    assert "monitor-bist.yml" not in keys(at(*mon, 18, 31, IST))
    assert "market-bist.yml" in keys(at(*mon, 9, 15, IST)) and "market-bist.yml" not in keys(at(*mon, 9, 14, IST))


def test_interval_respects_last_dispatch_and_next_grid_point():
    mon = (2026, 11, 2)
    t0 = at(*mon, 10, 0)
    assert "monitor.yml" not in keys(t0 + timedelta(minutes=1), last={"monitor.yml": t0})
    assert "monitor.yml" not in keys(t0 + timedelta(minutes=14), last={"monitor.yml": t0})
    assert "monitor.yml" in keys(t0 + timedelta(minutes=15), last={"monitor.yml": t0})
    # saatlik girdi: 30 dk sonra yok, 60 dk sonra var
    assert "market.yml" not in keys(t0 + timedelta(minutes=30), last={"market.yml": t0})
    assert "market.yml" in keys(t0 + timedelta(minutes=60), last={"market.yml": t0})
    # 120 dk'lık trend: 08:00, 10:00, 12:00 ...
    assert "trend.yml" in keys(at(*mon, 10, 0)) and "trend.yml" in keys(at(*mon, 12, 0))
    assert "trend.yml" not in keys(at(*mon, 11, 0), last={"trend.yml": at(*mon, 10, 0)})


def test_failed_dispatch_is_retried_next_tick():
    t0 = at(2026, 11, 2, 10, 0)
    # last güncellenmedi (başarısız dispatch): sonraki turda yine due
    assert "monitor.yml" in keys(t0 + timedelta(minutes=1), last={})


def test_dst_difference_new_york_vs_istanbul():
    # 26 Eki 2026 (EDT, UTC-4): ET 04:00 = 08:00Z; 2 Kas 2026 (EST, UTC-5): ET 04:00 = 09:00Z
    assert "monitor.yml" in keys(utc(2026, 10, 26, 8, 0))
    assert "monitor.yml" not in keys(utc(2026, 10, 26, 7, 45))
    assert "monitor.yml" not in keys(utc(2026, 11, 2, 8, 0))
    assert "monitor.yml" in keys(utc(2026, 11, 2, 9, 0))
    # İstanbul UTC+3 sabit: 09:45 = 06:45Z her iki haftada
    assert "monitor-bist.yml" in keys(utc(2026, 10, 26, 6, 45))
    assert "monitor-bist.yml" in keys(utc(2026, 11, 2, 6, 45))
    # ET 20:45: yazın 00:45Z (Salı UTC ama ET Pazartesi), kışın 01:45Z
    assert "monitor.yml" in keys(utc(2026, 10, 27, 0, 45))
    assert "monitor.yml" in keys(utc(2026, 11, 3, 1, 45))
    assert "monitor.yml" not in keys(utc(2026, 11, 3, 2, 0))  # kışın 21:00 ET: pencere dışı
    # 18:30 ET günlük kayıt: yazın 22:30Z, kışın 23:30Z
    assert "defter.yml:oto@18:30" in keys(utc(2026, 10, 26, 22, 30))
    assert "defter.yml:oto@18:30" not in keys(utc(2026, 11, 2, 22, 30))
    assert "defter.yml:oto@18:30" in keys(utc(2026, 11, 2, 23, 30))


def test_weekend_nothing_interval():
    for tz in (ET, IST):
        for day in (7, 8):  # 7 Kas 2026 Cumartesi, 8 Kas Pazar
            for h in (5, 10, 12, 17):
                k = keys(at(2026, 11, day, h, 0, tz))
                assert not {x for x in k if E[x].get("every")}, (tz, day, h, k)
    assert not keys(at(2026, 11, 8, 18, 30)) & {"defter.yml:oto@18:30", "technicals.yml@17:30"}


def test_once_fires_once_per_local_date():
    mon = (2026, 11, 2)
    k = "technicals.yml@17:30"
    t = at(*mon, 17, 30)
    assert k not in keys(at(*mon, 17, 29))
    assert k in keys(t)
    assert k not in keys(t + timedelta(minutes=1), last={k: t})
    # ertesi gün yeniden
    assert k in keys(at(2026, 11, 3, 17, 30), last={k: t})
    # Cuma çalıştı, Cumartesi/Pazar yok
    assert k not in keys(at(2026, 11, 7, 17, 30))


def test_once_istanbul_tue_sat_and_saturday_only():
    k = "trend.yml@03:15"
    assert k in keys(at(2026, 11, 3, 3, 15, IST))       # Salı
    assert k in keys(at(2026, 11, 7, 3, 15, IST))       # Cumartesi
    assert k not in keys(at(2026, 11, 2, 3, 15, IST))   # Pazartesi
    assert k not in keys(at(2026, 11, 8, 3, 15, IST))   # Pazar
    ex = "defter.yml:excel@10:10"
    assert ex in keys(at(2026, 11, 7, 10, 10, IST))
    assert ex not in keys(at(2026, 11, 6, 10, 10, IST))
    ib = "defter.yml:ibkr@09:15"
    assert ib in keys(at(2026, 11, 7, 9, 15, IST)) and ib not in keys(at(2026, 11, 2, 9, 15, IST))


def test_late_restart_rule():
    day = (2026, 11, 3)  # Salı
    target = at(*day, 9, 15, IST)
    ib = "defter.yml:ibkr@09:15"
    tr = "trend.yml@03:15"
    # saat 09:15'ten önce çalışıyordu, tur gecikti: yine tetiklenir
    assert ib in keys(target + timedelta(minutes=3), start=target - timedelta(hours=2))
    # 60 dk sonra yeniden başlayan saat hâlâ tetikler (<= 90 dk)
    assert ib in keys(target + timedelta(minutes=60), start=target + timedelta(minutes=60))
    # 91 dk sonra yeniden başlarsa tetiklemez (kopya yerine eksik)
    late = target + timedelta(minutes=91)
    assert ib not in keys(late, start=late)
    t3 = at(*day, 3, 15, IST)
    assert tr not in keys(t3 + timedelta(minutes=120), start=t3 + timedelta(minutes=120))
    # ... ama saat önceden çalışıyorsa geç tur yine tetikler
    assert tr in keys(t3 + timedelta(minutes=120), start=t3 - timedelta(hours=1))


def test_idempotent_entries_fire_late_same_date():
    mon = (2026, 11, 2)
    for k, t in (("technicals.yml@17:30", at(*mon, 17, 30)), ("technicals-bist.yml@18:35", at(*mon, 18, 35, IST)),
                 ("defter.yml:oto@18:30", at(*mon, 18, 30))):
        late = t + timedelta(hours=3)
        assert k in keys(late, start=late), k
    # 23:40 yeniden deneme
    assert "defter.yml:oto@23:40" in keys(at(*mon, 23, 40))
    assert "defter.yml:oto@23:40" not in keys(at(*mon, 23, 39))
    # ertesi yerel tarihte (Salı 00:10 ET) dünkü iş yeniden tetiklenmez
    assert "defter.yml:oto@18:30" not in keys(at(2026, 11, 3, 0, 10), last={"defter.yml:oto@18:30": at(*mon, 18, 30)})


def test_gh_args():
    assert saat.gh_args(E["monitor.yml"], "main") == ["gh", "workflow", "run", "monitor.yml", "--ref", "main", "-f", "mode=auto"]
    assert saat.gh_args(E["defter.yml:excel@10:10"], "x")[-2:] == ["-f", "komut=excel"]
    assert saat.gh_args({"wf": "saat.yml"}, "main") == ["gh", "workflow", "run", "saat.yml", "--ref", "main"]


def test_run_loop_dispatches_retries_and_hands_over():
    t = {"now": at(2026, 11, 2, 10, 0)}
    calls = []

    def dispatch(e, branch):
        calls.append((e["wf"], t["now"]))
        return not (e["wf"] == "market.yml" and len(calls) < 6), "hata"  # market.yml ilk denemede başarısız

    def sleep(s):
        t["now"] += timedelta(seconds=s)

    only = [E["monitor.yml"], E["market.yml"]]
    saat.run(only, "main", 3, now_fn=lambda: t["now"], sleep_fn=sleep, dispatch_fn=dispatch)
    wfs = [c[0] for c in calls]
    assert wfs.count("monitor.yml") == 1           # 3 dk içinde tek kez
    assert wfs.count("market.yml") >= 2            # başarısız -> sonraki turda yeniden
    assert wfs[-1] == "saat.yml"                   # süre dolunca devir


def test_dry_run_makes_no_gh_calls(monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("gh çağrıldı")
    monkeypatch.setattr(saat.subprocess, "run", boom)
    assert saat.main(["--dry-run", "--now", "2026-11-02T15:00:00Z"]) == 0
    assert "tetiklenirdi: gh workflow run monitor.yml" in capsys.readouterr().out


@pytest.mark.parametrize("wf", sorted({e["wf"] for e in saat.ENTRIES}))
def test_target_workflow_declares_mode(wf):
    path = ROOT / ".github" / "workflows" / wf
    assert path.exists(), wf
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    on = doc.get("on", doc.get(True))  # PyYAML `on:` anahtarını True okur
    inputs = on["workflow_dispatch"]["inputs"]
    assert "mode" in inputs and "auto" in inputs["mode"]["options"]
    for e in saat.ENTRIES:
        if e["wf"] == wf and e.get("komut"):
            assert "komut" in inputs and e["komut"] in inputs["komut"]["options"]


def test_saat_workflow_shape():
    doc = yaml.safe_load((ROOT / ".github" / "workflows" / "saat.yml").read_text(encoding="utf-8"))
    on = doc.get("on", doc.get(True))
    assert "workflow_dispatch" in on and on["schedule"][0]["cron"] == "7 * * * *"
    assert doc["concurrency"] == {"group": "saat", "cancel-in-progress": False}
    assert doc["permissions"]["actions"] == "write"
    assert doc["jobs"]["saat"]["timeout-minutes"] == 350
