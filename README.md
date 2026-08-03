# 🦀 RustPulse — Бот обновлений для LOLKA

Автоматически отслеживает выход обновлений и публикует уведомления в 5 каналов LOLKA.

| Канал | Что отслеживает | Источник |
|---|---|---|
| `#обнова-сервера` | Rust Dedicated Server | Steam AppID 258550 (steamcmd.net API) |
| `#обнова-клиента` | Rust Client | Steam AppID 252490 (steamcmd.net API) |
| `#обнова-оксида` | Oxide / uMod | GitHub Releases (oxidemod/Oxide.Rust) |
| `#обнова-карбона` | Carbon | GitHub Releases / `.info` файл |
| `#обнова-хуков` | Carbon Hooks | **`api.carbonmod.gg` MSILHash fingerprint** |

Запускается каждые **5 минут** через GitHub Actions — без сервера, без VPS.

> **Как детектируются хуки Carbon:**  
> Бот скачивает `api.carbonmod.gg/oxide/{branch}.opj` и вычисляет MD5-отпечаток  
> по всем `MSILHash` значениям. Fingerprint меняется при каждой пересборке хуков под новый протокол,  
> что позволяет мгновенно реагировать на обновления без привязки к GitHub release timing.

---

## Настройка

### 1. Создать репозиторий на GitHub
Залить все файлы в **открытый** репозиторий.  
> ⚠️ Если репозиторий **приватный** — иконка в карточке обновления хуков Carbon не отобразится (ссылка на картинку будет недоступна).

### 2. Добавить GitHub Secrets
`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

| Secret | Описание |
|---|---|
| `LOLKA_TOKEN` | Токен бота из Портала разработчика LOLKA |
| `GITHUB_TOKEN` | Персональный токен GitHub (снимает лимиты API) |
| `CHANNEL_RUST_SERVER` | ID канала #обнова-сервера |
| `CHANNEL_RUST_CLIENT` | ID канала #обнова-клиента |
| `CHANNEL_OXIDE` | ID канала #обнова-оксида |
| `CHANNEL_CARBON` | ID канала #обнова-карбона |
| `CHANNEL_HOOKS` | ID канала #обнова-хуков |

### 3. Включить Actions
`Settings` → `Actions` → `General` → `Allow all actions`

### 4. Первый запуск
`Actions` → `RustPulse — Check Updates` → `Run workflow`

При первом запуске бот сохранит текущие версии и fingerprints в `last_versions.json` и начнёт следить за изменениями.

---

## Локальное тестирование

```bash
# Скопировать и заполнить
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
        └── api.carbonmod.gg ───────► Carbon Hooks fingerprint (MSILHash)
                │
                ▼ (если есть изменение)
        POST → lolka.app/api/bot/v10/channels/{id}/messages
                │
                ▼
        git commit + push (last_versions.json)
```
