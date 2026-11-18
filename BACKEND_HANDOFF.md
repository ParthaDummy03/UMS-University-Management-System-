# Backend Developer Handoff — Lotus University UMS

## 1. Authentication and roles

Implement real login/logout and password recovery. Recommended flow: `POST /api/auth/login` validates university email/ID and password, returns the authenticated user profile plus a server-managed session (prefer secure, HttpOnly, SameSite cookie for a browser app). `GET /api/auth/me` returns the current user and role after reload. `POST /api/auth/logout` invalidates the session. Passwords must be hashed with a modern password-hashing algorithm (Argon2id or bcrypt), never stored or logged in plaintext. Add password reset tokens with short expiry, one-time use and rate limiting.

Roles: `SUPER_ADMIN`, `ADMIN`, `TEACHER`, `STUDENT`, `DEPARTMENT_HEAD`. Enforce role and record-level authorization on the server for every endpoint. Department Heads should be scoped to their assigned department; teachers to assigned courses/classes; students to their own records. The frontend's navigation filtering is not security.

## 2. Database entities and relationships

| Entity | Essential fields / relationships |
|---|---|
| users | id, university_id, email, password_hash, role, status; one account may link to a student or teacher profile |
| departments | id, name, code, head_teacher_id; one department has many students, teachers and courses |
| students | id, user_id, department_id, intake, year, semester, status, contact; belongs to user and department |
| teachers | id, user_id, department_id, designation, status; belongs to user and department |
| courses | id, code, title, department_id, credits, semester_id; belongs to department and semester |
| semesters | id, name, academic_year, start_date, end_date, status |
| enrollments | id, student_id, course_id, semester_id, status; many-to-many student/course join |
| schedules | id, course_id, teacher_id, day_of_week, start_time, end_time, room, section; belongs to course and teacher |
| attendance | id, enrollment_id, schedule_id, class_date, status, marked_by, marked_at; unique per enrollment/session |
| assessments / grades | id, course_id, student_id or enrollment_id, assessment_name, max_marks, marks, grade, grade_point, published_at |
| notices | id, title, body, category, audience, department_id nullable, author_id, published_at, status |
| complaints | id, student_id, subject, category, details, status, assigned_to, resolution, created_at, updated_at |

Confirm whether multiple roles per account are allowed, how semester/course sections work, whether grades are per assessment or final course result, and the institution's grading scale before migrations.

## 3. Required API endpoints

All protected routes require a valid session and server-side authorization. JSON examples are illustrative.

| Method + endpoint | Purpose | Authorized roles | Example body / response |
|---|---|---|---|
| POST `/api/auth/login` | Sign in | Public | `{ "identity":"student@lotus.edu", "password":"…" }` → `{ "user":{"id":"…","name":"…","role":"STUDENT"} }` + session cookie |
| GET `/api/auth/me` | Restore session/profile | Authenticated | `{ "id":"…", "name":"…", "role":"STUDENT", "department":"CSE" }` |
| GET/PATCH `/api/profile` | Read/update own profile | Authenticated; restricted fields | PATCH `{ "phone":"+880…" }` → `{ "item":{…} }` |
| GET/POST `/api/users` | Manage system accounts/roles | Super Admin | POST `{ "email":"staff@lotus.edu", "role":"TEACHER" }` → `{ "item":{"id":"…"} }` |
| POST `/api/auth/logout` | End session | Authenticated | `{ "ok":true }` |
| POST `/api/auth/forgot-password` | Start password reset | Public, rate-limited | `{ "identity":"student@lotus.edu" }` → generic `{ "ok":true }` |
| GET `/api/students` | List/search students | Super Admin, Admin, Department Head, assigned Teacher | `?q=sophia&department=CSE` → `{ "items":[{"id":"…","name":"…"}], "total":1 }` |
| POST `/api/students` | Create student | Super Admin, Admin | `{ "name":"…", "email":"…", "departmentId":"…" }` → `{ "item":{"id":"…"} }` |
| PATCH `/api/students/{id}` | Update student | Super Admin, Admin; scoped Department Head | `{ "status":"ACTIVE" }` → `{ "item":{…} }` |
| DELETE `/api/students/{id}` | Deactivate/remove student | Super Admin, Admin | `{ "ok":true }` |
| GET/POST `/api/teachers` | List/create faculty | List: Super Admin, Admin, Department Head; create: Super Admin, Admin | POST `{ "name":"…", "departmentId":"…" }` → `{ "item":{…} }` |
| PATCH/DELETE `/api/teachers/{id}` | Update/deactivate faculty | Super Admin, Admin | PATCH `{ "designation":"Professor" }` → `{ "item":{…} }` |
| GET/POST `/api/departments` | List/create departments | List: Super Admin, Admin, Department Head; create: Super Admin | POST `{ "name":"CSE", "code":"CSE" }` → `{ "item":{…} }` |
| PATCH `/api/departments/{id}` | Update department details/head | Super Admin, Admin | `{ "headTeacherId":"…" }` → `{ "item":{…} }` |
| GET/POST `/api/courses` | Course catalogue/manage | List: authenticated by scope; write: Super Admin, Admin | POST `{ "code":"CSE-310", "title":"Algorithms", "departmentId":"…" }` → `{ "item":{…} }` |
| PATCH/DELETE `/api/courses/{id}` | Update/archive a course | Super Admin, Admin | `{ "credits":3 }` → `{ "item":{…} }` |
| GET/POST `/api/attendance` | Read/mark attendance | Read: scoped roles; write: Teacher assigned course, Admin, Super Admin | POST `{ "courseId":"…", "studentId":"…", "date":"2026-11-18", "status":"PRESENT" }` → `{ "item":{…} }` |
| GET/POST `/api/results` | Read/enter grades | Read: student own, teacher assigned, scoped admin; write: assigned Teacher, Admin, Super Admin | POST `{ "studentId":"…", "courseId":"…", "assessment":"Midterm", "marks":86 }` → `{ "item":{ "grade":"A" } }` |
| GET `/api/schedules` | Read weekly timetable | Authenticated, scoped by role | `?semesterId=…` → `{ "items":[{"day":"SUNDAY","startTime":"09:00","room":"402"}] }` |
| POST/PATCH/DELETE `/api/schedules` or `/api/schedules/{id}` | Manage timetable entries | Super Admin, Admin | `{ "courseId":"…", "dayOfWeek":"SUNDAY", "room":"402" }` → `{ "item":{…} }` |
| GET/POST `/api/notices` | Read/publish notices | Read: audience; write: Super Admin, Admin, Department Head | POST `{ "title":"Exam notice", "body":"…", "audience":"ALL" }` → `{ "item":{…} }` |
| GET/POST `/api/complaints` | List own/scoped complaints and submit | GET: student own or authorized staff; POST: Student | POST `{ "subject":"Projector issue", "category":"FACILITIES", "details":"…" }` → `{ "item":{"id":"…","status":"SUBMITTED"} }` |
| PATCH `/api/complaints/{id}` | Update complaint status | Super Admin, Admin, assigned Department Head | `{ "status":"IN_REVIEW", "resolution":"…" }` → `{ "item":{…} }` |
| GET `/api/reports/overview` | Role-scoped dashboard summaries | Super Admin, Admin, Department Head; teacher scoped | `{ "studentCount":…, "attendanceRate":… }` |

Use consistent response envelopes (`{ "items": [], "total": 0 }` for collections; `{ "item": {} }` for single records) and consistent errors such as `{ "error": { "code":"VALIDATION_ERROR", "message":"…", "fields":{} } }` with appropriate HTTP status codes.

## 4. Firebase option

Firebase can provide **Firebase Authentication** for identity, password reset and session tokens, and **Cloud Firestore** for document storage. **Cloud Functions** or a trusted server should enforce role and record-level authorization and perform privileged operations. Set custom claims for roles only from trusted server code; never let clients assign their own roles. Configure Firestore Security Rules for every collection, validate data server-side, and avoid exposing privileged admin operations directly to clients. Firebase Hosting is optional for deployment. Firebase is not currently configured in this project, and choosing Firebase does not remove the need to design authorization, data relationships, validation, indexes, backups and audit logging. Backend team must decide REST API vs direct Firebase SDK, session-cookie strategy, schema/collections, grading policy and tenancy/department boundaries.

## 5. Frontend integration guide

1. Keep page rendering and event handling in `js/app.js`; keep data/service access behind `js/api.js`. `js/data.js` currently exports an in-memory `repository` used by the mock API.
2. Implement `api.auth.login(credentials)` in `js/api.js` as a request to `POST /api/auth/login`. On success, call the shell bootstrap with the returned canonical role and profile. Map server role codes to the existing frontend keys (`SUPER_ADMIN` → `superAdmin`, etc.). Do not read the role from a form selector or trust a role supplied by the browser.
3. Implement `api.auth.logout`, `api.auth.forgotPassword`, `api.list`, `api.create`, `api.update` and `api.remove` with `fetch()`. Add `credentials: 'include'` when using secure cookie sessions. For bearer-token auth, keep token handling aligned with the backend security decision; do not store long-lived sensitive tokens in localStorage by default.
4. On page load, call `GET /api/auth/me`. If it returns 200, render the returned user's permitted workspace. If it returns 401, show the login screen. A 403 should render an access-denied state; do not infer access from hidden links.
5. Normalize API payloads to the field names consumed by the renderers, or update renderers to consume the agreed response schema. Collections should return `{ "items": [...], "total": number }`; create/update should return `{ "item": {...} }`.
6. Add loading, empty, validation and retry states around every asynchronous page request. Show field-level validation errors from `error.fields`; handle 401 by clearing the UI session and returning to login; handle 403 with an access-denied message; handle network/5xx errors with a retry option.
7. Replace direct `repository` access in actions with `api` calls, then refresh or update the affected view from the response. Do not treat the in-memory mock records as persisted data.
8. Keep all authorization and ownership checks on the backend. The developer preview page and query-string preview are local UI inspection tools only and must not be deployed as an authentication pathway.

## 6. Handoff acceptance

Backend integration is complete only when real login/logout/password recovery, session restoration, server-side role enforcement, persistent records, API validation and error handling are tested. The frontend in this ZIP remains a mock-data prototype until then.
