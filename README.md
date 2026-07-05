# AISafetyBenchExplorer Web -- Phase 1 & 2

Admin CRUD web application for the AISafetyBenchExplorer AI safety
benchmark catalogue. Contains Phase 1 (PostgreSQL schema, FastAPI
backend, JWT auth) and Phase 2 (complexity auto-classifier, audit
logging, controlled-vocabulary API, Excel export, Next.js admin
frontend).

## Prerequisites

- Python 3.11 or newer
- Node.js 18 or newer (20 recommended) and npm
- PostgreSQL 15 or newer (or Docker)
- git

## Option A: Run with Docker (fastest)

    docker compose up --build

Then skip to "Load the schema" below (run against the containerized
Postgres on localhost:5432), and open http://localhost:3000 once
migrations are applied.

## Option B: Run natively

### 1. Unzip and enter the project

    unzip aisafetybenchexplorer-web.zip
    cd aisafetybenchexplorer-web

### 2. Set up PostgreSQL

    # macOS (Homebrew)
    brew install postgresql@15
    brew services start postgresql@15

    # Ubuntu/Debian
    sudo apt update && sudo apt install postgresql postgresql-contrib
    sudo service postgresql start

Create the database:

    createdb aisafetybenchexplorer
    # or:
    psql -U postgres -c "CREATE DATABASE aisafetybenchexplorer;"

### 3. Load the schema

    psql -U postgres -d aisafetybenchexplorer -f backend/app/db/schema.sql

Verify: psql -U postgres -d aisafetybenchexplorer -c "\dt"
Expected 8 tables: users, benchmarks, eval_metrics, use_cases,
benchmark_use_cases, repo_stats, extraction_jobs, audit_log.

### 4. Set up the backend

    cd backend
    python -m venv venv
    source venv/bin/activate        # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    cp .env.example .env

Edit .env: set DATABASE_URL to match your Postgres user/password, and
set SECRET_KEY to any long random string.
For example to get a secret key, run this in your terminal and copy and paste the ransom key:
    
    echo "SECRET_KEY=$(openssl rand -hex 32)" >> backend/.env

Start the API:

    uvicorn app.main:app --reload

Check http://localhost:8000/health -- expect
{"status":"ok","environment":"development"}.

Interactive docs: http://localhost:8000/docs

### 5. Create your first admin user

    curl -X POST http://localhost:8000/auth/register \
      -H "Content-Type: application/json" \
      -d '{"email":"admin@example.com","password":"YourPassword123!","role":"researcher"}'

Promote to admin:

    psql -U postgres -d aisafetybenchexplorer -c \
      "UPDATE users SET role = 'admin' WHERE email = 'admin@example.com';"

### 6. Set up the frontend

In a new terminal (keep the backend running):

    cd frontend
    npm install
    cp .env.local.example .env.local
    npm run dev

Open http://localhost:3000, you will land on the login page. Sign in
with the admin account from step 5.

## What to test once it's running

- Log in and confirm you land on the Benchmarks list page
- Click "+ New Benchmark", check some Task Type boxes, tick complexity
  signal checkboxes, click "Run Complexity Classifier", confirm it
  fills in a level and justification, then save
- Confirm the new benchmark appears with a colored complexity badge
- Edit an existing benchmark, change a field, save, confirm it persists
- Click "Export to Excel" and confirm a .xlsx file downloads
- Visit /admin/audit-log and confirm create/update actions are logged
- Delete a benchmark and confirm it disappears from the list

## Project Structure

    backend/
      app/
        core/       config, security, JWT deps, complexity_classifier, audit, controlled_vocab
        db/         schema.sql, SQLAlchemy session
        models/     SQLAlchemy ORM models
        routers/    auth, benchmarks, metrics, complexity, audit, export, vocab
        schemas/    Pydantic v2 request/response contracts
      alembic/       migration environment
      tests/         pytest suite
    frontend/
      app/            login, admin/benchmarks, admin/audit-log pages
      components/     BenchmarkForm, ComplexityBadge
      lib/api.ts      typed API client
    pipeline/         placeholder for the existing GitHub repo (Phase 3)
    scripts/
      migrate_excel_to_db.py    one-time workbook import
    docker-compose.yml

## Running the backend test suite

    cd backend
    pytest

## Troubleshooting

- bcrypt warning: harmless, already pinned to bcrypt==4.0.1.
- "role postgres does not exist": substitute your OS username.
- CORS errors: confirm CORS_ORIGINS in backend/.env includes
  http://localhost:3000.
- 401 on admin actions: token expired (24h default), or user not yet
  promoted to admin -- re-run the UPDATE users command from step 5.

## Known Limitation

This codebase has been verified via static syntax checks (py_compile
across all Python files, JSON validation of frontend configs) but has
not been re-verified with a live end-to-end run in the current session
due to repeated sandbox environment resets. Please report any issues
hit during local setup.
