#!/usr/bin/env python3
"""Send queued Telegram replies from outbox/."""

import json
from pathlib import Path
import requests

VSM_ROOT = Path(__file__).parent.parent
OUTBOX = VSM_ROOT / "state" / "outbox"


def load_config():
    config = {}
    env_file = VSM_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                config[k.strip()] = v.strip()
    return config


def main():
    OUTBOX.mkdir(parents=True, exist_ok=True)
    config = load_config()

    token = config.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return

    api = f"https://api.telegram.org/bot{token}"

    for msg_file in OUTBOX.glob("tg_*.json"):
        try:
            msg = json.loads(msg_file.read_text())
        except Exception:
            continue

        if msg.get("sent"):
            msg_file.unlink()
            continue

        try:
            resp = requests.post(
                f"{api}/sendMessage",
                json={
                    "chat_id": msg.get("chat_id"),
                    "text": msg["text"],
                },
                timeout=10,
            )
            resp.raise_for_status()

            msg["sent"] = True
            msg_file.write_text(json.dumps(msg, indent=2))
            msg_file.unlink(missing_ok=True)

        except Exception as e:
            print(f"[send-tg] Failed to send: {e}")


if __name__ == "__main__":
    main()
