# Backend and access model

The application runs as a same-origin Python HTTP server with SQLite persistence. `server.py` owns authentication, session management, validation and role checks. `js/api.js` is the browser service layer; `js/data.js` only holds empty workspace arrays that the API fills after sign-in.

## Architecture

- **Server**: `ThreadingHTTPServer` + `SimpleHTTPRequestHandler` (Python standard library, no framework). Serves static files from the project root and routes `/api/*` requests to the `dispatch()` method.
- **Database**: SQLite at `data/lotus_ums.sqlite3`. `PRAGMA foreign_keys = ON` and `PRAGMA busy_timeout = 15000`. The database file is tracked by Git so the dataset ships with the project; journal/WAL sidecars are ignored.
- **Auth boundary**: Every protected request resolves the account and role from the HttpOnly session cookie. The UI hides forbidden modules for usability, but `server.py` is the authorization boundary.

## Roles

| Role | Server access |
|---|---|
| `ADMIN` | Full access: accounts, student/teacher profiles, departments, courses, enrollments, schedules, attendance, results, notices, complaints and reports. Can create, update and deactivate any record. |
| `TEACHER` | Read the full student directory, teacher directory (no), departments, all academic records (courses, enrollments, schedules, attendance, results, notices, complaints). Create/update attendance and results **only** for students actively enrolled in the teacher's assigned courses. Read aggregate reports. Cannot manage accounts, departments, courses or enrollments. |
| `STUDENT` | Read only the session owner's profile, enrollments, enrolled courses, section schedule, attendance, results and complaints. Submit and manage own complaints. Read student-facing notices. Cannot read other users' data. |

## Authentication and sessions

| Endpoint | Method | Description |
|---|---|---|
| `/api/auth/setup-status` | GET | Returns `{ "required": bool }`. `required` is true only when `UMS_ALLOW_INITIAL_SETUP=1` and the `users` table is empty. |
| `/api/auth/setup-admin` | POST | One-time first-Admin creation. Refuses with `409 SETUP_COMPLETE` once any user exists. Body: `name`, `universityId`, `email`, `password`. Returns `{ "user": ... }` and a session cookie. |
| `/api/auth/register` | POST | Public student self-registration. Body: `name`, `universityId`, `email`, `password` (12+ chars), optional `department`. Creates a `STUDENT` user + linked student profile, then returns `201 { "user": ... }` with a session cookie (auto sign-in). Rejects duplicate ID/email with `409 DUPLICATE_ACCOUNT`. Disabled when `UMS_ALLOW_PUBLIC_REGISTRATION=0`. |
| `/api/auth/login` | POST | Body: `identity` (email or university ID, case-insensitive) + `password`. Returns `200 { "user": ... }` and a session cookie. Inactive accounts are rejected. Rate-limited to 8 failed attempts per IP+identity per 15 minutes (`429 RATE_LIMITED`). |
| `/api/auth/me` | GET | Returns the current session's `user` payload, or `401` if no valid session. |
| `/api/auth/logout` | POST | Deletes the server-side session and clears the cookie. Returns `200 { "ok": true }`. |

### Session mechanics

- Session tokens are 32-byte URL-safe secrets. Only the SHA-256 hash is stored (`sessions.token_hash`).
- Cookie name: `lotus_ums_session`. Flags: `HttpOnly`, `SameSite=Strict`, `Path=/`, `Max-Age=43200` (12 hours). Add `Secure` when `UMS_COOKIE_SECURE=1`.
- Expired sessions are pruned on every new session creation.
- Passwords are hashed with **PBKDF2-HMAC-SHA256** (600,000 iterations) in Django-compatible format `pbkdf2_sha256$<iterations>$<salt>$<base64digest>`. The `verify_password` helper also supports a legacy hex-salt format.
- All write methods (`POST`, `PATCH`, `DELETE`) validate the `Origin`/`Referer` header against the request host.

## User payload shape

The `user` object returned by auth and `/api/auth/me`:

```json
{
  "accountId": 1,
  "id": "223933212",
  "universityId": "223933212",
  "name": "...",
  "email": "...",
  "role": "STUDENT",
  "status": "Active",
  "department": "Computer Science and Engineering",
  "year": "2022", "semester": "Spring", "section": "A", "phone": "",
  "designation": ""
}
```

`id` is the linked profile ID (student/teacher university ID) when a profile exists, otherwise the `universityId`. `department` resolves to the profile's department name, or `"Central Administration"` for admins with no profile.

## Database schema

Tables: `users`, `sessions`, `login_attempts`, `departments`, `students`, `teachers`, `courses`, `enrollments`, `schedule`, `attendance`, `grades`, `notices`, `complaints`.

Key relationships:
- `users` 1—0/1 `students` (via `students.user_id`)
- `users` 1—0/1 `teachers` (via `teachers.user_id`)
- `departments` 1—N `students`/`teachers`/`courses`
- `teachers` 1—N `courses` (via `courses.teacher_id`)
- `students` M—N `courses` via `enrollments`
- `enrollments` 1—N `attendance`, `grades`
- `courses` 1—N `schedule`
- `students` 1—N `complaints`
- `users` 1—N `notices` (author), `attendance` (marked_by), `grades` (created_by)

`init_db()` runs `CREATE TABLE IF NOT EXISTS` for all tables on every start (no destructive migrations).

## API routes

### Workspace bootstrap

| Endpoint | Method | Roles | Description |
|---|---|---|---|
| `/api/bootstrap` | GET | All | Returns all collections the role is allowed to see in one call. Used once after sign-in. |
| `/api/reports/overview` | GET | ADMIN, TEACHER | Returns `studentCount`, `teacherCount`, `attendanceCount`, `gradeCount`. |
| `/api/health` | GET | All | `{ "ok": true }` liveness check (no auth). |

### Resources

All resource routes follow `/api/<resource>[/<id>]` with `GET` (list/item), `POST` (create), `PATCH` (update), `DELETE` (deactivate/delete).

| Resource | GET list | GET item | POST | PATCH | DELETE |
|---|---|---|---|---|---|
| `users` (accounts) | ADMIN | ADMIN | ADMIN | ADMIN | ADMIN (deactivate) |
| `students` | ADMIN, TEACHER, STUDENT (own) | same | ADMIN | ADMIN | ADMIN (deactivate) |
| `teachers` | ADMIN, TEACHER | same | ADMIN | ADMIN | ADMIN (deactivate) |
| `departments` | ADMIN, TEACHER | same | ADMIN | ADMIN | ADMIN (delete) |
| `courses` | ADMIN, TEACHER (assigned), STUDENT (enrolled) | same | ADMIN | ADMIN | ADMIN (delete) |
| `enrollments` | ADMIN, TEACHER (assigned), STUDENT (own) | same | ADMIN | ADMIN | ADMIN (delete) |
| `schedules` → `/api/schedules` | ADMIN, TEACHER (assigned), STUDENT (own section) | same | ADMIN | ADMIN | ADMIN (delete) |
| `attendance` | ADMIN, TEACHER (assigned), STUDENT (own) | same | ADMIN, TEACHER | ADMIN, TEACHER | — |
| `results` → `/api/results` (backed by `grades`) | ADMIN, TEACHER (assigned), STUDENT (own) | same | ADMIN, TEACHER | ADMIN, TEACHER | — |
| `notices` | All (audience-filtered) | same | ADMIN | ADMIN | ADMIN (delete) |
| `complaints` | ADMIN, STUDENT (own) | same | STUDENT | ADMIN (status only) | ADMIN (delete) |

**Aliases**: the browser calls `schedules` and `results`; the server maps `schedules`→`schedule` and `results`→`grades` internally. Direct calls to `/api/schedule` and `/api/grades` also work.

### Scoping rules

- **Students** see only their own rows for students, enrollments, attendance, grades, complaints and schedule. Notices are filtered by audience.
- **Teachers** see all students, all departments, and all notices, but courses, enrollments, schedules, attendance and grades are scoped to courses assigned to them (`courses.teacher_id` resolves via `teachers.user_id`).
- **Admins** see everything.

## Request and response conventions

- **List**: `{ "items": [...], "total": <n> }`
- **Single item** (POST/PATCH/GET by ID): `{ "item": {...} }` (auth endpoints use `{ "user": {...} }`)
- **Empty success** (DELETE): `200 { "ok": true }`
- **Errors**: `{ "error": { "code": "...", "message": "...", "fields": { "field": "hint" } } }`

Common error codes: `VALIDATION_ERROR` (400), `UNAUTHENTICATED` (401), `INVALID_CREDENTIALS` (401), `FORBIDDEN` (403), `NOT_FOUND` (404), `DUPLICATE_ACCOUNT` (409), `CONFLICT` (409), `RATE_LIMITED` (429), `SETUP_DISABLED`/`SETUP_COMPLETE` (403/409), `REGISTRATION_DISABLED` (403), `NOT_ENROLLED` (403), `COURSE_NOT_ASSIGNED` (403), `LAST_ADMIN` (400), `SELF_DEACTIVATION` (400).

A 401 from any non-auth `/api/*` route dispatches a `ums-auth-expired` DOM event in the browser, returning the user to the login screen.

## Validation rules

- Text fields are trimmed and length-checked (`clean_text`). Required fields reject empty values.
- Emails (`email_text`) must match `[^@\s]+@[^@\s]+\.[^@\s]+` and are lowercased.
- Passwords (`required_password`) must be 12–128 characters.
- Roles must be one of `ADMIN`, `TEACHER`, `STUDENT`.
- Statuses: users/students/teachers `Active`/`Inactive`; enrollments `Active`/`Withdrawn`; attendance `Present`/`Absent`/`Late`; complaints `Submitted`/`In Review`/`Resolved`; notice audience `All users`/`Students`/`Faculty`/`Students and Faculty`.
- Departments are resolved by name, code or ID (case-insensitive, with a fuzzy fallback); unknown values raise `VALIDATION_ERROR`.
- Schedule times must be `HH:MM` and end after start.
- Attendance requires an active enrollment in the course; teachers additionally require the course to be assigned to them.
- Grades: marks 0–100; grade and GPA point are server-computed via `grade_for()`.
- Attendance is upserted on `(enrollment_id, class_date)`; grades are unique per `(enrollment_id, assessment)`.
- Admin cannot deactivate their own account or the last active admin.

## Account provisioning

- **Public registration** creates a STUDENT account and, if a `students` row with the same `university_id` already exists, links to it (and reactivates it); otherwise it creates a new student profile.
- **Admin account creation** (`/api/users` POST, via the Accounts page) works the same way for any role: it links to an existing profile by university ID or creates a new one. Department is optional.
- **Password reset** is done by PATCH-ing the user with a new `password` field; sessions of that user (except the actor) are cleared.
- Self-service email-based password recovery is **not** implemented; users must ask an administrator.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `UMS_HOST` | `127.0.0.1` | Bind address. |
| `UMS_PORT` | `8000` | Bind port. |
| `UMS_DB_PATH` | `data/lotus_ums.sqlite3` | SQLite database path. |
| `UMS_ALLOW_INITIAL_SETUP` | `1` | Allow the first-Admin setup screen when the DB is empty. |
| `UMS_ALLOW_PUBLIC_REGISTRATION` | `1` | Allow student self-registration on the login screen. |
| `UMS_COOKIE_SECURE` | `0` | Set the `Secure` flag on the session cookie (use behind HTTPS/TLS termination). |

## Run and initialize

Run `python server.py` with Python 3.10+. The server binds to `127.0.0.1:8000` and uses `data/lotus_ums.sqlite3`.

The repository ships with a fully populated database (2,730 user accounts plus academic records). Sign in with any seeded account using the shared password `Lotus@123` — see [`README.md`](README.md) for the login formats. Only if the database file is absent does the server create an empty schema; in that case the first browser visit presents a one-time initial Admin setup, and the setup endpoint refuses further account creation once a user exists.

## Deployment limits

The built-in `ThreadingHTTPServer` is for local development. Public deployment needs:
- A production WSGI/ASGI server and a TLS reverse proxy.
- `UMS_ALLOW_INITIAL_SETUP=0` and `UMS_ALLOW_PUBLIC_REGISTRATION=0` after provisioning.
- `UMS_COOKIE_SECURE=1` when served over HTTPS.
- Protected database storage and regular backups.
- Monitoring and a real password-recovery delivery flow (email/SMS).
- Review of password hashing parameters and operational policy against the institution's production requirements before storing real student records.

The bundled records are demonstration data — never use them as real student data.
