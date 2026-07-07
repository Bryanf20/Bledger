# Bledger frontend

React + Vite frontend for Bledger. This session covers the initial
scaffold plus the Login/PIN screen; everything else (`pos/`,
`inventory/`, `sales/`, `suppliers/`, `dashboard/`, the real
`setup/` wizard) is a placeholder or not yet started.

## Running it

```bash
npm install
npm run dev
```

The Vite dev server proxies `/api/*` to `http://localhost:8000`
(see `vite.config.js`), so run the Django backend on port 8000
alongside this. In production, Django serves the built `dist/`
files directly and `VITE_API_URL` stays empty (same-origin).

## What's here

- `src/api/client.js` — axios instance. Adds `Authorization: Token
  <key>` from `localStorage` on every request; on a 401, clears the
  token and dispatches a `bledger:unauthorized` window event.
- `src/api/auth.js`, `src/api/errors.js` — auth endpoint wrappers and
  a DRF-error-shape-to-string helper.
- `src/context/AuthContext.jsx` — session state: restore-on-load via
  `GET /auth/me/`, `login()`, `pinLogin()`, `logout()`.
- `src/components/RoleGuard.jsx`, `XAFAmount.jsx` — shared components
  per the project structure doc.
- `src/features/auth/` — `LoginScreen.jsx` (role selector + PIN
  keypad or password form) and `PINKeypad.jsx`, matching
  `06_login.html`.
- `src/features/setup/SetupPlaceholder.jsx`,
  `src/features/HomePlaceholder.jsx` — deliberate stubs so the router
  has somewhere to land; not the real setup wizard or POS/dashboard.
- `src/styles/tokens.css` — design tokens ported verbatim from the
  project's `_base.css`, plus the Tailwind entry point.

## Known gaps / open items (carried to next session)

- **Branch name isn't shown pre-login.** The login mockup shows
  "Buea Main Branch · Standalone mode" under the title, but no
  `AllowAny` endpoint exposes branch info before authentication —
  `UserProfileSerializer.branch` only comes back *after* login. Left
  as a generic "Standalone mode" subtitle. Worth deciding: add a
  public branch-name field to `/setup/status/`, or drop the branch
  name from the pre-login screen.
- **Setup wizard is a placeholder route only** (`/setup`) — the real
  three-step wizard (`07_setup_wizard.html`) is a separate session.
- **No screen exists to route to after login yet** — `HomePlaceholder`
  just proves the auth flow end-to-end and shows a sign-out button.
- Verified with `npm run build` (clean) and `npx oxlint src` (0
  errors, 2 harmless fast-refresh warnings on files that export a
  helper alongside a component) — not yet run against a live Django
  backend in this sandbox, since the sandbox has no Django install.
  Endpoint contracts were taken directly from
  `apps/auth_users/views.py` / `serializers.py` in project knowledge,
  not assumed from the design doc.
