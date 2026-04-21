# TeleFlow (MVP)

Локальный userbot на Telethon:

- `/digest` — собрать и отправить дайджест из выбранной папки Telegram.
- `/stats` — сколько постов сохранено в базе по каждой теме (`THEMES`).
- `forward` в ЛС userbot — сохранить пост в базу с темой.
- `/write <тема>` — сгенерировать пост из сохраненных материалов темы.

Подробные требования: `SPEC.md`.

## 1) Установка

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Заполните `.env` минимум:

- `API_ID`, `API_HASH`, `PHONE_NUMBER`
- `SOURCE_FOLDER_NAMES`
- `ALLOWED_USER_IDS`
- `THEMES`
- **`OPENROUTER_API_KEY`** — обязательно, ключ с [openrouter.ai/keys](https://openrouter.ai/keys)

Установите зависимости из `requirements.txt` (в т.ч. `python-socks` для SOCKS/MTProxy в Telethon).

### OpenRouter (единственный LLM)

Эндпоинт зашит в коде: `https://openrouter.ai/api/v1/chat/completions`.

| Переменная | Обязательность | По умолчанию |
|------------|----------------|--------------|
| `OPENROUTER_API_KEY` | да | — |
| `OPENROUTER_MODEL` | нет | `openai/gpt-4o-mini` |
| `OPENROUTER_MAX_TOKENS` | нет | `8192` |
| `OPENROUTER_TIMEOUT_SEC` | нет | `120` — таймаут одного HTTP-запроса к OpenRouter |
| `OPENROUTER_ANNOTATE_BUDGET_SEC` | нет | `300` — суммарный лимит времени на все батчи разметки в одном `/digest` |
| `OPENROUTER_DIGEST_BATCH_SIZE` | нет | `8` — постов за один запрос разметки |
| `OPENROUTER_DIGEST_TEXT_CHARS` | нет | `1600` — обрезка текста поста на входе в LLM |
| `OPENROUTER_DIGEST_MAX_ITEMS` | нет | `80` — максимум кандидатов с LLM-разметкой |

Опционально для политики OpenRouter: **`OPENROUTER_HTTP_REFERER`**, **`OPENROUTER_APP_TITLE`** (если не заданы, подставляются нейтральные значения по умолчанию).

Список моделей: [openrouter.ai/models](https://openrouter.ai/models).

Параметры стабильности Telegram (прокси, connect, RPC и т.д.) — см. прежние пункты в `.env` / коде (`TG_*`, `RUN_ONCE_BUDGET_SEC`, `COLLECT_MAX_MESSAGES_PER_CHANNEL`).

## 2) Режимы запуска

### Daemon (основной режим)

```powershell
python -m teleflow --daemon
```

Что делает:

- держит userbot в ожидании;
- принимает команды в ЛС (`/digest`, `/write <тема>`);
- обрабатывает forward + выбор темы.

### Once (технический режим)

```powershell
python -m teleflow --once
```

Что делает:

- выполняет один цикл дайджеста и завершает работу;
- полезно для отладки/демо.

## 3) DRY_RUN поведение

- `DRY_RUN=false`
  - `--once`: отправка в `TARGET_CHANNEL` (или fallback target), обновление `state.db`.
  - `/digest` в демоне: отправка адресату команды, обновление `state.db`.
- `DRY_RUN=true`
  - `run_digest_once` не отправляет в основной target и не обновляет `state.db`.
  - `/digest` в демоне отправляет preview пользователю команды через chunked `send_text`.
  - `--once` пишет preview в лог.

## 4) Сценарий демо

1. Запустить `--daemon`.
2. Написать в ЛС userbot: `/digest`.
3. Переслать понравившийся текстовый пост.
4. На запрос темы ответить (например: `спорт`).
5. Выполнить `/write спорт`.
6. Получить сгенерированный пост в ЛС.

## 5) Smoke-чеклист

- [ ] `/digest` от whitelist-пользователя возвращает дайджест в ЛС.
- [ ] Длинный дайджест приходит целиком (chunked отправка, без ошибки длины Telegram).
- [ ] Forward текстового поста вызывает запрос темы.
- [ ] Валидная тема сохраняет `entry_*.json` в `data/knowledge/<тема>/`.
- [ ] Невалидная тема не сохраняется, бот повторно просит выбрать тему.
- [ ] `/write <тема>` читает только соответствующую папку темы.
- [ ] `/write <тема>` при пустой теме отвечает без вызова LLM.
- [ ] Сообщения от не-whitelist пользователя игнорируются.

## 6) Troubleshooting

- Если `--once` завершается по таймауту бюджета:
  - проверьте MTProxy и `TG_PROXY_*`;
  - уменьшите `SOURCE_FOLDER_NAMES` / `COLLECT_MAX_MESSAGES_PER_CHANNEL`;
  - для OpenRouter увеличьте `OPENROUTER_TIMEOUT_SEC` или `OPENROUTER_ANNOTATE_BUDGET_SEC`, уменьшите `OPENROUTER_DIGEST_BATCH_SIZE`.
- Если OpenRouter вернул ошибку — смотрите HTTP-код и тело в логе; проверьте баланс и id модели.
- **`PeerFloodError` / лимит Telegram** при preview в ЛС: подождите или включите отправку в канал (`DRY_RUN=false`); между частями длинного текста бот делает паузу, но лимит всё равно может сработать.
- Если `/write` дал короткий fallback — OpenRouter не вернул текст (сеть, лимиты, модель).
- Сессия Telegram: при неинтерактивном запуске без сессии процесс завершится с явной ошибкой (один раз войти в терминале).

## 7) Структура данных

```text
data/
├── knowledge/
│   ├── спорт/
│   │   └── entry_<id>.json
│   └── ...
└── drafts/
    ├── спорт/
    └── ...
```
