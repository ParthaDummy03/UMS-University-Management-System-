# Lotus University Management System — Frontend

A responsive frontend-only University Management System built with HTML5, CSS3 and vanilla JavaScript. The Lotus University logo and existing visual direction are retained. No frontend framework, build step or package installation is required.

## Run locally

1. Extract the project folder.
2. Open `university-management-system` in VS Code.
3. Install the **Live Server** extension if it is not already installed.
4. Right-click `index.html` and choose **Open with Live Server**.
5. The public entry page is the university login screen.

The login form is intentionally not a fake login: it displays an integration-pending message because no authentication service exists yet. No credentials are accepted, transmitted or stored. Forgot Password is also an integration point only.

## Implemented frontend

- Professional Lotus University sign-in page: University Email / ID, Password, Login and Forgot Password.
- Five role workspaces: Super Administrator, Administrator, Teacher / Faculty, Student and Department Head.
- Role-specific sidebar navigation and page visibility.
- Dashboard statistics, course summaries, notices and recent student records.
- Student and teacher directories with search, add, edit and delete operations for administrative roles.
- Department and course directories with administrative CRUD operations.
- Weekly timetable with days, times, course codes/titles, rooms and instructors.
- Attendance records, attendance marking and status changes for permitted preview roles.
- Result/marks entry with basic grade-point calculation and student result views.
- Notices and announcements; publishing for administrative roles.
- Student complaint submission and complaint status listing.
- Department summaries, basic reports and CSV export.
- Responsive sidebar, forms, tables, timetable and dialogs.
- Separate developer-only role preview utility.

## Developer role preview (not authentication)

Open `developer-preview.html` through Live Server to inspect the five dashboards without a backend. This page is deliberately separate from the normal login UI. It opens the selected workspace using mock data and displays a developer preview banner. Do not deploy this utility publicly. It does not authenticate anyone and must never be treated as an authorization mechanism.

## Mock data and persistence

- `js/data.js` contains the in-memory mock dataset and repository adapter.
- `js/api.js` is the service boundary intended for real API integration.
- `js/app.js` handles role navigation, page rendering, forms and interactions.
- `css/style.css` contains the preserved base styles plus the Lotus design completion layer.
- `assets/lotus-university-logo.png` is the supplied university logo.

Create, edit, delete, attendance and grade changes are held in JavaScript memory only. Refreshing the page resets them. No database or localStorage persistence is implemented.

## Backend integration status

**Pending:** real authentication, server-issued sessions/tokens, server-side role authorization, password reset, persistent database storage, API endpoints and Firebase configuration (if selected). The login form intentionally cannot create a session until the backend contract is implemented. See [`BACKEND_HANDOFF.md`](BACKEND_HANDOFF.md).

## Security notes

Frontend role navigation is for user experience only. It is not secure access control. Every protected endpoint and record must be authorized by the backend on every request. Never trust a role, user ID or department supplied by browser code.

## Suggested review checklist

- Open `index.html` and verify the login layout at desktop and mobile widths.
- Verify login does not claim success while the authentication API is unavailable.
- Open `developer-preview.html`; test all five role dashboards and role-specific sidebar links.
- Student: test My Courses, Attendance, Results, Schedule, Complaints and Notices.
- Teacher: test course list, students, attendance marking, marks entry, schedule and reports.
- Administrator: test add/edit/delete/search for students, teachers, departments and courses; publish notices; inspect attendance/results/reports.
- Department Head: verify department-scoped records and academic reporting.
- Super Administrator: verify all administrative modules are visible.
- Test schedule rows for Sunday–Thursday, times, rooms and instructors.
- Submit a complaint, add attendance, add a grade and publish a notice; refresh and confirm mock changes reset.
- Check browser DevTools for JavaScript errors and verify responsive behavior.

Static validation performed for this delivery: JavaScript syntax checks, HTML parsing, local asset existence and required module/navigation assertions. Interactive browser automation is not claimed as completed; run the checklist above in Live Server before release.
