# Презентация TeleFlow (статический сайт)

Папка: **HTML + CSS + JS**. На **титульном слайде** справа подгружается только Spline-сцена из `spline-app/spline-only.html` (лёгкий iframe; полное React-демо по-прежнему в `spline-app/index.html`).

## Сборка 3D-слайда (один раз и после правок React)

Из корня репозитория `assist-final-project`:

```powershell
cd presentation-react
npm install
npm run build
```

Артефакты попадут в `presentation/spline-app/`. Без этой папки iframe на слайде «3D» будет пустым.

## Как открыть

- Дважды кликнуть по `index.html` в проводнике, **или**
- Локальный сервер (если нужны шрифты Google без предупреждений CORS в некоторых браузерах):

```powershell
cd presentation
python -m http.server 8765
```

Откройте в браузере: `http://127.0.0.1:8765/`

## GitHub Pages (деплой)

Нужно один раз настроить репозиторий и закоммитить файлы презентации (включая `spline-app/`, если нужен iframe со Spline — см. раздел «Сборка 3D-слайда»).

1. **Закоммитьте** папку `assist-final-project/presentation/` (и при необходимости соберите `spline-app` перед пушем).
2. В GitHub: **Settings → Pages → Build and deployment**.
3. В **Source** выберите **GitHub Actions** (не «Deploy from a branch»).
4. Запушьте в ветку **`main`** или **`master`** (или вручную запустите workflow **Deploy TeleFlow presentation** на вкладке Actions).

После зелёного job страница будет по адресу вида **`https://<ваш-логин>.github.io/<имя-репозитория>/`** (корень сайта = содержимое `presentation/`, откроется `index.html`).

Если репозиторий **приватный**, бесплатный Pages для организаций ограничен; для личного аккаунта приватный репо тоже может требовать платный план — тогда либо публичный репо, либо деплой на Netlify/Vercel.

### Без Actions (только ветка)

Альтернатива: в **Pages → Source** указать ветку **`main`** и папку **`/docs`**, а содержимое `presentation/` скопировать в `docs/` (или сделать `docs` submodule/symlink — на Windows проще копирование или отдельный скрипт). Тогда workflow не нужен.

## Управление

- **Прокрутка** колёсиком / тачпадом — секции прилипают по высоте экрана (`scroll-snap`).
- **Стрелки** ↑ ↓, **Page Up / Down**, **Home / End** — переход между слайдами.
- **Точки слева** (на мобильных — снизу) — переход к разделу.

## Что править под себя

- Тексты в `index.html` (блоки с классом `placeholder-block` — время на проект и выводы с курса).
- Цвета и шрифты — в `:root` в `style.css`.
