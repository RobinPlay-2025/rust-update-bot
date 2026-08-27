"""RustPulse - Rust/Oxide/Carbon update monitoring bot for LOLKA. Runs via GitHub Actions cron."""

import os
import json
import hashlib
import requests
from datetime import datetime, timezone

# ─── Конфигурация из переменных окружения ────────────────────────────────────

LOLKA_TOKEN    = os.environ.get("LOLKA_TOKEN", "")
GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN", "")

# ─── Каналы из config.json (не секрет — ID каналов не являются чувствительными данными)
_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
try:
    with open(_CONFIG_FILE, "r", encoding="utf-8") as _f:
        _cfg = json.load(_f)
    CHANNELS: dict = _cfg["channels"]
except Exception as _e:
    raise RuntimeError(f"Не удалось загрузить config.json: {_e}")


# ─── HTTP-заголовки ───────────────────────────────────────────────────────────

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
    token = os.environ.get("LOLKA_TOKEN", LOLKA_TOKEN)
    if not token:
        print(f"  [ERROR] LOLKA_TOKEN не задан! Невозможно отправить сообщение в канал {channel_id}.")
        return False
    url = f"{LOLKA_BASE}/channels/{channel_id}/messages"
    payload = {"embeds": [embed]}
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if not r.ok:
            print(f"  [ERROR] LOLKA API {r.status_code} | channel={channel_id}")
            print(f"  [ERROR] Response: {r.text[:500]}")
            print(f"  [ERROR] Payload size: {len(str(payload))} chars")
        return r.ok
    except Exception as e:
        print(f"  [ERROR] send_embed exception: {e}")
        return False

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

def _compute_opj_fingerprint(branch: str) -> str | None:
    """Fetch the .opj hook file from carbonmod.gg and compute a fingerprint from all MSILHash values.
    This fingerprint changes every time Carbon rebuilds hooks for a new protocol."""
    try:
        url = f"https://api.carbonmod.gg/oxide/{branch}.opj"
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        all_hashes = []
        for manifest in data.get("Manifests", []):
            for hook_entry in manifest.get("Hooks", []):
                mh = hook_entry.get("Hook", {}).get("MSILHash", "")
                if mh:
                    all_hashes.append(mh)
        if not all_hashes:
            return None
        return hashlib.md5("|".join(sorted(all_hashes)).encode()).hexdigest()[:16]
    except Exception as e:
        log("!", f"carbonmod.gg fingerprint ({branch}) ошибка: {e}")
        return None

HOOK_BRANCHES = ["public", "staging", "aux03"]

def get_carbon_hook_info(branch: str) -> dict | None:
    """Fetch fingerprint and metadata for a specific Carbon hooks branch.
    Checks carbonmod.gg for OPJ fingerprint and GitHub for protocol/release info."""
    fp = _compute_opj_fingerprint(branch)
    if not fp:
        return None

    repo = "CarbonCommunity/Carbon"
    protocol    = ""
    version     = ""
    commit_h    = ""
    rel_type    = "debug+release"
    release_url = f"https://github.com/{repo}/releases"
    action_url  = f"https://github.com/{repo}/actions"

    # Пытаемся получить протокол из соответствующего GitHub release .info
    try:
        r = requests.get(
            f"https://api.github.com/repos/{repo}/releases",
            headers=GITHUB_HEADERS,
            params={"per_page": 15},
            timeout=20
        )
        if r.ok:
            releases = sorted(r.json(), key=lambda x: x.get("published_at") or "", reverse=True)
            for release in releases:
                tag = release.get("tag_name", "").lower()
                if branch == "staging" and "staging" not in tag:
                    continue
                if branch == "aux03" and "aux03" not in tag:
                    continue
                if branch == "public" and any(k in tag for k in ("staging", "aux03", "edge", "preview")):
                    continue

                assets = release.get("assets", [])
                info_asset = next(
                    (a for a in assets if a["name"].endswith(".info") and "Windows" in a["name"] and "Minimal" not in a["name"]),
                    next((a for a in assets if a["name"].endswith(".info")), None)
                )
                if not info_asset:
                    continue
                info = _parse_info_file(info_asset["browser_download_url"])
                if not info:
                    continue

                protocol    = info.get("Protocol", release.get("tag_name", ""))
                version     = info.get("Version", "")
                commit_h    = info.get("Commit", {}).get("HashShort", "")
                has_debug   = any("Debug"   in a["name"] and "Minimal" not in a["name"] for a in assets)
                has_release = any("Release" in a["name"] and "Minimal" not in a["name"] for a in assets)
                rel_type    = "debug+release" if (has_debug and has_release) else ("debug" if has_debug else "release")
                release_url = release["html_url"]
                break

    except Exception as e:
        log("!", f"GitHub metadata ({branch}) ошибка: {e}")

    # Ссылка на последний успешный Actions run воркфлоу Protocol Hooks Build
    try:
        r_act = requests.get(
            f"https://api.github.com/repos/{repo}/actions/workflows/hook-build.yml/runs",
            headers=GITHUB_HEADERS,
            params={"per_page": 5},
            timeout=10
        )
        if r_act.status_code == 200:
            for run in r_act.json().get("workflow_runs", []):
                if run.get("conclusion") == "success":
                    action_url = run.get("html_url", action_url)
                    break
        else:
            r_fallback = requests.get(
                f"https://api.github.com/repos/{repo}/actions/runs",
                headers=GITHUB_HEADERS,
                params={"per_page": 10},
                timeout=10
            )
            if r_fallback.status_code == 200:
                for run in r_fallback.json().get("workflow_runs", []):
                    if run.get("name") == "Protocol Hooks Build" and run.get("conclusion") == "success":
                        action_url = run.get("html_url", action_url)
                        break
    except Exception:
        pass

    return {
        "fingerprint": fp,
        "branch":      branch,
        "protocol":    protocol,
        "version":     version,
        "commit":      commit_h,
        "rel_type":    rel_type,
        "url":         release_url,
        "action_url":  action_url,
    }

# Для совместимости со старыми импортами (по умолчанию возвращает public)
def get_carbon_hooks_release(branch: str = "public") -> dict | None:
    return get_carbon_hook_info(branch)



# ─── Embed-шаблоны ────────────────────────────────────────────────────────────

def embed_rust_server(old: str, new: str) -> dict:
    return {
        "title":       "🖥️  Обновление Rust Dedicated Server",
        "color":       COLOR_SERVER,
        "description": "Вышло обновление серверной части Rust. Обновите сервер через `steamcmd`.",
        "thumbnail":   {"url": "https://raw.githubusercontent.com/RobinPlay-2025/rust-update-bot/main/thumb_server.png"},
        "fields": [
            {"name": "Предыдущий BuildID", "value": f"`{old}`", "inline": True},
            {"name": "Новый BuildID",       "value": f"`{new}`", "inline": True},
            {"name": "Ссылки",
             "value": "[SteamDB](https://steamdb.info/app/258550/) • [Facepunch Blog](https://rust.facepunch.com/blog)",
             "inline": False},
        ],
    }

def embed_rust_client(old: str, new: str) -> dict:
    return {
        "title":       "🎮  Обновление Rust Client",
        "color":       COLOR_CLIENT,
        "description": "Вышло обновление клиента Rust в Steam.",
        "thumbnail":   {"url": "https://raw.githubusercontent.com/RobinPlay-2025/rust-update-bot/main/thumb_client.png"},
        "fields": [
            {"name": "Предыдущий BuildID", "value": f"`{old}`", "inline": True},
            {"name": "Новый BuildID",       "value": f"`{new}`", "inline": True},
            {"name": "Ссылки",
             "value": "[SteamDB](https://steamdb.info/app/252490/) • [Facepunch Blog](https://rust.facepunch.com/blog)",
             "inline": False},
        ],
    }

def embed_oxide(old: str, release: dict) -> dict:
    new_ver = release["tag_name"]
    body    = (release.get("body") or "Нет описания").strip()[:400]
    return {
        "title":       "⚙️  Новый релиз Oxide / uMod",
        "color":       COLOR_OXIDE,
        "description": body if body else "",
        "thumbnail":   {"url": "https://raw.githubusercontent.com/RobinPlay-2025/rust-update-bot/main/thumb_oxide.png"},
        "fields": [
            {"name": "Предыдущая версия", "value": f"`{old}`",     "inline": True},
            {"name": "Новая версия",       "value": f"`{new_ver}`", "inline": True},
            {"name": "GitHub Release",
             "value": f"[Открыть]({release['html_url']})", "inline": False},
        ],
    }

def embed_carbon(old: str, release: dict) -> dict:
    new_ver = release["tag_name"]
    body    = (release.get("body") or "Нет описания").strip()[:400]
    return {
        "title":       "🔶  Новый релиз Carbon",
        "color":       COLOR_CARBON,
        "description": body if body else "",
        "thumbnail":   {"url": "https://raw.githubusercontent.com/RobinPlay-2025/rust-update-bot/main/carbonvector_go.png"},
        "fields": [
            {"name": "Предыдущая версия", "value": f"`{old}`",     "inline": True},
            {"name": "Новая версия",       "value": f"`{new_ver}`", "inline": True},
            {"name": "GitHub Release",
             "value": f"[Открыть]({release['html_url']})", "inline": False},
        ],
    }

def embed_hooks(hook: dict) -> dict:
    branch = hook.get("branch", "public")
    branch_info = {
        "public":  {"emoji": "✅", "name": "Public (Релизная)"},
        "staging": {"emoji": "🧪", "name": "Staging (Тестовая)"},
        "aux03":   {"emoji": "🔧", "name": "Aux03 (Экспериментальная)"},
        "edge":    {"emoji": "⚡", "name": "Edge"},
    }.get(branch, {"emoji": "🪝", "name": branch.capitalize()})
    
    emoji = branch_info["emoji"]
    branch_title = branch_info["name"]

    # Oxide Hooks URL
    oxide_url = f"https://api.carbonmod.gg/oxide/{branch}.opj"

    # Ссылки на прямое скачивание .dll файлов
    comm_dll = "Carbon.Hooks.Community.dll"
    ox_dll   = "Carbon.Hooks.Oxide.dll"
    prot     = hook.get("protocol", "")
    
    download_fields = []
    if prot:
        base_win_debug = f"https://cdn.carbonmod.gg/hooks/server/debug/{prot}/carbon/managed/hooks"
        base_unx_debug = f"https://cdn.carbonmod.gg/hooks/server/debugunix/{prot}/carbon/managed/hooks"
        base_win_rel   = f"https://cdn.carbonmod.gg/hooks/server/release/{prot}/carbon/managed/hooks"
        base_unx_rel   = f"https://cdn.carbonmod.gg/hooks/server/releaseunix/{prot}/carbon/managed/hooks"
        
        col_debug = (
            f"Windows:\n[{comm_dll}]({base_win_debug}/{comm_dll})\n[{ox_dll}]({base_win_debug}/{ox_dll})\n"
            f"Unix:\n[{comm_dll}]({base_unx_debug}/{comm_dll})\n[{ox_dll}]({base_unx_debug}/{ox_dll})"
        )
        
        col_rel = (
            f"Windows:\n[{comm_dll}]({base_win_rel}/{comm_dll})\n[{ox_dll}]({base_win_rel}/{ox_dll})\n"
            f"Unix:\n[{comm_dll}]({base_unx_rel}/{comm_dll})\n[{ox_dll}]({base_unx_rel}/{ox_dll})"
        )

        download_fields = [
            {"name": "Скачать (Debug)",   "value": col_debug + "\n━━━━━━━━━━━━━━━━━━━", "inline": False},
            {"name": "Скачать (Release)", "value": col_rel, "inline": False},
        ]

    prot_display = prot if prot else "н/д"
    type_display  = hook.get("rel_type", "debug+release")

    fields = [
        {"name": "Ветка",      "value": f"{emoji} `{branch}` ({branch_title})", "inline": True},
        {"name": "Протокол",   "value": f"`{prot_display}`",                    "inline": True},
        {"name": "Тип",        "value": type_display,                           "inline": True},
        {"name": "Хуки Oxide", "value": f"[{branch}.opj]({oxide_url})",         "inline": False},
        *download_fields,
    ]

    return {
        "title":       f"{emoji} Обновление хуков Carbon — {branch.upper()}",
        "url":         hook.get("action_url", "https://github.com/CarbonCommunity/Carbon/actions"),
        "color":       0x76B82A,
        "description": f"**Доступно новое обновление хуков для ветки `{branch}`!**\nПерезапустите сервер с тем же протоколом для обновления.",
        "fields":      fields,
        "thumbnail":  {"url": "https://raw.githubusercontent.com/RobinPlay-2025/rust-update-bot/main/carbonvector_go.png"},
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
        old = versions.get("rust_server", "")
        if not old:
            log("=", f"Rust Server: первый запуск, запоминаю {build}")
            versions["rust_server"] = build
            updated = True
        elif old != build:
            log("+", f"Rust Server: {old} -> {build}")
            if send_embed(CHANNELS["rust_server"], embed_rust_server(old, build)):
                versions["rust_server"] = build
                updated = True
            else:
                log("!", "Ошибка отправки в LOLKA, версия не сохранена")
        else:
            log("=", f"Rust Server без изменений ({build})")

    # 2. Rust Client
    log("~", "Проверяю Rust Client (AppID 252490)...")
    build = get_steam_buildid(252490)
    if build:
        old = versions.get("rust_client", "")
        if not old:
            log("=", f"Rust Client: первый запуск, запоминаю {build}")
            versions["rust_client"] = build
            updated = True
        elif old != build:
            log("+", f"Rust Client: {old} -> {build}")
            if send_embed(CHANNELS["rust_client"], embed_rust_client(old, build)):
                versions["rust_client"] = build
                updated = True
            else:
                log("!", "Ошибка отправки в LOLKA, версия не сохранена")
        else:
            log("=", f"Rust Client без изменений ({build})")

    # 3. Oxide / uMod
    log("~", "Проверяю Oxide (oxidemod/Oxide.Rust)...")
    release = get_github_latest_release("oxidemod/Oxide.Rust")
    if release:
        new_ver = release["tag_name"]
        old_ver = versions.get("oxide", "")
        if not old_ver:
            log("=", f"Oxide: первый запуск, запоминаю {new_ver}")
            versions["oxide"] = new_ver
            updated = True
        elif old_ver != new_ver:
            log("+", f"Oxide: {old_ver} -> {new_ver}")
            if send_embed(CHANNELS["oxide"], embed_oxide(old_ver, release)):
                versions["oxide"] = new_ver
                updated = True
            else:
                log("!", "Ошибка отправки в LOLKA, версия не сохранена")
        else:
            log("=", f"Oxide без изменений ({new_ver})")

    # 4. Carbon
    log("~", "Проверяю Carbon (CarbonCommunity/Carbon)...")
    release = get_github_latest_release("CarbonCommunity/Carbon")
    if release:
        new_ver = release["tag_name"]
        # Carbon использует теги вроде "production_build". Настоящая версия лежит в .info файле!
        for a in release.get("assets", []):
            if a["name"] == "Carbon.Windows.Release.info":
                try:
                    r_info = requests.get(a["browser_download_url"], timeout=10)
                    if r_info.status_code == 200:
                        info_data = r_info.json()
                        if "Version" in info_data:
                            new_ver = info_data["Version"]
                except Exception:
                    pass
                break

        old_ver = versions.get("carbon", "")
        release["tag_name"] = new_ver
        if not old_ver:
            log("=", f"Carbon: первый запуск, запоминаю {new_ver}")
            versions["carbon"] = new_ver
            updated = True
        elif old_ver != new_ver:
            log("+", f"Carbon: {old_ver} -> {new_ver}")
            if send_embed(CHANNELS["carbon"], embed_carbon(old_ver, release)):
                versions["carbon"] = new_ver
                updated = True
            else:
                log("!", "Ошибка отправки в LOLKA, версия не сохранена")
        else:
            log("=", f"Carbon без изменений ({new_ver})")

    # 5. Carbon Hooks (проверка всех активных веток: public, staging, aux03)
    log("~", "Проверяю хуки Carbon по веткам (public, staging, aux03)...")

    # Миграция со старого формата carbon_hooks (если в файле хранилась одна строка)
    raw_hooks = versions.get("carbon_hooks")
    if not isinstance(raw_hooks, dict):
        hooks_state: dict = {}
        old_legacy_fp   = str(raw_hooks) if raw_hooks else ""
        old_legacy_prot = versions.get("carbon_hooks_protocol", "")
        if old_legacy_fp:
            hooks_state["public"] = {
                "fingerprint": old_legacy_fp,
                "protocol":    old_legacy_prot
            }
        versions["carbon_hooks"] = hooks_state
    else:
        hooks_state = versions["carbon_hooks"]

    for branch in HOOK_BRANCHES:
        hook = get_carbon_hook_info(branch)
        if not hook:
            continue

        new_fp   = hook["fingerprint"]
        new_prot = hook["protocol"]

        branch_saved = hooks_state.get(branch, {})
        old_fp   = branch_saved.get("fingerprint", "")
        old_prot = branch_saved.get("protocol", "")

        fp_changed   = old_fp != new_fp
        prot_changed = bool(old_prot and new_prot and old_prot != new_prot)

        # Первый запуск для данной ветки — тихо запоминаем текущее состояние
        if not old_fp:
            log("=", f"Carbon Hooks [{branch}]: первый запуск, запоминаю состояние (fp: {new_fp}, prot: {new_prot or 'н/д'})")
            hooks_state[branch] = {"fingerprint": new_fp, "protocol": new_prot}
            updated = True
        elif fp_changed or prot_changed:
            reasons = []
            if prot_changed: reasons.append(f"протокол {old_prot} -> {new_prot}")
            if fp_changed:   reasons.append(f"fingerprint {old_fp} -> {new_fp}")
            log("+", f"Carbon Hooks [{branch}]: {', '.join(reasons)}")

            if send_embed(CHANNELS["hooks"], embed_hooks(hook)):
                hooks_state[branch] = {"fingerprint": new_fp, "protocol": new_prot}
                updated = True
            else:
                log("!", f"Ошибка отправки в LOLKA для ветки {branch}, версия не сохранена")
        else:
            log("=", f"Carbon Hooks [{branch}] без изменений (protocol: {new_prot or 'н/д'})")

    # Сохраняем версии если были изменения
    if updated:
        save_versions(versions)
        log("v", "last_versions.json обновлён")
    else:
        log("v", "Новых обновлений нет")

    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
