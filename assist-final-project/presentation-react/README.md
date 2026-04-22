# TeleFlow Presentation (React + shadcn-style)

Эта папка содержит React-версию презентации с TypeScript, Tailwind и shadcn-совместимой структурой:

- `src/components/ui/splite.tsx`
- `src/components/ui/demo.tsx`
- `src/components/ui/spotlight.tsx` (вариант ibelick)
- `src/components/ui/card.tsx`
- `src/lib/utils.ts`
- `components.json`

## Запуск

```bash
npm install
npm run dev
```

## Сборка

Сборка по умолчанию пишет статику в **`../presentation/spline-app/`** (встраивается в основную презентацию `presentation/index.html`).

```bash
npm run build
npm run preview
```

Локально проверить только React-страницу после сборки можно, открыв `presentation/spline-app/index.html` через тот же HTTP-сервер из папки `presentation`.

## Можно ли захостить на GitHub Pages?

Да. Для Vite это обычный static build.

1) В `vite.config.ts` задайте `base` под имя репозитория, например:

```ts
export default defineConfig({
  base: '/YOUR_REPO_NAME/',
  plugins: [react()],
})
```

2) Соберите проект:

```bash
npm run build
```

3) Залейте содержимое папки `dist` в ветку `gh-pages` (или настройте GitHub Action).

Если нужен, могу добавить готовый GitHub Action workflow для автодеплоя Pages.
