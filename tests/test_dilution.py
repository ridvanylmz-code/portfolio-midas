"""dilution.py saf mantığı: 424B sınıflama, son 12 ay hesabı, seviye kararı. Ağ yok."""
from datetime import date

import dilution as d


def facts(ocf_rows, cash_rows, capex_rows=()):
    def rows(lst, flow):
        out = []
        for r in lst:
            e = {"val": r[-1], "form": "10-Q", "filed": r[-2] if len(r) > 3 else "2026-01-01"}
            if flow:
                e.update(start=r[0], end=r[1])
            else:
                e.update(end=r[0])
            out.append(e)
        return out
    return {"facts": {"us-gaap": {
        "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": rows(ocf_rows, True)}},
        "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": rows(capex_rows, True)}},
        "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": rows(cash_rows, False)}},
    }}}


def test_classify():
    assert d.classify_doc("<p>We have entered into an <b>At-The-Market</b> Sales Agreement</p>") == "ATM"
    assert d.classify_doc("Offering of $125,000,000 4.50% Convertible Senior Notes due 2031") == "dönüştürülebilir"
    assert d.classify_doc("PROSPECTUS SUPPLEMENT $1,000,000,000 4.10% Notes due 2033") == "borç"
    assert d.classify_doc("10,000,000 Shares of Common Stock and Pre-Funded Warrants") == "hisse"
    assert d.classify_doc("25,000,000 Shares of Common Stock offered by the Selling Stockholders") == "ikincil"
    assert d.classify_doc("anything", "424B7") == "ikincil"
    assert d.classify_doc("$500,000,000 5.25% Senior Notes due 2036. The notes rank equally ... shares of common stock of the company") == "borç"


def test_latest_concept_wins():
    f = {"facts": {"us-gaap": {
        "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [{"end": "2019-09-30", "val": 1, "form": "10-K", "filed": "2019-10-01"}]}},
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents": {"units": {"USD": [{"end": "2026-09-30", "val": 9, "form": "10-Q", "filed": "2026-10-20"}]}}}}}
    assert d.latest_instant(f, d.CASH)["end"] == "2026-09-30"


def test_ttm_uses_ytd():
    f = facts(
        ocf_rows=[("2025-01-01", "2025-12-31", -400), ("2025-01-01", "2025-09-30", -300),
                  ("2026-01-01", "2026-09-30", -150)],
        cash_rows=[("2026-09-30", 500), ("2025-12-31", 900)],
        capex_rows=[("2025-01-01", "2025-12-31", 40), ("2025-01-01", "2025-09-30", 30),
                    ("2026-01-01", "2026-09-30", 10)])
    fin = d.financials(f)
    assert fin["ocf_ttm"] == -400 - 150 + 300          # −250
    assert fin["capex_ttm"] == 40 + 10 - 30            # 20
    assert fin["fcf_ttm"] == -270
    assert fin["cash"] == 500 and fin["cash_date"] == "2026-09-30"
    assert fin["runway_q"] == round(500 / (270 / 4), 1)   # 7,4
    assert fin["fcf_basis"] == "son 12 ay"


def _f(form, dt, acc="0001-26-1"):
    return {"form": form, "date": dt, "acc": acc, "doc": "x.htm", "items": ""}


def test_levels():
    today = date(2026, 11, 21)
    burn = {"fcf_ttm": -400, "runway_q": 2.5, "cash": 250, "unit": "USD", "cash_date": "2026-09-30", "fcf_basis": "son 12 ay"}
    lv, *_ = d.assess([], burn, today)
    assert lv == "Yüksek"
    rich = dict(burn, fcf_ttm=-100, runway_q=10)
    lv, *_ = d.assess([_f("424B5", "2026-06-01", "a")], rich, today, {"a": "ATM"})
    assert lv == "Yüksek"
    pos = dict(burn, fcf_ttm=500, runway_q=None)
    lv, r, *_ = d.assess([_f("S-3ASR", "2025-02-01")], pos, today)
    assert lv == "Düşük" and any("genel kayıt" in x for x in r)
    lv, *_ = d.assess([_f("424B5", "2026-08-01", "b")], pos, today, {"b": "dönüştürülebilir"})
    assert lv == "Orta"
    lv, *_ = d.assess([_f("424B5", "2026-08-01", "c")], pos, today, {"c": "borç"})
    assert lv == "Düşük"
    lv, *_ = d.assess([_f("424B5", "2024-08-01", "e")], burn | {"runway_q": 9, "fcf_ttm": -50}, today, {"e": "ATM"})
    assert lv == "Orta"   # 12 aydan eski satış sayılmaz; nakit yakımı tek başına Orta
    lv, *_ = d.assess([], None, today)
    assert lv == "Doğrulanamadı"
