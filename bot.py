"""RustPulse - Rust/Oxide/Carbon update monitoring bot for LOLKA. Runs via GitHub Actions cron."""

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
    """Get public branch BuildID from steamcmd.net API."""
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
    """Get the latest GitHub Release for a given repo (owner/name)."""
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

def _parse_info_file(url: str) -> dict:
    """Download and parse a Carbon .info JSON file."""
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}

def get_carbon_hooks_release() -> dict | None:
    """Read .info files from Carbon GitHub releases to get Protocol/Branch/Type. Picks the most recently published release."""
    repo = "CarbonCommunity/Carbon"
    try:
        url = f"https://api.github.com/repos/{repo}/releases"
        r = requests.get(url, headers=GITHUB_HEADERS, params={"per_page": 20}, timeout=20)
        r.raise_for_status()
        releases = r.json()

        # Сортируем по дате публикации — самый свежий первый
        sorted_releases = sorted(
            releases,
            key=lambda rel: rel.get("published_at", ""),
            reverse=True
        )

        for release in sorted_releases:
            tag    = release.get("tag_name", "")
            assets = release.get("assets", [])

            # Ищем .info файл (Windows, не Minimal)
            info_asset = next(
                (a for a in assets if a["name"].endswith(".info") and "Windows" in a["name"] and "Minimal" not in a["name"]),
                next((a for a in assets if a["name"].endswith(".info")), None)
            )
            if not info_asset:
                continue

            info = _parse_info_file(info_asset["browser_download_url"])
            if not info:
                continue

            protocol  = info.get("Protocol", tag)
            branch_raw = info.get("Commit", {}).get("Branch", tag)

            # Нормализуем ветку
            tag_lower = tag.lower()
            if "staging" in branch_raw.lower() or "staging" in tag_lower:
                branch = "staging"
            elif "aux03" in branch_raw.lower() or "aux03" in tag_lower:
                branch = "aux03"
            elif "edge" in tag_lower:
                branch = "edge"
            else:
                branch = "public"

            # Тип сборки
            has_debug   = any("Debug"   in a["name"] and "Minimal" not in a["name"] for a in assets)
            has_release = any("Release" in a["name"] and "Minimal" not in a["name"] for a in assets)
            if has_debug and has_release:
                rel_type = "debug+release"
            elif has_debug:
                rel_type = "debug"
            else:
                rel_type = "release"

            return {
                "id":       str(release["id"]),
                "tag":      tag,
                "protocol": protocol,
                "branch":   branch,
                "rel_type": rel_type,
                "version":  info.get("Version", ""),
                "commit":   info.get("Commit", {}).get("HashShort", ""),
                "url":      release["html_url"],
            }

        log("-", "Carbon: .info файлы не найдены в релизах")
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

def embed_hooks(hook: dict) -> dict:
    branch_emoji = {"staging": "🧪", "aux03": "🔧", "public": "✅", "edge": "⚡"}.get(hook["branch"], "🪝")

    # Oxide Hooks URL
    oxide_url = f"https://api.carbonmod.gg/oxide/{hook['branch']}.opj"

    # Ссылки на скачивание (без каких-либо скрытых пробелов)
    dl_url = hook["url"]
    comm_dll = "Carbon.Hooks.Community.dll"
    ox_dll   = "Carbon.Hooks.Oxide.dll"
    
    one_col = (
        f"Windows:\n[{comm_dll}]({dl_url})\n[{ox_dll}]({dl_url})\n"
        f"Unix:\n[{comm_dll}]({dl_url})\n[{ox_dll}]({dl_url})"
    )

    # Возвращаем 2 колонки как в оригинале
    download_fields = [
        {"name": "Download Debug",   "value": one_col, "inline": True},
        {"name": "Download Release", "value": one_col, "inline": True},
    ]

    return {
        "title":       "Hook Update",
        "color":       0x76B82A,
        "description": "**New protocol hook update available!**\nRestart the server with the same protocol to update.",
        "fields": [
            {"name": "Protocol", "value": hook["protocol"], "inline": True},
            {"name": "Type",     "value": "debug+release",  "inline": True},
            {"name": "Rust",     "value": hook["branch"],   "inline": True},
            {"name": "Oxide Hooks",
             "value": f"[Rust.opj]({oxide_url})",
             "inline": False},
            *download_fields,
            {"name": "\u200b", "value": "\u00A0" * 65, "inline": False}, # Force width
        ],
        "thumbnail":  {"url": "https://raw.githubusercontent.com/RobinPlay-2025/rust-update-bot/main/carbonvector_go.png"},
        "footer":     {"text": f"RustPulse • Carbon Hooks • {branch_emoji} {hook['branch']}"},
        "timestamp":  now_iso(),
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
    log("~", "Проверяю хуки Carbon (GitHub Releases)...")
    hook = get_carbon_hooks_release()
    if hook:
        new_id = hook["id"]
        old_id = versions.get("carbon_hooks", "")
        if old_id != new_id:
            log("+", f"Carbon Hooks: {old_id} -> {new_id} (ветка: {hook['branch']})")
            send_embed(CHANNELS["hooks"], embed_hooks(hook))
            versions["carbon_hooks"] = new_id
            updated = True
        else:
            log("=", f"Carbon Hooks без изменений (id: {new_id}, ветка: {hook['branch']})")

    # Сохраняем версии если были изменения
    if updated:
        save_versions(versions)
        log("v", "last_versions.json обновлён")
    else:
        log("v", "Новых обновлений нет")

    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
