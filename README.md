# Lotus University Management System

Django application with a vanilla JavaScript frontend and MySQL database.

## Run locally

1. Create a virtual environment and install dependencies:

   ```powershell
   py -m venv venv
   .\venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and set the local MySQL connection values and a development secret.
3. Start the app:

   ```powershell
   .\venv\Scripts\python.exe manage.py runserver
   ```

Open `http://127.0.0.1:8000`. The sample login data in the SQL seed file is for local development only; set new passwords before deploying real data.

## Database setup

For a new, empty local database, run `01_schema.sql`, then `02_seed_data.sql`, then `03_alter_and_fill.sql` in that order. **The first script drops and recreates `lotus_university`; do not run it on a database containing data you need to keep.**

For an existing database, only apply the migration steps that have not already been applied. The current application expects the additions in `03_alter_and_fill.sql`.

## Deploy to Vercel

Vercel detects Django from `manage.py`. Import the repository in Vercel and set the following project environment variables for Preview and Production:

- `DJANGO_SECRET_KEY`: a new, randomly generated secret
- `DJANGO_DEBUG`: `false`
- `DJANGO_ALLOWED_HOSTS`: `.vercel.app` and any custom domain hostnames, comma-separated
- `DJANGO_CSRF_TRUSTED_ORIGINS`: full `https://` origins for the Vercel and custom domains, comma-separated
- `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT`: connection details for a hosted MySQL database

The database must accept connections from the deployed application. `localhost` refers to the Vercel function, not your computer. Import the schema and data into the hosted database before serving traffic. Never commit `.env` or use the sample account passwords in production. Django reads local `.env` values for development; Vercel supplies its environment variables at runtime.

After the hosted database is configured, run `python manage.py migrate` once against it to create Django's built-in auth and session tables. Do this before enabling login.

The API, frontend and static assets are served by the same Django origin. API requests use `/api/...`.
