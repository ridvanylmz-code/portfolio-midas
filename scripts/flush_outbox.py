#!/usr/bin/env python3
"""Telegram giden kutusunu gönder (iş akışında veri push edildikten SONRA çalışır).

Kullanım: TELEGRAM_OUTBOX=/tmp/outbox.jsonl PUSH_OK=1 python scripts/flush_outbox.py [--on-fail "metin"]
PUSH_OK=1 değilse ve --on-fail verilmişse kutu yerine bu uyarı gönderilir (ör. işlem kaydedilemedi).
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--on-fail", default="")
    args = ap.parse_args(argv)
    box = os.environ.get("TELEGRAM_OUTBOX", "")
    ok_push = os.environ.get("PUSH_OK") == "1"
    msgs = []
    if box and os.path.exists(box):
        with open(box, encoding="utf-8") as f:
            msgs = [json.loads(line)["text"] for line in f if line.strip()]
    if not ok_push and args.on_fail:
        msgs = [args.on_fail]
    bad = 0
    for m in msgs:
        for attempt in range(3):
            if common.send_telegram_now(m):
                break
            time.sleep(3 * (attempt + 1))
        else:
            bad += 1
    print(f"Telegram: {len(msgs) - bad}/{len(msgs)} mesaj gönderildi" + ("" if ok_push else " (push başarısız)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
