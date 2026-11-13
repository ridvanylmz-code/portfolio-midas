"""B33: bars-bist.json'a `last_date` (hisselerin çoğunun son mum tarihi) yazılır. Ağ yok: fetch sahte."""
import json

import bist_bars


def rows(last):
    return [[f"2026-10-{d:02d}", 1, 1, 1, 1] for d in range(1, 29)] + [[last, 1, 1, 1, 1], [last, 1, 1, 1, 1]]


def test_last_date_is_most_common(tmp_path, monkeypatch):
    data = {"AAA": rows("2026-11-11"), "BBB": rows("2026-11-11"), "CCC": rows("2026-11-10")}
    monkeypatch.setattr(bist_bars, "fetch", lambda t, days: data[t])
    (tmp_path / "t.txt").write_text("AAA BBB CCC\n", encoding="utf-8")
    out = tmp_path / "o.json"
    assert bist_bars.main(["--file", str(tmp_path / "t.txt"), "--out", str(out)]) == 0
    j = json.loads(out.read_text(encoding="utf-8"))
    assert j["last_date"] == "2026-11-11" and set(j["bars"]) == {"AAA", "BBB", "CCC"} and "updated" in j
