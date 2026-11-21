"""SEC EDGAR'dan dilüsyon (sermaye artırımı / sulanma) taraması.

Kaynak: data.sec.gov resmî ücretsiz servisleri (anahtar gerekmez, User-Agent'ta iletişim bilgisi zorunlu).
  - www.sec.gov/files/company_tickers.json      → hisse kodu → CIK
  - data.sec.gov/submissions/CIK##########.json  → son başvurular (form, tarih, belge)
  - data.sec.gov/api/xbrl/companyfacts/CIK...    → nakit, faaliyet nakit akışı, yatırım harcaması

Taranan hisseler: docs/data/symbols.json + (varsa) market.json içindeki picks adayları.
Çıktı: docs/data/dilution.json. Seviyeler takip-listesi-tarama skill'indeki tabloyla aynıdır:
  Yüksek  : FCF negatif ve nakit ömrü < 4 çeyrek; veya 12 ayda hisse/ATM satışı (424B5) var ve FCF negatif
  Orta    : FCF negatif ama nakit ömrü ≥ 4 çeyrek; veya 12 ayda hisse satışı / dönüştürülebilir tahvil (FCF pozitifken)
  Düşük   : FCF pozitif, 12 ayda hisse satışı yok (yalnız genel shelf kaydı varsa not düşülür)
  Doğrulanamadı: CIK ya da finansal veri okunamadı

Kullanım: python scripts/dilution.py [--market /tmp/market.json] [--out docs/data/dilution.json]
Ortam: SEC_USER_AGENT="Ad Soyad eposta@ornek.com" (SEC kuralı; yoksa varsayılan kullanılır)
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"

UA = os.environ.get("SEC_USER_AGENT", "").strip() or "portfolio-midas github.com/ridvanylmz-code/portfolio-midas"
PAUSE = 0.15  # SEC sınırı saniyede 10 istek

SHELF_FORMS = {"S-3", "S-3ASR", "F-3", "F-3ASR", "S-3/A", "F-3/A"}
REG_FORMS = {"S-1", "S-1/A", "F-1", "F-1/A"}  # shelf dışı kayıtlı halka arz
TAKEDOWN_FORMS = {"424B5", "424B4", "424B3", "424B7"}
SHELF_YEARS = 3          # shelf kaydı 3 yıl geçerli
TAKEDOWN_DAYS = 365      # satışlara 12 ay geriye bakılır
MAX_DOCS = 4             # şirket başına okunacak en fazla 424B belgesi
DOC_BYTES = 120_000      # belgenin okunacak ilk kısmı

# XBRL kavramları: (taksonomi, kavram) öncelik sırasıyla
CASH = [("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
        ("us-gaap", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
        ("ifrs-full", "CashAndCashEquivalents")]
SHORT_INV = [("us-gaap", "ShortTermInvestments"), ("us-gaap", "MarketableSecuritiesCurrent"),
             ("us-gaap", "AvailableForSaleSecuritiesDebtSecuritiesCurrent"),
             ("ifrs-full", "CurrentInvestments"), ("ifrs-full", "OtherCurrentFinancialAssets")]
OCF = [("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
       ("us-gaap", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
       ("ifrs-full", "CashFlowsFromUsedInOperatingActivities")]
CAPEX = [("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment"),
         ("us-gaap", "PaymentsToAcquireProductiveAssets"),
         ("ifrs-full", "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"),
         ("ifrs-full", "PurchaseOfPropertyPlantAndEquipment")]


# ---------------------------------------------------------------- ağ
def _session():
    import requests
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Encoding": "gzip, deflate"})
    return s


def get_json(s, url):
    time.sleep(PAUSE)
    r = s.get(url, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def get_text(s, url, limit=DOC_BYTES):
    time.sleep(PAUSE)
    r = s.get(url, timeout=30, stream=True)
    r.raise_for_status()
    buf = b""
    for chunk in r.iter_content(16384):
        buf += chunk
        if len(buf) >= limit:
            break
    r.close()
    return buf.decode("utf-8", "ignore")


# ---------------------------------------------------------------- saf mantık (testli)
def parse_date(s):
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def recent_filings(sub):
    """submissions JSON → [{form, date, acc, doc, items}] (yalnız 'recent' blok)."""
    r = (sub or {}).get("filings", {}).get("recent", {})
    forms = r.get("form", [])
    out = []
    for i, f in enumerate(forms):
        out.append({"form": f, "date": r["filingDate"][i], "acc": r["accessionNumber"][i],
                    "doc": (r.get("primaryDocument") or [""] * len(forms))[i],
                    "items": (r.get("items") or [""] * len(forms))[i]})
    return out


def filing_url(cik, f):
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{f['acc'].replace('-', '')}/{f['doc']}"


def classify_doc(text):
    """424B belge metni → 'ATM' | 'dönüştürülebilir' | 'borç' | 'hisse' | 'diğer'."""
    t = re.sub(r"<[^>]+>", " ", text)
    t = re.sub(r"&#?\w+;", " ", t)
    t = re.sub(r"\s+", " ", t).lower()
    if re.search(r"at[- ]the[- ]market|equity distribution agreement|sales agreement|open market sale agreement|controlled equity offering", t):
        return "ATM"
    if re.search(r"convertible (senior )?notes|convertible (senior )?debentures|exchangeable notes", t):
        return "dönüştürülebilir"
    head = t[:6000]
    equity = re.search(r"(shares of (our )?(class a )?common stock|ordinary shares|american depositary shares|pre-funded warrants|units)", head)
    debt = re.search(r"(\d+(\.\d+)?% (senior |subordinated )?notes due|floating rate notes|debentures due)", head)
    if debt and not equity:
        return "borç"
    if equity:
        return "hisse"
    return "diğer"


def _duration_days(e):
    if not e.get("start"):
        return 0
    return (parse_date(e["end"]) - parse_date(e["start"])).days


def _entries(facts, keys):
    """İlk bulunan kavramın girdileri ve birimi. Aynı dönem için son başvurunun değeri tutulur."""
    for tax, name in keys:
        node = (facts or {}).get("facts", {}).get(tax, {}).get(name)
        if not node:
            continue
        for unit, rows in node.get("units", {}).items():
            if not rows:
                continue
            best = {}
            for e in rows:
                if e.get("form", "").startswith(("10-", "20-", "40-", "6-K")) or "form" not in e:
                    k = (e.get("start"), e["end"])
                    if k not in best or e.get("filed", "") > best[k].get("filed", ""):
                        best[k] = e
            if best:
                return list(best.values()), unit, f"{tax}:{name}"
    return [], None, None


def latest_instant(facts, keys):
    rows, unit, concept = _entries(facts, keys)
    rows = [e for e in rows if not e.get("start")]
    if not rows:
        return None
    e = max(rows, key=lambda x: x["end"])
    return {"value": e["val"], "end": e["end"], "unit": unit, "concept": concept}


def ttm(facts, keys):
    """Akış kalemi için son 12 ay: yıllık + (son kümülatif − önceki yılın aynı kümülatifi)."""
    rows, unit, concept = _entries(facts, keys)
    rows = [e for e in rows if e.get("start")]
    if not rows:
        return None
    annual = [e for e in rows if 340 <= _duration_days(e) <= 380]
    if not annual:
        return None
    fy = max(annual, key=lambda x: x["end"])
    out = {"value": fy["val"], "end": fy["end"], "unit": unit, "concept": concept, "basis": "yıllık"}
    fy_end = parse_date(fy["end"])
    ytd = [e for e in rows if parse_date(e["start"]) > fy_end - timedelta(days=5)
           and 80 <= _duration_days(e) < 340 and parse_date(e["end"]) > fy_end]
    if ytd:
        cur = max(ytd, key=lambda x: x["end"])
        d = _duration_days(cur)
        cur_end = parse_date(cur["end"])
        prior = [e for e in rows if abs(_duration_days(e) - d) <= 10
                 and abs((cur_end - parse_date(e["end"])).days - 365) <= 15]
        if prior:
            p = max(prior, key=lambda x: x["end"])
            out.update(value=fy["val"] + cur["val"] - p["val"], end=cur["end"], basis="son 12 ay")
    return out


def financials(facts):
    cash = latest_instant(facts, CASH)
    inv = latest_instant(facts, SHORT_INV)
    ocf = ttm(facts, OCF)
    capex = ttm(facts, CAPEX)
    if not cash or not ocf:
        return None
    liquid = cash["value"]
    if inv and inv["end"] == cash["end"] and inv["unit"] == cash["unit"]:
        liquid += inv["value"]
    cap = capex["value"] if capex and capex["unit"] == ocf["unit"] else 0
    fcf = ocf["value"] - cap
    runway = None
    if fcf < 0:
        runway = round(liquid / (-fcf / 4), 1)
    return {"unit": cash["unit"], "cash": liquid, "cash_date": cash["end"],
            "ocf_ttm": ocf["value"], "capex_ttm": cap, "fcf_ttm": fcf,
            "fcf_basis": ocf["basis"], "fcf_end": ocf["end"], "runway_q": runway}


def assess(filings, fin, today, docs=None):
    """Başvurular + finansal → seviye, gerekçeler, ilgili başvurular.
    docs: {acc: tür} (424B belgelerinin classify_doc sonucu)."""
    docs = docs or {}
    shelf_from = today - timedelta(days=365 * SHELF_YEARS)
    take_from = today - timedelta(days=TAKEDOWN_DAYS)
    shelves = [f for f in filings if f["form"] in SHELF_FORMS and parse_date(f["date"]) >= shelf_from]
    regs = [f for f in filings if f["form"] in REG_FORMS and parse_date(f["date"]) >= take_from]
    takes = []
    for f in filings:
        if f["form"] in TAKEDOWN_FORMS and parse_date(f["date"]) >= take_from:
            takes.append(dict(f, kind=docs.get(f["acc"], "okunmadı")))
    equity_takes = [t for t in takes if t["kind"] in ("ATM", "hisse")]
    conv_takes = [t for t in takes if t["kind"] == "dönüştürülebilir"]
    unknown_takes = [t for t in takes if t["kind"] in ("okunmadı", "diğer")]
    atm = [t for t in takes if t["kind"] == "ATM"]

    reasons = []
    if fin is None:
        level = "Doğrulanamadı"
        reasons.append("XBRL finansal verisi okunamadı (nakit / faaliyet nakit akışı yok)")
        if equity_takes or regs:
            reasons.append("12 ayda hisse satışı başvurusu var")
    else:
        neg = fin["fcf_ttm"] < 0
        short = neg and fin["runway_q"] is not None and fin["runway_q"] < 4
        if short:
            level = "Yüksek"
            reasons.append(f"serbest nakit akışı negatif, nakit ömrü {fin['runway_q']} çeyrek (< 4)")
        elif neg and (equity_takes or regs):
            level = "Yüksek"
            reasons.append("serbest nakit akışı negatif ve 12 ayda hisse/ATM satışı var")
        elif equity_takes or conv_takes or regs or neg:
            level = "Orta"
            if neg:
                reasons.append(f"serbest nakit akışı negatif, nakit ömrü {fin['runway_q']} çeyrek")
        else:
            level = "Düşük"
            reasons.append("serbest nakit akışı pozitif")
        if unknown_takes and level == "Düşük":
            level = "Orta"
            reasons.append(f"{len(unknown_takes)} adet 424B başvurusunun türü belirlenemedi")
    if atm:
        reasons.append(f"ATM programı: son {atm[0]['form']} {atm[0]['date']}")
    if equity_takes and not atm:
        reasons.append(f"hisse satışı: son {equity_takes[0]['form']} {equity_takes[0]['date']}")
    if conv_takes:
        reasons.append(f"dönüştürülebilir tahvil: {conv_takes[0]['date']}")
    if regs:
        reasons.append(f"halka arz kaydı ({regs[0]['form']} {regs[0]['date']})")
    if shelves:
        s = shelves[0]
        note = f"etkin shelf: {s['form']} {s['date']}"
        if level == "Düşük":
            note += " (genel kayıt; 12 ayda hisse satışı yok)"
        reasons.append(note)
    return level, reasons, shelves, takes, regs


def fmt_money(v, unit):
    cur = "$" if unit == "USD" else (unit + " ")
    a = abs(v)
    s = f"{a / 1e9:.2f} mlr" if a >= 1e9 else f"{a / 1e6:.0f} mn"
    return ("−" if v < 0 else "") + cur + s.replace(".", ",")


def summary_text(level, reasons, fin, today):
    parts = [f"{today.isoformat()} (SEC EDGAR)"]
    if fin:
        parts.append(f"nakit {fmt_money(fin['cash'], fin['unit'])} ({fin['cash_date']}), "
                     f"serbest nakit akışı {fin['fcf_basis']} {fmt_money(fin['fcf_ttm'], fin['unit'])}")
    parts += reasons
    return "; ".join(parts) + "."


# ---------------------------------------------------------------- çalıştırma
def load_tickers(market_path):
    syms = json.loads((DATA / "symbols.json").read_text())["tickers"]
    roles = {t: "liste/pozisyon" for t in syms}
    if market_path and Path(market_path).exists():
        m = json.loads(Path(market_path).read_text())
        for lst in (m.get("picks") or {}).values():
            for p in lst:
                roles.setdefault(p["t"], "aday")
    return roles


def scan_one(s, t, cik, today):
    sub = get_json(s, f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    filings = recent_filings(sub)
    take_from = today - timedelta(days=TAKEDOWN_DAYS)
    docs = {}
    for f in [f for f in filings if f["form"] in TAKEDOWN_FORMS and parse_date(f["date"]) >= take_from][:MAX_DOCS]:
        try:
            docs[f["acc"]] = classify_doc(get_text(s, filing_url(cik, f)))
        except Exception as e:  # belge okunamazsa tür bilinmez kalır
            print(f"  {t}: {f['form']} {f['date']} okunamadı: {e}", file=sys.stderr)
    try:
        facts = get_json(s, f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")
        fin = financials(facts)
    except Exception as e:
        print(f"  {t}: companyfacts okunamadı: {e}", file=sys.stderr)
        fin = None
    level, reasons, shelves, takes, regs = assess(filings, fin, today, docs)
    link = lambda f: {"form": f["form"], "date": f["date"], "url": filing_url(cik, f)}
    return {
        "cik": cik, "name": (sub or {}).get("name"), "risk": level,
        "text": summary_text(level, reasons, fin, today), "reasons": reasons, "fin": fin,
        "shelf": [link(f) for f in shelves[:3]],
        "takedowns": [dict(link(f), kind=f["kind"]) for f in takes[:8]],
        "registrations": [link(f) for f in regs[:3]],
        "checked": today.isoformat(),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default="")
    ap.add_argument("--out", default=str(DATA / "dilution.json"))
    args = ap.parse_args(argv)
    today = datetime.now(timezone.utc).date()
    roles = load_tickers(args.market)
    s = _session()
    cmap = get_json(s, "https://www.sec.gov/files/company_tickers.json")
    ciks = {v["ticker"].upper(): int(v["cik_str"]) for v in cmap.values()}
    out_path = Path(args.out)
    old = json.loads(out_path.read_text()) if out_path.exists() else {}
    res, errors = {}, []
    for t, role in sorted(roles.items()):
        key = t.replace(".", "-").upper()
        cik = ciks.get(key) or ciks.get(t.upper())
        if not cik:
            res[t] = {"risk": "Doğrulanamadı", "role": role, "checked": today.isoformat(),
                      "text": f"{today.isoformat()}: SEC'de CIK bulunamadı (yabancı/OTC olabilir).", "reasons": []}
            continue
        try:
            r = scan_one(s, t, cik, today)
        except Exception as e:
            errors.append(f"{t}: {e}")
            prev = (old.get("tickers") or {}).get(t)
            r = dict(prev, stale=True) if prev else {"risk": "Doğrulanamadı", "checked": today.isoformat(),
                                                    "text": f"{today.isoformat()}: EDGAR okunamadı ({e}).", "reasons": []}
        r["role"] = role
        res[t] = r
        print(f"{t:6} {r['risk']:13} {r.get('text', '')[:110]}")
    doc = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
           "source": "SEC EDGAR (data.sec.gov submissions + XBRL companyfacts)",
           "method": "takip-listesi-tarama dilüsyon tablosu; shelf 3 yıl, satışlar (424B) 12 ay geriye; "
                     "FCF = faaliyet nakit akışı − yatırım harcaması (son 12 ay); nakit ömrü = (nakit + kısa vadeli yatırım) / çeyreklik yakım",
           "errors": errors, "tickers": res}
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    if len(errors) > len(res) // 2:
        print("Hataların sayısı yüksek; EDGAR erişimi sorunlu olabilir", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
