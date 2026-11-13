"""Toplu giriş (B28), eski kopya taşıma (B7), holdings.json (B14), şifreli yol."""
import json

import pytest

from conftest import base_portfolio, read_json, write_json

KEY = "test-anahtar-123"


# ------------------------------------------------------------------ B28 toplu giriş
def mk_state():
    pf = base_portfolio(cash=10_000.0, watchlist=["AMD"],
                        portfolio={"CRWV": {"shares": 20, "cost_basis": 50.0}})
    return pf, {"transactions": [], "snapshots": []}


def test_parse_batch_formats(load):
    up = load().update_position
    ops = up.parse_batch("buy RKLB 10 52.3 1.5; sell CRWV 5 56\n# yorum\n\ndeposit 1000;withdraw 500\n"
                         "watch_add AMD; watch_remove AMD; zone_below AMD 95; zone_above AMD 120; zone_clear AMD; "
                         "trail_off CRWV; trail_on CRWV")
    assert [o[2]["action"] for o in ops] == ["buy", "sell", "deposit", "withdraw", "watch_add", "watch_remove",
                                              "zone_below", "zone_above", "zone_clear", "trail_off", "trail_on"]
    assert ops[0][2] == {"action": "buy", "ticker": "RKLB", "shares": "10", "price": "52.3", "commission": "1.5"}
    assert ops[1][2] == {"action": "sell", "ticker": "CRWV", "shares": "5", "price": "56"}


@pytest.mark.parametrize("bad", ["", "foo X 1", "buy RKLB 10", "deposit", "zone_clear", "buy A 1 2 3 4"])
def test_parse_batch_rejects(load, bad):
    with pytest.raises(ValueError):
        load().update_position.parse_batch(bad)


def test_batch_applies_all_in_order(load):
    up = load().update_position
    pf, hist = mk_state()
    pf2, hist2, msg = up.apply_batch(pf, hist, "deposit 1000; buy RKLB 10 50; sell CRWV 5 56; watch_add NVDA; "
                                     "zone_below NVDA 100; trail_off CRWV", quotes={})
    assert pf2["cash"] == pytest.approx(10_000 + 1000 - 500 + 280)
    assert pf2["portfolio"]["RKLB"]["shares"] == 10 and pf2["portfolio"]["CRWV"]["shares"] == 15
    assert "NVDA" in pf2["watchlist"] and pf2["buy_zones"]["NVDA"] == {"below": 100.0}
    assert pf2["position_levels"]["CRWV"]["trail"] is False
    assert len(hist2["transactions"]) == 6 and len({t["time"] for t in hist2["transactions"]}) == 6
    assert msg.startswith("📦 Toplu işlem (6 satır)") and "1. " in msg and "6. " in msg
    assert pf == mk_state()[0] and hist == mk_state()[1]  # girdi nesneleri değişmedi


def test_batch_all_or_nothing_names_failing_line(load):
    up = load().update_position
    pf, hist = mk_state()
    with pytest.raises(ValueError) as ei:
        up.apply_batch(pf, hist, "deposit 1000\nbuy RKLB 10 50\nsell NOPE 5 56\nwatch_add AMD", quotes={})
    assert "Satır 3 (sell NOPE 5 56)" in str(ei.value)
    assert pf == mk_state()[0] and hist == mk_state()[1]


def test_batch_main_one_save_one_message_and_failure_saves_nothing(load, tmp_path, outbox):
    mods = load()
    up = mods.update_position
    pf, hist = mk_state()
    write_json(tmp_path, "docs/data/portfolio.json", pf)
    write_json(tmp_path, "docs/data/history.json", hist)
    before = (tmp_path / "docs/data/portfolio.json").read_bytes()
    assert up.main(["--batch", "deposit 100; buy RKLB 10 50; sell NOPE 1 1"]) == 1
    assert (tmp_path / "docs/data/portfolio.json").read_bytes() == before
    assert len(outbox()) == 1 and "Satır 3" in outbox()[0]
    assert up.main(["--batch", "deposit 100; buy RKLB 10 50"]) == 0
    saved = read_json(tmp_path, "docs/data/portfolio.json")
    assert saved["portfolio"]["RKLB"]["shares"] == 10 and saved["cash"] == pytest.approx(10_000 + 100 - 500)
    assert len(read_json(tmp_path, "docs/data/history.json")["transactions"]) == 2
    msgs = outbox()
    assert len(msgs) == 2 and "Toplu işlem (2 satır)" in msgs[1]
    assert (tmp_path / "docs/data/holdings.json").exists()


# ------------------------------------------------------------------ B7 eski kopya taşıma
def test_migrate_plain_legacy_is_authoritative(load, tmp_path):
    c = load().common
    legacy = {"cash": 5.0, "portfolio": {}, "watchlist": []}
    write_json(tmp_path, "portfolio.json", legacy)
    write_json(tmp_path, "docs/data/portfolio.json", {"cash": 1.0})
    write_json(tmp_path, "history.json", {"transactions": [], "snapshots": []})
    raw = (tmp_path / "portfolio.json").read_bytes()
    assert sorted(c.migrate_legacy()) == ["history.json", "portfolio.json"]
    assert (tmp_path / "docs/data/portfolio.json").read_bytes() == raw
    assert not (tmp_path / "portfolio.json").exists() and not (tmp_path / "history.json").exists()
    assert c.migrate_legacy() == []  # ikinci çağrı etkisiz
    assert c.load_portfolio()["cash"] == 5.0


def test_migrate_encrypted_envelope_moved_byte_identical(load, tmp_path):
    c = load(key=KEY).common
    pf = base_portfolio(cash=777.0)
    env = c.vault_encrypt(pf, KEY)
    raw = json.dumps(env, indent=1).encode() + b"\n"
    (tmp_path / "portfolio.json").write_bytes(raw)
    write_json(tmp_path, "docs/data/portfolio.json", {"cash": 1.0})   # eski/farklı docs kopyası
    c.migrate_legacy()
    assert (tmp_path / "docs/data/portfolio.json").read_bytes() == raw
    assert not (tmp_path / "portfolio.json").exists()
    assert c.load_portfolio()["cash"] == 777.0                          # test anahtarıyla çözülür
    assert c.is_vault(json.loads(raw))


def test_migrate_bist_legacy_and_load_triggers_it(load, tmp_path):
    c = load("bist").common
    assert c.F_PORTFOLIO == "docs/bist/data/portfolio.json" and c.F_STATE == "bist/state.json"
    write_json(tmp_path, "bist/portfolio.json", base_portfolio(cash=42.0))
    write_json(tmp_path, "bist/history.json", {"transactions": [{"date": "2026-11-01", "action": "deposit", "amount": 1}],
                                              "snapshots": []})
    write_json(tmp_path, "bist/state.json", {"date": "x"})
    assert c.load_portfolio()["cash"] == 42.0                           # load_portfolio göçü tetikler
    assert len(c.load_history()["transactions"]) == 1
    assert not (tmp_path / "bist/portfolio.json").exists() and not (tmp_path / "bist/history.json").exists()
    assert (tmp_path / "bist/state.json").exists()                      # state kökte kalır


def test_defter_paths_point_to_docs_copy(load):
    d = load().defter
    assert d.ACCOUNTS["midas_usd"]["src"] == "docs/data/history.json"
    assert d.ACCOUNTS["midas_tr"]["src"] == "docs/bist/data/history.json"
    assert d.TX_SRC["midas_usd"][:2] == ("docs/data/history.json", "docs/data/portfolio.json")
    assert d.TX_SRC["midas_tr"][:2] == ("docs/bist/data/history.json", "docs/bist/data/portfolio.json")


# ------------------------------------------------------------------ B14 holdings.json, sync_public
@pytest.mark.parametrize("key", [None, KEY])
def test_sync_public_writes_symbols_and_holdings_only(load, tmp_path, key):
    c = load(key=key).common
    pf = base_portfolio(portfolio={"ZZZ": {"shares": 3, "cost_basis": 9.0}, "AAA": {"shares": 10, "cost_basis": 50.0}},
                        watchlist=["BBB", "AAA"])
    c.save_json(c.F_PORTFOLIO, pf)
    c.save_json(c.F_HISTORY, {"transactions": [], "snapshots": []})
    before = (tmp_path / "docs/data/portfolio.json").read_bytes()
    c.sync_public()
    assert (tmp_path / "docs/data/portfolio.json").read_bytes() == before   # sync artık portföyü yeniden yazmaz
    h = read_json(tmp_path, "docs/data/holdings.json")
    assert h["holdings"] == ["AAA", "ZZZ"] and set(h) == {"updated", "holdings"}
    from datetime import datetime
    assert datetime.fromisoformat(h["updated"]).utcoffset().total_seconds() == 0
    assert read_json(tmp_path, "docs/data/symbols.json") == {"tickers": ["AAA", "BBB", "ZZZ"]}
    assert "shares" not in (tmp_path / "docs/data/holdings.json").read_text()
    assert c.is_vault(json.loads(before)) == bool(key)
