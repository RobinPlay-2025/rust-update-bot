"""
RustPulse — бот мониторинга обновлений Rust/Oxide/Carbon для LOLKA
Запускается через GitHub Actions каждые 30 минут.
"""

import os
import json
import requests
from datetime import datetime, timezone

# ─── Конфигурация из переменных окружения ────────────────────────────────────

LOLKA_TOKEN    = os.environ["LOLKA_TOKEN"]
GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN", "")

CHANNELS = {
    "rust_server": os.environ["CHANNEL_RUST_SERVER"],
    "rust_client": os.environ["CHANNEL_RUST_CLIENT"],
    "oxide":       os.environ["CHANNEL_OXIDE"],
    "carbon":      os.environ["CHANNEL_CARBON"],
    "hooks":       os.environ["CHANNEL_HOOKS"],
}

# ─── HTTP-заголовки ───────────────────────────────────────────────────────────

LOLKA_HEADERS = {
    "Authorization": f"Bot {LOLKA_TOKEN}",
    "Content-Type": "application/json",
}

GITHUB_HEADERS: dict = {"Accept": "application/vnd.github.v3+json"}
if GITHUB_TOKEN:
    GITHUB_HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"

LOLKA_BASE    = "https://lolka.app/api/bot/v10"
VERSIONS_FILE = "last_versions.json"

# ─── Цвета embed ─────────────────────────────────────────────────────────────
COLOR_SERVER  = 0xCD4632   # тёмно-ржавый
COLOR_CLIENT  = 0xE8643A   # ярко-ржавый
COLOR_OXIDE   = 0x5865F2   # синий
COLOR_CARBON  = 0xF39C12   # янтарно-оранжевый
COLOR_HOOKS   = 0x9B59B6   # фиолетовый

# ─── Вспомогательные функции ─────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def load_versions() -> dict:
    try:
        with open(VERSIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_versions(versions: dict) -> None:
    with open(VERSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(versions, f, indent=2, ensure_ascii=False)

def send_embed(channel_id: str, embed: dict) -> bool:
    url = f"{LOLKA_BASE}/channels/{channel_id}/messages"
    r = requests.post(url, headers=LOLKA_HEADERS, json={"embeds": [embed]}, timeout=15)
    if not r.ok:
        print(f"  [ERROR] LOLKA API {r.status_code}: {r.text[:200]}")
    return r.ok

def log(symbol: str, text: str) -> None:
    print(f"[{symbol}] {text}")

# ─── Источники данных ─────────────────────────────────────────────────────────

def get_steam_buildid(appid: int) -> str | None:
    """Получить BuildID из SteamCMD API."""
    try:
        url = f"https://api.steamcmd.net/v1/info/{appid}"
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        build = data["data"][str(appid)]["depots"]["branches"]["public"]["buildid"]
        return str(build)
    except Exception as e:
        log("!", f"Steam API ({appid}) ошибка: {e}")
        return None

def get_github_latest_release(repo: str) -> dict | None:
    """Получить последний GitHub Release."""
    try:
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        r = requests.get(url, headers=GITHUB_HEADERS, timeout=20)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log("!", f"GitHub Releases ({repo}) ошибка: {e}")
        return None

def get_carbon_hooks_commit() -> dict | None:
    """
    Получить последний коммит Carbon, затрагивающий файлы хуков.
    Возвращает dict с sha, message, author, hook_files или None.
    """
    repo = "CarbonCommunity/Carbon"
    try:
        url = f"https://api.github.com/repos/{repo}/commits"
        r = requests.get(url, headers=GITHUB_HEADERS, params={"per_page": 15}, timeout=20)
        r.raise_for_status()
        commits = r.json()

        for commit in commits:
            sha = commit["sha"]
            detail_r = requests.get(
                f"https://api.github.com/repos/{repo}/commits/{sha}",
                headers=GITHUB_HEADERS, timeout=20
            )
            detail_r.raise_for_status()
            detail = detail_r.json()
            files = detail.get("files", [])

            hook_files = [
                f["filename"] for f in files
                if "hook" in f["filename"].lower()
            ]
            if hook_files:
                return {
                    "sha":        sha[:8],
                    "full_sha":   sha,
                    "message":    commit["commit"]["message"].split("\n")[0][:120],
                    "author":     commit["commit"]["author"]["name"],
                    "date":       commit["commit"]["author"]["date"],
                    "hook_files": hook_files[:10],
                    "url":        commit["html_url"],
                }

        log("-", "Carbon: коммиты с хуками не найдены в последних 15")
        return None
    except Exception as e:
        log("!", f"Carbon Hooks ошибка: {e}")
        return None

# ─── Embed-шаблоны ────────────────────────────────────────────────────────────

def embed_rust_server(old: str, new: str) -> dict:
    return {
        "title":       "🖥️  Обновление Rust Dedicated Server",
        "color":       COLOR_SERVER,
        "description": "Вышло обновление серверной части Rust. Обновите сервер через `steamcmd`.",
        "fields": [
            {"name": "Предыдущий BuildID", "value": f"`{old}`", "inline": True},
            {"name": "Новый BuildID",       "value": f"`{new}`", "inline": True},
            {"name": "Ссылки",
             "value": "[SteamDB](https://steamdb.info/app/258550/) • [Facepunch Blog](https://rust.facepunch.com/blog)",
             "inline": False},
        ],
        "footer":    {"text": "RustPulse • Rust Server"},
        "timestamp": now_iso(),
    }

def embed_rust_client(old: str, new: str) -> dict:
    return {
        "title":       "🎮  Обновление Rust Client",
        "color":       COLOR_CLIENT,
        "description": "Вышло обновление клиента Rust в Steam.",
        "fields": [
            {"name": "Предыдущий BuildID", "value": f"`{old}`", "inline": True},
            {"name": "Новый BuildID",       "value": f"`{new}`", "inline": True},
            {"name": "Ссылки",
             "value": "[SteamDB](https://steamdb.info/app/252490/) • [Facepunch Blog](https://rust.facepunch.com/blog)",
             "inline": False},
        ],
        "footer":    {"text": "RustPulse • Rust Client"},
        "timestamp": now_iso(),
    }

def embed_oxide(old: str, release: dict) -> dict:
    new_ver = release["tag_name"]
    body    = (release.get("body") or "Нет описания").strip()[:400]
    return {
        "title":       "⚙️  Новый релиз Oxide / uMod",
        "color":       COLOR_OXIDE,
        "description": f"```\n{body}\n```" if body else "",
        "fields": [
            {"name": "Предыдущая версия", "value": f"`{old}`",     "inline": True},
            {"name": "Новая версия",       "value": f"`{new_ver}`", "inline": True},
            {"name": "GitHub Release",
             "value": f"[Открыть]({release['html_url']})", "inline": False},
        ],
        "footer":    {"text": "RustPulse • Oxide/uMod"},
        "timestamp": now_iso(),
    }

def embed_carbon(old: str, release: dict) -> dict:
    new_ver = release["tag_name"]
    body    = (release.get("body") or "Нет описания").strip()[:400]
    return {
        "title":       "🔶  Новый релиз Carbon",
        "color":       COLOR_CARBON,
        "description": f"```\n{body}\n```" if body else "",
        "fields": [
            {"name": "Предыдущая версия", "value": f"`{old}`",     "inline": True},
            {"name": "Новая версия",       "value": f"`{new_ver}`", "inline": True},
            {"name": "GitHub Release",
             "value": f"[Открыть]({release['html_url']})", "inline": False},
        ],
        "footer":    {"text": "RustPulse • Carbon"},
        "timestamp": now_iso(),
    }

def embed_hooks(commit: dict) -> dict:
    files_text = "\n".join(commit["hook_files"]) or "—"
    return {
        "title":       "🪝  Обновление хуков Carbon",
        "color":       COLOR_HOOKS,
        "description": f"**{commit['message']}**",
        "fields": [
            {"name": "Коммит", "value": f"`{commit['sha']}`", "inline": True},
            {"name": "Автор",  "value": commit["author"],      "inline": True},
            {"name": "Изменённые файлы хуков",
             "value": f"```\n{files_text}\n```", "inline": False},
            {"name": "Смотреть коммит",
             "value": f"[GitHub]({commit['url']})", "inline": False},
        ],
        "footer":    {"text": "RustPulse • Carbon Hooks"},
        "timestamp": now_iso(),
    }

# ─── Точка входа ─────────────────────────────────────────────────────────────

def main() -> None:
    versions = load_versions()
    updated  = False

    print(f"\n{'='*55}")
    print(f"  RustPulse | {now_iso()}")
    print(f"{'='*55}")

    # 1. Rust Dedicated Server
    log("~", "Проверяю Rust Server (AppID 258550)...")
    build = get_steam_buildid(258550)
    if build:
        old = versions.get("rust_server", "unknown")
        if old != build:
            log("+", f"Rust Server: {old} -> {build}")
            send_embed(CHANNELS["rust_server"], embed_rust_server(old, build))
            versions["rust_server"] = build
            updated = True
        else:
            log("=", f"Rust Server без изменений ({build})")

    # 2. Rust Client
    log("~", "Проверяю Rust Client (AppID 252490)...")
    build = get_steam_buildid(252490)
    if build:
        old = versions.get("rust_client", "unknown")
        if old != build:
            log("+", f"Rust Client: {old} -> {build}")
            send_embed(CHANNELS["rust_client"], embed_rust_client(old, build))
            versions["rust_client"] = build
            updated = True
        else:
            log("=", f"Rust Client без изменений ({build})")

    # 3. Oxide / uMod
    log("~", "Проверяю Oxide (oxidemod/Oxide.Rust)...")
    release = get_github_latest_release("oxidemod/Oxide.Rust")
    if release:
        new_ver = release["tag_name"]
        old_ver = versions.get("oxide", "unknown")
        if old_ver != new_ver:
            log("+", f"Oxide: {old_ver} -> {new_ver}")
            send_embed(CHANNELS["oxide"], embed_oxide(old_ver, release))
            versions["oxide"] = new_ver
            updated = True
        else:
            log("=", f"Oxide без изменений ({new_ver})")

    # 4. Carbon
    log("~", "Проверяю Carbon (CarbonCommunity/Carbon)...")
    release = get_github_latest_release("CarbonCommunity/Carbon")
    if release:
        new_ver = release["tag_name"]
        old_ver = versions.get("carbon", "unknown")
        if old_ver != new_ver:
            log("+", f"Carbon: {old_ver} -> {new_ver}")
            send_embed(CHANNELS["carbon"], embed_carbon(old_ver, release))
            versions["carbon"] = new_ver
            updated = True
        else:
            log("=", f"Carbon без изменений ({new_ver})")

    # 5. Carbon Hooks
    log("~", "Проверяю хуки Carbon...")
    hook = get_carbon_hooks_commit()
    if hook:
        new_sha = hook["full_sha"]
        old_sha = versions.get("carbon_hooks", "")
        if old_sha != new_sha:
            log("+", f"Carbon Hooks: {old_sha[:8]} -> {new_sha[:8]} ({len(hook['hook_files'])} файл(ов))")
            send_embed(CHANNELS["hooks"], embed_hooks(hook))
            versions["carbon_hooks"] = new_sha
            updated = True
        else:
            log("=", f"Carbon Hooks без изменений ({new_sha[:8]})")

    # Сохраняем версии если были изменения
    if updated:
        save_versions(versions)
        log("v", "last_versions.json обновлён")
    else:
        log("v", "Новых обновлений нет")

    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
