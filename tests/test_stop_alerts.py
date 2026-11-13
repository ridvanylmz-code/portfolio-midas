"""B5 stop kuralı, takip eden stop (yalnız piyasa kapalıyken), B12 hareket alarmı, B32 sınırda, B39."""
import json
import sys
from datetime import date, datetime, timezone

from conftest import SCRIPTS, base_portfolio, write_json


# ------------------------------------------------------------------ B5: ATR stop kuralı
def test_atr_stop_is_close_minus_two_atr_without_clamp_or_high_leg(load):
    m = load()
    mk = m.market
    # eski kural: 3A tepe 150 ise stop = min(150-6, 100-2)=98 ile max(96, 98) = 98 olurdu; yenisi 96
    assert mk.atr_stop({"close": 100, "atr": 2, "high3m": 150}) == 96.0
    assert mk.atr_stop({"close": 56.60, "atr": 6.49, "high3m": 90}) == 43.62
    assert mk.atr_stop({"close": 100, "atr": None}) is None
    assert mk.atr_stop({"close": None, "atr": 2}) is None


def test_bist_generator_uses_same_stop_rule_and_method_text(load):
    m = load("bist")
    assert m.market_bist.mk.atr_stop is m.market.atr_stop
    src = (SCRIPTS / "market_bist.py").read_text(encoding="utf-8")
    assert "kapanış − 2×ATR" in src and "3×ATR" not in src
    src_us = (SCRIPTS / "market.py").read_text(encoding="utf-8")
    assert "kapanış − 2×ATR" in src_us and "3A tepeden 3×ATR" not in src_us


# ------------------------------------------------------------------ takip eden stop
def _market(stop, updated="2026-11-12", **row):
    return {"updated": updated + "T20:00:00+00:00", "stocks": {"AAA": {"stop_atr": stop, **row}}}


TODAY = date(2026, 11, 12)


def test_trail_only_when_market_closed(load):
    c = load().common
    q = {"AAA": {"c": 100.0}}
    for mo in (None, True):
        pf = base_portfolio()
        assert c.trail_stops(pf, q, _market(90), TODAY, market_open=mo) == []
        assert pf["position_levels"] == {}
    assert c.trail_stops(base_portfolio(), q, _market(90), TODAY) == []  # varsayılan: bilinmiyor -> taşıma yok
    pf = base_portfolio()
    out = c.trail_stops(pf, q, _market(90), TODAY, market_open=False)
    assert len(out) == 1 and pf["position_levels"]["AAA"]["stop_loss"] == 90.0


def test_trail_only_upward(load):
    c = load().common
    q = {"AAA": {"c": 100.0}}
    pf = base_portfolio(position_levels={"AAA": {"stop_loss": 95.0}})
    assert c.trail_stops(pf, q, _market(90), TODAY, market_open=False) == []   # aşağı inmez
    assert pf["position_levels"]["AAA"]["stop_loss"] == 95.0
    assert c.trail_stops(pf, q, _market(95.2), TODAY, market_open=False) == []  # %0,5'ten az adım
    out = c.trail_stops(pf, q, _market(97), TODAY, market_open=False)
    assert out and pf["position_levels"]["AAA"]["stop_loss"] == 97.0


def test_trail_guards(load):
    c = load().common
    q = {"AAA": {"c": 100.0}}
    run = lambda pf, mk, quotes=q: c.trail_stops(pf, quotes, mk, TODAY, market_open=False)  # noqa: E731
    assert run(base_portfolio(position_levels={"AAA": {"trail": False}}), _market(90)) == []
    assert run(base_portfolio(), _market(90, stale=True)) == []
    assert run(base_portfolio(), _market(90, updated="2026-11-01")) == []        # veri 5 günden eski
    assert run(base_portfolio(), _market(99.9)) == []                              # fiyatın %0,5 altında değil
    assert run(base_portfolio(), _market(90), quotes={}) == []                     # güncel fiyat yok
    assert run(base_portfolio(position_levels={"AAA": {"target": 85.0}}), _market(90)) == []  # hedefin altında kalmalı
    assert run(base_portfolio(), None) == []


# ------------------------------------------------------------------ B12 hareket alarmı
def test_move_alert_only_when_market_open(load):
    c = load().common
    q = {"AAA": {"c": 100.0, "dp": 7.0}}
    keys = lambda mo: {a["key"] for a in c.check_alerts(base_portfolio(), q, mo)}  # noqa: E731
    assert "AAA:move_up" in keys(True)
    assert "AAA:move_up" not in keys(False)
    assert "AAA:move_up" not in keys(None)


def test_stop_target_zone_alerts_unaffected_by_market_state(load):
    c = load().common
    pf = base_portfolio(position_levels={"AAA": {"stop_loss": 105.0, "target": 99.0}},
                        buy_zones={"BBB": {"below": 20.0}})
    q = {"AAA": {"c": 100.0, "dp": 9.0}, "BBB": {"c": 19.0}}
    got = {a["key"] for a in c.check_alerts(pf, q, False)}
    assert {"AAA:stop", "AAA:target", "BBB:zone_below:20.0"} <= got
    assert not any("move" in k for k in got)


# ------------------------------------------------------------------ B32 sınırda
def test_borderline_flag(load):
    mk = load().market
    assert mk.borderline(3, 7) is True      # 3/7=0,43 < 0,45; bir puan artsa nötr
    assert mk.borderline(4, 7) is True
    assert mk.borderline(5, 7) is True      # 6/7 = 0,857 risk-on
    assert mk.borderline(7, 7) is False
    assert mk.borderline(0, 7) is False
    reg = mk.regime({"SPY": {"close": 100, "SMA50": 90, "SMA200": 80, "Perf.1M": 1},
                     "QQQ": {"close": 100, "SMA50": 90}, "IWM": {"close": 80, "SMA50": 90},
                     "RSP": {"Perf.1M": 1}}, [], {})
    assert reg["borderline"] == mk.borderline(reg["score"], reg["max"])


def test_market_lines_marks_borderline(load, tmp_path, monkeypatch):
    mon = load().monitor
    f = write_json(tmp_path, "m.json", {"regime": {"label": "Nötr / seçici", "score": 3, "max": 7,
                                                   "cash_target": [20, 25], "borderline": True}, "groups": []})
    monkeypatch.setenv("MARKET_JSON", str(f))
    assert "Nötr / seçici (sınırda) (3/7)" in mon.market_lines({"cash_pct": 22.0})[0]
    write_json(tmp_path, "m.json", {"regime": {"label": "Nötr / seçici", "score": 3, "max": 7,
                                               "cash_target": [20, 25], "borderline": False}, "groups": []})
    assert "sınırda" not in mon.market_lines({"cash_pct": 22.0})[0]


# ------------------------------------------------------------------ B39
def test_overlay_recomputes_supertrend_distance(load, monkeypatch):
    mods = load()
    fake = type(sys)("extended")
    fake.session_name = lambda now: "pre"
    fake.fetch = lambda tickers: ({"AAA": {"pre": 98.0, "pre_pct": -1.0}}, None)
    monkeypatch.setitem(sys.modules, "extended", fake)
    trend = mods.trend
    out = {"AAA": {"price": 100.0, "state": "bullish", "st15": {"dir": "up", "line": 95.0, "dist_pct": 5.0}}}
    assert trend.overlay_extended(out) == "pre"
    assert out["AAA"]["price"] == 98.0
    assert out["AAA"]["st15"]["dist_pct"] == round((98.0 - 95.0) / 98.0 * 100, 2)
