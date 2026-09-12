# Nosrat — Modern Tunnel & Node Management Platform

Nosrat is the frontend for a self-hosted tunnel/server management panel,
rebranded and redesigned from the open-source [Smite](https://github.com/zZedix/Smite)
project (see `NOTICE.md` and `LICENSE`).

- **Design:** a "liquid glass" design system (glassmorphism, dark mode by
  default, full light mode) — see `NOSRAT_FRONTEND_CHANGELOG.md` for the
  full list of what changed and why.
- **Node Management:** manage Iran and foreign nodes from one place, either
  by registering a self-installing node via CA certificate (works today) or
  through a guided SSH install wizard (frontend + API contract ready; needs
  backend support — see `NOSRAT_BACKEND_CONTRACT.md`).
- **Persian & English**, RTL/LTR aware, throughout.

## Requirements

- Node.js 18+
- A running Nosrat/Smite-compatible backend (see the backend repository for
  setup; this repo is frontend-only)

## Install

```bash
npm install
```

## Development

```bash
npm run dev
```

By default the dev server proxies API calls to the backend — check
`vite.config.ts` if you need to point it at a different host.

## Type-check

```bash
npx tsc --noEmit -p .
```

## Production build

```bash
npm run build
```

Output is written to `dist/`; serve it with any static file server or
behind the same reverse proxy as the backend API.

## More detail

- `NOSRAT_FRONTEND_CHANGELOG.md` — everything that changed in this redesign,
  bugs found and fixed in the original project, and what still needs
  backend work.
- `NOSRAT_BACKEND_CONTRACT.md` — the full API contract the frontend expects,
  split into "already implemented" and "new, documented but not yet built."
