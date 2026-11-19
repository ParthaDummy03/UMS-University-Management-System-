/* Client-side store. It is filled from the API after sign-in and holds no sample records. */
const store = {
  departments: [], students: [], teachers: [], courses: [], schedule: [],
  attendance: [], grades: [], notices: [], complaints: [],
  report: null, me: null, meta: {}, loadedAt: {}
};

/* store key -> API resource name */
const RESOURCE = {
  students: 'students', teachers: 'teachers', departments: 'departments', courses: 'courses',
  schedule: 'schedules', attendance: 'attendance', grades: 'results',
  notices: 'notices', complaints: 'complaints'
};

/* Which collections each role is allowed to load (the server enforces this too) */
const ROLE_RESOURCES = {
  admin: ['students', 'teachers', 'departments', 'courses', 'schedule', 'attendance', 'grades', 'notices', 'complaints'],
  teacher: ['students', 'teachers', 'departments', 'courses', 'schedule', 'attendance', 'grades', 'notices'],
  student: ['students', 'departments', 'courses', 'schedule', 'attendance', 'grades', 'notices', 'complaints']
};

function resetStore() {
  Object.keys(RESOURCE).forEach(k => { store[k] = []; });
  store.report = null; store.me = null; store.meta = {}; store.loadedAt = {};
}
