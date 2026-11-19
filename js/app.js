const $ = (s,root=document) => root.querySelector(s);
const $$ = (s,root=document) => [...root.querySelectorAll(s)];
const roleConfig={
 admin:{label:'Administrator',nav:['dashboard','students','teachers','departments','courses','attendance','results','schedule','notices','complaints','reports','profile']},
 teacher:{label:'Teacher / Faculty',nav:['dashboard','myCourses','students','attendance','results','schedule','notices','reports','profile']},
 student:{label:'Student',nav:['dashboard','myCourses','attendance','results','schedule','complaints','notices','profile']}
};
const pageMeta={dashboard:['Dashboard overview','Your Lotus University workspace.'],students:['Student management','Search, review and maintain student records.'],teachers:['Teacher directory','Faculty records and teaching assignments.'],departments:['Departments','Academic departments and leadership.'],courses:['Course catalogue','Course details and semester assignments.'],myCourses:['My courses','Courses associated with your account.'],attendance:['Attendance','Review and record class attendance.'],results:['Results & grades','Assessment records and academic performance.'],schedule:['Class schedule','Weekly class timetable, classrooms and instructors.'],notices:['Notices & announcements','University updates and academic announcements.'],complaints:['Complaints','Submit and follow up on student concerns.'],reports:['Reports','Academic and operational summaries.'],profile:['My profile','Your university account information.']};
const navItems=[['dashboard','Dashboard','▦'],['students','Students','♙'],['teachers','Teachers','♟'],['departments','Departments','▤'],['courses','Courses','▧'],['myCourses','My courses','▣'],['attendance','Attendance','◷'],['results','Results','▥'],['schedule','Schedule','▦'],['notices','Notices','♧'],['complaints','Complaints','☷'],['reports','Reports','▤'],['profile','My profile','◎']];
let activeRole=null, activePage='dashboard', toastTimer=null, searchTerm='';
const esc=(v='')=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const initials=(name='LU')=>name.split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase();
const safeClass=(value='')=>String(value).toLowerCase().replace(/[^a-z0-9_-]/g,'-');
function toast(message){const el=$('#toast');el.textContent=message;el.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('show'),3200)}
function normalizeRole(role){return ({ADMIN:'admin',TEACHER:'teacher',STUDENT:'student'})[role]||null}
function canSee(page){return !!activeRole&&roleConfig[activeRole].nav.includes(page)}
function scopedStudents(){return store.students}
function scopedCourses(){return store.courses}
async function mountShell(user){
 store.me=user;$('#loginScreen').hidden=true;$('#appShell').hidden=false;
 const label=roleConfig[activeRole].label;
 $('#topbarName').textContent=user.name;$('#sideName').textContent=user.name;$('#topbarRole').textContent=label;$('#sideRole').textContent=label;$('#topbarAvatar').textContent=initials(user.name);$('#sideAvatar').textContent=initials(user.name);
 renderNavigation();$('#pageBody').innerHTML='<div class="empty-state">Loading your workspace…</div>';
 await loadWorkspace();navigate('dashboard')}
function renderNavigation(){const nav=$('#mainNavigation');nav.replaceChildren();navItems.filter(([key])=>canSee(key)).forEach(([key,label,icon])=>{const a=document.createElement('a');a.className='nav-link';a.href='#'+key;a.dataset.page=key;a.innerHTML=`<span class="nav-icon">${icon}</span>${esc(label)}`;a.addEventListener('click',e=>{e.preventDefault();navigate(key)});nav.append(a)})}
function navigate(page){if(!canSee(page)){toast('This section is not available for this account.');return}activePage=page;searchTerm='';$$('.nav-link').forEach(a=>a.classList.toggle('active',a.dataset.page===page));$('#breadcrumbPage').textContent=pageMeta[page][0];$('#pageTitle').textContent=pageMeta[page][0];$('#pageSubtitle').textContent=pageMeta[page][1];$('#pageActions').replaceChildren();$('#sidebar').classList.remove('sidebar-open');history.replaceState(null,'','#'+page);renderPage();refreshForPage(page)}
function statCard(label,value,note,tone='blue'){return `<article class="stat-card"><div class="stat-top"><span>${esc(label)}</span><span class="stat-icon ${tone}">◈</span></div><div class="stat-value">${esc(value)}</div><div class="stat-foot">${esc(note)}</div></article>`}
function panel(title,subtitle,body,extra=''){return `<section class="panel module-panel"><div class="panel-heading"><div><h2>${esc(title)}</h2><p>${esc(subtitle||'')}</p></div>${extra}</div>${body}</section>`}
function table(headers,rows){if(!rows.length)return `<div class="empty-state">No records found.</div>`;return `<div class="table-scroll"><table><thead><tr>${headers.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`}
function actionButton(action,label,id='',kind='secondary-button'){return `<button type="button" class="${kind}" data-action="${action}" ${id?`data-id="${esc(id)}"`:''}>${esc(label)}</button>`}
function toolbar(placeholder='Search records…',addLabel='',value=''){return `<div class="module-toolbar"><input type="search" class="table-search" placeholder="${esc(placeholder)}" aria-label="${esc(placeholder)}" value="${esc(value)}">${addLabel?actionButton('add',addLabel,'','primary-button'):''}</div>`}
function dashboard(){
 const isStudent=activeRole==='student',isTeacher=activeRole==='teacher';
 const students=store.students,courses=store.courses;let stats;
 if(isStudent){const att=store.attendance,attended=att.filter(a=>a.status!=='Absent').length;const finals=store.grades.filter(g=>g.assessment==='Final'&&g.point!=null);
  stats=[['Enrolled courses',courses.length,'Current semester','blue'],['Attendance',att.length?Math.round(attended*100/att.length)+'%':'—','Present or late','green'],['Average grade point',finals.length?average(finals.map(g=>g.point)).toFixed(2):'—','Final assessments','purple'],['Notices',total('notices'),'University updates','orange']]}
 else if(isTeacher)stats=[['Assigned courses',courses.length,'Current semester','blue'],['Students',total('students'),'University directory','purple'],['Attendance records',total('attendance'),'Recorded entries','green'],['Result records',total('grades'),'Assessment records','orange']];
 else stats=[['Total students',total('students'),'Student records','blue'],['Total teachers',total('teachers'),'Faculty records','purple'],['Departments',total('departments'),'Academic units','orange'],['Active courses',total('courses'),'Current catalogue','green']];
 const recent=students.slice(0,5).map(s=>`<tr><td><div class="student-cell"><div class="avatar avatar-blue">${initials(s.name)}</div><div><strong>${esc(s.name)}</strong><span>${esc(s.email)}</span></div></div></td><td>${esc(s.id)}</td><td>${esc(s.department)}</td><td>${esc(s.year)}</td><td><span class="status status-${safeClass(s.status)}">${esc(s.status)}</span></td></tr>`);
 const notices=store.notices.slice(0,3).map(n=>`<article class="notice-item"><span class="notice-tag notice-blue">${esc(n.category)}</span><strong>${esc(n.title)}</strong><span class="notice-date">${esc(n.date)}</span></article>`).join('');
 const studentsPanel=isStudent?'':panel('Recent students','Latest student records',table(['STUDENT','STUDENT ID','DEPARTMENT','YEAR','STATUS'],recent),actionButton('navigate','View students','students'));
 return `<div class="stats-grid">${stats.map(s=>statCard(...s)).join('')}</div><div class="dashboard-grid">${panel(isStudent?'My courses':'Academic overview','Your current academic activity',`<div class="quick-grid">${courses.slice(0,4).map(c=>`<div class="quick-course"><strong>${esc(c.id)}</strong><span>${esc(c.title)}</span><small>${esc(c.teacher)}</small></div>`).join('')}</div>`)}${panel('Weekly schedule','Your upcoming classes',schedulePreview())}</div>${studentsPanel}<div class="bottom-grid">${panel('Recent notices','University announcements',notices)}${panel('Quick access','Frequently used sections',`<div class="quick-links">${roleConfig[activeRole].nav.filter(p=>p!=='dashboard').slice(0,6).map(p=>`<button class="quick-link" data-action="navigate" data-page="${p}">${esc(pageMeta[p][0])} →</button>`).join('')}</div>`)}</div>`}
function schedulePreview(){return `<div class="schedule-preview">${store.schedule.slice(0,4).map(x=>`<div class="schedule-row"><div><strong>${esc(x.day)}</strong><small>${esc(x.start)}–${esc(x.end)}</small></div><div><strong>${esc(x.course)}</strong><small>${esc(x.room)} · ${esc(x.teacher)}</small></div></div>`).join('')}</div><button class="text-button" data-action="navigate" data-page="schedule">View full timetable →</button>`}
function directoryPage(key){
 const rows=store[key],admin=activeRole==='admin',serverSearch=['students','teachers'].includes(key);
 const add=admin&&['students','teachers','departments','courses'].includes(key)?`Add ${({students:'student',teachers:'teacher',departments:'department',courses:'course'})[key]}`:'';
 const buttons=r=>admin?actionButton('edit','Edit',r.id)+actionButton('delete','Delete',r.id):'—';
 let headers,render;
 if(key==='students'){headers=['NAME','STUDENT ID','EMAIL','DEPARTMENT','YEAR','STATUS','ACTIONS'];render=r=>`<tr><td>${esc(r.name)}</td><td>${esc(r.id)}</td><td>${esc(r.email)}</td><td>${esc(r.department)}</td><td>${esc(r.year)}</td><td><span class="status status-${safeClass(r.status)}">${esc(r.status)}</span></td><td>${buttons(r)}</td></tr>`}
 if(key==='teachers'){headers=['NAME','FACULTY ID','EMAIL','DEPARTMENT','DESIGNATION','ACTIONS'];render=r=>`<tr><td>${esc(r.name)}</td><td>${esc(r.id)}</td><td>${esc(r.email)}</td><td>${esc(r.department)}</td><td>${esc(r.designation)}</td><td>${buttons(r)}</td></tr>`}
 if(key==='departments'){headers=['DEPARTMENT','CODE','HEAD OF DEPARTMENT','STUDENTS','TEACHERS','ACTIONS'];render=r=>`<tr><td>${esc(r.name)}</td><td>${esc(r.code)}</td><td>${esc(r.head)}</td><td>${r.students}</td><td>${r.teachers}</td><td>${buttons(r)}</td></tr>`}
 if(key==='courses'){headers=['COURSE','TITLE','DEPARTMENT','INSTRUCTOR','CREDITS','ACTIONS'];render=r=>`<tr><td>${esc(r.id)}</td><td>${esc(r.title)}</td><td>${esc(r.department)}</td><td>${esc(r.teacher)}</td><td>${r.credits}</td><td>${buttons(r)}</td></tr>`}
 const visible=serverSearch?rows:rows.filter(r=>JSON.stringify(r).toLowerCase().includes(searchTerm));
 return `${toolbar('Search '+key+'…',add,serverSearch?(store.meta[key]?.q||''):'')}${panel(pageMeta[key][0],`${total(key)} records`,table(headers,visible.map(render)))}${pager(key)}`}
function attendancePage(){
 const canMark=['teacher','admin'].includes(activeRole);
 const rows=store.attendance.filter(a=>JSON.stringify(a).toLowerCase().includes(searchTerm));
 return `${toolbar('Search attendance…')}${panel('Attendance records',`${total('attendance')} entries`,table(['DATE','STUDENT','STUDENT ID','COURSE','STATUS',...(canMark?['ACTION']:[])],rows.map(r=>`<tr><td>${esc(r.date)}</td><td>${esc(r.student)}</td><td>${esc(r.studentId)}</td><td>${esc(r.course)}</td><td><span class="status status-${safeClass(r.status)}">${esc(r.status)}</span></td>${canMark?`<td>${actionButton('toggle-attendance','Change',r.studentId+'|'+r.date+'|'+r.course)}</td>`:''}</tr>`)))}${pager('attendance')}${canMark?panel('Mark class attendance','Choose a class and record student attendance',attendanceForm()):''}`}
function attendanceForm(){return `<form id="attendanceForm" class="inline-form"><label>Course<select name="course">${store.courses.map(c=>`<option>${esc(c.id)}</option>`).join('')}</select></label><label>Class date<input type="date" name="date" value="${todayISO()}" required></label><label>Student ID<input name="studentId" required pattern="[0-9]{9}" maxlength="9" placeholder="9-digit student ID"></label><label>Status<select name="status"><option>Present</option><option>Absent</option><option>Late</option></select></label><button class="primary-button" type="submit">Save attendance</button></form>`}
function resultsPage(){
 const canEdit=['teacher','admin'].includes(activeRole);
 const rows=store.grades.filter(r=>JSON.stringify(r).toLowerCase().includes(searchTerm));
 return `${toolbar('Search results…')}${panel('Academic results','Assessment marks and grade points',table(['STUDENT','STUDENT ID','COURSE','ASSESSMENT','MARKS','GRADE','GRADE POINT'],rows.map(r=>`<tr><td>${esc(r.student)}</td><td>${esc(r.studentId)}</td><td>${esc(r.course)}</td><td>${esc(r.assessment)}</td><td>${esc(r.marks)}</td><td>${esc(r.grade)}</td><td>${r.point==null?'—':r.point.toFixed(2)}</td></tr>`)))}${pager('grades')}${canEdit?panel('Enter assessment result','Grade and grade point are calculated by the server',`<form id="gradeForm" class="inline-form"><label>Student ID<input name="studentId" required pattern="[0-9]{9}" maxlength="9" placeholder="9-digit student ID"></label><label>Course<select name="course">${store.courses.map(c=>`<option>${esc(c.id)}</option>`).join('')}</select></label><label>Assessment<select name="assessment"><option>Midterm</option><option>Final</option><option>Quiz</option><option>Assignment</option></select></label><label>Marks<input name="marks" type="number" min="0" max="100" step="0.01" required></label><button class="primary-button">Save result</button></form>`):''}`}
function schedulePage(){const days=['Saturday','Sunday','Monday','Tuesday','Wednesday','Thursday'];const schedule=store.schedule;return panel('Weekly class timetable','Academic week · Saturday to Thursday',`<div class="timetable-wrap"><table class="timetable"><thead><tr><th>DAY</th><th>TIME</th><th>COURSE</th><th>CLASSROOM</th><th>INSTRUCTOR</th></tr></thead><tbody>${days.map(day=>{const slots=schedule.filter(x=>x.day===day).sort((a,b)=>a.start.localeCompare(b.start));return slots.length?slots.map((x,i)=>`<tr>${i===0?`<td rowspan="${slots.length}"><strong>${day}</strong></td>`:''}<td>${esc(x.start)}–${esc(x.end)}</td><td><strong>${esc(x.code)}</strong><small>${esc(x.course)}</small></td><td>${esc(x.room)}</td><td>${esc(x.teacher)}</td></tr>`).join(''):`<tr><td><strong>${day}</strong></td><td colspan="4" class="muted-cell">No classes scheduled</td></tr>`}).join('')}</tbody></table></div>`)}
function noticesPage(){const canPublish=activeRole==='admin';return `${canPublish?`<div class="module-toolbar">${actionButton('add','Publish notice','','primary-button')}</div>`:''}${panel('University announcements','Official updates and academic notices',store.notices.map(n=>`<article class="notice-full"><div><span class="notice-tag notice-blue">${esc(n.category)}</span><small>${esc(n.date)} · ${esc(n.audience)}</small></div><h3>${esc(n.title)}</h3><p>${esc(n.body)}</p>${canPublish?actionButton('edit','Edit',n.id)+actionButton('delete','Delete notice',n.id):''}</article>`).join('')||'<div class="empty-state">No notices published.</div>')}`}
function complaintsPage(){const admin=activeRole==='admin';return `${activeRole==='student'?`<div class="module-toolbar">${actionButton('add','Submit complaint','','primary-button')}</div>`:''}${panel('Complaint tracking','Student concerns and resolution progress',table(['REFERENCE','SUBMITTED BY','SUBJECT','CATEGORY','DATE','STATUS'],store.complaints.map(c=>`<tr><td>${esc(c.id)}</td><td>${esc(c.studentId||c.name)}</td><td>${esc(c.subject)}</td><td>${esc(c.category)}</td><td>${esc(c.date)}</td><td><span class="status status-${c.status==='Resolved'?'active':'pending'}">${esc(c.status)}</span>${admin?actionButton('cycle-complaint','Update',c.id):''}</td></tr>`)))}`}
function reportsPage(){const r=store.report;if(!r)return '<div class="empty-state">Reports are not available right now.</div>';return `<div class="stats-grid">${statCard('Students',r.students,'Total student records','blue')}${statCard('Faculty',r.teachers,'Faculty records','purple')}${statCard('Attendance rate',r.attendanceRate+'%','Entries marked present','green')}${statCard('Average final marks',r.averageMarks??'—','All final assessments','orange')}</div>${panel('Department summary','Students and teachers by department',table(['DEPARTMENT','STUDENTS','TEACHERS'],r.departmentSummary.map(d=>`<tr><td>${esc(d.name)}</td><td>${d.students}</td><td>${d.teachers}</td></tr>`)))}<div class="module-toolbar">${actionButton('export','Export department report','','primary-button')}</div>`}
function profilePage(){const u=store.me||{};return panel('Account information','Details of the signed-in account',`<div class="profile-grid"><div><small>FULL NAME</small><strong>${esc(u.name)}</strong></div><div><small>UNIVERSITY ID</small><strong>${esc(u.id)}</strong></div><div><small>EMAIL</small><strong>${esc(u.email)}</strong></div><div><small>ROLE</small><strong>${esc(roleConfig[activeRole].label)}</strong></div><div><small>DEPARTMENT</small><strong>${esc(u.department)}</strong></div></div>`)}
function renderPage(){const body=$('#pageBody');switch(activePage){case'dashboard':body.innerHTML=dashboard();break;case'students':case'teachers':case'departments':case'courses':body.innerHTML=directoryPage(activePage);break;case'myCourses':body.innerHTML=panel('Course enrolments','Courses associated with this account',table(['COURSE','TITLE','DEPARTMENT','INSTRUCTOR','CREDITS'],scopedCourses().map(c=>`<tr><td>${esc(c.id)}</td><td>${esc(c.title)}</td><td>${esc(c.department)}</td><td>${esc(c.teacher)}</td><td>${c.credits}</td></tr>`)));break;case'attendance':body.innerHTML=attendancePage();break;case'results':body.innerHTML=resultsPage();break;case'schedule':body.innerHTML=schedulePage();break;case'notices':body.innerHTML=noticesPage();break;case'complaints':body.innerHTML=complaintsPage();break;case'reports':body.innerHTML=reportsPage();break;case'profile':body.innerHTML=profilePage();break;default:body.innerHTML='<div class="empty-state">Section unavailable.</div>'}}
function formDefs(key){
 const departments=store.departments.map(d=>d.name);
 const defs={
  students:[
   {name:'name',label:'Full name',type:'text'},
   {name:'email',label:'University email (optional)',type:'email',required:false},
   {name:'department',label:'Department',type:'select',options:departments},
   {name:'batch',label:'Admission year',type:'text',pattern:'20[0-9]{2}',placeholder:'2025',maxlength:4},
   {name:'year',label:'Year',type:'select',options:['1st Year','2nd Year','3rd Year','4th Year'],mode:'edit'},
   {name:'semester',label:'Semester',type:'number',min:1,max:12,mode:'edit'},
   {name:'status',label:'Status',type:'select',options:['Active','Inactive']},
   {name:'phone',label:'Phone',type:'tel',required:false},
   {name:'password',label:'Password (min 8 characters)',editLabel:'New password (leave blank to keep)',type:'password',required:'add'}],
  teachers:[
   {name:'name',label:'Full name',type:'text'},
   {name:'email',label:'University email (optional)',type:'email',required:false},
   {name:'department',label:'Department',type:'select',options:departments},
   {name:'designation',label:'Designation',type:'select',options:['Professor','Associate Professor','Assistant Professor','Lecturer']},
   {name:'phone',label:'Phone',type:'tel',required:false},
   {name:'status',label:'Status',type:'select',options:['Active','Inactive'],mode:'edit'},
   {name:'password',label:'Password (min 8 characters)',editLabel:'New password (leave blank to keep)',type:'password',required:'add'}],
  departments:[
   {name:'name',label:'Department name',type:'text'},
   {name:'code',label:'Department code (2 digits)',type:'text',pattern:'[0-9]{2}',placeholder:'12',maxlength:2,mode:'add'},
   {name:'headId',label:'Head teacher ID (e.g. F12001)',type:'text',required:false}],
  courses:[
   {name:'code',label:'Course code',type:'text',mode:'add'},
   {name:'title',label:'Course title',type:'text'},
   {name:'department',label:'Department',type:'select',options:departments},
   {name:'teacherId',label:'Teacher ID (optional)',type:'text',required:false},
   {name:'credits',label:'Credits',type:'number',min:0.5,max:9,step:0.5}],
  notices:[
   {name:'title',label:'Notice title',type:'text'},
   {name:'category',label:'Category',type:'select',options:['Academic','General','Event','Finance']},
   {name:'audience',label:'Audience',type:'select',options:['All users','Students','Faculty','Students and Faculty']},
   {name:'body',label:'Notice details',type:'textarea'}],
  complaints:[
   {name:'subject',label:'Complaint subject',type:'text'},
   {name:'category',label:'Category',type:'select',options:['Academic','Facilities','Administrative','Finance','Other']},
   {name:'details',label:'Details',type:'textarea'}]
 };
 return defs[key]||[]}
function fieldsFor(key,record={},mode='add'){
 return formDefs(key).filter(d=>!d.mode||d.mode===mode).map(d=>{
  const value=record[d.name]??'';const label=(mode==='edit'&&d.editLabel)?d.editLabel:d.label;
  const req=d.required===undefined?true:d.required==='add'?mode==='add':d.required;
  const attrs=`name="${d.name}" ${req?'required':''} ${d.pattern?`pattern="${d.pattern}"`:''} ${d.placeholder?`placeholder="${esc(d.placeholder)}"`:''} ${d.min!==undefined?`min="${d.min}"`:''} ${d.max!==undefined?`max="${d.max}"`:''} ${d.step?`step="${d.step}"`:''}`;
  if(d.type==='select')return `<label>${esc(label)}<select name="${d.name}" required>${d.options.map(o=>`<option ${o===value?'selected':''}>${esc(o)}</option>`).join('')}</select></label>`;
  if(d.type==='textarea')return `<label>${esc(label)}<textarea ${attrs} rows="4" maxlength="1000">${esc(value)}</textarea></label>`;
  return `<label>${esc(label)}<input type="${d.type}" ${attrs} value="${d.type==='password'?'':esc(value)}" maxlength="${d.maxlength||120}"></label>`}).join('')}
let dialogContext=null;
function openRecordDialog(resource,id=null){
 const record=id?store[resource].find(x=>String(x.id)===String(id)):null;
 dialogContext={resource,id};
 const singular=({students:'student',teachers:'teacher',departments:'department',courses:'course',notices:'notice',complaints:'complaint'})[resource]||'record';
 $('#dialogTitle').textContent=(id?'Edit ':'Add ')+singular;
 $('#dialogFields').innerHTML=fieldsFor(resource,record||{},id?'edit':'add');
 $('#saveRecordButton').textContent=id?'Save changes':(resource==='complaints'?'Submit complaint':'Save record');
 $('#recordDialog').showModal()}
function formObject(form){return Object.fromEntries(new FormData(form).entries())}
async function handleClick(e){
 const btn=e.target.closest('[data-action]');if(!btn)return;const {action,id,page}=btn.dataset;
 try{
  if(action==='navigate')return navigate(page);
  if(action==='add')return openRecordDialog(activePage);
  if(action==='edit')return openRecordDialog(activePage,id);
  if(action==='delete'){
   if(!confirm('Delete this record permanently?'))return;
   await api.remove(RESOURCE[activePage],id);await refreshAfterWrite(activePage);renderPage();return toast('Record deleted.')}
  if(action==='cycle-complaint'){
   const row=store.complaints.find(c=>String(c.id)===String(id));if(!row)return;
   const next=({Pending:'In Review','In Review':'Resolved',Resolved:'Pending'})[row.status]||'Pending';
   await api.update('complaints',id,{status:next});await refreshAfterWrite('complaints');renderPage();return toast('Complaint marked as '+next+'.')}
  if(action==='toggle-attendance'){
   const [studentId,date,course]=id.split('|');const row=store.attendance.find(a=>a.studentId===studentId&&a.date===date&&a.course===course);if(!row)return;
   const next=row.status==='Present'?'Absent':'Present';
   await api.create('attendance',{studentId,date,course,status:next});await refreshAfterWrite('attendance');renderPage();return toast('Attendance updated.')}
  if(action==='page'){
   const [k,dir]=id.split('|');const m=store.meta[k];if(!m)return;
   await loadResource(k,{page:Math.max(1,m.page+Number(dir)),q:m.q});renderPage();return}
  if(action==='export'){
   const r=store.report;if(!r)return toast('No report data to export.');
   const csv=['Department,Students,Teachers',...r.departmentSummary.map(d=>[d.name,d.students,d.teachers].map(v=>'"'+String(v).replaceAll('"','""')+'"').join(','))].join('\n');
   const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));a.download='lotus-department-report.csv';a.click();URL.revokeObjectURL(a.href);return toast('Report exported.')}
 }catch(err){toast(describeError(err))}}
function bindForms(){const body=$('#pageBody');let searchTimer=null;
 body.oninput=e=>{if(!e.target.matches('.table-search'))return;const value=e.target.value;searchTerm=value.toLowerCase();const serverKey=['students','teachers'].includes(activePage)?activePage:null;clearTimeout(searchTimer);
  searchTimer=setTimeout(async()=>{if(serverKey){try{await loadResource(serverKey,{page:1,q:value.trim()})}catch(err){return toast(describeError(err))}}renderPage();const input=$('.table-search');if(input){input.value=value;input.focus();input.setSelectionRange(value.length,value.length)}},serverKey?300:0)};
 body.onclick=handleClick;
 body.onsubmit=async e=>{e.preventDefault();const form=e.target;const button=form.querySelector('button[type=submit],button:not([type])');if(button)button.disabled=true;
  try{
   if(form.id==='attendanceForm'){const v=formObject(form);await api.create('attendance',{studentId:v.studentId.trim(),course:v.course,date:v.date,status:v.status});await loadResource('attendance');renderPage();toast('Attendance saved.')}
   if(form.id==='gradeForm'){const v=formObject(form),marks=Number(v.marks);if(!Number.isFinite(marks)||marks<0||marks>100)return toast('Marks must be between 0 and 100.');
    const saved=await api.create('results',{studentId:v.studentId.trim(),course:v.course,assessment:v.assessment,marks});await loadResource('grades');renderPage();toast('Result saved. Grade: '+saved.item.grade)}
  }catch(err){toast(describeError(err))}finally{if(button)button.disabled=false}}}
const total=key=>store.meta[key]?.total??store[key].length;
const average=list=>list.length?list.reduce((a,b)=>a+b,0)/list.length:0;
const todayISO=()=>new Date().toISOString().slice(0,10);
function describeError(err){const f=err&&err.fields&&Object.keys(err.fields).length?' ('+Object.entries(err.fields).map(([k,v])=>k+': '+v).join('; ')+')':'';return (err&&err.message?err.message:'Something went wrong.')+f}
async function loadResource(key,{page=1,q=''}={}){
 const params=new URLSearchParams({page:String(page),page_size:['students','teachers','attendance','grades'].includes(key)?'50':'200'});
 if(q&&['students','teachers'].includes(key))params.set('q',q);
 const data=await api.list(RESOURCE[key],params.toString());
 store[key]=data.items;store.meta[key]={total:data.total,page:data.page,pageSize:data.page_size,q:q||''};store.loadedAt[key]=Date.now();return data}
async function loadWorkspace(){
 const keys=ROLE_RESOURCES[activeRole];
 const results=await Promise.allSettled(keys.map(k=>loadResource(k)));
 const failed=results.find(r=>r.status==='rejected');
 if(activeRole!=='student'){try{store.report=(await api.reports()).item}catch(err){store.report=null}}
 if(failed)toast(describeError(failed.reason))}
async function refreshAfterWrite(key){
 const m=store.meta[key]||{};const jobs=[loadResource(key,{page:m.page||1,q:m.q||''})];
 if(['students','teachers','courses'].includes(key))jobs.push(loadResource('departments'));
 await Promise.all(jobs);
 if(activeRole==='admin'&&['students','teachers','courses'].includes(key)){try{store.report=(await api.reports()).item}catch(err){}}}
async function refreshForPage(page){
 const wanted=({dashboard:['students','notices','courses','schedule'],students:['students'],teachers:['teachers'],departments:['departments'],courses:['courses'],myCourses:['courses'],attendance:['attendance'],results:['grades'],schedule:['schedule'],notices:['notices'],complaints:['complaints']})[page]||[];
 const keys=wanted.filter(k=>ROLE_RESOURCES[activeRole].includes(k)).filter(k=>store.loadedAt[k]===undefined||Date.now()-store.loadedAt[k]>15000||store.meta[k]?.q);
 try{
  if(page==='reports'&&activeRole!=='student')store.report=(await api.reports()).item;
  if(keys.length)await Promise.all(keys.map(k=>loadResource(k)));
  if(activePage===page&&(keys.length||page==='reports'))renderPage()
 }catch(err){toast(describeError(err))}}
function pager(key){const m=store.meta[key];if(!m||m.total<=m.pageSize)return '';const pages=Math.ceil(m.total/m.pageSize);
 return `<div class="module-toolbar"><span class="muted-cell">Page ${m.page} of ${pages} · ${m.total} records</span><span>${m.page>1?actionButton('page','← Previous',key+'|-1'):''}${m.page<pages?actionButton('page','Next →',key+'|1'):''}</span></div>`}
function cleanPayload(v){return Object.fromEntries(Object.entries(v).map(([k,x])=>[k,k==='password'?x:String(x).trim()]).filter(([k,x])=>x!==''||k==='phone'))}
async function initialize(){
 const now=new Date();$('#todayLabel').textContent=now.toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'}).toUpperCase();
 $('#loginForm').addEventListener('submit',async e=>{e.preventDefault();
  const identity=$('#loginIdentity').value.trim(),password=$('#loginPassword').value;
  if(!identity||!password){$('#loginFeedback').textContent='Enter your university email or ID and password.';return}
  const submit=$('.login-submit');submit.disabled=true;$('#loginFeedback').textContent='Signing in…';
  try{const session=await api.auth.login({identity,password});const role=normalizeRole(session.user&&session.user.role);
   if(!role)throw new Error('Your account does not have a recognised university role.');
   activeRole=role;$('#loginFeedback').textContent='';$('#loginPassword').value='';await mountShell(session.user)
  }catch(err){activeRole=null;$('#loginFeedback').textContent=err.message}finally{submit.disabled=false}});
 $('#forgotPasswordButton').addEventListener('click',async()=>{try{await api.auth.forgotPassword()}catch(err){$('#loginFeedback').textContent=err.message}});
 $('#logoutButton').addEventListener('click',async()=>{await api.auth.logout();activeRole=null;resetStore();$('#appShell').hidden=true;$('#loginScreen').hidden=false;history.replaceState(null,'',location.pathname);$('#loginPassword').value='';$('#loginFeedback').textContent='';toast('You have been logged out.')});
 $('#menuToggle').addEventListener('click',()=>$('#sidebar').classList.toggle('sidebar-open'));
 $('#notificationButton').addEventListener('click',()=>navigate(canSee('notices')?'notices':'dashboard'));
 $('#recordForm').addEventListener('submit',async e=>{
  if(e.submitter&&e.submitter.value==='cancel')return;e.preventDefault();
  const ctx=dialogContext;const button=$('#saveRecordButton');button.disabled=true;
  try{const payload=cleanPayload(formObject(e.currentTarget));
   if(ctx.id)await api.update(RESOURCE[ctx.resource],ctx.id,payload);else await api.create(RESOURCE[ctx.resource],payload);
   $('#recordDialog').close();await refreshAfterWrite(ctx.resource);renderPage();toast(ctx.id?'Changes saved.':'Record created.')
  }catch(err){toast(describeError(err))}finally{button.disabled=false}});
 bindForms();
 try{const user=await api.auth.currentUser();const role=normalizeRole(user&&user.role);
  if(user&&role){activeRole=role;await mountShell(user)}
 }catch(err){$('#loginFeedback').textContent='Unable to reach the server. Please try again.'}}
document.addEventListener('DOMContentLoaded',initialize);
