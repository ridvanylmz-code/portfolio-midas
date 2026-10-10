#!/usr/bin/env python3
"""BIST botunu kur: menü düğmesi (mini uygulama) + hoş geldin mesajı. Token yalnızca ortam değişkeninden okunur."""
import os
import sys

import requests


def call(token, method, payload):
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=payload, timeout=15)
        ok = r.status_code == 200 and r.json().get("ok")
        print(f"{method}: {'tamam' if ok else 'HATA ' + str(r.status_code) + ' ' + r.text[:200]}")
        return bool(ok)
    except requests.RequestException as ex:
        print(f"{method}: {type(ex).__name__}")
        return False


def main():
    token = os.environ.get("BOT_TOKEN", "").strip()
    chat = os.environ.get("CHAT_ID", "").strip()
    app = os.environ.get("APP_URL", "").strip()
    dash = os.environ.get("DASH_URL", "").strip()
    if not token or not chat or not app:
        print("[ERROR] BOT_TOKEN / CHAT_ID / APP_URL eksik (secret'ları kontrol et).")
        return 1
    ok = call(token, "setChatMenuButton", {"chat_id": int(chat) if chat.lstrip("-").isdigit() else chat,
                                           "menu_button": {"type": "web_app", "text": "BIST", "web_app": {"url": app}}})
    ok &= call(token, "setChatMenuButton", {"menu_button": {"type": "web_app", "text": "BIST", "web_app": {"url": app}}})
    ok &= call(token, "setMyCommands", {"commands": [{"command": "start", "description": "BIST mini uygulamasını aç"}]})
    ok &= call(token, "sendMessage", {
        "chat_id": chat, "text": "🇹🇷 BIST takip botu hazır. Alttaki BIST düğmesinden mini uygulamayı aç.",
        "reply_markup": {"inline_keyboard": [[{"text": "📈 BIST mini uygulama", "web_app": {"url": app}}],
                                             [{"text": "🖥 Dashboard", "url": dash}]]}})
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
