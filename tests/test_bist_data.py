"""B36: Yahoo mum tarihi kontrolü, TradingView yedeği, stale işareti (ağ yok: yfinance ve requests sahte)."""
import sys
from datetime import datetime, timezone

import pandas as pd

from conftest import IST, at


def make_df(bars):
    """bars: {TICKER: [(tarih, kapanış), ...]} -> yfinance (group_by=ticker) biçimli DataFrame."""
    frames = []
    for t, rows in bars.items():
        idx = pd.DatetimeIndex([pd.Timestamp(d) for d, _ in rows])
        cols = pd.MultiIndex.from_product([[t + ".IS"], ["Open", "High", "Low", "Close", "Volume"]])
        data = [[c, c, c, c, 1000] for _, c in rows]
        frames.append(pd.DataFrame(data, index=idx, columns=cols))
    return pd.concat(frames, axis=1, sort=True)


def fake_yf(monkeypatch, bars):
    mod = type(sys)("yfinance")
    mod.download = lambda *a, **k: make_df(bars)
    monkeypatch.setitem(sys.modules, "yfinance", mod)


class FakeResp:
    def __init__(self, rows):
        self.rows = rows

    def raise_for_status(self):
        pass

    def json(self):
        return {"data": [{"s": f"BIST:{t}", "d": [c, chg, c, c, c]} for t, c, chg in self.rows]}


def fake_tv(monkeypatch, bd, rows):
    monkeypatch.setattr(bd.requests, "post", lambda *a, **k: FakeResp(rows))


def test_expected_session(load):
    bd = load("bist").bist_data
    ex = lambda *a: bd.expected_session(at(*a, tz=IST))  # noqa: E731
    assert str(ex(2026, 11, 12, 9, 0)) == "2026-11-11"     # Per 09:00 -> Çarşamba
    assert str(ex(2026, 11, 12, 10, 0)) == "2026-11-12"    # Per 10:00 -> bugün
    assert str(ex(2026, 11, 12, 23, 0)) == "2026-11-12"
    assert str(ex(2026, 11, 14, 12, 0)) == "2026-11-13"    # Cumartesi -> Cuma
    assert str(ex(2026, 11, 15, 12, 0)) == "2026-11-13"    # Pazar -> Cuma
    assert str(ex(2026, 11, 16, 9, 59)) == "2026-11-13"    # Pazartesi sabahı -> Cuma


def test_tv_stamp_not_later_than_last_completed_session(load):
    bd = load("bist").bist_data
    tr = lambda *a: datetime.fromtimestamp(bd._stamp(at(*a, tz=IST)), IST)  # noqa: E731
    assert tr(2026, 11, 12, 11, 0) == at(2026, 11, 12, 11, 0, tz=IST)            # seans açık: şimdi
    assert tr(2026, 11, 12, 20, 0) == at(2026, 11, 12, 18, 10, tz=IST)           # kapanış sonrası
    assert tr(2026, 11, 14, 11, 0) == at(2026, 11, 13, 18, 10, tz=IST)           # hafta sonu
    assert tr(2026, 11, 17, 0, 30) == at(2026, 11, 16, 18, 10, tz=IST)           # gece yarısından sonra


def test_stale_yahoo_falls_through_to_tradingview(load, monkeypatch):
    bd = load("bist").bist_data
    now = at(2026, 11, 12, 19, 0, tz=IST)  # beklenen son seans 12 Kas
    fake_yf(monkeypatch, {
        "AAA": [("2026-11-11", 10.0), ("2026-11-12", 11.0)],     # güncel
        "BBB": [("2026-11-10", 20.0), ("2026-11-11", 21.0)],     # bayat, TV farklı kapanış veriyor
        "CCC": [("2026-11-10", 30.0), ("2026-11-11", 31.0)],     # bayat, TV aynı kapanışı veriyor
        "DDD": [("2026-11-10", 40.0), ("2026-11-11", 41.0)],     # bayat, TV'de yok
    })
    fake_tv(monkeypatch, bd, [("BBB", 19.0, -9.5), ("CCC", 31.0, 3.3)])
    fetch = bd.make_fetch(["AAA", "BBB", "CCC", "DDD"], now=now)
    day = lambda q: datetime.fromtimestamp(q["t"], IST).date().isoformat()  # noqa: E731
    a, b, c, d = (fetch(t) for t in ("AAA", "BBB", "CCC", "DDD"))
    assert a["c"] == 11.0 and not a.get("stale") and day(a) == "2026-11-12"
    assert b["c"] == 19.0 and not b.get("stale") and day(b) == "2026-11-12"   # TV yetkili; 18:10 damgası
    assert datetime.fromtimestamp(b["t"], IST).hour == 18
    # BBB'de kapanış değişmiş: yeni seans var, kapanışı aynı kalan CCC de günceldir (tatilde hepsi aynı kalır -> bayat)
    assert c["c"] == 31.0 and not c.get("stale") and day(c) == "2026-11-12"
    assert d["stale"] is True and d["c"] == 41.0 and day(d) == "2026-11-11"


def test_yahoo_batch_excludes_stale_and_reports_them(load, monkeypatch):
    bd = load("bist").bist_data
    fake_yf(monkeypatch, {"AAA": [("2026-11-10", 1.0), ("2026-11-11", 2.0)]})
    stale = {}
    assert bd.yahoo_batch(["AAA"], now=at(2026, 11, 12, 12, 0, tz=IST), stale_out=stale) == {}
    assert stale["AAA"]["stale"] is True
    # önceki iş günü sabahı: 11 Kas barı beklenen seans -> güncel
    assert "AAA" in bd.yahoo_batch(["AAA"], now=at(2026, 11, 12, 9, 0, tz=IST))


def test_unchanged_close_is_fresh_when_other_tickers_show_new_session(monkeypatch):
    """Yeni seans varsa (diğer hisselerde kapanış değişmiş) kapanışı aynı kalan hisse bayat sayılmaz; tatilde hepsi bayat."""
    import bist_data
    from datetime import datetime, timezone
    now = datetime(2026, 11, 12, 16, 0, tzinfo=timezone.utc)  # Per 19:00 İst.
    old_t = datetime(2026, 11, 11, tzinfo=timezone.utc).timestamp()
    stale = {t: {**bist_data._quote(10, 9, 10, 10, 10, old_t), "stale": True} for t in ("AAA", "BBB", "CCC")}

    def fake_yahoo(tickers, now=None, stale_out=None):
        stale_out.update(stale)
        return {}
    monkeypatch.setattr(bist_data, "yahoo_batch", fake_yahoo)
    ts = bist_data._stamp(now)
    monkeypatch.setattr(bist_data, "tradingview_batch", lambda tk, now=None: {
        "AAA": bist_data._quote(10, 10, 10, 10, 10, ts), "BBB": bist_data._quote(11, 10, 10, 11, 10, ts),
        "CCC": bist_data._quote(9, 10, 10, 10, 9, ts)})
    f = bist_data.make_fetch(["AAA", "BBB", "CCC"], now=now)
    assert not f("AAA").get("stale") and f("AAA")["t"] == int(ts)
    monkeypatch.setattr(bist_data, "tradingview_batch", lambda tk, now=None: {
        t: bist_data._quote(10, 9, 10, 10, 10, ts) for t in ("AAA", "BBB", "CCC")})
    f = bist_data.make_fetch(["AAA", "BBB", "CCC"], now=now)
    assert all(f(t).get("stale") and f(t)["t"] == int(old_t) for t in ("AAA", "BBB", "CCC"))
