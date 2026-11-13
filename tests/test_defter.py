"""Defter (scripts/defter.py): sentetik veri, sahte anahtar, ağ yok."""
import argparse
import json
from pathlib import Path

import pytest

from zoneinfo import ZoneInfo

from conftest import at, write_json

IST, NY = ZoneInfo("Europe/Istanbul"), ZoneInfo("America/New_York")

KEY = "test-anahtari"
H_USD = "docs/data/history.json"
H_TR = "docs/bist/data/history.json"


def defter(load, key=KEY):
    return load("us", key=key).defter


def acc_day(ds, **accs):
    return {"d": ds, "a": {k: dict(v) for k, v in accs.items()}}


# ------------------------------------------------------------------ B8: geri alınan akış
def test_flows_on_ignores_undone(load):
    m = defter(load)
    hist = {"transactions": [
        {"date": "2026-11-10", "action": "deposit", "amount": 1000},
        {"date": "2026-11-10", "action": "deposit", "amount": 500, "undone": True},
        {"date": "2026-11-10", "action": "withdraw", "amount": 200},
        {"date": "2026-11-10", "action": "buy", "amount": 9999},
    ]}
    assert m.flows_on(hist, "2026-11-10") == 800
    assert m.flows_on(hist, "2026-11-11") == 0


def test_rederive_flows_last_60_days_leaves_x_and_m(load, tmp_path):
    m = defter(load)
    write_json(tmp_path, H_USD, {"transactions": [
        {"date": "2026-11-10", "action": "deposit", "amount": 300, "undone": True},
        {"date": "2026-11-11", "action": "deposit", "amount": 100}]})
    write_json(tmp_path, H_TR, {"transactions": []})
    d = m.load()
    old = "2026-08-01"   # 60 günden eski: dokunulmaz
    d["days"] = [
        acc_day(old, midas_usd={"v": 1000, "c": 5, "f": 50, "s": "a"}),
        acc_day("2026-11-09", midas_usd={"v": 1000, "s": "a"}, midas_tr={"v": 500, "c": 1, "f": 7, "s": "x"}),
        acc_day("2026-11-10", midas_usd={"v": 1010, "c": 10, "f": 300, "fm": 25, "s": "a"},
                midas_tr={"v": 510, "c": 10, "f": 5, "s": "m"}),
        acc_day("2026-11-11", midas_usd={"v": 1120, "c": 10, "s": "a"}),
    ]
    now = at(2026, 11, 12, 12, 0, IST)
    m.rederive_flows(d, now)
    for acc in m.ACCOUNTS:
        m.recompute(d, acc)
    by = {x["d"]: x["a"] for x in d["days"]}
    assert by[old]["midas_usd"]["f"] == 50                       # eski gün
    assert by["2026-11-10"]["midas_usd"]["f"] == 25              # geri alınan 300 düştü, elle kısım (fm) kaldı
    assert by["2026-11-10"]["midas_usd"]["c"] == 1010 - 1000 - 25
    assert by["2026-11-11"]["midas_usd"]["f"] == 100
    assert by["2026-11-11"]["midas_usd"]["c"] == 1120 - 1010 - 100
    assert by["2026-11-09"]["midas_tr"] == {"v": 500, "c": 1, "f": 7, "s": "x"}    # Excel
    # elle: f ve v aynı (c'yi recompute her zaman yaptığı gibi yeniden hesaplar: 510 − 500 − 5)
    assert by["2026-11-10"]["midas_tr"] == {"v": 510, "c": 5, "f": 5, "s": "m"}


def test_rederive_skips_when_history_unreadable(load):
    m = defter(load)
    d = m.load()
    d["days"] = [acc_day("2026-11-10", midas_usd={"v": 1, "f": 9, "s": "a"})]
    m.rederive_flows(d, at(2026, 11, 12, 12, 0, IST))   # geçmiş dosyası yok -> akış silinmez
    assert d["days"][0]["a"]["midas_usd"]["f"] == 9


# ------------------------------------------------------------------ B9: ileri doldurma
def ledger(m):
    d = m.load()
    d["accounts"]["ibkr"]["start"] = "2026-11-03"
    d["days"] = [
        acc_day("2026-11-02", midas_usd={"v": 1000, "c": 0, "s": "a"}),            # IBKR henüz başlamadı
        acc_day("2026-11-03", midas_usd={"v": 1010, "c": 10, "s": "a"}, ibkr={"v": 500, "s": "a"}),
        acc_day("2026-11-04", midas_usd={"v": 1020, "c": 10, "s": "a"}),            # IBKR eksik
        acc_day("2026-11-05", midas_usd={"v": 1030, "c": 10, "s": "a"}, ibkr={"v": 520, "c": 20, "s": "a"}),
    ]
    return d


def test_carry_group_helper(load):
    m = defter(load)
    accs = ("midas_usd", "ibkr")
    assert m.carry_group({}, {}, accs) is None
    last = {"ibkr": ("2026-11-03", {"v": 500})}
    g = m.carry_group({"midas_usd": {"v": 1020}}, last, accs)
    assert g == {"v": 1520, "carry": [["ibkr", "2026-11-03"]]}
    # hesap henüz başlamadı (last'ta yok): taşınmaz, eksik sayılmaz
    assert m.carry_group({"midas_usd": {"v": 1000}}, {}, accs) == {"v": 1000, "carry": []}
    # iki hesap da gerçek
    assert m.carry_group({"midas_usd": {"v": 1}, "ibkr": {"v": 2}}, last, accs) == {"v": 3, "carry": []}


def test_daily_rows_and_periods_carry(load):
    m = defter(load)
    rows = {r["d"]: r for r in m.daily_rows(ledger(m))}
    assert rows["2026-11-02"]["g"]["usd"] == {"v": 1000, "carry": []}
    assert rows["2026-11-03"]["g"]["usd"]["v"] == 1510
    assert rows["2026-11-04"]["g"]["usd"] == {"v": 1520, "carry": [["ibkr", "2026-11-03"]]}
    assert rows["2026-11-05"]["g"]["usd"] == {"v": 1550, "carry": []}
    assert "tl" not in rows["2026-11-04"]["g"]
    # Gün içi değişim yalnız gerçek kayıtlardan: 11-04 grup c'si Midas-USD'nin kendisi
    ps = m.periods(ledger(m), "W")
    assert ps[-1]["usd"]["v"] == 1550 and ps[-1]["usd"]["carry"] == []
    d = ledger(m)
    d["days"].pop()   # hafta IBKR'siz bitiyor: dönem sonu değeri taşınmış IBKR'yi içerir
    p = m.periods(d, "W")[-1]
    assert p["usd"]["v"] == 1520 and p["usd"]["carry"] == [["ibkr", "2026-11-03"]]


def test_xlsx_builds_with_fx_and_carry(load, tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    m = defter(load)
    d = ledger(m)
    for x in d["days"]:
        x["xu"], x["sp"], x["fx"] = 10000.0, 500.0, 42.5
    out = tmp_path / "x.xlsx"
    m.build_xlsx(d, out)
    ws = openpyxl.load_workbook(out)["Günlük"]
    hdr = [c.value for c in ws[1]]
    assert "USD/TRY" in hdr and hdr[-1] == "Not"
    col = hdr.index("USD/TRY") + 1
    assert ws.cell(2, col).value == 42.5
    tot = hdr.index("USD Toplam") + 1
    assert [ws.cell(i, tot).value for i in (2, 3, 4, 5)] == [1000, 1510, 1520, 1550]
    assert "taşındı" in ws.cell(4, len(hdr)).comment.text
    assert "değer" in m.week_summary(d)


# ------------------------------------------------------------------ B10: tamamlanmış seans
@pytest.mark.parametrize("market,y,mo,d_,h,mi,tz,want", [
    ("bist", 2026, 11, 12, 14, 0, IST, "2026-11-11"),    # seans ortası
    ("bist", 2026, 11, 12, 18, 10, IST, "2026-11-11"),   # kapanış seansı sürüyor
    ("bist", 2026, 11, 12, 18, 15, IST, "2026-11-12"),
    ("bist", 2026, 11, 13, 1, 20, IST, "2026-11-12"),    # 22:20 UTC cron'u
    ("bist", 2026, 11, 14, 10, 0, IST, "2026-11-13"),    # Cumartesi
    ("bist", 2026, 11, 14, 20, 0, IST, "2026-11-13"),
    ("bist", 2026, 11, 16, 9, 0, IST, "2026-11-13"),     # Pazartesi sabahı
    ("us", 2026, 11, 12, 16, 14, NY, "2026-11-11"),
    ("us", 2026, 11, 12, 16, 15, NY, "2026-11-12"),
    ("us", 2026, 11, 12, 10, 0, NY, "2026-11-11"),       # seans ortası
    ("us", 2026, 11, 14, 12, 0, NY, "2026-11-13"),
    ("us", 2026, 11, 16, 9, 0, NY, "2026-11-13"),
])
def test_target_day_last_completed_session(load, market, y, mo, d_, h, mi, tz, want):
    m = defter(load)
    assert m.target_day(market, at(y, mo, d_, h, mi, tz)) == want


def test_markets_differ_between_closes(load):
    m = defter(load)
    now = at(2026, 11, 12, 19, 0, IST)    # BIST kapandı, New York henüz açılmadı
    assert m.target_day("bist", now) == "2026-11-12" and m.target_day("us", now) == "2026-11-11"


def snapshot_files(tmp_path, ds_list):
    for f, base in ((H_TR, 200000), (H_USD, 5000)):
        write_json(tmp_path, f, {"snapshots": [{"date": ds, "value": base + i * 10, "cash": 100}
                                               for i, ds in enumerate(ds_list)], "transactions": []})


@pytest.fixture
def quiet(monkeypatch, outbox):
    """Ağ yok: piyasa kaynakları boş."""
    def _q(m):
        monkeypatch.setattr(m, "yahoo_closes", lambda *a, **k: {})
        monkeypatch.setattr(m, "twelvedata_closes", lambda *a, **k: {})
        monkeypatch.setattr(m, "stooq_closes", lambda *a, **k: {})
        monkeypatch.setattr(m, "tv_close", lambda *a, **k: None)
        m.DIAG.clear()
    return _q


def test_cmd_auto_mid_session_writes_nothing_for_unfinished_day(load, tmp_path, quiet, outbox):
    m = defter(load)
    quiet(m)
    snapshot_files(tmp_path, ["2026-11-11", "2026-11-12"])
    now = at(2026, 11, 12, 14, 0, IST)    # BIST ortası
    assert m.cmd_auto(argparse.Namespace(date=None), now) == 0
    d = m.load()
    days = {x["d"] for x in d["days"]}
    assert "2026-11-12" not in days and "2026-11-11" in days
    assert not any("snapshot yok" in t for t in outbox())


def test_cmd_auto_writes_completed_day(load, tmp_path, quiet, outbox):
    m = defter(load)
    quiet(m)
    snapshot_files(tmp_path, ["2026-11-11", "2026-11-12"])
    now = at(2026, 11, 13, 1, 20, IST)
    m.cmd_auto(argparse.Namespace(date=None), now)
    by = {x["d"]: x for x in m.load()["days"]}
    assert by["2026-11-12"]["a"]["midas_tr"]["s"] == "a" and by["2026-11-12"]["a"]["midas_usd"]["s"] == "a"
    assert not any("snapshot yok" in t for t in outbox())


# ------------------------------------------------------------------ B10: Info-TR tarihli kapanış
def info_setup(tmp_path, m):
    write_json(tmp_path, m.F_INFO, {"cash": 100.0, "transactions": [],
                                    "positions": {"AAA": {"shares": 10, "cost": 5.0}, "BBB": {"shares": 2, "cost": 50.0}}})
    bars = {"updated": "x", "source": "t", "bars": {
        "AAA": [["2026-11-11", 1, 1, 1, 7.0], ["2026-11-12", 1, 1, 1, 8.0]],
        "BBB": [["2026-11-11", 1, 1, 1, 60.0]]}}
    p = write_json(tmp_path, "bars-bist.json", bars)
    return str(p)


def test_info_value_uses_dated_close(load, tmp_path, monkeypatch):
    m = defter(load)
    monkeypatch.setenv("BIST_BARS_JSON", info_setup(tmp_path, m))
    monkeypatch.setattr(m, "info_prices", lambda t: pytest.fail("canlı fiyat istenmemeliydi"))
    iv = m.info_value("2026-11-11", at(2026, 11, 12, 14, 0, IST))
    assert iv["stocks"] == 10 * 7.0 + 2 * 60.0 and iv["total"] == iv["stocks"] + 100 and iv["missing"] == []


def test_info_value_refuses_mid_session(load, tmp_path, monkeypatch):
    m = defter(load)
    monkeypatch.setenv("BIST_BARS_JSON", info_setup(tmp_path, m))
    monkeypatch.setattr(m, "info_prices", lambda t: pytest.fail("canlı fiyat istenmemeliydi"))
    m.DIAG.clear()
    # 12 Kas için BBB mumu yok; saat 14:00 (seans açık) -> yazılmaz
    assert m.info_value("2026-11-12", at(2026, 11, 12, 14, 0, IST)) is None
    assert any("BBB" in x for x in m.DIAG)
    # hedef gün beklenen seans değilse (geçmiş gün) canlı kotasyon yine kullanılmaz
    assert m.info_value("2026-11-10", at(2026, 11, 13, 20, 0, IST)) is None


def test_info_value_live_fallback_when_closed_and_expected(load, tmp_path, monkeypatch):
    m = defter(load)
    monkeypatch.setenv("BIST_BARS_JSON", info_setup(tmp_path, m))
    monkeypatch.setattr(m, "info_prices", lambda t: {k: 55.0 for k in t})
    iv = m.info_value("2026-11-12", at(2026, 11, 12, 19, 0, IST))   # kapalı, 12 Kas beklenen son seans
    assert iv["stocks"] == 10 * 8.0 + 2 * 55.0
    # bars dosyası hiç yoksa da aynı kural
    monkeypatch.setenv("BIST_BARS_JSON", str(tmp_path / "yok.json"))
    iv = m.info_value("2026-11-12", at(2026, 11, 12, 19, 0, IST))
    assert iv["stocks"] == 10 * 55.0 + 2 * 55.0
    assert m.info_value("2026-11-12", at(2026, 11, 12, 11, 0, IST)) is None


def test_cmd_auto_info_dated_close_and_missing_note(load, tmp_path, quiet, monkeypatch):
    m = defter(load)
    quiet(m)
    monkeypatch.setenv("BIST_BARS_JSON", info_setup(tmp_path, m))
    monkeypatch.setattr(m, "info_prices", lambda t: {k: None for k in t})   # canlı kaynak yanıt vermiyor
    snapshot_files(tmp_path, ["2026-11-12"])
    m.cmd_auto(argparse.Namespace(date=None), at(2026, 11, 13, 1, 20, IST))
    e = {x["d"]: x for x in m.load()["days"]}["2026-11-12"]["a"]["info_tr"]
    # AAA 12 Kas mumundan (8.0), BBB mumu yok -> son bilinen/maliyet (50) ve not
    assert e["h"] == 10 * 8.0 + 2 * 50.0 and "fiyat yok: BBB" in e["n"]


# ------------------------------------------------------------------ B6: yazmadan karşılaştır, işlemleri ayır
def test_save_skips_when_unchanged_and_splits_islem(load, tmp_path):
    m = defter(load)
    d = m.load()
    d["islem"] = {"at": "eski", "rows": []}   # eski sürüm: defter.json içinde
    d["days"] = [acc_day("2026-11-11", midas_usd={"v": 1000, "s": "a"})]
    assert m.save(d) is True
    f, isl, st = (tmp_path / "docs/defter/data" / n for n in ("defter.json", "islem.json", "status.json"))
    assert m.common.is_vault(json.loads(f.read_text())) and m.common.is_vault(json.loads(isl.read_text()))
    assert "islem" not in m.common.load_json(m.F_DEFTER)            # eski anahtar kalktı
    assert "rows" in m.common.load_json(m.F_ISLEM)
    before = [p.read_bytes() for p in (f, isl, st)]
    assert m.save(m.load()) is False                                  # içerik aynı: hiçbir dosya yazılmaz
    assert [p.read_bytes() for p in (f, isl, st)] == before
    d = m.load()
    d["days"][0]["a"]["midas_usd"]["v"] = 1001
    assert m.save(d) is True
    assert f.read_bytes() != before[0] and isl.read_bytes() == before[1]   # islem.json içeriği aynı: yazılmadı


def test_islemler_only_touches_islem_json(load, tmp_path):
    m = defter(load)
    d = m.load()
    d["days"] = [acc_day("2026-11-11", midas_usd={"v": 1000, "s": "a"})]
    m.save(d)
    f = tmp_path / "docs/defter/data/defter.json"
    before = f.read_bytes()
    write_json(tmp_path, H_USD, {"transactions": [
        {"date": "2026-11-11", "action": "buy", "ticker": "AAA", "shares": 1, "price": 10, "time": "2026-11-11T10:00:00Z"}]})
    assert m.cmd_trades(None) == 0
    assert f.read_bytes() == before
    rows = m.common.load_json(m.F_ISLEM)["rows"]
    assert any(r["sym"] == "AAA" for r in rows)


def test_save_without_key_refuses(load):
    m = load("us").defter
    with pytest.raises(m.common.VaultError):
        m.save(m.load())


# ------------------------------------------------------------------ B29: USD/TRY
def test_fill_indices_fx(load, monkeypatch):
    m = defter(load)
    calls = []

    def yc(sym, rng="10d", nd=2):
        calls.append((sym, rng))
        return {"USDTRY=X": {"2026-11-10": 42.1234, "2026-11-11": 42.2},
                "XU100.IS": {"2026-11-10": 10000.0, "2026-11-11": 10100.0, "2026-11-12": 10200.0},
                "SPY": {"2026-11-10": 500.0, "2026-11-11": 501.0, "2026-11-12": 502.0}}[sym]
    monkeypatch.setattr(m, "yahoo_closes", yc)
    monkeypatch.setattr(m, "twelvedata_closes", lambda *a, **k: {})
    tv = {}
    monkeypatch.setattr(m, "tv_close", lambda s, nd=2: tv.get(s))
    d = m.load()
    d["sp_src"] = "SPY"
    d["days"] = [acc_day(ds, midas_usd={"v": 1, "s": "a"}) for ds in ("2026-11-10", "2026-11-11", "2026-11-12")]
    # son gün: Yahoo'da yok, TradingView yedeği yalnız son tamamlanan seans günü için
    monkeypatch.setattr(m, "last_session", lambda mk, now=None: "2026-11-12")
    tv["FX_IDC:USDTRY"] = 42.3
    m.fill_indices(d, "10d", today="2026-11-12")
    assert [x.get("fx") for x in d["days"]] == [42.1234, 42.2, 42.3]
    assert ("USDTRY=X", "max") in calls          # günlerin yarısından azında fx vardı: geçmiş doldurma
    calls.clear()
    m.fill_indices(d, "10d", today="2026-11-12")
    assert ("USDTRY=X", "10d") in calls          # artık yeterli
    # son gün tamamlanmış seans değilse TradingView kullanılmaz
    d["days"][-1].pop("fx")
    monkeypatch.setattr(m, "last_session", lambda mk, now=None: "2026-11-11")
    m.fill_indices(d, "10d", today="2026-11-12")
    assert "fx" not in d["days"][-1]
