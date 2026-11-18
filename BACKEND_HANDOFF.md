# Backend and access model

The application now runs as a same-origin Python HTTP server with SQLite persistence. `server.py` owns authentication, session management, validation and role checks. `js/api.js` is the browser service layer; `js/data.js` contains empty workspace arrays, not university records.

## Roles

| Role | Server access | OLA
|---|---|
| `ADMIN` | All accounts, student/teacher profiles, departments, courses, enrollments, schedules, attendance, results, notices, complaints and reports. |
| `TEACHER` | Read all student profiles and academic records. Read assigned courses, enrollments and schedules. Create/update attendance and results only for students actively enrolled in the teacher’s assigned courses. Read notices and aggregate reports. |
| `STUDENT` | Read the session owner’s profile, enrollments, course schedule, attendance, results and complaints. Create own complaints and read student-facing notices. |

Protected reads and writes derive the user ID and role from the HttpOnly session cookie. Student IDs and teacher course IDs in request bodies are checked against database relationships. UI navigation checks improve usability; `server.py` is the authorization boundary.

## Run and initialize

Run `python server.py` with Python 3.10+. The server binds to `127.0.0.1:8000`, creates `data/lotus_ums.sqlite3`, and seeds sample academic records without user accounts. The first browser visit presents one-time initial Admin setup. The setup endpoint refuses subsequent account creation after the first user exists.

Admin provisions accounts from the **Accounts** page. A Student or Teacher account links to an existing profile when its university ID matches, or creates a profile when no match exists. Admin assigns courses and students from **Courses** and **Enrollments**. The Accounts page can reset a password; self-service email recovery is not configured.

The generated database is intentionally ignored by Git. Back it up separately before replacing or deleting it.

## API routes

- Auth: `GET /api/auth/setup-status`, `POST /api/auth/setup-admin`, `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`.
- Workspace: `GET /api/bootstrap` returns only collections allowed for the session role.
- Direct resources: `/api/users`, `/api/students`, `/api/teachers`, `/api/departments`, `/api/courses`, `/api/enrollments`, `/api/schedules`, `/api/attendance`, `/api/results`, `/api/notices`, `/api/complaints`.
- Reports: `GET /api/reports/overview` for Admin and Teacher.

Collections use `{ "items": [], "total": 0 }`; writes return `{ "item": {} }`. Errors return `{ "error": { "code", "message", "fields" } }`. The server validates inputs, rejects cross-origin writes, rate-limits failed logins, hashes passwords with PBKDF2-HMAC-SHA256 and issues 12-hour HttpOnly, SameSite cookies. Set `UMS_COOKIE_SECURE=1` when TLS terminates in a trusted reverse proxy.

## Deployment limits

The built-in `ThreadingHTTPServer` is for local development. Public deployment needs a production WSGI server and TLS reverse proxy, a protected database and backups, monitoring, and a real password-recovery delivery flow. Disable first-admin setup with `UMS_ALLOW_INITIAL_SETUP=0` after provisioning. Review password hashing and operational policy against the institution’s production requirements before storing real student records.
