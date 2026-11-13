"""B15: aynı getiri hesabı Python'da ve tarayıcı JS'inde var. Aynı sentetik veriyi ikisine de verip sonuçları
karşılaştırır (bağıl tolerans 1e-9); biri sessizce kayarsa test düşer. JS tarafı node ile çalışır (yoksa atlanır).
Ağ yok, gerçek veri yok."""
import json
import math
import re
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node kurulu değil: JS/Python tutarlılık testleri atlandı")
TOL = 1e-9


def run_node(code, payload):
    r = subprocess.run([NODE, "-e", code], input=json.dumps(payload), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def close(a, b):
    if a is None or b is None:
        return a is None and b is None
    return math.isclose(a, b, rel_tol=TOL, abs_tol=1e-9)


# ------------------------------------------------------------------ a) docs/perf.js ↔ common.perf_summary
# perf.js yalnız window'a bağlanır (yükleme anında DOM'a dokunmaz). period() dışa açık değil: bellekteki kaynak
# metne eklenerek dışarı verilir (dosya değişmez).
PERF_JS = r"""
const fs = require('fs');
global.window = {}; global.document = { getElementById() { return null }, createElement() { return {} }, head: { appendChild() {} } };
const inp = JSON.parse(fs.readFileSync(0, 'utf8'));
let src = fs.readFileSync(inp.js, 'utf8');
const hook = 'window.PerfView = {';
if (!src.includes(hook)) throw new Error('PerfView dışa aktarımı bulunamadı');
(0, eval)(src.replace(hook, hook + ' period: period,'));
const S = window.PerfView.series(inp.H, { cash: 0 }, inp.total, inp.today);
const out = {};
for (const [k, from] of Object.entries(inp.from)) { const p = window.PerfView.period(S, from); out[k] = p && { gain: p.gain, twr: p.twr, start: p.start.date }; }
console.log(JSON.stringify(out));
"""


def perf_history(days, skip=()):
    """Günlük kayıtlar (yıl sınırını geçer); bir günü 0 değerli (yok sayılmalı), akışlar aralarda."""
    snaps, d = [], date(2026, 12, 1)
    for i in range(days):
        ds = d.isoformat()
        if ds not in skip:
            snaps.append({"date": ds, "value": round(10000 + 300 * math.sin(i / 3) + 40 * i, 2), "cash": 100})
        d += timedelta(days=1)
    for s in snaps:
        if s["date"] == "2026-12-10":
            s["value"] = 0            # portföy girilmeden önceki kayıt: ikisi de yok saymalı
    tx = [{"date": "2026-12-05", "action": "deposit", "amount": 1500},
          {"date": "2026-12-14", "action": "withdraw", "amount": 700},
          {"date": "2026-12-20", "action": "deposit", "amount": 999, "undone": True},   # geri alınmış
          {"date": "2026-12-31", "action": "deposit", "amount": 2000},
          {"date": "2027-01-06", "action": "withdraw", "amount": 400},
          {"date": "2027-01-13", "action": "deposit", "amount": 800},
          {"date": "2027-01-15", "action": "buy", "amount": 5555}]                       # akış değil
    return {"snapshots": snaps, "transactions": tx}


def perf_cases():
    full = perf_history(50)
    gaps = perf_history(50, skip={"2026-12-31", "2027-01-01", "2027-01-13", "2027-01-23"})   # ay/yıl sonu ve t-7 yok
    return [("daily-jan", full, "2027-01-20", 12345.67), ("daily-jan-gaps", gaps, "2027-01-20", 12345.67),
            ("daily-dec", full, "2026-12-27", 11000.5), ("gaps-jan-30", gaps, "2027-01-30", 13000.0)]


@pytest.mark.parametrize("name,hist,today,total", perf_cases(), ids=[c[0] for c in perf_cases()])
def test_perf_js_matches_common_perf_summary(load, name, hist, today, total):
    common = load().common
    t = date.fromisoformat(today)
    hist = dict(hist, snapshots=[s for s in hist["snapshots"] if s["date"] <= today])   # gelecek kaydı olmaz
    py = common.perf_summary(hist, total, today)
    # JS dönem başlangıçları (perf.js ozet()): hafta = bugün−7, ay = önceki ay sonu, yıl = önceki yıl 31 Ara.
    # Python'daki tanımlar aynı günlere denk gelmeli: "Hafta" t−7 (dahil), "Ay"/"Yıl" önceki dönem sonu.
    frm = {"Hafta": (t - timedelta(days=7)).isoformat(), "Ay": (date(t.year, t.month, 1) - timedelta(days=1)).isoformat(),
           "Yıl": f"{t.year - 1}-12-31"}
    js = run_node(PERF_JS, {"js": str(ROOT / "docs/perf.js"), "H": hist, "total": total, "today": today, "from": frm})
    # JS 'Başlangıçtan' vb. Python'da yok; yalnız ortak üç dönem karşılaştırılır
    assert set(py) == {k for k, v in js.items() if v}, (py.keys(), js)
    for k in py:
        assert close(py[k]["gain"], js[k]["gain"]), (k, py[k], js[k])
        assert close(py[k]["twr"], js[k]["twr"]), (k, py[k], js[k])


# ------------------------------------------------------------------ b) defter/index.html ↔ defter.py
HTML = (ROOT / "docs/defter/index.html").read_text(encoding="utf-8")


def js_source():
    """Sayfanın satır içi betiğinden build/pkey/periods ile ACC/GRP sabitlerini çıkarır (DOM'suz çalışsın)."""
    scripts = re.findall(r"<script>([\s\S]*?)</script>", HTML)
    body = next(s for s in scripts if "function build(" in s)
    consts = re.search(r"var ACC=[\s\S]*?\nvar GRP=[\s\S]*?\}\};", body)
    assert consts, "ACC/GRP sabitleri bulunamadı"
    parts = [consts.group(0)]
    for fn in ("build", "pkey", "periods"):
        i = body.index(f"function {fn}(")
        j, depth, q = body.index("{", i), 0, None
        for k in range(j, len(body)):          # gövdeyi süslü parantez eşleştirmesiyle al (dizgeler atlanır)
            ch = body[k]
            if q:
                if ch == "\\":
                    continue
                if ch == q and body[k - 1] != "\\":
                    q = None
            elif ch in "\"'`":
                q = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    parts.append(body[i:k + 1])
                    break
    assert len(parts) == 4
    return "\n".join(parts)


DEFTER_JS = r"""
const inp = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const f = new Function('D', 'kinds', inp.src + `
  var ROWS = build(); var out = {rows: ROWS, p: {}};
  kinds.forEach(function (k) { out.p[k] = periods(k) });
  out.keys = inp_dates.map(function (d) { return [d, pkey(d, 'w'), pkey(d, 'm'), pkey(d, 'y')] });
  return out;`.replace('inp_dates', JSON.stringify(inp.dates)));
console.log(JSON.stringify(f(inp.D, ['w', 'm', 'y'])));
"""


def ledger():
    """4 hesap, ~90 gün (yıl sınırını geçer): Info-TR sonradan başlar (başlangıçtan önceki kayıt yok sayılır),
    IBKR bir gün geriden gelir (son gün ve iki gün daha yok), akış, yedek değişimi, boşluklu endeks."""
    accounts = {"midas_tr": {"cur": "TRY", "reserve": 90000}, "info_tr": {"cur": "TRY", "reserve": 25000, "start": "2026-11-20"},
                "midas_usd": {"cur": "USD", "reserve": 0, "start": "2026-10-14"},
                "ibkr": {"cur": "USD", "reserve": 0, "start": "2026-10-25"}}
    val = {"midas_tr": 100000.0, "info_tr": 50000.0, "midas_usd": 8000.0, "ibkr": 3000.0}
    days, d = [], date(2026, 10, 14)
    for i in range(90):
        ds = d.isoformat()
        x = {"d": ds, "a": {}}
        for j, (acc, v0) in enumerate(val.items()):
            if acc == "ibkr" and (i in (40, 41) or i == 89):      # gecikme: kayıt yok, grup toplamında taşınır
                continue
            if acc == "info_tr" and i < 10:                       # başlangıçtan önce de kayıt var: atlanmalı
                pass
            chg = round(v0 * 0.01 * math.sin(i * (j + 2) / 5), 2)
            flow = 500.0 if (acc == "midas_usd" and i == 30) else -2000.0 if (acc == "midas_tr" and i == 55) else 0.0
            val[acc] = round(val[acc] + chg + flow, 2)
            e = {"v": val[acc], "s": "a"}
            if i > 0:
                e["c"] = chg
            if flow:
                e["f"] = flow
            if acc == "midas_tr" and i >= 60:
                e["r"] = 95000                                   # yedek değişimi (v, c, pct'yi etkilemez)
            x["a"][acc] = e
        if i % 4 != 3:
            x["xu"] = round(9000 + 15 * i + 40 * math.sin(i), 2)
        if i % 3 != 1 and i < 80:
            x["sp"] = round(6000 + 4 * i + 10 * math.cos(i), 2)
        days.append(x)
        d += timedelta(days=1)
    return {"accounts": accounts, "days": days}


def test_defter_js_matches_python(load):
    m = load("us", key="k").defter
    L = ledger()
    kinds = {"w": "W", "m": "M", "y": "Y"}
    js = run_node(DEFTER_JS, {"src": js_source(), "D": L, "dates": [x["d"] for x in L["days"]]})

    # ---- gün gün
    py_rows = m.daily_rows(L)
    assert [r["d"] for r in py_rows] == [r["d"] for r in js["rows"]]
    for pr, jr in zip(py_rows, js["rows"]):
        assert set(pr["a"]) == set(jr["a"]), pr["d"]               # başlangıç öncesi kayıtlar ikisinde de elenir
        for acc, e in pr["a"].items():
            assert close(e["pct"], jr["a"][acc]["pct"]), (pr["d"], acc)
            assert close(e["v"], jr["a"][acc]["v"]), (pr["d"], acc)
        for grp, accs in m.GROUPS:
            jg = jr.get(grp)
            assert (grp in pr["g"]) == (jg is not None), (pr["d"], grp)
            if jg is None:
                continue
            assert close(pr["g"][grp]["v"], jg["v"]), (pr["d"], grp)          # ileri doldurmalı grup değeri
            assert pr["g"][grp]["carry"] == [[c["a"], c["d"]] for c in jg["carry"]], (pr["d"], grp)
            ok = [pr["a"][a] for a in accs if a in pr["a"] and pr["a"][a]["pct"] is not None]
            num, den = sum(e["c"] for e in ok), sum(e["pv"] for e in ok)   # Python'da gün başına grup % yok: dönemde türetilir
            assert close(num if ok else None, jg["c"]) and close(num / den if den else None, jg["pct"]), (pr["d"], grp)
        for k in ("xu", "sp"):
            assert close(pr.get(k + "p"), jr.get(k + "p")), (pr["d"], k)
    assert any(r["g"]["usd"]["carry"] for r in py_rows)              # senaryo gerçekten ileri doldurma içeriyor
    assert any(len(r["a"]) < 4 for r in py_rows)

    # ---- hafta / ay / yıl
    for jk, pk in kinds.items():
        py_p, js_p = m.periods(L, pk), js["p"][jk]
        assert [p["k"] for p in py_p] == [p["k"] for p in js_p], jk
        for pp, jp in zip(py_p, js_p):
            assert (pp["from"], pp["to"]) == (jp["from"], jp["to"])
            for acc, e in pp["a"].items():
                je = jp["a"][acc]
                assert close(e["v"], je["v"]) and close(e["pct"], je["pct"]), (jk, pp["k"], acc)
                if e["pct"] is not None:
                    assert close(e["c"], je["c"]), (jk, pp["k"], acc)
            assert set(pp["a"]) == set(jp["a"])
            for grp, _ in m.GROUPS:
                assert (grp in pp) == (grp in jp), (jk, pp["k"], grp)
                if grp in pp:
                    assert close(pp[grp]["v"], jp[grp]["v"]) and close(pp[grp]["pct"], jp[grp]["pct"]), (jk, pp["k"], grp)
                    if pp[grp]["pct"] is not None:
                        assert close(pp[grp]["c"], jp[grp]["c"]), (jk, pp["k"], grp)
                    assert pp[grp]["carry"] == [[c["a"], c["d"]] for c in jp[grp]["carry"]]
            for idx in ("xu", "sp"):
                assert (idx in pp) == (idx in jp), (jk, pp["k"], idx)
                if idx in pp:
                    assert close(pp[idx], jp[idx]) and close(pp[idx + "p"], jp[idx + "p"]), (jk, pp["k"], idx)

    # ---- ISO hafta anahtarı: yıl sınırı (2026-12-28..2027-01-03 = 2026-H53) dahil her gün için aynı
    for ds, w, mo, y in js["keys"]:
        assert w == m.period_key(ds, "W") and mo == m.period_key(ds, "M") and y == m.period_key(ds, "Y"), ds
    assert m.period_key("2027-01-01", "W") == "2026-H53"
