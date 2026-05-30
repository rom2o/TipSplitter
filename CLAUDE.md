# TipSplitter — Project Context

## What this is
Single-restaurant tip splitting PWA. Julien uses it to split daily card/cash tips across staff by shift at his restaurant. Deployed on Railway, auto-deploys from GitHub (rom2o/TipSplitter).

## Stack
- Backend: Python/Flask, SQLAlchemy (SQLite locally, Postgres on Railway via DATABASE_URL env var)
- Frontend: Vanilla HTML/CSS/JS — single file at templates/index.html (~1100 lines)
- Deployment: Railway connected to GitHub main branch

## Key config (Railway env vars)
- `APP_PIN` — the login PIN (default 1234 if not set)
- `SECRET_KEY` — Flask session secret
- `DATABASE_URL` — set automatically by Railway Postgres plugin

## Architecture
- `app.py` — all backend logic (~530 lines): models, auth, shift API, CSV import/export
- `templates/index.html` — entire frontend: tabs (Week, Summary, History, Staff, Import)
- `tips.db` — local SQLite dev db (not committed)

## Data model
- `Staff` — name, active flag
- `Shift` — week_start (YYYY-MM-DD, always a Monday), day (0=Mon…6=Sun), shift_type (lunch/dinner), cash_tips, card_tips
- `ShiftStaff` — many-to-many: which staff worked which shift
- `DayNote` — optional note per day

## Business logic
- Card tips are reduced by 30% before splitting (CARD_DEDUCTION = 0.30, hardcoded in app.py)
- Lunch = transactions before 17:00, Dinner = 17:00 and after
- Weeks run Monday–Sunday
- CSV import: auto-detects tip column, date/time column, payment type column from Square POS exports

## What's done
- PIN auth
- Staff management
- Weekly tip entry (cash + card per shift, staff selection)
- CSV import from Square POS
- Summary, history, CSV export
- PWA (installable on iPhone)
- Timezone fix (all dates use local time, not UTC)

## Backlog (no priority set)
- [ ] Configurable card deduction % in UI (currently hardcoded 30%)
- [ ] Edit shift after saving (currently must delete and re-enter)
- [ ] Change PIN from within the app (currently requires Railway env var change)
- [ ] Confirm before deleting a day
- [ ] Staff reordering

## Potential future (not decided)
- Multi-tenant (multiple restaurants, accounts, login)
- Logo upload per restaurant
- App store native wrapper (Capacitor)
- Billing/subscriptions
