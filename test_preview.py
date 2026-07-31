"""
RustPulse — Тестовая отправка всех 5 типов уведомлений.
Запускай: python test_preview.py
Нужен файл .env с токеном и ID каналов.
"""

import os
import requests
from datetime import datetime, timezone

# Загружаем .env если есть
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

LOLKA_TOKEN = os.environ.get("LOLKA_TOKEN", "")
CHANNELS = {
    "rust_server": os.environ.get("CHANNEL_RUST_SERVER", ""),
    "rust_client": os.environ.get("CHANNEL_RUST_CLIENT", ""),
    "oxide":       os.environ.get("CHANNEL_OXIDE", ""),
    "carbon":      os.environ.get("CHANNEL_CARBON", ""),
    "hooks":       os.environ.get("CHANNEL_HOOKS", ""),
}

LOLKA_BASE = "https://lolka.app/api/bot/v10"
HEADERS = {
    "Authorization": f"Bot {LOLKA_TOKEN}",
    "Content-Type": "application/json",
}

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def send_embed(channel_id: str, embed: dict, label: str):
    if not channel_id:
        print(f"  [SKIP] {label} — ID канала не задан")
        return
    url = f"{LOLKA_BASE}/channels/{channel_id}/messages"
    r = requests.post(url, headers=HEADERS, json={"embeds": [embed]}, timeout=15)
    if r.ok:
        print(f"  [OK] {label} — отправлено!")
    else:
        print(f"  [ERR] {label} — {r.status_code}: {r.text[:150]}")

def main():
    print("\n" + "="*55)
    print("  RustPulse PREVIEW — тестовая отправка")
    print("="*55)

    if not LOLKA_TOKEN:
        print("[ERR] LOLKA_TOKEN не задан! Создай .env файл.")
        return

    # 1. Rust Server
    send_embed(CHANNELS["rust_server"], {
        "title": "🖥️  Обновление Rust Dedicated Server",
        "color": 0xCD4632,
        "description": "Вышло обновление серверной части Rust. Обновите сервер через `steamcmd`.",
        "fields": [
            {"name": "Предыдущий BuildID", "value": "`24251003`", "inline": True},
            {"name": "Новый BuildID",       "value": "`24253458`", "inline": True},
            {"name": "Ссылки",
             "value": "[SteamDB](https://steamdb.info/app/258550/) • [Facepunch Blog](https://rust.facepunch.com/blog)",
             "inline": False},
        ],
        "footer": {"text": "RustPulse • Rust Server"},
        "timestamp": now_iso(),
    }, "Rust Server")

    # 2. Rust Client
    send_embed(CHANNELS["rust_client"], {
        "title": "🎮  Обновление Rust Client",
        "color": 0xE8643A,
        "description": "Вышло обновление клиента Rust в Steam.",
        "fields": [
            {"name": "Предыдущий BuildID", "value": "`24455000`", "inline": True},
            {"name": "Новый BuildID",       "value": "`24457949`", "inline": True},
            {"name": "Ссылки",
             "value": "[SteamDB](https://steamdb.info/app/252490/) • [Facepunch Blog](https://rust.facepunch.com/blog)",
             "inline": False},
        ],
        "footer": {"text": "RustPulse • Rust Client"},
        "timestamp": now_iso(),
    }, "Rust Client")

    # 3. Oxide
    send_embed(CHANNELS["oxide"], {
        "title": "⚙️  Новый релиз Oxide / uMod",
        "color": 0x5865F2,
        "description": "```\nOxide.Rust 2.0.7529\nBug fixes and stability improvements\n```",
        "fields": [
            {"name": "Предыдущая версия", "value": "`2.0.7521`",   "inline": True},
            {"name": "Новая версия",       "value": "`2.0.7529`",   "inline": True},
            {"name": "GitHub Release",
             "value": "[Открыть](https://github.com/oxidemod/Oxide.Rust/releases/latest)",
             "inline": False},
        ],
        "footer": {"text": "RustPulse • Oxide/uMod"},
        "timestamp": now_iso(),
    }, "Oxide")

    # 4. Carbon
    send_embed(CHANNELS["carbon"], {
        "title": "🔶  Новый релиз Carbon",
        "color": 0xF39C12,
        "description": "```\nCarbon production_build\nPerformance improvements and hook updates\n```",
        "fields": [
            {"name": "Предыдущая версия", "value": "`v2.0.4.2`",         "inline": True},
            {"name": "Новая версия",       "value": "`production_build`", "inline": True},
            {"name": "GitHub Release",
             "value": "[Открыть](https://github.com/CarbonCommunity/Carbon/releases/latest)",
             "inline": False},
        ],
        "footer": {"text": "RustPulse • Carbon"},
        "timestamp": now_iso(),
    }, "Carbon")

    # 5. Carbon Hooks
    send_embed(CHANNELS["hooks"], {
        "title": "🪝  Обновление хуков Carbon",
        "color": 0x9B59B6,
        "description": "**fix: add OnServerCommand hook and update OnPlayerChat**",
        "fields": [
            {"name": "Коммит", "value": "`9703ab1b`",         "inline": True},
            {"name": "Автор",  "value": "CarbonCommunity",    "inline": True},
            {"name": "Изменённые файлы хуков",
             "value": "```\nCarbon.Core/src/Hooks/OnServerCommand.cs\n```",
             "inline": False},
            {"name": "Смотреть коммит",
             "value": "[GitHub](https://github.com/CarbonCommunity/Carbon/commit/9703ab1b)",
             "inline": False},
        ],
        "footer": {"text": "RustPulse • Carbon Hooks"},
        "timestamp": now_iso(),
    }, "Carbon Hooks")

    print("="*55 + "\n")

if __name__ == "__main__":
    main()
