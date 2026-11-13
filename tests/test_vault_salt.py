"""Kasa: mevcut şifreli dosya yeniden yazılınca tuz ve iter korunur (tarayıcı türetilmiş anahtarı saklayabilsin)."""
import base64
import json

KEY = "sentetik-parola-123"


def _raw(root, name):
    return json.loads((root / name).read_text(encoding="utf-8"))


def test_rewrite_keeps_salt_and_iter(load, tmp_path):
    c = load(key=KEY).common
    c.save_json(c.F_PORTFOLIO, {"a": 1})
    e1 = _raw(tmp_path, c.F_PORTFOLIO)
    c._SAVE_SALT = b"\x01" * 16          # süreç tuzu değişse bile dosya kendi tuzunu korumalı
    c.save_json(c.F_PORTFOLIO, {"a": 2})
    e2 = _raw(tmp_path, c.F_PORTFOLIO)
    assert e2["salt"] == e1["salt"] and e2["iter"] == e1["iter"]
    assert e2["iv"] != e1["iv"] and e2["data"] != e1["data"]
    assert c.vault_decrypt(e2, KEY) == {"a": 2}


def test_new_file_gets_salt(load, tmp_path):
    c = load(key=KEY).common
    c.save_json(c.F_HISTORY, {"h": 1})
    e = _raw(tmp_path, c.F_HISTORY)
    assert len(base64.b64decode(e["salt"])) == 16 and e["iter"] == c.VAULT_ITER
    assert c.vault_decrypt(e, KEY) == {"h": 1}


def test_unchanged_not_rewritten(load, tmp_path):
    c = load(key=KEY).common
    c.save_json(c.F_PORTFOLIO, {"a": 1})
    before = (tmp_path / c.F_PORTFOLIO).read_text(encoding="utf-8")
    c.save_json(c.F_PORTFOLIO, {"a": 1})
    assert (tmp_path / c.F_PORTFOLIO).read_text(encoding="utf-8") == before


def test_plain_legacy_file_encrypted_with_new_salt(load, tmp_path):
    c = load(key=KEY).common
    (tmp_path / c.F_PORTFOLIO).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / c.F_PORTFOLIO).write_text(json.dumps({"a": 1}), encoding="utf-8")
    c.save_json(c.F_PORTFOLIO, {"a": 2})
    e = _raw(tmp_path, c.F_PORTFOLIO)
    assert c.is_vault(e) and base64.b64decode(e["salt"]) == c._SAVE_SALT
    assert c.vault_decrypt(e, KEY) == {"a": 2}
