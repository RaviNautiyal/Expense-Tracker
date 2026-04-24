# Spendly

Spendly is a Flask-based expense tracker for logging daily spending, reviewing category-wise summaries, and managing expenses through a clean dashboard.

## Current Features

- User registration with password hashing
- Login and logout with session-based authentication
- Protected dashboard for signed-in users
- Add, edit, filter, search, import, export, and delete expenses
- Add, edit, filter, and delete income records
- Database-backed category management
- Monthly category budgets with alert states
- Dashboard analytics for category breakdown and six-month income vs expense trends
- Yearly financial report page with monthly income, expense, and net totals
- Downloadable PDF financial reports
- JSON backup and restore for user financial data
- Admin dashboard for role management and category administration
- Profile editing and password change
- SQLite-backed persistence with demo seed data
- Responsive landing, auth, legal, and dashboard pages
- Environment-driven app configuration
- Automated tests for auth, budgets, CSV, income, profile, reports, admin, and expense CRUD flows

## Tech Stack

- Python
- Flask
- SQLite
- Jinja2 templates
- Plain CSS and JavaScript
- Pytest

## Environment Variables

Copy `.env.example` into your local environment setup and provide values through PowerShell, your IDE, or your deployment platform.

- `SPENDLY_SECRET_KEY`
- `SPENDLY_DATABASE_PATH`
- `SPENDLY_PORT`
- `SPENDLY_DEBUG`
- `SPENDLY_MAX_CONTENT_LENGTH`
- `SPENDLY_SESSION_COOKIE_SECURE`
- `SPENDLY_BUDGET_ALERT_THRESHOLD`
- `SPENDLY_CSV_MAX_IMPORT_ROWS`
- `SPENDLY_DEMO_EMAIL`
- `SPENDLY_DEMO_PASSWORD`
- `SPENDLY_ADMIN_EMAIL`
- `SPENDLY_ADMIN_PASSWORD`

## Run Locally

1. Create and activate a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Set the required environment variables. In PowerShell, for example:

```powershell
$env:SPENDLY_SECRET_KEY="replace-with-a-random-secret"
$env:SPENDLY_DATABASE_PATH="D:\games\expense-tracker\expense-tracker\expense_tracker.db"
$env:SPENDLY_PORT="5001"
$env:SPENDLY_DEBUG="true"
```

4. Start the app with `flask --app app run --port $env:SPENDLY_PORT`.
5. Open `http://127.0.0.1:5001`.

## Deployment

This repo now includes:

- [wsgi.py](D:\games\expense-tracker\expense-tracker\wsgi.py:1) for Gunicorn
- [Procfile](D:\games\expense-tracker\expense-tracker\Procfile:1) for simple platform deploys
- [render.yaml](D:\games\expense-tracker\expense-tracker\render.yaml:1) for Render

Useful production defaults:

- set `SPENDLY_DEBUG=false`
- set `SPENDLY_SESSION_COOKIE_SECURE=true`
- use a non-dev `SPENDLY_SECRET_KEY`
- point `SPENDLY_DATABASE_PATH` at persistent storage

## Demo Account

- Email: `SPENDLY_DEMO_EMAIL` value
- Password: `SPENDLY_DEMO_PASSWORD` value

## Admin Account

- Email: `SPENDLY_ADMIN_EMAIL` value
- Password: `SPENDLY_ADMIN_PASSWORD` value

## Resume-Worthy Next Steps

- Deploy on Render or Railway and add screenshots
- Add recurring expenses and reminders
- Add richer analytics like year-over-year and budget history
- Add database migrations and backup/restore workflows
