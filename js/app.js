const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const roleConfig = {
  admin: {
    label: 'Admin',
    nav: ['dashboard', 'users', 'students', 'teachers', 'departments', 'courses', 'enrollments', 'attendance', 'results', 'schedule', 'notices', 'complaints', 'reports', 'profile']
  },
  teacher: {
    label: 'Teacher',
    nav: ['dashboard', 'myCourses', 'students', 'attendance', 'results', 'schedule', 'notices', 'reports', 'profile']
  },
  student: {
    label: 'Student',
    nav: ['dashboard', 'myCourses', 'attendance', 'results', 'schedule', 'complaints', 'notices', 'profile']
  }
};

const pageMeta = {
  dashboard: ['Dashboard overview', 'Your Lotus University workspace.'],
  students: ['Student records', 'Create and maintain student profiles. Add sign-in access from Accounts.'],
  teachers: ['Teacher directory', 'Faculty records and teaching assignments.'],
  departments: ['Departments', 'Academic departments and leadership.'],
  courses: ['Course catalogue', 'Course details and semester assignments.'],
  myCourses: ['My courses', 'Courses associated with your account.'],
  attendance: ['Attendance', 'Review and record class attendance.'],
  results: ['Results & grades', 'Assessment records and academic performance.'],
  schedule: ['Class schedule', 'Weekly class timetable, classrooms and instructors.'],
  notices: ['Notices & announcements', 'University updates and academic announcements.'],
  complaints: ['Complaints', 'Submit and follow up on student concerns.'],
  reports: ['Reports', 'Academic and operational summaries.'],
  profile: ['My profile', 'Your university account information.'],
  users: ['Accounts', 'Create and maintain university sign-in accounts.'],
  enrollments: ['Enrollments', 'Manage student course registrations and sections.']
};

const navItems = [
  ['dashboard', 'Dashboard', '▦'], ['users', 'Accounts', '◎'], ['students', 'Students', '♙'], ['teachers', 'Teachers', '♟'],
  ['departments', 'Departments', '▤'], ['courses', 'Courses', '▧'], ['myCourses', 'My courses', '▣'],
  ['enrollments', 'Enrollments', '▤'],
  ['attendance', 'Attendance', '◷'], ['results', 'Results', '▥'], ['schedule', 'Schedule', '▦'],
  ['notices', 'Notices', '♧'], ['complaints', 'Complaints', '☷'], ['reports', 'Reports', '▤'],
  ['profile', 'My profile', '◎']
];

let activeRole = null;
let activeUser = null;
let activePage = 'dashboard';
let toastTimer = null;
let pageAnimationTimer = null;
let searchTerm = '';
let dialogContext = null;

const PAGE_SIZE = 25;
let pageIndex = 1;

// Lotus University runs its academic week from Saturday to Thursday.
const weekDays = ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday'];

const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[char]));
const initials = (name = 'LU') => name.split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();
const safeClass = value => String(value ?? '').toLowerCase().replace(/[^a-z0-9_-]/g, '-');
const isAdmin = () => activeRole === 'admin';
const canManageAcademicRecords = () => ['admin', 'teacher'].includes(activeRole);

function toast(message) {
  const element = $('#toast');
  element.textContent = message;
  element.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove('show'), 3200);
}

function normalizeRole(role) {
  const roles = { ADMIN: 'admin', TEACHER: 'teacher', STUDENT: 'student' };
  return roles[String(role ?? '').toUpperCase()] || null;
}

function canSee(page) {
  return Boolean(activeRole && roleConfig[activeRole]?.nav.includes(page));
}

function studentCourses(studentId = activeUser?.id) {
  const courseIds = new Set(workspaceData.enrollments
    .filter(enrollment => enrollment.studentId === studentId)
    .map(enrollment => enrollment.courseId));
  return workspaceData.courses.filter(course => courseIds.has(course.id));
}

function scopedCourses() {
  if (activeRole === 'student') return studentCourses();
  if (activeRole === 'teacher') return workspaceData.courses.filter(course => course.teacherId === activeUser?.id);
  return workspaceData.courses;
}

function scopedStudents() {
  if (activeRole === 'student') return workspaceData.students.filter(student => student.id === activeUser?.id);
  // Teachers can read the full directory; the server enforces course-specific write access.
  return workspaceData.students;
}

function scopedAttendance() {
  return activeRole === 'student'
    ? workspaceData.attendance.filter(record => record.studentId === activeUser?.id)
    : workspaceData.attendance;
}

function scopedGrades() {
  return activeRole === 'student'
    ? workspaceData.grades.filter(record => record.studentId === activeUser?.id)
    : workspaceData.grades;
}

function scopedComplaints() {
  return activeRole === 'student'
    ? workspaceData.complaints.filter(record => record.studentId === activeUser?.id)
    : workspaceData.complaints;
}

function visibleNotices() {
  if (isAdmin()) return workspaceData.notices;
  const audience = activeRole === 'student' ? 'Students' : 'Faculty';
  return workspaceData.notices.filter(notice =>
    notice.audience === 'All users' || notice.audience === audience || notice.audience === 'Students and Faculty'
  );
}

function scopedSchedule() {
  const courseIds = new Set(scopedCourses().map(course => course.id));
  // The API already limits each role's timetable, including student section rules.
  return workspaceData.schedule.filter(item => courseIds.has(item.code));
}

function localDateInputValue(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function animatePageEntry() {
  const body = $('#pageBody');
  clearTimeout(pageAnimationTimer);
  body.classList.remove('page-entering');
  void body.offsetWidth;
  body.classList.add('page-entering');
  pageAnimationTimer = setTimeout(() => body.classList.remove('page-entering'), 600);
}

function setSidebarOpen(open) {
  $('#sidebar').classList.toggle('sidebar-open', open);
  $('#sidebarBackdrop').classList.toggle('is-visible', open);
  $('#menuToggle').setAttribute('aria-expanded', String(open));
}

function studentsForCourse(courseId) {
  const enrolledIds = new Set(workspaceData.enrollments
    .filter(enrollment => enrollment.courseId === courseId && enrollment.status === 'Active')
    .map(enrollment => enrollment.studentId));
  return workspaceData.students.filter(student => enrolledIds.has(student.id));
}

function studentOptionsForCourse(courseId, selectedId = '') {
  const students = studentsForCourse(courseId);
  if (!students.length) return '<option value="" selected disabled>No active students enrolled</option>';
  return students.map(student => `<option value="${esc(student.id)}" ${student.id === selectedId ? 'selected' : ''}>${esc(student.name)} · ${esc(student.id)}</option>`).join('');
}

function applyWorkspaceData(data) {
  Object.keys(workspaceData).forEach(key => {
    workspaceData[key] = Array.isArray(data[key]) ? data[key] : [];
  });
  if (data.user) {
    activeUser = data.user;
    if (!$('#appShell').hidden) {
      $('#topbarName').textContent = activeUser.name;
      $('#sideName').textContent = activeUser.name;
      $('#topbarAvatar').textContent = initials(activeUser.name);
      $('#sideAvatar').textContent = initials(activeUser.name);
    }
  }
}

async function refreshWorkspace() {
  const data = await api.bootstrap();
  applyWorkspaceData(data);
  return data;
}

async function mountShell(user) {
  activeUser = user;
  await refreshWorkspace();
  $('#loginScreen').hidden = true;
  $('#appShell').hidden = false;
  $('#topbarName').textContent = user.name;
  $('#sideName').textContent = user.name;
  $('#topbarRole').textContent = roleConfig[activeRole].label;
  $('#sideRole').textContent = roleConfig[activeRole].label;
  $('#topbarAvatar').textContent = initials(user.name);
  $('#sideAvatar').textContent = initials(user.name);
  renderNavigation();
  navigate('dashboard');
}

function renderNavigation() {
  const nav = $('#mainNavigation');
  nav.replaceChildren();
  navItems.filter(([key]) => canSee(key)).forEach(([key, label, icon]) => {
    const link = document.createElement('a');
    link.className = 'nav-link';
    link.href = `#${key}`;
    link.dataset.page = key;
    link.innerHTML = `<span class="nav-icon">${icon}</span>${esc(label)}`;
    link.addEventListener('click', event => {
      event.preventDefault();
      navigate(key);
    });
    nav.append(link);
  });
}

function navigate(page) {
  if (!canSee(page)) {
    toast('This section is not available for this account.');
    return;
  }
  activePage = page;
  searchTerm = '';
  pageIndex = 1;
  $$('.nav-link').forEach(link => link.classList.toggle('active', link.dataset.page === page));
  $('#breadcrumbPage').textContent = pageMeta[page][0];
  $('#pageTitle').textContent = pageMeta[page][0];
  $('#pageSubtitle').textContent = pageMeta[page][1];
  $('#pageActions').replaceChildren();
  setSidebarOpen(false);
  history.replaceState(null, '', `#${page}`);
  animatePageEntry();
  renderPage();
}

function statCard(label, value, note, tone = 'blue') {
  return `<article class="stat-card"><div class="stat-top"><span>${esc(label)}</span><span class="stat-icon ${tone}">◈</span></div><div class="stat-value">${esc(value)}</div><div class="stat-foot">${esc(note)}</div></article>`;
}

function panel(title, subtitle, body, extra = '') {
  return `<section class="panel module-panel"><div class="panel-heading"><div><h2>${esc(title)}</h2><p>${esc(subtitle || '')}</p></div>${extra}</div>${body}</section>`;
}

function table(headers, rows) {
  if (!rows.length) return '<div class="empty-state">No records found.</div>';
  return `<div class="table-scroll"><table><thead><tr>${headers.map(header => `<th>${esc(header)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
}

// Large collections (tens of thousands of rows) are rendered one page at a time so the
// browser stays responsive.
function paginate(rows) {
  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  pageIndex = Math.min(Math.max(1, pageIndex), pageCount);
  const start = (pageIndex - 1) * PAGE_SIZE;
  const controls = rows.length <= PAGE_SIZE ? '' : `<div class="pagination">
    <button type="button" class="secondary-button" data-action="page" data-page-num="${pageIndex - 1}" ${pageIndex <= 1 ? 'disabled' : ''}>← Previous</button>
    <span>Page ${pageIndex} of ${pageCount} · ${rows.length} records</span>
    <button type="button" class="secondary-button" data-action="page" data-page-num="${pageIndex + 1}" ${pageIndex >= pageCount ? 'disabled' : ''}>Next →</button></div>`;
  return { page: rows.slice(start, start + PAGE_SIZE), controls };
}

function actionButton(action, label, id = '', kind = 'secondary-button') {
  const target = action === 'navigate' ? `data-page="${esc(id)}"` : (id ? `data-id="${esc(id)}"` : '');
  return `<button type="button" class="${kind}" data-action="${action}" ${target}>${esc(label)}</button>`;
}

function toolbar(placeholder = 'Search records…', addLabel = '') {
  return `<div class="module-toolbar"><input type="search" class="table-search" placeholder="${esc(placeholder)}" aria-label="${esc(placeholder)}">${addLabel ? actionButton('add', addLabel, '', 'primary-button') : ''}</div>`;
}

function dashboard() {
  const students = scopedStudents();
  const courses = scopedCourses();
  const attendance = scopedAttendance();
  const grades = scopedGrades();
  const notices = visibleNotices();
  let stats;

  if (activeRole === 'student') {
    const present = attendance.filter(record => record.status === 'Present').length;
    const attendanceRate = attendance.length ? `${Math.round((present / attendance.length) * 100)}%` : '—';
    const gpa = grades.length
      ? (grades.reduce((sum, record) => sum + Number(record.point || 0), 0) / grades.length).toFixed(2)
      : '—';
    stats = [
      ['Enrolled courses', courses.length, 'Your current courses', 'blue'],
      ['Attendance', attendanceRate, `${present} of ${attendance.length} recorded classes`, 'green'],
      ['Latest GPA', gpa, 'Based on recorded results', 'purple'],
      ['Notices', notices.length, 'Notices for students', 'orange']
    ];
  } else if (activeRole === 'teacher') {
    stats = [
      ['All students', students.length, 'Student directory access', 'blue'],
      ['My courses', courses.length, 'Assigned courses', 'purple'],
      ['Attendance records', attendance.length, 'All recorded student sessions', 'green'],
      ['Grade records', grades.length, 'All recorded student results', 'orange']
    ];
  } else {
    stats = [
      ['Total students', workspaceData.students.length, 'Student records', 'blue'],
      ['Total teachers', workspaceData.teachers.length, 'Faculty records', 'purple'],
      ['Departments', workspaceData.departments.length, 'Academic units', 'orange'],
      ['Active courses', workspaceData.courses.length, 'Course catalogue', 'green']
    ];
  }

  const recentStudents = activeRole === 'student' ? '' : panel(
    activeRole === 'teacher' ? 'Student records' : 'Recent students',
    activeRole === 'teacher' ? 'Search the full university student directory' : 'Latest student records',
    table(['STUDENT', 'STUDENT ID', 'DEPARTMENT', 'YEAR', 'STATUS'], students.slice(0, 5).map(student =>
      `<tr><td><div class="student-cell"><div class="avatar avatar-blue">${initials(student.name)}</div><div><strong>${esc(student.name)}</strong><span>${esc(student.email)}</span></div></div></td><td>${esc(student.id)}</td><td>${esc(student.department)}</td><td>${esc(student.year)}</td><td><span class="status status-${safeClass(student.status)}">${esc(student.status)}</span></td></tr>`
    )),
    actionButton('navigate', 'View students', 'students')
  );

  const noticeCards = notices.slice(0, 3).map(notice =>
    `<article class="notice-item"><span class="notice-tag notice-blue">${esc(notice.category)}</span><strong>${esc(notice.title)}</strong><span class="notice-date">${esc(notice.date)}</span></article>`
  ).join('') || '<div class="empty-state">No notices available.</div>';

  return `<div class="stats-grid">${stats.map(item => statCard(...item)).join('')}</div>
    <div class="dashboard-grid">${panel(activeRole === 'student' ? 'My courses' : 'Academic overview', 'Your current academic activity',
      `<div class="quick-grid">${courses.slice(0, 4).map(course => `<div class="quick-course"><strong>${esc(course.id)}</strong><span>${esc(course.title)}</span><small>${esc(course.teacher)}</small></div>`).join('') || '<div class="empty-state">No courses to show.</div>'}</div>`
    )}${panel('Weekly schedule', 'Your upcoming classes', schedulePreview())}</div>
    ${recentStudents}
    <div class="bottom-grid">${panel('Recent notices', 'University announcements', noticeCards)}${panel('Quick access', 'Frequently used sections',
      `<div class="quick-links">${roleConfig[activeRole].nav.filter(page => page !== 'dashboard').slice(0, 6).map(page => `<button class="quick-link" data-action="navigate" data-page="${page}">${esc(pageMeta[page][0])} →</button>`).join('')}</div>`
    )}</div>`;
}

function schedulePreview() {
  const entries = scopedSchedule().slice(0, 4);
  const rows = entries.map(item => `<div class="schedule-row"><div><strong>${esc(item.day)}</strong><small>${esc(item.start)}–${esc(item.end)}</small></div><div><strong>${esc(item.course)}</strong><small>${esc(item.room)} · ${esc(item.teacher)}</small></div></div>`).join('');
  return `<div class="schedule-preview">${rows || '<div class="empty-state">No classes scheduled.</div>'}</div><button class="text-button" data-action="navigate" data-page="schedule">View full timetable →</button>`;
}

function directoryPage(key) {
  let rows;
  if (key === 'users') rows = workspaceData.users;
  else if (key === 'students') rows = scopedStudents();
  else if (key === 'teachers') rows = workspaceData.teachers;
  else if (key === 'departments') rows = workspaceData.departments;
  else if (key === 'enrollments') rows = workspaceData.enrollments;
  else rows = scopedCourses();

  const addLabel = isAdmin() ? `Add ${({ users: 'account', students: 'student', teachers: 'teacher', departments: 'department', courses: 'course', enrollments: 'enrollment' })[key]}` : '';
  let headers;
  let render;

  if (key === 'users') {
    headers = ['NAME', 'UNIVERSITY ID', 'EMAIL', 'ROLE', 'DEPARTMENT', 'STATUS', 'ACTIONS'];
    render = account => `<tr><td>${esc(account.name)}</td><td>${esc(account.universityId)}</td><td>${esc(account.email)}</td><td>${esc(account.role)}</td><td>${esc(account.department || '—')}</td><td><span class="status status-${safeClass(account.status)}">${esc(account.status)}</span></td><td>${actionButton('edit', 'Edit / reset password', account.accountId)}${account.status === 'Active' ? actionButton('delete', 'Deactivate', account.accountId) : ''}</td></tr>`;
  } else if (key === 'students') {
    headers = ['NAME', 'STUDENT ID', 'EMAIL', 'DEPARTMENT', 'YEAR', 'SEMESTER', 'SECTION', 'PHONE', 'STATUS', ...(isAdmin() ? ['ACTIONS'] : [])];
    render = student => `<tr><td>${esc(student.name)}</td><td>${esc(student.id)}</td><td>${esc(student.email)}</td><td>${esc(student.department)}</td><td>${esc(student.year)}</td><td>${esc(student.semester)}</td><td>${esc(student.section)}</td><td>${esc(student.phone)}</td><td><span class="status status-${safeClass(student.status)}">${esc(student.status)}</span></td>${isAdmin() ? `<td>${actionButton('edit', 'Edit', student.id)}${student.status === 'Active' ? actionButton('delete', 'Deactivate', student.id) : ''}</td>` : ''}</tr>`;
  } else if (key === 'teachers') {
    headers = ['NAME', 'FACULTY ID', 'EMAIL', 'DEPARTMENT', 'DESIGNATION', 'STATUS', 'ACTIONS'];
    render = teacher => `<tr><td>${esc(teacher.name)}</td><td>${esc(teacher.id)}</td><td>${esc(teacher.email)}</td><td>${esc(teacher.department)}</td><td>${esc(teacher.designation)}</td><td>${esc(teacher.status)}</td><td>${actionButton('edit', 'Edit', teacher.id)}${teacher.status === 'Active' ? actionButton('delete', 'Deactivate', teacher.id) : ''}</td></tr>`;
  } else if (key === 'departments') {
    headers = ['DEPARTMENT', 'CODE', 'HEAD OF DEPARTMENT', 'STUDENTS', 'ACTIONS'];
    render = department => `<tr><td>${esc(department.name)}</td><td>${esc(department.code)}</td><td>${esc(department.head)}</td><td>${department.students}</td><td>${actionButton('edit', 'Edit', department.id)}${actionButton('delete', 'Delete', department.id)}</td></tr>`;
  } else if (key === 'enrollments') {
    headers = ['STUDENT', 'STUDENT ID', 'COURSE', 'COURSE CODE', 'SEMESTER', 'SECTION', 'STATUS', 'ACTIONS'];
    render = enrollment => `<tr><td>${esc(enrollment.student)}</td><td>${esc(enrollment.studentId)}</td><td>${esc(enrollment.course)}</td><td>${esc(enrollment.courseId)}</td><td>${esc(enrollment.semester)}</td><td>${esc(enrollment.section)}</td><td>${esc(enrollment.status)}</td><td>${actionButton('edit', 'Edit', enrollment.id)}${actionButton('delete', 'Remove', enrollment.id)}</td></tr>`;
  } else {
    headers = ['COURSE', 'TITLE', 'DEPARTMENT', 'INSTRUCTOR', 'CREDITS', 'ACTIONS'];
    render = course => `<tr><td>${esc(course.id)}</td><td>${esc(course.title)}</td><td>${esc(course.department)}</td><td>${esc(course.teacher)}</td><td>${course.credits}</td><td>${actionButton('edit', 'Edit', course.id)}${actionButton('delete', 'Delete', course.id)}</td></tr>`;
  }

  const filtered = rows.filter(row => JSON.stringify(row).toLowerCase().includes(searchTerm));
  const { page, controls } = paginate(filtered);
  return `${toolbar(`Search ${key}…`, addLabel)}${panel(pageMeta[key][0], `${filtered.length} records`, table(headers, page.map(render)) + controls)}`;
}

function attendancePage() {
  const filtered = scopedAttendance().filter(record => JSON.stringify(record).toLowerCase().includes(searchTerm));
  const { page, controls } = paginate(filtered);
  const canMark = canManageAcademicRecords();
  const headers = ['DATE', 'STUDENT', 'STUDENT ID', 'COURSE', 'STATUS', ...(canMark ? ['ACTION'] : [])];
  const content = table(headers, page.map(record => {
    const canChange = isAdmin() || (activeRole === 'teacher' && scopedCourses().some(course => course.id === record.course) && studentsForCourse(record.course).some(student => student.id === record.studentId));
    const action = canMark ? `<td>${canChange ? `${actionButton('toggle-attendance', 'Change', record.id)}${isAdmin() ? actionButton('delete', 'Delete', record.id) : ''}` : '—'}</td>` : '';
    return `<tr><td>${esc(record.date)}</td><td>${esc(record.student)}</td><td>${esc(record.studentId)}</td><td>${esc(record.course)}</td><td><span class="status status-${safeClass(record.status)}">${esc(record.status)}</span></td>${action}</tr>`;
  }));
  return `${toolbar('Search attendance…')}${panel('Attendance records', activeRole === 'student' ? 'Your recorded class attendance' : 'Attendance records for students', content + controls)}${canMark ? panel('Mark class attendance', 'Choose a course, date and enrolled student', attendanceForm()) : ''}`;
}

function attendanceForm() {
  const courses = scopedCourses();
  const firstCourse = courses[0]?.id || '';
  return `<form id="attendanceForm" class="inline-form">
    <label>Course<select name="course" required>${courses.map(course => `<option value="${esc(course.id)}">${esc(course.id)} · ${esc(course.title)}</option>`).join('')}</select></label>
    <label>Class date<input type="date" name="date" value="${localDateInputValue()}" required></label>
    <label>Student<select name="studentId" required>${studentOptionsForCourse(firstCourse)}</select></label>
    <label>Status<select name="status"><option>Present</option><option>Absent</option><option>Late</option></select></label>
    <button class="primary-button" type="submit">Save attendance</button>
  </form>`;
}

function resultsPage() {
  const filtered = scopedGrades().filter(record => JSON.stringify(record).toLowerCase().includes(searchTerm));
  const { page, controls } = paginate(filtered);
  const canEdit = canManageAcademicRecords();
  const headers = ['STUDENT', 'STUDENT ID', 'COURSE', 'ASSESSMENT', 'MARKS', 'GRADE', 'GRADE POINT', ...(canEdit ? ['ACTIONS'] : [])];
  const content = table(headers, page.map(record => {
    const canChange = isAdmin() || (activeRole === 'teacher' && scopedCourses().some(course => course.id === record.course) && workspaceData.enrollments.some(enrollment => enrollment.courseId === record.course && enrollment.studentId === record.studentId && enrollment.status === 'Active'));
    return `<tr><td>${esc(record.student)}</td><td>${esc(record.studentId)}</td><td>${esc(record.course)}</td><td>${esc(record.assessment)}</td><td>${record.marks}</td><td>${esc(record.grade)}</td><td>${Number(record.point || 0).toFixed(2)}</td>${canEdit ? `<td>${canChange ? actionButton('edit', 'Edit', record.id) : '—'}${isAdmin() ? actionButton('delete', 'Delete', record.id) : ''}</td>` : ''}</tr>`;
  }));
  return `${toolbar('Search results…')}${panel('Academic results', activeRole === 'student' ? 'Your assessment marks and grade points' : 'Student assessment marks and grade points', content + controls)}${canEdit ? panel('Enter assessment result', 'Record marks for an enrolled student', gradeForm()) : ''}`;
}

function gradeForm() {
  const courses = scopedCourses();
  const firstCourse = courses[0]?.id || '';
  return `<form id="gradeForm" class="inline-form">
    <label>Course<select name="course" required>${courses.map(course => `<option value="${esc(course.id)}">${esc(course.id)} · ${esc(course.title)}</option>`).join('')}</select></label>
    <label>Student<select name="studentId" required>${studentOptionsForCourse(firstCourse)}</select></label>
    <label>Assessment<input name="assessment" required maxlength="40" placeholder="Midterm"></label>
    <label>Marks<input name="marks" type="number" min="0" max="100" required></label>
    <button class="primary-button" type="submit">Save result</button>
  </form>`;
}

function schedulePage() {
  const days = weekDays;
  const schedule = scopedSchedule().filter(item => JSON.stringify(item).toLowerCase().includes(searchTerm));
  const admin = isAdmin();
  const body = days.map(day => {
    const slots = schedule.filter(item => item.day === day);
    if (!slots.length) return `<tr><td><strong>${day}</strong></td><td colspan="${admin ? 5 : 4}" class="muted-cell">No classes scheduled</td></tr>`;
    return slots.map((item, index) => `<tr>${index === 0 ? `<td rowspan="${slots.length}"><strong>${day}</strong></td>` : ''}<td>${esc(item.start)}–${esc(item.end)}</td><td><strong>${esc(item.code)}</strong><small>${esc(item.course)}</small></td><td>${esc(item.room)}</td><td>${esc(item.teacher)}</td>${admin ? `<td>${actionButton('edit', 'Edit', item.id)}${actionButton('delete', 'Delete', item.id)}</td>` : ''}</tr>`).join('');
  }).join('');
  return `${admin ? toolbar('Search schedule…', 'Add schedule entry') : ''}${panel('Weekly class timetable', 'Academic week · Sunday to Thursday', `<div class="timetable-wrap"><table class="timetable"><thead><tr><th>DAY</th><th>TIME</th><th>COURSE</th><th>CLASSROOM</th><th>INSTRUCTOR</th>${admin ? '<th>ACTIONS</th>' : ''}</tr></thead><tbody>${body}</tbody></table></div>`)}`;
}

function noticesPage() {
  const canPublish = isAdmin();
  const records = visibleNotices();
  const cards = records.map(notice => `<article class="notice-full"><div><span class="notice-tag notice-blue">${esc(notice.category)}</span><small>${esc(notice.date)} · ${esc(notice.audience)}</small></div><h3>${esc(notice.title)}</h3><p>${esc(notice.body)}</p>${canPublish ? `${actionButton('edit', 'Edit notice', notice.id)}${actionButton('delete', 'Delete notice', notice.id)}` : ''}</article>`).join('') || '<div class="empty-state">No notices available.</div>';
  return `${canPublish ? `<div class="module-toolbar">${actionButton('add', 'Publish notice', '', 'primary-button')}</div>` : ''}${panel('University announcements', 'Notices for your account', cards)}`;
}

function complaintsPage() {
  const mine = scopedComplaints();
  const headers = ['REFERENCE', ...(isAdmin() ? ['STUDENT ID'] : []), 'SUBJECT', 'CATEGORY', 'DETAILS', 'DATE', 'STATUS', ...(isAdmin() ? ['ACTION'] : [])];
  const rows = table(headers, mine.map(complaint =>
    `<tr><td>${esc(complaint.id)}</td>${isAdmin() ? `<td>${esc(complaint.studentId)}</td>` : ''}<td>${esc(complaint.subject)}</td><td>${esc(complaint.category)}</td><td>${esc(complaint.details)}</td><td>${esc(complaint.date)}</td><td><span class="status status-${complaint.status === 'Resolved' ? 'active' : 'pending'}">${esc(complaint.status)}</span></td>${isAdmin() ? `<td>${actionButton('cycle-complaint', 'Update status', complaint.id)}</td>` : ''}</tr>`
  ));
  return `${activeRole === 'student' ? `<div class="module-toolbar">${actionButton('add', 'Submit complaint', '', 'primary-button')}</div>` : ''}${panel('Complaint tracking', isAdmin() ? 'Review and update student concerns' : 'Your concerns and resolution progress', rows)}`;
}

function reportsPage() {
  const people = workspaceData.students;
  const attendance = workspaceData.attendance;
  const grades = workspaceData.grades;
  return `<div class="stats-grid">${statCard('Students', people.length, 'University student records', 'blue')}${statCard('Faculty', workspaceData.teachers.length, 'Faculty records', 'purple')}${statCard('Attendance entries', attendance.length, 'Recorded class sessions', 'green')}${statCard('Grade records', grades.length, 'Assessment records', 'orange')}</div>${panel('Department summary', 'Student counts by department', table(['DEPARTMENT', 'CODE', 'STUDENT COUNT', 'DEPARTMENT HEAD'], workspaceData.departments.map(department => `<tr><td>${esc(department.name)}</td><td>${esc(department.code)}</td><td>${department.students}</td><td>${esc(department.head)}</td></tr>`)))}<div class="module-toolbar">${actionButton('export', 'Export visible report', '', 'primary-button')}</div>`;
}

function profilePage() {
  const user = activeUser || {};
  const fields = [
    ['FULL NAME', user.name], ['UNIVERSITY ID', user.id], ['EMAIL', user.email],
    ['ROLE', roleConfig[activeRole].label], ['DEPARTMENT', user.department]
  ];
  if (activeRole === 'student') fields.push(['YEAR', user.year], ['SEMESTER', user.semester], ['SECTION', user.section], ['PHONE', user.phone]);
  return panel('Account information', 'Profile details for the signed-in account', `<div class="profile-grid">${fields.filter(([, value]) => value).map(([label, value]) => `<div><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`).join('')}</div>`);
}

function renderPage() {
  const body = $('#pageBody');
  switch (activePage) {
    case 'dashboard': body.innerHTML = dashboard(); break;
    case 'users': case 'students': case 'teachers': case 'departments': case 'courses': case 'enrollments': body.innerHTML = directoryPage(activePage); break;
    case 'myCourses': body.innerHTML = panel('Course enrolments', activeRole === 'student' ? 'Courses linked to your student account' : 'Courses assigned to you', table(['COURSE', 'TITLE', 'DEPARTMENT', 'INSTRUCTOR', 'CREDITS'], scopedCourses().map(course => `<tr><td>${esc(course.id)}</td><td>${esc(course.title)}</td><td>${esc(course.department)}</td><td>${esc(course.teacher)}</td><td>${course.credits}</td></tr>`))); break;
    case 'attendance': body.innerHTML = attendancePage(); break;
    case 'results': body.innerHTML = resultsPage(); break;
    case 'schedule': body.innerHTML = schedulePage(); break;
    case 'notices': body.innerHTML = noticesPage(); break;
    case 'complaints': body.innerHTML = complaintsPage(); break;
    case 'reports': body.innerHTML = reportsPage(); break;
    case 'profile': body.innerHTML = profilePage(); break;
    default: body.innerHTML = '<div class="empty-state">Section unavailable.</div>';
  }
}

function fieldsFor(key, record = {}) {
  const definitions = {
    students: [
      ['id', 'Student ID', 'text'], ['name', 'Full name', 'text'], ['email', 'University email', 'email'],
      ['department', 'Department', 'select', workspaceData.departments.map(item => item.name)],
      ['year', 'Year', 'select', ['1st Year', '2nd Year', '3rd Year', '4th Year']],
      ['semester', 'Semester', 'text'], ['section', 'Section', 'text'],
      ['status', 'Status', 'select', ['Active', 'Pending', 'Inactive']], ['phone', 'Phone', 'tel']
    ],
    teachers: [
      ['id', 'Faculty ID', 'text'], ['name', 'Full name', 'text'], ['email', 'University email', 'email'],
      ['department', 'Department', 'select', workspaceData.departments.map(item => item.name)],
      ['designation', 'Designation', 'text'], ['status', 'Status', 'select', ['Active', 'On leave', 'Inactive']]
    ],
    departments: [
      ['id', 'Department ID', 'text'], ['name', 'Department name', 'text'], ['code', 'Department code', 'text'],
      ['head', 'Department head', 'text']
    ],
    courses: [
      ['id', 'Course code', 'text'], ['title', 'Course title', 'text'],
      ['department', 'Department', 'select', workspaceData.departments.map(item => item.name)],
      ['teacherId', 'Teacher', 'select', workspaceData.teachers.map(item => item.id)],
      ['credits', 'Credits', 'number'], ['semester', 'Semester', 'text']
    ],
    notices: [
      ['title', 'Notice title', 'text'], ['category', 'Category', 'select', ['Academic', 'General', 'Event']],
      ['audience', 'Audience', 'select', ['All users', 'Students', 'Faculty', 'Students and Faculty']], ['body', 'Notice details', 'textarea']
    ],
    complaints: [
      ['subject', 'Complaint subject', 'text'], ['category', 'Category', 'select', ['Academic', 'Facilities', 'Finance', 'Other']],
      ['details', 'Details', 'textarea']
    ],
    users: [
      ['universityId', 'University ID', 'text'], ['name', 'Full name', 'text'], ['email', 'University email', 'email'],
      ['role', 'Account role', 'select', ['ADMIN', 'TEACHER', 'STUDENT']], ['password', 'Password (12 characters minimum)', 'password'],
      ['department', 'Department', 'select', workspaceData.departments.map(item => item.name)],
      ['designation', 'Designation (teachers)', 'text'], ['year', 'Year (students)', 'text'],
      ['semester', 'Semester (students)', 'text'], ['section', 'Section (students)', 'text'], ['phone', 'Phone (students)', 'tel'],
      ['status', 'Account status', 'select', ['Active', 'Inactive']]
    ],
    enrollments: [
      ['studentId', 'Student', 'select', workspaceData.students.map(item => item.id)],
      ['courseId', 'Course', 'select', workspaceData.courses.map(item => item.id)],
      ['semester', 'Semester', 'text'], ['section', 'Section', 'text'],
      ['status', 'Enrollment status', 'select', ['Active', 'Withdrawn']]
    ],
    schedule: [
      ['courseId', 'Course', 'select', workspaceData.courses.map(item => item.id)],
      ['day', 'Day', 'select', weekDays],
      ['start', 'Start time', 'time'], ['end', 'End time', 'time'], ['room', 'Room', 'text'], ['section', 'Section', 'text']
    ],
    grades: [
      ['assessment', 'Assessment', 'text'], ['marks', 'Marks', 'number']
    ]
  };
  return (definitions[key] || []).map(([name, label, type, options]) => {
    const value = key === 'schedule' && name === 'courseId' ? (record.courseId ?? record.code ?? '') : (record[name] ?? '');
    if (key === 'courses' && name === 'teacherId') return `<label>${esc(label)}<select name="teacherId"><option value="" ${!value ? 'selected' : ''}>Unassigned</option>${workspaceData.teachers.map(teacher => `<option value="${esc(teacher.id)}" ${teacher.id === value ? 'selected' : ''}>${esc(teacher.name)} · ${esc(teacher.id)}</option>`).join('')}</select></label>`;
    if (key === 'enrollments' && record.id && name === 'studentId') return `<label>${esc(label)}<input value="${esc(record.student)} · ${esc(record.studentId)}" readonly></label>`;
    if (key === 'enrollments' && record.id && name === 'courseId') return `<label>${esc(label)}<input value="${esc(record.course)} · ${esc(record.courseId)}" readonly></label>`;
    if (key === 'enrollments' && name === 'studentId') return `<label>${esc(label)}<select name="studentId" required>${workspaceData.students.map(student => `<option value="${esc(student.id)}" ${student.id === value ? 'selected' : ''}>${esc(student.name)} · ${esc(student.id)}</option>`).join('')}</select></label>`;
    if (key === 'enrollments' && name === 'courseId' || key === 'schedule' && name === 'courseId') return `<label>${esc(label)}<select name="courseId" required>${workspaceData.courses.map(course => `<option value="${esc(course.id)}" ${course.id === value ? 'selected' : ''}>${esc(course.id)} · ${esc(course.title)}</option>`).join('')}</select></label>`;
    if (key === 'users' && name === 'department') return `<label>${esc(label)}<select name="department"><option value="">No department</option>${options.map(option => `<option value="${esc(option)}" ${option === value ? 'selected' : ''}>${esc(option)}</option>`).join('')}</select></label>`;
    if (key === 'users' && name === 'role' && record.accountId) return `<label>Account role<input value="${esc(value)}" readonly></label>`;
    if (key === 'users' && name === 'universityId' && record.accountId) return `<label>${esc(label)}<input name="universityId" value="${esc(value)}" readonly></label>`;
    if (key === 'users' && name === 'status' && !record.accountId) return '';
    if (type === 'select') return `<label>${esc(label)}<select name="${name}" required>${options.map(option => `<option value="${esc(option)}" ${option === value ? 'selected' : ''}>${esc(option)}</option>`).join('')}</select></label>`;
    if (type === 'textarea') return `<label>${esc(label)}<textarea name="${name}" rows="4" required maxlength="1000">${esc(value)}</textarea></label>`;
    const passwordAttrs = key === 'users' && name === 'password' ? `minlength="12" ${record.accountId ? '' : 'required'} autocomplete="new-password"` : '';
    const required = key === 'users' && ['designation', 'year', 'semester', 'section', 'phone', 'password'].includes(name) ? '' : 'required';
    return `<label>${esc(label)}<input name="${name}" type="${type}" value="${type === 'password' ? '' : esc(value)}" ${name === 'id' && record.id ? 'readonly' : ''} ${passwordAttrs} maxlength="160" ${required}></label>`;
  }).join('');
}

function canOpenDialog(resource, id = null) {
  if (resource === 'complaints') return activeRole === 'student' && !id;
  if (resource === 'notices') return isAdmin();
  if (resource === 'grades') return canManageAcademicRecords() && Boolean(id);
  return isAdmin() && ['users', 'students', 'teachers', 'departments', 'courses', 'enrollments', 'schedule'].includes(resource);
}

function openRecordDialog(resource, id = null) {
  if (!canOpenDialog(resource, id)) {
    toast('You do not have permission to make that change.');
    return;
  }
  const dataKey = resource === 'grades' ? 'grades' : resource;
  const record = id ? workspaceData[dataKey]?.find(item => String(resource === 'users' ? item.accountId : item.id) === String(id)) : null;
  if (id && !record) return toast('Record not found.');
  dialogContext = { resource, id };
  const singular = { users: 'account', students: 'student', teachers: 'teacher', departments: 'department', courses: 'course', enrollments: 'enrollment', schedule: 'schedule entry', notices: 'notice', complaints: 'complaint' }[resource] || resource;
  $('#dialogTitle').textContent = `${id ? 'Edit ' : resource === 'complaints' ? 'Submit ' : 'Add '}${singular}`;
  $('#dialogFields').innerHTML = fieldsFor(resource, record || {});
  $('#recordDialog').showModal();
}

function formObject(form) {
  return Object.fromEntries(new FormData(form).entries());
}

async function handleClick(event) {
  const button = event.target.closest('[data-action]');
  if (!button) return;
  const { action, id, page } = button.dataset;
  if (action === 'navigate') return navigate(page);
  if (action === 'page') {
    pageIndex = Number(button.dataset.pageNum) || 1;
    renderPage();
    window.scrollTo({ top: 0, behavior: 'smooth' });
    return;
  }
  if (action === 'add') {
    return openRecordDialog(activePage);
  }
  if (action === 'edit') return openRecordDialog(activePage === 'results' ? 'grades' : activePage, id);

  try {
    if (action === 'delete') {
      if (!isAdmin()) return toast('You do not have permission to remove this record.');
      const verb = activePage === 'users' || activePage === 'students' || activePage === 'teachers' ? 'Deactivate' : 'Remove';
      if (!confirm(`${verb} this record?`)) return;
      await api.remove(activePage === 'results' ? 'grades' : activePage, id);
      await refreshWorkspace();
      renderPage();
      return toast(`${verb}d successfully.`);
    }
    if (action === 'cycle-complaint') {
      if (!isAdmin()) return toast('You do not have permission to update complaints.');
      const complaint = workspaceData.complaints.find(record => record.id === id);
      if (!complaint) return toast('Complaint not found.');
      const status = complaint.status === 'Submitted' ? 'In Review' : complaint.status === 'In Review' ? 'Resolved' : 'Submitted';
      await api.update('complaints', id, { status });
      await refreshWorkspace();
      renderPage();
      return toast('Complaint status updated.');
    }
    if (action === 'toggle-attendance') {
      if (!canManageAcademicRecords()) return toast('You do not have permission to change attendance.');
      const row = workspaceData.attendance.find(record => String(record.id) === String(id));
      if (!row) return toast('Attendance record not found.');
      const statuses = ['Present', 'Absent', 'Late'];
      const status = statuses[(statuses.indexOf(row.status) + 1) % statuses.length];
      await api.update('attendance', id, { status });
      await refreshWorkspace();
      renderPage();
      return toast('Attendance status updated.');
    }
    if (action === 'export') {
      if (!['admin', 'teacher'].includes(activeRole)) return toast('You do not have permission to export reports.');
      const csv = ['Department,Code,Students,Head', ...workspaceData.departments.map(department =>
        [department.name, department.code, department.students, department.head].map(value => `"${String(value).replaceAll('"', '""')}"`).join(',')
      )].join('\n');
      const anchor = document.createElement('a');
      const fileUrl = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
      anchor.href = fileUrl;
      anchor.download = 'lotus-department-report.csv';
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(fileUrl), 1000);
      return toast('Report exported.');
    }
  } catch (error) {
    return toast(error.message);
  }
}

function updateCourseStudentOptions(form) {
  const courseId = form.elements.course.value;
  const studentSelect = form.elements.studentId;
  const selectedId = studentSelect.value;
  const students = studentsForCourse(courseId);
  const options = students.length
    ? students.map(student => new Option(`${student.name} · ${student.id}`, student.id))
    : [new Option('No active students enrolled', '')];
  studentSelect.replaceChildren(...options);
  if (students.some(student => student.id === selectedId)) studentSelect.value = selectedId;
}

function bindPageForms() {
  const body = $('#pageBody');
  body.oninput = event => {
    if (!event.target.matches('.table-search')) return;
    searchTerm = event.target.value.toLowerCase();
    pageIndex = 1;
    const value = event.target.value;
    renderPage();
    const input = $('.table-search');
    if (input) {
      input.value = value;
      input.focus();
      input.setSelectionRange(value.length, value.length);
    }
  };
  body.onchange = event => {
    if (!event.target.matches('#attendanceForm [name="course"], #gradeForm [name="course"]')) return;
    updateCourseStudentOptions(event.target.form);
  };
  body.onclick = event => { void handleClick(event); };
  body.addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.target;
    if (form.id === 'attendanceForm') {
      if (!canManageAcademicRecords()) return toast('You do not have permission to record attendance.');
      try {
        await api.create('attendance', formObject(form));
        await refreshWorkspace();
        renderPage();
        return toast('Attendance saved.');
      } catch (error) { return toast(error.message); }
    }
    if (form.id === 'gradeForm') {
      if (!canManageAcademicRecords()) return toast('You do not have permission to enter results.');
      try {
        await api.create('grades', formObject(form));
        await refreshWorkspace();
        renderPage();
        return toast('Result saved.');
      } catch (error) { return toast(error.message); }
    }
  });
}

function showAuthForm(which = 'login') {
  const login = $('#loginForm');
  const register = $('#registerForm');
  const setup = $('#setupForm');
  const title = $('#loginTitle');
  const intro = $('#loginIntro');
  login.hidden = which !== 'login';
  register.hidden = which !== 'register';
  setup.hidden = which !== 'setup';
  $('#loginFeedback').textContent = '';
  $('#registerFeedback').textContent = '';
  $('#setupFeedback').textContent = '';
  if (which === 'register') {
    title.textContent = 'Create your account';
    intro.textContent = 'Register a student account to access the Lotus University workspace.';
  } else if (which === 'setup') {
    title.textContent = 'Set up the system';
    intro.textContent = 'Create the first administrator account. Only one account can complete this setup.';
  } else {
    title.textContent = 'Welcome back';
    intro.textContent = 'Sign in with your university credentials to continue.';
  }
}

function bindGlobalEvents() {
  $('#loginForm').addEventListener('submit', async event => {
    event.preventDefault();
    const identity = $('#loginIdentity').value.trim();
    const password = $('#loginPassword').value;
    if (!identity || !password) {
      $('#loginFeedback').textContent = 'Enter your university email or ID and password.';
      return;
    }
    const submit = event.currentTarget.querySelector('[type="submit"]');
    submit.disabled = true;
    try {
      const session = await api.auth.login({ identity, password });
      const user = session?.user;
      const role = normalizeRole(user?.role);
      if (!user || !role || !user.id) throw new Error('The authentication response must include a valid account, ID and role.');
      activeRole = role;
      await mountShell(user);
    } catch (error) {
      $('#loginFeedback').textContent = error.message;
    } finally {
      submit.disabled = false;
    }
  });

  $('#registerForm').addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    if (!form.reportValidity()) return;
    const value = formObject(form);
    if (value.password !== value.passwordConfirm) {
      $('#registerFeedback').textContent = 'The passwords do not match.';
      return;
    }
    const payload = {
      name: value.name,
      universityId: value.universityId,
      email: value.email,
      password: value.password
    };
    if (value.department?.trim()) payload.department = value.department.trim();
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    try {
      const result = await api.auth.register(payload);
      const user = result?.user;
      const role = normalizeRole(user?.role);
      if (!user || !role || !user.id) throw new Error('Registration succeeded but the account could not be loaded.');
      activeRole = role;
      await mountShell(user);
    } catch (error) {
      $('#registerFeedback').textContent = error.message;
    } finally {
      submit.disabled = false;
    }
  });

  $('#showRegisterButton').addEventListener('click', () => showAuthForm('register'));
  $('#showLoginButton').addEventListener('click', () => showAuthForm('login'));

  $('#setupForm').addEventListener('submit', async event => {
    event.preventDefault();
    if (!event.currentTarget.reportValidity()) return;
    const value = formObject(event.currentTarget);
    if (value.password !== value.passwordConfirm) {
      $('#setupFeedback').textContent = 'The passwords do not match.';
      return;
    }
    delete value.passwordConfirm;
    const submit = event.currentTarget.querySelector('[type="submit"]');
    submit.disabled = true;
    try {
      const result = await api.auth.setupAdmin(value);
      activeRole = 'admin';
      await mountShell(result.user);
    } catch (error) {
      $('#setupFeedback').textContent = error.message;
    } finally {
      submit.disabled = false;
    }
  });

  $('#forgotPasswordButton').addEventListener('click', () => {
    $('#loginFeedback').textContent = 'Ask a system administrator to reset your password.';
  });

  $('#logoutButton').addEventListener('click', async () => {
    try { await api.auth.logout(); } catch (error) { /* Clear the local workspace even if the server is offline. */ }
    activeRole = null;
    activeUser = null;
    Object.keys(workspaceData).forEach(key => { workspaceData[key] = []; });
    $('#appShell').hidden = true;
    $('#loginScreen').hidden = false;
    history.replaceState(null, '', location.pathname);
    $('#loginPassword').value = '';
    showAuthForm('login');
    toast('You have been logged out.');
  });

  $('#menuToggle').addEventListener('click', () => setSidebarOpen(!$('#sidebar').classList.contains('sidebar-open')));
  $('#sidebarBackdrop').addEventListener('click', () => setSidebarOpen(false));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && $('#sidebar').classList.contains('sidebar-open')) setSidebarOpen(false);
  });
  $('#notificationButton').addEventListener('click', () => navigate(canSee('notices') ? 'notices' : 'dashboard'));
  window.addEventListener('ums-auth-expired', () => {
    activeRole = null;
    activeUser = null;
    dialogContext = null;
    if ($('#recordDialog').open) $('#recordDialog').close();
    Object.keys(workspaceData).forEach(key => { workspaceData[key] = []; });
    $('#appShell').hidden = true;
    $('#loginScreen').hidden = false;
    showAuthForm('login');
    $('#loginFeedback').textContent = 'Your session expired. Sign in again.';
    history.replaceState(null, '', location.pathname);
  });
  $('#recordForm').addEventListener('submit', async event => {
    if (event.submitter?.value === 'cancel') return;
    event.preventDefault();
    if (!dialogContext || !canOpenDialog(dialogContext.resource, dialogContext.id)) return toast('You do not have permission to save this record.');
    const value = formObject(event.currentTarget);
    const resource = dialogContext.resource;
    if (resource === 'users' && !value.password) delete value.password;
    const submit = $('#saveRecordButton');
    submit.disabled = true;
    try {
      if (dialogContext.id) await api.update(resource, dialogContext.id, value);
      else await api.create(resource, value);
      $('#recordDialog').close();
      dialogContext = null;
      await refreshWorkspace();
      renderPage();
      toast('Saved successfully.');
    } catch (error) {
      toast(error.message);
    } finally {
      submit.disabled = false;
    }
  });
}

async function initialize() {
  const now = new Date();
  $('#todayLabel').textContent = now.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }).toUpperCase();
  bindGlobalEvents();
  bindPageForms();

  try {
    const user = await api.auth.currentUser();
    const role = normalizeRole(user?.role);
    if (user && role && user.id) {
      activeRole = role;
      await mountShell(user);
      return;
    }
    const setup = await api.auth.setupStatus();
    if (setup.required) {
      showAuthForm('setup');
    }
  } catch (error) {
    $('#loginFeedback').textContent = `Cannot connect to the UMS server. Start the project with python server.py. (${error.message})`;
  }
}

document.addEventListener('DOMContentLoaded', initialize);
