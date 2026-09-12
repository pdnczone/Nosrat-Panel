# Nosrat Frontend Changelog

Rebrand + redesign of the panel frontend from "Smite" to **Nosrat**, plus a
new Node Management area. This document is the section-23 deliverable:
what changed, what's new, what still needs backend work, bugs found in the
original project, and how to run everything.

## 1. Rebrand

- All "Smite" branding replaced: page title, favicon, sidebar, header,
  login page, `package.json` name, and every UI string in both English and
  Farsi translation tables.
- The old `SmiteL.png` / `SmiteD.png` raster logos were removed. The new
  mark is an inline icon (`lucide-react`'s `Waypoints`) inside a brand
  gradient badge (`.brand-mark`), so it scales cleanly, needs no binary
  asset, and adapts automatically to dark/light mode.
- Added `LICENSE` and `NOTICE.md`: the original project (Smite, by zZedix)
  is MIT-licensed, which permits this kind of rebrand/redistribution as
  long as the license text is preserved — it now lives in the repo even
  though the live UI shows only Nosrat branding.

## 2. Design system ("liquid glass")

- `tailwind.config.js` and `src/index.css` rewritten around CSS variables:
  glass surfaces (`--glass-surface`, blur + saturation), a brand gradient
  (teal → indigo), full light/dark token sets, and new radii/shadow/animation
  scales.
- New reusable component library in `src/components/ui/`: `Card`, `Button`,
  `Badge`, `StatusDot`, `Modal`, `Drawer`, `ConfirmDialog`, `Tabs`,
  `ProgressSteps`, `SecretField` (password/key show-hide, never logs its
  value), `Toast`, and `EmptyState` / `ErrorState` / `Skeleton` for
  consistent loading/empty/error states everywhere.
- Fully redesigned pages: **Login**, **Layout** (sidebar/header/mobile nav),
  **Dashboard**, **Nodes**, **Servers**.
- Remaining pages (**Tunnels**, **Logs**, **CoreHealth**, **Settings**)
  received a scripted, systematic token pass — every hard-coded
  gray/blue/green/red Tailwind combination was mapped onto the new design
  tokens (`text-foreground`, `text-muted-foreground`, `btn-primary`,
  `field-input`, `glass-panel`, semantic `success`/`warning`/`destructive`
  colors, etc.) so the whole app reads as one system. Their internal logic
  was not rewritten — these pages are large and functionally dense (Tunnels
  alone is ~2,300 lines across five tunnel core types), so this was a
  visual-consistency pass rather than a full bespoke redesign. If you want
  Tunnels redesigned to the same depth as Nodes/Dashboard (e.g. the
  multi-core forms restructured, not just re-themed), that's a good next
  chunk of work.
- Dark mode is the default and primary experience; light mode is fully
  themed via the same CSS variables (no hard-coded colors).

## 3. Node Management (new)

- **Nodes** (Iran) and **Servers** (Foreign) pages redesigned as a glass
  card grid with live status dots (🟢 online / 🟡 connecting / 🔴 offline /
  ⚪ unknown), search-free but filter-ready structure, skeleton loading,
  and proper empty/error states.
- **Add Node** is now a two-path menu:
  - **Register via CA Certificate** — the existing, working flow (node
    self-installs and registers using the panel's CA), reskinned.
  - **Add Node via SSH** — a new 7-step wizard (Server Info → SSH Auth →
    Connection Test → Install → Progress → Verify → Completed), matching
    the flow requested in the spec. It calls real endpoints
    (`/nodes/ssh/test-connection`, `/nodes/ssh/install`, install-progress
    WebSocket with polling fallback) documented in
    `NOSRAT_BACKEND_CONTRACT.md`. **These endpoints don't exist on the
    backend yet**, so right now the wizard will genuinely fail at the
    Connection Test step with a real error — this is intentional per the
    "do not fake backend features" requirement, not a bug. Once the backend
    implements the contract, the wizard works with no frontend changes.
- **Node Details** is now a drawer with Overview / Resources / Tunnel /
  Logs / Actions tabs. Actions (Test Connection, Restart, Update,
  Reinstall, Remove) call real endpoints; Remove has a proper confirmation
  dialog. Resources/Tunnel/Logs show a clear "requires agent support" hint
  (with the exact endpoint needed) instead of fabricated numbers, because
  the current API doesn't report per-node CPU/RAM/disk/logs yet.

## 4. Architecture

New folders, split out of the previously page-only structure:
- `src/types/node.ts` — shared node types, plus `mapApiNodeToView` to keep
  the raw API shape separate from what components render.
- `src/services/nodesApi.ts` — all node-related HTTP calls in one place
  (existing + documented-but-unimplemented SSH ones), instead of inline
  `axios`/`api` calls scattered through components.
- `src/hooks/useNodes.ts` — data loading + 10s refresh for a node list.
- `src/components/ui/` — the shared design system components listed above.
- `src/components/nodes/` — `AddNodeSSHWizard`, `NodeDetailsDrawer`.

Existing routes, pages, auth flow, and API calls not mentioned above were
left untouched functionally.

## 5. Bugs found in the original project (fixed during QA)

These were pre-existing TypeScript errors in the original codebase,
unrelated to the rebrand, that blocked a clean `tsc`/production build:

- `Tunnel` interface was missing `iran_node_id` / `foreign_node_id`, which
  were already used at runtime in `Tunnels.tsx`.
- The tunnel edit form's local state was missing `rathole_local_port`,
  referenced by the Rathole "Local Port" field.
- `BackhaulAdvancedServerState` was missing `sniffer_log`, used by the
  Backhaul advanced-settings form.
- `Settings.tsx` referenced `t.settings.tunnelAutoReapply` and three related
  keys that existed in the translation *data* but not in the `Translations`
  *type*, so the settings page's tunnel-auto-reapply section was relying on
  runtime fallback strings (`t.settings.x || 'fallback'`) instead of real
  localization.
- Two generic `Object.entries(...).forEach` blocks writing into
  `BackhaulAdvancedServerState`/`ClientState` via a computed key hit a
  TypeScript inference limit (`Type 'boolean' is not assignable to type
  'never'`) — fixed with a narrow, contained cast rather than loosening the
  surrounding types.

All of the above are now fixed; `npx tsc --noEmit` and `npm run build` both
complete cleanly.

## 6. Still needs backend work

Everything under "SSH remote install (contract)" in
`NOSRAT_BACKEND_CONTRACT.md`:
- `POST /nodes/ssh/test-connection`
- `POST /nodes/ssh/install` + install-progress stream/poll endpoint
- `POST /nodes/:id/test-connection` (for already-registered nodes)
- `GET /nodes/:id/logs`
- Per-node resource reporting (CPU/RAM/disk/uptime/OS/version) on the
  existing `GET /nodes` (or a new `GET /nodes/:id/status`)

None of these are faked in the frontend — the relevant UI sections show a
clear "requires agent support" / real error state until they exist.

## 7. Running it

```bash
# install
npm install

# development
npm run dev

# type-check
npx tsc --noEmit -p .

# production build
npm run build
```

Build output goes to `dist/`; no external services are required to install,
type-check, or build the frontend itself (only to actually use the SSH
node-install flow, once the backend contract is implemented).
