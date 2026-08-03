# 🦀 RustPulse — Бот обновлений для LOLKA

Автоматически отслеживает выход обновлений и публикует уведомления в 5 каналов LOLKA.

| Канал | Что отслеживает | Источник |
|---|---|---|
| `#SERVER UPDATE` | Rust Dedicated Server | Steam AppID 258550 (steamcmd.net API) |
| `#CLIENT UPDATE` | Rust Client | Steam AppID 252490 (steamcmd.net API) |
| `#OXIDE UPDATE` | Oxide / uMod | GitHub Releases (oxidemod/Oxide.Rust) |
| `#CARBON UPDATE` | Carbon | GitHub Releases / `.info` файл |
| `#CARBON HOOKS UPDATE` | Carbon Hooks | `api.carbonmod.gg` MSILHash fingerprint |

Запускается каждые **5 минут** через GitHub Actions — без сервера, без VPS.

> ⚠️ **Задержка уведомлений:** GitHub Actions не гарантирует точное время запуска.
> В среднем задержка составляет **0–5 минут**, при нагрузке на серверы GitHub — до 15 минут.

---

## Настройка

### 1. Создать репозиторий на GitHub
Залить все файлы в **открытый** репозиторий.
> Если репозиторий **приватный** — иконка в карточке обновления хуков Carbon не отобразится.

### 2. Заполнить `config.json`
Открой файл [`config.json`](config.json) и замени значения на ID каналов из твоего сервера LOLKA.

```json
{
  "channels": {
    "rust_server": "806278127027200",
    "rust_client":  "815797214249984",
    "oxide":        "815797409219584",
    "carbon":       "815797588984832",
    "hooks":        "815797917861888"
  }
}
```

ID канала скопировать в Lolka: правая кнопка по каналу → **Копировать ID**.

### 3. Добавить GitHub Secrets
`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

| Secret | Описание |
|---|---|
| `LOLKA_TOKEN` | Токен бота из Портала разработчика LOLKA |
| `GITHUB_TOKEN` | Персональный токен GitHub (снимает лимиты API до 5000 запросов/час) |

> Channel ID больше **не нужно** добавлять в секреты — они хранятся в `config.json`.

### 4. Включить Actions
`Settings` → `Actions` → `General` → `Allow all actions`

### 5. Первый запуск
`Actions` → `RustPulse — Check Updates` → `Run workflow`

При первом запуске бот сохранит текущие версии в `last_versions.json` и начнёт следить за изменениями.

---

## Локальное тестирование

```bash
# Скопировать и заполнить токен
cp .env.example .env

# Установить зависимости
pip install -r requirements.txt

# Запустить
python bot.py
```

---

## Файлы проекта

```
rust-update-bot/
├── .github/workflows/check_updates.yml  # GitHub Actions cron (каждые 5 мин)
├── bot.py                                # Основной скрипт
├── config.json                           # ID каналов LOLKA (заполнить вручную)
├── last_versions.json                    # Последние версии (авто-коммит)
├── requirements.txt                      # requests==2.32.3
├── .env.example                          # Пример переменных окружения
├── .gitignore
└── README.md
```

---

## Как это работает

```
GitHub Actions (каждые 5 мин)
        │
        ▼
   python bot.py
        │
        ├── Steam API ──────────────► Rust Server / Client BuildID
        ├── GitHub Releases ────────► Oxide версия
        ├── GitHub Releases + .info ► Carbon версия
        └── api.carbonmod.gg ───────► Carbon Hooks MSILHash fingerprint
                │
                ▼ (если есть изменение)
        POST → lolka.app/api/bot/v10/channels/{id}/messages
                │
                ▼
        git commit + push (last_versions.json)
```
