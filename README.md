# 🦀 RustPulse — Бот обновлений для LOLKA

Автоматически отслеживает выход обновлений и публикует уведомления в 5 каналов LOLKA.

| Канал | Что отслеживает |
|---|---|
| `#обнова-сервера` | Rust Dedicated Server (Steam AppID 258550) |
| `#обнова-клиента` | Rust Client (Steam AppID 252490) |
| `#обнова-оксида` | Oxide/uMod (GitHub Releases) |
| `#обнова-карбона` | Carbon (GitHub Releases / .info) |
| `#обнова-хуков` | Carbon Hooks (GitHub Releases / .info) |

Запускается каждые **30 минут** через GitHub Actions — без сервера, без VPS.

---

## Настройка

### 1. Создать приватный репозиторий на GitHub
Залить все файлы в **открытый** репозиторий.

### 2. Добавить GitHub Secrets
`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

| Secret | Значение |
|---|---|
| `GITHUB_TOKEN` | Персональный токен GitHub (нужен для обхода лимитов API) |
| `LOLKA_TOKEN` | Токен бота из Портала разработчика LOLKA / Discord |
| `CHANNEL_RUST_SERVER` | ID канала #обнова-сервера |
| `CHANNEL_RUST_CLIENT` | ID канала #обнова-клиента |
| `CHANNEL_OXIDE` | ID канала #обнова-оксида |
| `CHANNEL_CARBON` | ID канала #обнова-карбона |
| `CHANNEL_HOOKS` | ID канала #обнова-хуков |

### 3. Включить Actions
`Settings` → `Actions` → `General` → `Allow all actions`

### 4. Первый запуск
`Actions` → `RustPulse — Check Updates` → `Run workflow`

При первом запуске бот сохранит текущие версии в `last_versions.json` и начнёт следить за изменениями.

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
├── .github/workflows/check_updates.yml  # GitHub Actions cron
├── bot.py                                # Основной скрипт
├── test_hooks.py                         # Скрипт для тестирования хуков
├── test_preview.py                       # Скрипт для тестирования оформления
├── last_versions.json                    # Последние версии (авто-коммит)
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```
