"""Ortak test yardımcıları: scripts/ modülleri ortam değişkenlerini import anında okur (MARKET, PORTFOLIO_ROOT),
bu yüzden `load` fixture'ı her çağrıda modülleri sıfırdan içe aktarır. Ağ yok; veri sentetiktir."""
import importlib
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
MODULES = [p.stem for p in SCRIPTS.glob("*.py")]
ET = ZoneInfo("America/New_York")
IST = ZoneInfo("Europe/Istanbul")


def at(y, mo, d, h, mi, tz=ET):
    """Belirli bir yerel zamanın UTC'ye çevrilmiş (aware) datetime'ı."""
    return datetime(y, mo, d, h, mi, tzinfo=tz)


def epoch(y, mo, d, h, mi, tz=ET):
    return at(y, mo, d, h, mi, tz).timestamp()


class Mods:
    def __getattr__(self, name):
        return importlib.import_module(name)


@pytest.fixture
def load(tmp_path, monkeypatch):
    """load(market="us", key=None) -> modül ad alanı (mods.common, mods.monitor ...); kök = tmp_path."""
    def _load(market="us", key=None):
        monkeypatch.setenv("PORTFOLIO_ROOT", str(tmp_path))
        monkeypatch.setenv("MARKET", market)
        monkeypatch.delenv("MARKET_JSON", raising=False)
        if key:
            monkeypatch.setenv("PORTFOLIO_KEY", key)
        else:
            monkeypatch.delenv("PORTFOLIO_KEY", raising=False)
        for m in MODULES:
            sys.modules.pop(m, None)
        return Mods()
    return _load


@pytest.fixture
def outbox(tmp_path, monkeypatch):
    """Telegram mesajları dosyaya yazılır; fixture mesaj listesini döndürür."""
    import json
    p = tmp_path / "outbox.jsonl"
    monkeypatch.setenv("TELEGRAM_OUTBOX", str(p))

    def read():
        return [json.loads(x)["text"] for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []
    return read


def write_json(root, name, obj):
    import json
    p = Path(root) / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return p


def read_json(root, name):
    import json
    return json.loads((Path(root) / name).read_text(encoding="utf-8"))


def base_portfolio(**kw):
    pf = {"cash": 100.0, "portfolio": {"AAA": {"shares": 10, "cost_basis": 50.0}}, "watchlist": ["BBB"],
          "alerts": {"daily_move_pct": 5}, "position_levels": {}, "buy_zones": {}, "monthly_target": 0}
    pf.update(kw)
    return pf
