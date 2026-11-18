# Lotus University Administration System

University administration app with separate Admin, Teacher and Student workspaces. It uses the existing HTML/CSS/vanilla JavaScript frontend, a Python standard-library web server and SQLite persistence. There are no package installs or build step.

## Run locally

1. Install Python 3.10 or newer.
2. Open PowerShell in this project folder.
3. Run `python server.py`.
4. Open [http://127.0.0.1:8000](http://127.0.0.1:8000).
5. On first launch, create the initial Admin account. Use a strong password with at least 12 characters.

The database is created at `data/lotus_ums.sqlite3` and is seeded with sample university records. It contains no preconfigured accounts or shared passwords. After signing in as Admin, open **Accounts** to create Teacher and Student logins. Link an account to an existing profile by using the same university ID, or let the account form create a profile. Add course registrations under **Enrollments**.

## Workspaces

| Role | Main access |
|---|---|
| Admin | All modules: accounts, students, teachers, departments, courses, enrollments, attendance, results, schedule, notices, complaints and reports. Admin can create and maintain records. |
| Teacher | Read the full student directory and academic records. Record or update attendance/results only for students enrolled in assigned courses. See assigned courses, schedules and reports. |
| Student | Read only their own profile, enrolled courses, section schedule, attendance, results and complaints. Submit their own complaints and read student notices. |

The backend applies role and record checks to each API request. Student record IDs and teacher course assignments are resolved from the signed-in session.

## Features

- First-admin setup, university ID/email login, logout and server-managed sessions.
- Passwords hashed with PBKDF2; sign-in attempts are rate-limited.
- SQLite storage for users, profiles, departments, courses, enrollments, schedules, attendance, grades, notices and complaints.
- Admin account creation, profile linking and password reset.
- Searchable student and teacher directories, course and department management, enrollment management and schedule editing.
- Attendance and grade entry with course enrollment checks and server-side grade calculation.
- Audience-filtered notices, student-owned complaints, reports and CSV export.
- Responsive layouts, mobile navigation, input validation and explicit empty/error states.
- Animated page transitions and hover feedback, with reduced-motion support.

## Configuration and deployment

The server binds to `127.0.0.1:8000` by default. Set `UMS_HOST` and `UMS_PORT` to change the listener; set `UMS_DB_PATH` to change the database path. Set `UMS_ALLOW_INITIAL_SETUP=0` after provisioning the first Admin. For HTTPS behind a trusted reverse proxy, set `UMS_COOKIE_SECURE=1`.

This built-in server is intended for local development. Before public deployment, put the app behind a production WSGI server and TLS reverse proxy, disable first-admin setup after provisioning, configure backups, and add an email-based password recovery flow. Never use the sample academic records as real student data.

See [`BACKEND_HANDOFF.md`](BACKEND_HANDOFF.md) for the API and permission model.
