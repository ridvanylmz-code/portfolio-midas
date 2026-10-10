"""Ortak yardımcılar: dosya I/O, hesaplamalar, uyarılar, Telegram, şifreli kasa."""
import base64
import html
import json
import math
import os
import re
import tempfile
from pathlib import Path

import requests

ROOT = Path(os.environ.get("PORTFOLIO_ROOT") or Path(__file__).resolve().parent.parent)
TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")

# Piyasa seçimi: MARKET=bist -> BIST kopyası (ayrı portföy/geçmiş/durum dosyaları, ₺, docs/bist/data).
# Varsayılan (MARKET boş/us) ABD yapısıdır ve davranışı değişmez.
MARKET = (os.environ.get("MARKET") or "us").strip().lower()
if MARKET == "bist":
    F_PORTFOLIO, F_HISTORY, F_STATE = "bist/portfolio.json", "bist/history.json", "bist/state.json"
    DATA_DIR, CUR = "docs/bist/data", "₺"
else:
    F_PORTFOLIO, F_HISTORY, F_STATE = "portfolio.json", "history.json", "state.json"
    DATA_DIR, CUR = "docs/data", "$"


# ---------------------------------------------------------------- şifreli kasa
# Repo ve GitHub Pages herkese açık. Adet/maliyet/nakit/işlem içeren dosyalar PORTFOLIO_KEY (GitHub secret,
# mini uygulamada girilen parola) ile AES-256-GCM şifrelenir; anahtar PBKDF2-SHA256 ile parolanın türevidir.
# Dosya adları değişmez, içerik {"vault": 1, ...} zarfıdır. Tarayıcı tarafı: docs/vault.js (WebCrypto, aynı biçim).
# Anahtar tanımlı değilse eski davranış (düz JSON) sürer; tanımlanınca ilk yazımda dosyalar şifrelenir.
SECRET_FILES = {F_PORTFOLIO, F_HISTORY, F_STATE, f"{DATA_DIR}/portfolio.json", f"{DATA_DIR}/history.json"}
VAULT_ITER = 600_000
_KEYS = {}      # (parola, salt, iter) -> türetilmiş anahtar (aynı çalışmada tekrar türetme olmasın)
_SAVE_SALT = os.urandom(16)


class VaultError(RuntimeError):
    pass


def vault_key():
    return (os.environ.get("PORTFOLIO_KEY") or "").strip()


def is_vault(d):
    return isinstance(d, dict) and d.get("vault") == 1


def _derive(passphrase, salt, iters):
    k = (passphrase, salt, iters)
    if k not in _KEYS:
        import hashlib
        _KEYS[k] = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, iters, 32)
    return _KEYS[k]


def vault_encrypt(obj, passphrase):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    iv = os.urandom(12)
    plain = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ct = AESGCM(_derive(passphrase, _SAVE_SALT, VAULT_ITER)).encrypt(iv, plain, None)
    b = lambda x: base64.b64encode(x).decode()  # noqa: E731
    return {"vault": 1, "alg": "AES-256-GCM", "kdf": "PBKDF2-SHA256", "iter": VAULT_ITER,
            "salt": b(_SAVE_SALT), "iv": b(iv), "data": b(ct)}


def vault_decrypt(env, passphrase):
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    try:
        salt, iv, ct = (base64.b64decode(env[k]) for k in ("salt", "iv", "data"))
        plain = AESGCM(_derive(passphrase, salt, int(env["iter"]))).decrypt(iv, ct, None)
    except InvalidTag:
        raise VaultError("Şifreli dosya çözülemedi: PORTFOLIO_KEY yanlış") from None
    return json.loads(plain.decode("utf-8"))


# ---------------------------------------------------------------- dosya I/O
def path(name):
    return ROOT / name


def load_json(name, default=None):
    p = path(name)
    if not p.exists():
        return default
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    if is_vault(data):
        key = vault_key()
        if not key:
            raise VaultError(f"{name} şifreli; PORTFOLIO_KEY secret'ı bu iş akışına verilmeli")
        data = vault_decrypt(data, key)
    return data


def save_json(name, data):
    """Atomik yazım: yarım dosya kalmasın. Hassas dosyalar anahtar varsa şifreli yazılır."""
    p = path(name)
    if str(name) in SECRET_FILES and vault_key():
        data = vault_encrypt(data, vault_key())
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            if is_vault(data):
                json.dump(data, f, indent=1)
            else:
                json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, p)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load_portfolio():
    data = load_json(F_PORTFOLIO)
    if data is None:
        raise FileNotFoundError(f"{F_PORTFOLIO} bulunamadı")
    # Eski şema: "cash_reserve". Tek anahtara ("cash") taşı ki bayat kopya kalmasın.
    data["cash"] = float(data.get("cash", data.get("cash_reserve", 0)))
    data.pop("cash_reserve", None)
    data.setdefault("portfolio", {})
    data.setdefault("watchlist", [])
    data.setdefault("alerts", {})
    data.setdefault("position_levels", {})
    data.setdefault("buy_zones", {})
    data.setdefault("monthly_target", 0)
    for t, pos in data["portfolio"].items():
        if not TICKER_RE.match(t):
            raise ValueError(f"Geçersiz ticker: {t}")
        if not (pos["shares"] > 0 and pos["cost_basis"] > 0):
            raise ValueError(f"{t}: shares ve cost_basis > 0 olmalı")
    return data


def load_history():
    h = load_json(F_HISTORY, {}) or {}
    h.setdefault("transactions", [])
    h.setdefault("snapshots", [])
    return h


def sync_public():
    """Dashboard (GitHub Pages /docs) sadece docs/ altını görür; kopyala (anahtar varsa şifreli).
    symbols.json: diğer iş akışları (intraday/technicals) için yalnızca sembol listesi; adet/maliyet içermez,
    pozisyon ile izleme listesi ayrılmadan alfabetik yazılır."""
    ensure_encrypted()
    pf = None
    for name, src in (("portfolio.json", F_PORTFOLIO), ("history.json", F_HISTORY)):
        data = load_json(src)
        if data is not None:
            save_json(f"{DATA_DIR}/{name}", data)
            if name == "portfolio.json":
                pf = data
    if pf is not None:
        syms = sorted(set(pf.get("portfolio", {})) | set(pf.get("watchlist", [])))
        save_json(f"{DATA_DIR}/symbols.json", {"tickers": syms})


def ensure_encrypted():
    """Anahtar tanımlıyken diskte düz kalmış hassas dosya varsa şifreli yeniden yaz (ilk geçiş)."""
    if not vault_key():
        return
    for name in sorted(SECRET_FILES):
        p = path(name)
        if not p.exists():
            continue
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
        if not is_vault(raw):
            save_json(name, raw)
            print(f"[vault] {name} şifrelendi")


def public_symbols(data_dir=None):
    """Sembol listesi (şifre gerektirmez): symbols.json, yoksa düz portfolio.json."""
    d = data_dir or DATA_DIR
    s = load_json(f"{d}/symbols.json")
    if s and s.get("tickers"):
        return list(s["tickers"])
    try:
        pf = load_json(f"{d}/portfolio.json", {}) or {}
    except VaultError:
        return []
    return list(dict.fromkeys(list(pf.get("portfolio", {})) + list(pf.get("watchlist", []))))


# ------------------------------------------------------------- hesaplamalar
def pct(a, b):
    return (a / b * 100) if b else 0.0


def valid_quote(q):
    try:
        return bool(q) and float(q.get("c") or 0) > 0
    except (TypeError, ValueError):
        return False


def position_metrics(shares, cost_basis, quote):
    price = float(quote["c"])
    prev = float(quote.get("pc") or price)
    value = shares * price
    cost = shares * cost_basis
    return {
        "price": price,
        "prev_close": prev,
        "value": value,
        "cost": cost,
        "pnl": value - cost,
        "pnl_pct": pct(value - cost, cost),
        "day_pnl": shares * (price - prev),
        "day_pct": pct(price - prev, prev),
    }


def summarize(portfolio, quotes):
    positions, missing = [], []
    value = cost = day_pnl = prev_value = 0.0
    for t, pos in portfolio["portfolio"].items():
        q = quotes.get(t)
        if not valid_quote(q):
            missing.append(t)
            continue
        m = position_metrics(pos["shares"], pos["cost_basis"], q)
        m.update(ticker=t, shares=pos["shares"], cost_basis=pos["cost_basis"],
                 stale=bool(q.get("stale")))
        positions.append(m)
        value += m["value"]
        cost += m["cost"]
        day_pnl += m["day_pnl"]
        prev_value += pos["shares"] * m["prev_close"]
    cash = portfolio["cash"]
    total = value + cash
    for m in positions:
        m["weight"] = pct(m["value"], total)
    return {
        "positions": positions,
        "positions_value": value,
        "cost": cost,
        "cash": cash,
        "total_value": total,
        "pnl": value - cost,
        "pnl_pct": pct(value - cost, cost),
        "day_pnl": day_pnl,
        "day_pct": pct(day_pnl, prev_value),
        "cash_pct": pct(cash, total),
        "missing": missing,
    }


def levels_for(portfolio, ticker):
    """Stop / hedef fiyatı: pozisyona özel seviye varsa o, yoksa maliyet ± yüzde."""
    pos = portfolio["portfolio"][ticker]
    custom = portfolio["position_levels"].get(ticker, {})
    a = portfolio["alerts"]
    stop = custom.get("stop_loss")
    target = custom.get("target")
    if stop is None and a.get("stop_loss_pct") is not None:
        stop = pos["cost_basis"] * (1 + a["stop_loss_pct"] / 100)
    if target is None and a.get("target_pct") is not None:
        target = pos["cost_basis"] * (1 + a["target_pct"] / 100)
    return stop, target


def zone_of(portfolio, t):
    """Alım bölgesi: eski biçim sayı (= fiyat ≤ değer) ya da {"below": x, "above": y}."""
    z = (portfolio.get("buy_zones") or {}).get(t)
    if z is None:
        return {}
    if isinstance(z, (int, float)):
        return {"below": float(z)}
    return {k: float(v) for k, v in z.items() if k in ("below", "above") and v is not None}


def check_alerts(portfolio, fresh_quotes):
    out = []
    # İzleme listesi alım bölgeleri: geri çekilme (fiyat ≤ below) ya da kırılım (fiyat ≥ above)
    for t in list(dict.fromkeys(list(portfolio.get("watchlist", [])) + list(portfolio.get("buy_zones", {})))):
        q = fresh_quotes.get(t)
        z = zone_of(portfolio, t)
        if not z or not valid_quote(q):
            continue
        price = float(q["c"])
        if "below" in z and price <= z["below"]:
            out.append({"key": f"{t}:zone_below:{z['below']}",
                        "text": f"🎯 {t} alım bölgesinde (geri çekilme): {CUR}{price:.2f} ≤ {CUR}{z['below']:.2f}"})
        if "above" in z and price >= z["above"]:
            out.append({"key": f"{t}:zone_above:{z['above']}",
                        "text": f"🚀 {t} kırılım seviyesini geçti: {CUR}{price:.2f} ≥ {CUR}{z['above']:.2f}"})
    move = portfolio["alerts"].get("daily_move_pct")
    for t in portfolio["portfolio"]:
        q = fresh_quotes.get(t)
        if not valid_quote(q):
            continue
        price = float(q["c"])
        stop, target = levels_for(portfolio, t)
        if stop is not None and price <= stop:
            out.append({"key": f"{t}:stop", "text": f"🛑 {t} stop seviyesinde: {CUR}{price:.2f} (stop {CUR}{stop:.2f})"})
        if target is not None and price >= target:
            out.append({"key": f"{t}:target", "text": f"🎯 {t} hedefe ulaştı: {CUR}{price:.2f} (hedef {CUR}{target:.2f})"})
        dp = q.get("dp")
        if move and dp is not None and abs(dp) >= move:
            side = "up" if dp > 0 else "down"
            out.append({"key": f"{t}:move_{side}", "text": f"⚡ {t} günlük %{dp:+.2f} hareket ({CUR}{price:.2f})"})
    return out


def month_progress(history, target, total_value, today_iso):
    """Ay başı ilk snapshot'a göre kazanç; para yatırma/çekmeyi düzeltir."""
    if not target:
        return None
    month = today_iso[:7]
    snaps = sorted((s for s in history["snapshots"] if s["date"].startswith(month)),
                   key=lambda s: s["date"])
    if not snaps:
        return None
    start = snaps[0]
    flows = 0.0
    for tx in history["transactions"]:
        if tx.get("undone"):
            continue
        if tx["date"] > start["date"] and tx["date"].startswith(month):
            if tx["action"] == "deposit":
                flows += tx["amount"]
            elif tx["action"] == "withdraw":
                flows -= tx["amount"]
    gain = total_value - start["value"] - flows
    return {"start": start["value"], "start_date": start["date"], "gain": gain,
            "target": target, "pct": pct(gain, target)}


# ----------------------------------------------------------------- Telegram
def _chunks(text, limit=3900):
    """4096 sınırı: satır sınırında böl (HTML etiketi ortadan kesilmesin)."""
    out, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > limit and cur:
            out.append(cur)
            cur = ""
        cur = (cur + "\n" + line) if cur else line[:limit]
    if cur:
        out.append(cur)
    return out or [""]


def send_telegram(text):
    """TELEGRAM_OUTBOX tanımlıysa mesaj dosyaya yazılır; iş akışı veriyi push ettikten SONRA
    scripts/flush_outbox.py ile gönderir (kaydedilmemiş işlem için 'güncellendi' denmesin)."""
    box = os.environ.get("TELEGRAM_OUTBOX")
    if box:
        with open(box, "a", encoding="utf-8") as f:
            f.write(json.dumps({"text": text}, ensure_ascii=False) + "\n")
        return True
    return send_telegram_now(text)


def send_telegram_now(text):
    ok = True
    for part in _chunks(text):
        ok = _send_one(part) and ok
    return ok


def _send_one(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[WARN] Telegram bilgileri yok; mesaj gönderilmedi.")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=15,
        )
        if r.status_code != 200:
            # URL token içerir; sadece durum kodunu yaz
            print(f"[WARN] Telegram HTTP {r.status_code}")
            return False
        return True
    except requests.RequestException as e:
        print(f"[WARN] Telegram hatası: {type(e).__name__}")
        return False


def e(s):
    return html.escape(str(s))


def finite_positive(x, name):
    try:
        x = float(x)
    except (TypeError, ValueError):
        raise ValueError(f"{name} sayı olmalı")
    if not math.isfinite(x) or x <= 0:
        raise ValueError(f"{name} > 0 olmalı")
    return x


def perf_summary(history, total_value, today_iso):
    """Rapor satırı: Hafta / Ay / Yıl kazancı ($) ve zaman ağırlıklı getiri (%), para giriş-çıkışından arındırılmış."""
    snaps = sorted(history.get("snapshots", []), key=lambda s: s["date"])
    if not snaps:
        return None
    snaps = [s for s in snaps if s["date"] != today_iso] + [{"date": today_iso, "value": total_value}]
    if len(snaps) < 2:
        return None
    flows = {}
    for tx in history.get("transactions", []):
        if tx.get("undone") or tx.get("action") not in ("deposit", "withdraw"):
            continue
        flows[tx["date"]] = flows.get(tx["date"], 0) + (tx["amount"] if tx["action"] == "deposit" else -tx["amount"])
    idx, out_idx, fl = 1.0, [1.0], [0.0]
    for i in range(1, len(snaps)):
        f = sum(v for d, v in flows.items() if snaps[i - 1]["date"] < d <= snaps[i]["date"])
        prev = snaps[i - 1]["value"]
        idx *= ((snaps[i]["value"] - f) / prev) if prev else 1
        out_idx.append(idx)
        fl.append(f)
    from datetime import date, timedelta
    t = date.fromisoformat(today_iso)
    marks = {"Hafta": (t - timedelta(days=7)).isoformat(), "Ay": date(t.year, t.month, 1).isoformat(),
             "Yıl": date(t.year, 1, 1).isoformat()}
    res = {}
    for k, d0 in marks.items():
        j = max([i for i, s in enumerate(snaps) if s["date"] < d0] or [0])
        if j >= len(snaps) - 1:
            continue
        gain = snaps[-1]["value"] - snaps[j]["value"] - sum(fl[j + 1:])
        res[k] = {"gain": gain, "twr": (out_idx[-1] / out_idx[j] - 1) * 100}
    return res or None
