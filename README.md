# Lotus University Administration System

University administration app with separate Admin, Teacher and Student workspaces. It uses the existing HTML/CSS/vanilla JavaScript frontend, a Python standard-library web server and SQLite persistence. There are no package installs and no build step.

## Run locally

1. Install Python 3.10 or newer.
2. Open PowerShell in this project folder.
3. Run `python server.py`.
4. Open [http://127.0.0.1:8000](http://127.0.0.1:8000).
5. Sign in with one of the accounts below.

The database is created at `data/lotus_ums.sqlite3` (path configurable via `UMS_DB_PATH`). The repository ships with a fully populated dataset, so no setup or seeding step is required. If you delete the database file, the server recreates an empty database on the next start and presents the one-time first-Admin setup screen.

## Sign-in accounts

Every seeded account uses the same password: **`Lotus@123`**.

| Role | Login | Example |
|---|---|---|
| Admin | `admin01@lotus.edu` … `admin30@lotus.edu` | `admin01@lotus.edu` (superuser) |
| Teacher | `firstname.lastname@lotus.edu` | `zahid.hossain@lotus.edu` |
| Student | `<student_id>@student.lotus.edu` | `223933212@student.lotus.edu` |

University IDs follow a fixed scheme: students are 9 digits (first 2 = admission year, last 2 = department code), teachers are `F` + department code + 3 digits, and admins are `A001`–`A030`. Department codes: CSE `12`, EEE `10`, Economics `14`, English `16`, Social Economics `18`.

## Dataset

| Collection | Records |
|---|---|
| Users | 2,730 (30 Admin, 200 Teacher, 2,500 Student) |
| Departments | 5 |
| Courses | 40 (8 per department) |
| Enrollments | 25,000 |
| Class schedule | 80 |
| Attendance | 37,500 |
| Results | 12,500 |
| Notices | 12 |
| Complaints | 54 |

## Workspaces

| Role | Main access |
|---|---|
| Admin | All modules: accounts, students, teachers, departments, courses, enrollments, attendance, results, schedule, notices, complaints and reports. Admin can create and maintain records. |
| Teacher | Read the full student directory and academic records. Record or update attendance/results only for students enrolled in assigned courses. See assigned courses, schedules and reports. |
| Student | Read only their own profile, enrolled courses, section schedule, attendance, results and complaints. Submit their own complaints and read student notices. |

The backend applies role and record checks to each API request. Student record IDs and teacher course assignments are resolved from the signed-in session.

## Features

- University ID/email login, logout and server-managed sessions.
- Passwords hashed with PBKDF2-HMAC-SHA256; sign-in attempts are rate-limited.
- SQLite storage for users, profiles, departments, courses, enrollments, schedules, attendance, grades, notices and complaints.
- Admin account creation, profile linking and password reset.
- Searchable student and teacher directories, course and department management, enrollment management and schedule editing.
- Attendance and grade entry with course enrollment checks and server-side grade calculation.
- Audience-filtered notices, student-owned complaints, reports and CSV export.
- Client-side pagination (25 rows per page) keeps the large collections responsive.
- Responsive layouts, mobile navigation, input validation and explicit empty/error states.
- Animated page transitions, staggered row entries and hover feedback, with reduced-motion support.

## Configuration and deployment

The server binds to `127.0.0.1:8000` by default. Set `UMS_HOST` and `UMS_PORT` to change the listener; set `UMS_DB_PATH` to change the database path. Set `UMS_ALLOW_INITIAL_SETUP=0` to disable first-Admin setup. For HTTPS behind a trusted reverse proxy, set `UMS_COOKIE_SECURE=1`.

This built-in server is intended for local development. Before public deployment, put the app behind a production WSGI server and TLS reverse proxy, disable first-admin setup, configure backups, and add an email-based password recovery flow. The bundled records are demonstration data — never use them as real student data.

See [`BACKEND_HANDOFF.md`](BACKEND_HANDOFF.md) for the API and permission model.
