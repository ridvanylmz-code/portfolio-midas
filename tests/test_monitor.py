"""monitor.run uçtan uca (sentetik): işlem günü damgası (B13/B24), fiyat budama, bayat kotasyon (B36),
rapor slotları + gecikmiş rapor (B3/B4/B23), aylık hedef tabanı (B11), perf_summary."""
from datetime import date

import pytest

from conftest import at, base_portfolio, epoch, read_json, write_json


def setup_root(root, pf=None, hist=None, prices=None):
    d = "docs/data" if True else ""
    write_json(root, f"{d}/portfolio.json", pf or base_portfolio())
    write_json(root, f"{d}/history.json", hist or {"transactions": [], "snapshots": []})
    if prices is not None:
        write_json(root, f"{d}/prices.json", prices)


def setup_bist(root, pf=None, hist=None, prices=None):
    write_json(root, "docs/bist/data/portfolio.json", pf or base_portfolio())
    write_json(root, "docs/bist/data/history.json", hist or {"transactions": [], "snapshots": []})
    if prices is not None:
        write_json(root, "docs/bist/data/prices.json", prices)


def q(c, t, **kw):
    return {"c": c, "pc": c, "d": 0.0, "dp": 0.0, "h": c, "l": c, "o": c, "t": t, **kw}


def run_us(mon, quotes, now, status=False, report=False, force=True):
    mon.attach_ext = lambda *a, **k: None
    mon.apply_extended = lambda quotes, tickers, now: (quotes, None)
    return mon.run(report=report, force=force, key="k", fetch=lambda t, k: quotes.get(t),
                   status_fn=lambda k: {"isOpen": status}, now=now)


# ------------------------------------------------------------------ işlem günü damgası
def test_trade_date_from_quote_time_us(load, tmp_path):
    mon = load().monitor
    fri = epoch(2026, 11, 13, 15, 59)
    run_date = "2026-11-14"  # Cumartesi
    assert mon.trade_date({"t": fri}, run_date) == "2026-11-13"
    assert mon.trade_date({}, run_date) == "2026-11-13"                 # t yok: çalışma günü, hafta sonu -> cuma
    assert mon.trade_date({"t": 0}, "2026-11-12") == "2026-11-12"       # t yok: çalışma günü
    assert mon.trade_date({"t": epoch(2026, 11, 15, 12, 0)}, run_date) == "2026-11-13"  # pazar damgası -> cuma
    # UTC'de ertesi güne taşan ET işlem saati yine ET gününe yazılır
    assert mon.trade_date({"t": epoch(2026, 11, 12, 20, 0)}, "2026-11-13") == "2026-11-12"


def test_us_weekend_run_writes_friday_not_saturday(load, tmp_path):
    mon = load().monitor
    setup_root(tmp_path)
    t = epoch(2026, 11, 13, 15, 59)
    run_us(mon, {"AAA": q(110, t), "BBB": q(20, t)}, at(2026, 11, 14, 10, 0))
    prices = read_json(tmp_path, "docs/data/prices.json")
    assert set(prices["AAA"]) == {"2026-11-13"} and set(prices["BBB"]) == {"2026-11-13"}
    assert [s["date"] for s in read_json(tmp_path, "docs/data/history.json")["snapshots"]] == ["2026-11-13"]


def test_us_after_midnight_run_uses_previous_session_date(load, tmp_path):
    mon = load().monitor
    setup_root(tmp_path)
    t = epoch(2026, 11, 12, 16, 0)
    run_us(mon, {"AAA": q(110, t), "BBB": q(20, t)}, at(2026, 11, 13, 0, 30))  # ET 00:30, takvim günü 13'ü
    prices = read_json(tmp_path, "docs/data/prices.json")
    assert set(prices["AAA"]) == {"2026-11-12"}
    assert read_json(tmp_path, "docs/data/history.json")["snapshots"][0]["date"] == "2026-11-12"


def test_bist_weekend_and_after_midnight(load, tmp_path):
    mon = load("bist").monitor
    setup_bist(tmp_path)
    fri = epoch(2026, 11, 13, 18, 10, mon.IST)
    mon.attach_ext = lambda *a, **k: None
    quotes = {"AAA": q(110, fri), "BBB": q(20, fri)}
    mon.run(force=True, fetch=lambda t, k: quotes.get(t), status_fn=lambda k: {"isOpen": False},
            now=at(2026, 11, 14, 11, 0, mon.IST))
    prices = read_json(tmp_path, "docs/bist/data/prices.json")
    assert set(prices["AAA"]) == {"2026-11-13"}
    # Salı 00:30 (İstanbul), kotasyon pazartesi 18:10
    mon_t = epoch(2026, 11, 16, 18, 10, mon.IST)
    quotes = {"AAA": q(111, mon_t), "BBB": q(21, mon_t)}
    mon.run(force=True, fetch=lambda t, k: quotes.get(t), status_fn=lambda k: {"isOpen": False},
            now=at(2026, 11, 17, 0, 30, mon.IST))
    prices = read_json(tmp_path, "docs/bist/data/prices.json")
    assert set(prices["AAA"]) == {"2026-11-13", "2026-11-16"}


def test_snapshot_skipped_when_held_trade_dates_disagree(load, tmp_path):
    mon = load().monitor
    pf = base_portfolio(portfolio={"AAA": {"shares": 10, "cost_basis": 50.0}, "CCC": {"shares": 5, "cost_basis": 10.0}})
    setup_root(tmp_path, pf=pf)
    run_us(mon, {"AAA": q(110, epoch(2026, 11, 13, 15, 59)), "CCC": q(12, epoch(2026, 11, 12, 15, 59)),
                 "BBB": q(20, epoch(2026, 11, 13, 15, 59))}, at(2026, 11, 14, 10, 0))
    assert read_json(tmp_path, "docs/data/history.json")["snapshots"] == []
    assert set(read_json(tmp_path, "docs/data/prices.json")["AAA"]) == {"2026-11-13"}  # fiyat geçmişi yine yazılır


def test_prices_pruned_and_window_kept(load, tmp_path):
    mon = load().monitor
    old = {f"2026-10-{d:02d}": 1.0 for d in range(1, 32) if date(2026, 10, d).weekday() < 5}   # 22 iş günü
    old.update({f"2026-11-{d:02d}": 2.0 for d in (2, 3, 4, 5, 6, 9, 10)})
    old["2026-11-08"] = 9.9  # pazar tarihli eski kayıt
    setup_root(tmp_path, prices={"AAA": old, "ZZZ": {"2026-11-05": 5.0}})
    t = epoch(2026, 11, 12, 16, 0)
    run_us(mon, {"AAA": q(110, t), "BBB": q(20, t)}, at(2026, 11, 12, 17, 0))
    prices = read_json(tmp_path, "docs/data/prices.json")
    assert "ZZZ" not in prices                      # portföy+izleme listesinde değil
    assert "2026-11-08" not in prices["AAA"]        # hafta sonu kaydı temizlendi
    assert len(prices["AAA"]) == mon.PRICE_DAYS and "2026-11-12" in prices["AAA"]
    assert "BBB" in prices


# ------------------------------------------------------------------ bayat kotasyon (B36)
def test_stale_quote_is_not_fresh(load, tmp_path, outbox):
    mon = load("bist").monitor
    pf = base_portfolio(position_levels={"AAA": {"stop_loss": 200.0}})   # fiyat stopun altında: taze olsaydı alarm olurdu
    hist = {"transactions": [], "snapshots": [{"date": "2026-11-11", "value": 900.0, "cost": 500.0, "cash": 100.0}]}
    setup_bist(tmp_path, pf=pf, hist=hist, prices={"AAA": {"2026-11-11": 100.0}})
    t_old, t_new = epoch(2026, 11, 11, 18, 10, mon.IST), epoch(2026, 11, 12, 18, 10, mon.IST)
    quotes = {"AAA": q(100, t_old, stale=True), "BBB": q(20, t_new)}
    mon.attach_ext = lambda *a, **k: None
    mon.run(force=True, fetch=lambda t, k: quotes.get(t), status_fn=lambda k: {"isOpen": False},
            now=at(2026, 11, 12, 19, 0, mon.IST))
    prices = read_json(tmp_path, "docs/bist/data/prices.json")
    assert prices["AAA"] == {"2026-11-11": 100.0}                       # güncellenmedi
    assert prices["BBB"] == {"2026-11-12": 20.0}
    assert read_json(tmp_path, "docs/bist/data/history.json")["snapshots"] == hist["snapshots"]  # kayıt yok
    assert outbox() == []                                                # stop alarmı yok
    assert read_json(tmp_path, "docs/bist/data/quotes.json")["quotes"]["AAA"]["stale"] is True


# ------------------------------------------------------------------ rapor slotları
def test_slots_us(load):
    mon = load().monitor
    due = lambda now, done=(): mon.due_slots(now, done)  # noqa: E731
    assert due(at(2026, 11, 12, 9, 20)) == []
    assert due(at(2026, 11, 12, 9, 30)) == ["2026-11-12T0927"]
    assert mon.late_label(at(2026, 11, 12, 9, 30), due(at(2026, 11, 12, 9, 30))) is None   # zamanında
    assert due(at(2026, 11, 12, 9, 30), {"2026-11-12T0927"}) == []
    assert due(at(2026, 11, 12, 16, 20)) == ["2026-11-12T0927", "2026-11-12T1617"]
    late = mon.late_label(at(2026, 11, 12, 16, 50), due(at(2026, 11, 12, 16, 50)))
    assert late == "⏰ Gecikmiş rapor (planlanan 16:17 ET)"
    assert due(at(2026, 11, 12, 16, 50), {"2026-11-12T0927"}) == ["2026-11-12T1617"]
    assert due(at(2026, 11, 14, 12, 0)) == [] and due(at(2026, 11, 15, 22, 30)) == []   # hafta sonu, Pazar 22:17 yok
    assert due(at(2026, 11, 12, 23, 59)) == ["2026-11-12T0927", "2026-11-12T1617"]      # aynı gün geç gece hâlâ borçlu
    assert due(at(2026, 11, 13, 0, 5)) == []                                            # yeni gün, slot saati gelmedi


def test_slots_bist(load):
    mon = load("bist").monitor
    ist = mon.IST
    assert mon.REPORT_SLOTS["bist"] == [(9, 50, mon.WEEK), (18, 20, mon.WEEK)]
    assert mon.due_slots(at(2026, 11, 12, 9, 40, ist), ()) == []
    assert mon.due_slots(at(2026, 11, 12, 9, 55, ist), ()) == ["2026-11-12T0950"]
    d = mon.due_slots(at(2026, 11, 12, 19, 30, ist), ())
    assert d == ["2026-11-12T0950", "2026-11-12T1820"]
    assert mon.late_label(at(2026, 11, 12, 19, 30, ist), d) == "⏰ Gecikmiş rapor (planlanan 18:20 İstanbul)"
    assert mon.due_slots(at(2026, 11, 14, 12, 0, ist), ()) == []
    # ABD saat dilimine göre değil İstanbul'a göre: UTC 07:00 = 10:00 İstanbul
    assert mon.due_slots(at(2026, 11, 12, 7, 0, mon.ET.__class__("UTC")), ()) == ["2026-11-12T0950"]


@pytest.mark.parametrize("market", ["us", "bist"])
def test_auto_run_sends_one_late_report_and_marks_all_owed(load, tmp_path, outbox, market):
    mon = load(market).monitor
    tz = mon.IST if market == "bist" else mon.ET
    (setup_bist if market == "bist" else setup_root)(tmp_path)
    mon.attach_ext = lambda *a, **k: None
    mon.apply_extended = lambda quotes, tickers, now: (quotes, None)
    now = at(2026, 11, 12, 23, 0, tz) if market == "us" else at(2026, 11, 12, 20, 0, tz)
    t = now.timestamp() - 3600
    quotes = {"AAA": q(110, t), "BBB": q(20, t)}
    mon.run(report="auto", fetch=lambda tk, k: quotes.get(tk), status_fn=lambda k: {"isOpen": False}, now=now)
    msgs = outbox()
    assert len(msgs) == 1 and msgs[0].startswith("⏰ Gecikmiş rapor")
    state = read_json(tmp_path, "state.json" if market == "us" else "bist/state.json")
    assert len(state["reports"]) == 2
    # aynı gün sonraki çalışma: artık borç yok -> yeni rapor yok
    mon.run(report="auto", fetch=lambda tk, k: quotes.get(tk), status_fn=lambda k: {"isOpen": False},
            now=at(2026, 11, 12, 23, 30, tz))
    assert len(outbox()) == 1


def test_auto_run_on_time_report_has_no_late_line(load, tmp_path, outbox):
    mon = load().monitor
    setup_root(tmp_path)
    mon.attach_ext = lambda *a, **k: None
    mon.apply_extended = lambda quotes, tickers, now: (quotes, None)
    now = at(2026, 11, 12, 9, 35)
    t = epoch(2026, 11, 11, 15, 59)
    quotes = {"AAA": q(110, t), "BBB": q(20, t)}
    mon.run(report="auto", fetch=lambda tk, k: quotes.get(tk), status_fn=lambda k: {"isOpen": False}, now=now)
    msgs = outbox()
    assert len(msgs) == 1 and "Gecikmiş" not in msgs[0] and msgs[0].startswith("<b>📊 Portföy Raporu")


# ------------------------------------------------------------------ B11 aylık hedef + perf_summary
def _hist():
    return {"transactions": [{"date": "2026-11-06", "action": "deposit", "amount": 100.0}],
            "snapshots": [{"date": "2026-10-30", "value": 1000.0}, {"date": "2026-11-02", "value": 1050.0},
                          {"date": "2026-11-05", "value": 1100.0}]}


def test_perf_summary_small_example(load):
    c = load().common
    p = c.perf_summary(_hist(), 1210.0, "2026-11-12")
    # taban: ayın ilk gününden ÖNCEKİ son kayıt (30 Eki = 1000); 100 yatırma akıştır
    assert p["Ay"]["gain"] == pytest.approx(110.0)
    assert p["Ay"]["twr"] == pytest.approx(((1050 / 1000) * (1100 / 1050) * ((1210 - 100) / 1100) - 1) * 100)
    assert p["Hafta"]["gain"] == pytest.approx(60.0)  # t-7 = 5 Kas -> son kayıt < 5 Kas = 2 Kas (1050): 1210-1050-100
    assert c.perf_summary({"snapshots": []}, 1.0, "2026-11-12") is None


def test_monthly_target_uses_same_base_as_month_line(load):
    mods = load()
    c, mon = mods.common, mods.monitor
    assert not hasattr(c, "month_progress")
    pf = base_portfolio(monthly_target=500, cash=110.0)
    quotes = {"AAA": q(110, 0), "BBB": q(20, 0)}
    summary = c.summarize(pf, quotes)  # 110 + 10*110 = 1210
    mon.history_for_report = _hist()
    text = mon.build_report(pf, quotes, quotes, summary, False, [], at(2026, 11, 12, 17, 0), None)
    assert "Ay: +110" in text
    # önceki ay sonu tabanı (1000): kazanç +110. Ay içi ilk kayıt (1050) olsaydı +60 çıkardı.
    assert "Aylık hedef: +110" in text and "(%22)" in text
    assert "Aylık hedef: +60" not in text
