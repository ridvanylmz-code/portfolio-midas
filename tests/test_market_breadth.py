"""B32: ABD rejim genişliği hisse tarama havuzundan (market_bist ile aynı tanım); havuz yoksa eski hesap."""
BENCH = {"SPY": {"close": 100, "SMA50": 90, "SMA200": 80, "Perf.1M": 1},
         "QQQ": {"close": 100, "SMA50": 90}, "IWM": {"close": 80, "SMA50": 90}, "RSP": {"Perf.1M": 1}}


def rows(n_up, n_down):
    """Sentetik havuz: n_up hisse SMA50 üstünde, n_down altında."""
    return ([{"name": f"U{i}", "close": 110.0, "SMA50": 100.0} for i in range(n_up)]
            + [{"name": f"D{i}", "close": 90.0, "SMA50": 100.0} for i in range(n_down)])


def breadth_check(reg):
    return [c for c in reg["checks"] if c[0].startswith("Genişlik")][0]


def test_pool_breadth_counts_only_rows_with_close_and_sma50(load):
    mk = load().market
    pool = rows(30, 10) + [{"name": "X1", "close": None, "SMA50": 50}, {"name": "X2", "close": 5}, {"name": "X3"}]
    assert mk.pool_breadth(pool) == (75, 40)          # 30/40; eksik alanlı 3 satır sayılmaz


def test_pool_breadth_unavailable_or_too_small(load):
    mk = load().market
    assert mk.pool_breadth(None) == (None, 0)
    assert mk.pool_breadth([]) == (None, 0)
    assert mk.pool_breadth(rows(10, 10)) == (None, 20)   # MIN_POOL (30) altı: güvenilmez


def test_regime_uses_pool_not_mixed_universe(load):
    mk = load().market
    # eski karışık hesap %100 üstte görünür; havuz %25 üstte: karar havuzdan gelmeli
    mixed = [{"close": 10, "sma50": 5}] * 50
    reg = mk.regime(BENCH, mixed, {}, rows(10, 30))
    lbl, ok = breadth_check(reg)
    assert reg["breadth50"] == 25 and ok is False
    assert lbl == "Genişlik: 40 hisselik havuzun %25'i SMA50 üstünde (>%50)"
    # eşik ve puanlama aynı: %50 sınırı dahil değil (>%50)
    assert breadth_check(mk.regime(BENCH, [], {}, rows(20, 20)))[1] is False
    assert breadth_check(mk.regime(BENCH, [], {}, rows(21, 19)))[1] is True


def test_regime_falls_back_to_mixed_and_says_so(load):
    mk = load().market
    mixed = [{"close": 10, "sma50": 5}] * 6 + [{"close": 1, "sma50": 5}] * 4
    for pool in (None, [], rows(5, 5)):
        reg = mk.regime(BENCH, mixed, {}, pool)
        lbl, ok = breadth_check(reg)
        assert reg["breadth50"] == 60 and ok is True
        assert "hisse havuzu yok" in lbl and "10 kalem" in lbl
    # çağrı eski imzayla (havuz verilmeden) da çalışır
    assert mk.regime(BENCH, mixed, {})["breadth50"] == 60


def test_regime_score_changes_only_through_breadth(load):
    mk = load().market
    base = mk.regime(BENCH, [], {}, rows(0, 40))
    up = mk.regime(BENCH, [], {}, rows(40, 0))
    assert base["max"] == up["max"] and up["score"] == base["score"] + 1


def test_build_picks_returns_deduplicated_pool_rows(load, monkeypatch):
    mk = load().market
    big = [{"name": "AAA", "industry": "Software", "sector": "Tech", "close": 10, "SMA50": 9},
           {"name": "HPE/PC", "industry": "Software", "sector": "Tech", "close": 10, "SMA50": 9},
           {"name": "ZZZ", "industry": "?", "sector": "?", "close": 10, "SMA50": 9}]   # grubu yok: havuza girmez
    cur = {"AAA": big[0], "BBB": {"name": "BBB", "close": 5, "SMA50": 6}}
    monkeypatch.setattr(mk.tvscan, "screen", lambda *a, **k: big)
    monkeypatch.setattr(mk.tvscan, "fetch", lambda *a, **k: cur)
    uni = {"sector_group": {}, "picks": {"industry_group": {"Software": "IGV"}, "theme_candidates": {"IGV": ["AAA", "BBB"]}}}
    out, n, pool = mk.build_picks(uni, {}, {}, set())
    assert n == 3 and sorted(x["name"] for x in pool) == ["AAA", "BBB"]
