# TeleFlow (MVP)

Локальный userbot на Telethon:

- `/digest` — собрать и отправить дайджест из выбранной папки Telegram.
- `/stats` — сколько постов сохранено в базе по каждой теме (`THEMES`).
- `/list <тема>` — показать последние записи темы (id + короткий хвост).
- `/rm <id>` — удалить запись `entry_<id>.json`.
- `/mv <id> <новая тема>` — перенести запись между темами.
- `/undo` — отменить последнее успешное сохранение в базу (для текущего пользователя).
- `forward` в ЛС userbot — сохранить пост в базу с темой.
- `/write <тема поста> [--theme=<тема базы>]` — сгенерировать пост по релевантным материалам (глобально или в рамках темы базы).

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
- `LLM_PROVIDER` (`openrouter` или `yandex`)
- для `LLM_PROVIDER=openrouter`: **`OPENROUTER_API_KEY`**
- для `LLM_PROVIDER=yandex`: **`YANDEX_API_KEY`** и **`YANDEX_FOLDER_ID`**

Установите зависимости из `requirements.txt` (в т.ч. `python-socks` для SOCKS/MTProxy в Telethon).

### LLM-провайдеры (OpenRouter / Yandex)

Переключение делается через `LLM_PROVIDER`:

- `openrouter` → `https://openrouter.ai/api/v1/chat/completions`
- `yandex` → `https://llm.api.cloud.yandex.net/foundationModels/v1/completion`

> Для Yandex используется `Authorization: Api-Key <key>`, `x-folder-id: <folder_id>` и `modelUri` формата `gpt://<folder_id>/<model>`.
> Формат взят из официальной документации Yandex AI Studio: [TextGeneration.Completion](https://aistudio.yandex.ru/docs/en/ai-studio/text-generation/api-ref/TextGeneration/completion.html) и [Authentication](https://aistudio.yandex.ru/docs/en/search-api/api-ref/authentication.html).

| Переменная | Обязательность | По умолчанию |
|------------|----------------|--------------|
| `LLM_PROVIDER` | нет | `openrouter` |
| `OPENROUTER_API_KEY` | да | — |
| `OPENROUTER_MODEL` | нет | `openai/gpt-4o-mini` |
| `OPENROUTER_MAX_TOKENS` | нет | `8192` |
| `OPENROUTER_TIMEOUT_SEC` | нет | `180` — таймаут одного HTTP-запроса к LLM |
| `OPENROUTER_ANNOTATE_BUDGET_SEC` | нет | `600` — суммарный лимит времени на все батчи разметки в одном `/digest` |
| `OPENROUTER_DIGEST_BATCH_SIZE` | нет | `8` — постов за один запрос разметки |
| `OPENROUTER_DIGEST_TEXT_CHARS` | нет | `1600` — обрезка текста поста на входе в LLM |
| `OPENROUTER_DIGEST_MAX_ITEMS` | нет | `120` — максимум кандидатов с LLM-разметкой |
| `YANDEX_API_KEY` | да (для `LLM_PROVIDER=yandex`) | — |
| `YANDEX_FOLDER_ID` | да (для `LLM_PROVIDER=yandex`) | — |
| `YANDEX_MODEL` | нет (для `LLM_PROVIDER=yandex`) | `yandexgpt/latest` |

Опционально для политики OpenRouter: **`OPENROUTER_HTTP_REFERER`**, **`OPENROUTER_APP_TITLE`** (если не заданы, подставляются нейтральные значения по умолчанию).

Список моделей: [openrouter.ai/models](https://openrouter.ai/models).

Параметры стабильности Telegram (прокси, connect, RPC и т.д.) — см. прежние пункты в `.env` / коде (`TG_*`, `RUN_ONCE_BUDGET_SEC`, `COLLECT_MAX_MESSAGES_PER_CHANNEL`).

Параметры базы и дедупликации:

| Переменная | Обязательность | По умолчанию |
|------------|----------------|--------------|
| `DEDUPE_TEXT_MAX_CHARS` | нет | `6000` — сколько символов учитывать при SHA-256 для дедупа |
| `LIST_ENTRIES_LIMIT` | нет | `10` — сколько записей выводить в `/list` |

## 2) Режимы запуска

### Daemon (основной режим)

```powershell
export PYTHONPATH=src
python -m teleflow --daemon
```

Что делает:

- держит userbot в ожидании;
- принимает команды в ЛС (`/digest`, `/stats`, `/list`, `/rm`, `/mv`, `/undo`, `/write`);
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
5. Выполнить `/write ai-агенты для бизнеса`.
6. Получить сгенерированный пост в ЛС.

## 5) Smoke-чеклист

- [ ] `/digest` от whitelist-пользователя возвращает дайджест в ЛС.
- [ ] Длинный дайджест приходит целиком (chunked отправка, без ошибки длины Telegram).
- [ ] Forward текстового поста вызывает запрос темы.
- [ ] Валидная тема сохраняет `entry_*.json` в `data/knowledge/<тема>/`.
- [ ] Невалидная тема не сохраняется, бот повторно просит выбрать тему.
- [ ] `/write <тема поста>` ищет релевантные записи по всей базе.
- [ ] `/write <тема поста> --theme=<тема базы>` ограничивает поиск выбранной темой базы.
- [ ] `/list <тема>` показывает последние записи с id.
- [ ] `/rm <id>` удаляет нужный файл.
- [ ] `/mv <id> <тема>` переносит запись между папками тем.
- [ ] `/undo` отменяет последнее сохранение.
- [ ] `/write` при пустой теме корректно подсказывает формат команды.
- [ ] `/write` при отсутствии релевантных материалов отвечает, что контекста недостаточно.
- [ ] Сообщения от не-whitelist пользователя игнорируются.

## 6) Troubleshooting

- Если `--once` завершается по таймауту бюджета:
  - проверьте MTProxy и `TG_PROXY_*`;
  - уменьшите `SOURCE_FOLDER_NAMES` / `COLLECT_MAX_MESSAGES_PER_CHANNEL`;
  - для OpenRouter увеличьте `OPENROUTER_TIMEOUT_SEC` или `OPENROUTER_ANNOTATE_BUDGET_SEC`, уменьшите `OPENROUTER_DIGEST_BATCH_SIZE`.
- Если OpenRouter вернул ошибку — смотрите HTTP-код и тело в логе; проверьте баланс и id модели.
- **`PeerFloodError` / лимит Telegram** при preview в ЛС: подождите или включите отправку в канал (`DRY_RUN=false`); между частями длинного текста бот делает паузу, но лимит всё равно может сработать.
- Если `/write` дал короткий fallback — OpenRouter не вернул текст (сеть, лимиты, модель).
- Если `/write` сообщает "Недостаточно контекста" — в базе нет релевантных записей под тему поста; переформулируйте тему или добавьте материалы.
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
