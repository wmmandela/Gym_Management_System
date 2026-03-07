# GetFit (Django + PostgreSQL)

GetFit is a Django fitness coaching app with multiple dashboard experiences:
- Individual
- Personal Trainer
- Hybrid

It includes onboarding, trainer selection, timetable planning, meal timetable planning, workout sessions, and progress tracking.

## Tech Stack
- Python 3.12+ (project currently runs with Python 3.14 in local venv)
- Django 6.0.1
- PostgreSQL (required)
- psycopg2-binary
- Optional deployment on Vercel

## Project Structure
- `gym_project/` Django project settings and URLs
- `gym/` app logic (views, models, migrations)
- `templates/` HTML templates
- `static/` CSS and static assets
- `api/index.py` Vercel Python entrypoint
- `vercel.json` Vercel routing/build config

## 1. Clone and Open in IDE
```bash
git clone <your-repo-url>
cd gym_project
```

Open the folder in VS Code (or your preferred IDE).

## 2. Create and Activate Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

On Windows (PowerShell):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

## 3. Install Dependencies
```bash
pip install -r requirements.txt
```

## 4. PostgreSQL Setup (Required)
This app is configured for PostgreSQL only.

### Option A: Use a PostgreSQL URL (recommended)
Set one of:
- `POSTGRES_URL`
- `DATABASE_URL`

Format:
```bash
postgresql://USER:PASSWORD@HOST:5432/DB_NAME?sslmode=require
```

### Option B: Use discrete environment variables
Set:
- `POSTGRES_DB` (or `POSTGRES_DATABASE`)
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

### Example local `.env` values
```bash
SECRET_KEY=replace-me
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
POSTGRES_DB=gym_project
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

You can export vars in terminal or use your IDE run configuration.

## 5. Run Migrations
```bash
python manage.py migrate
```

## 6. Create Admin User (optional but recommended)
```bash
python manage.py createsuperuser
```

## 7. Start Development Server
```bash
python manage.py runserver
```

App URLs:
- Home: `http://127.0.0.1:8000/`
- Admin: `http://127.0.0.1:8000/admin/`

## Core App Flows
1. Sign up
2. Complete onboarding (includes plan selection: Basic / Pro / Elite)
3. Choose trainer where required
4. Build timetable
5. Use dashboard, workout flow, and meal timetable planner

## Meal Plan / Timetable
- Route: `/dashboard/meal-timetable/`
- Persisted in `MealTimetablePlan`
- Meal plan panels are visible across dashboard variants in variant-appropriate sections.

## Progress Tracking
Workout session events are tracked via:
- `start`
- `complete`

Used for dashboard metrics and progress cards.

## Optional: Deploy on Vercel
Vercel config is already included.

### Prerequisites
- Vercel account
- `vercel` CLI installed

```bash
npm i -g vercel
vercel login
```

### Set production environment variables
At minimum:
- `SECRET_KEY`
- `DEBUG=False`
- `ALLOWED_HOSTS=.vercel.app,<your-domain>`
- `CSRF_TRUSTED_ORIGINS=https://<your-domain>`
- `POSTGRES_URL` (recommended) or full `POSTGRES_*` set

You can use `.env.vercel.example` as reference.

### Deploy
```bash
vercel --prod
```

Or use helper script:
```bash
./scripts/deploy_vercel.sh
```

## Production Checklist
- Confirm DB connectivity
- Run migrations against production DB
- Confirm static files load (`/static/css/style.css` returns 200)
- Verify sign up / sign in works
- Verify onboarding + dashboard rendering

## Troubleshooting
### "Service is temporarily unavailable" during signup/signin
Usually means DB query failed.
1. Verify `POSTGRES_URL` / `DATABASE_URL`
2. Ensure DB is reachable from runtime
3. Run migrations on the target DB

### Missing tables (e.g., `auth_user does not exist`)
Run:
```bash
python manage.py migrate
```
against the same database used by the app.

### CSS/UI not loading on deployment
Ensure Vercel routes and static build config are present in `vercel.json`.

## Contributor Notes
- Avoid committing secrets or real DB credentials.
- Keep migrations committed with model changes.
- Run `python manage.py check` before push.
