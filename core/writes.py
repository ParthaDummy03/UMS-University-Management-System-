import json
import random
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.utils import timezone

from .api import (AUDIENCE_LABEL, COMPLAINT_STATUS, DAY_NAME, forbidden, ser_attendance,
                  ser_complaint, ser_course, ser_department, ser_enrollment, ser_notice,
                  ser_result, ser_schedule, ser_student, ser_teacher)
from .models import (Attendance, Complaint, Course, Department, Enrollment, Faculty, Notice,
                     Result, Schedule, Student, User)
from .views import error


# ---------- Error ও validation ----------

class ApiError(Exception):
    def __init__(self, code, message, status=400, fields=None):
        self.code, self.message, self.status, self.fields = code, message, status, fields or {}


def fail(fields):
    raise ApiError('validation_error', 'Please correct the highlighted fields.', 422, fields)


def read_body(request):
    try:
        body = json.loads(request.body or b'{}')
    except ValueError:
        raise ApiError('bad_request', 'Request body must be valid JSON.')
    if not isinstance(body, dict):
        raise ApiError('bad_request', 'Request body must be a JSON object.')
    return body


def clean_text(body, key, errs, required=True, max_len=255):
    value = body.get(key)
    if value is None or str(value).strip() == '':
        if required:
            errs[key] = 'This field is required.'
        return None
    value = str(value).strip()
    if len(value) > max_len:
        errs[key] = f'Use at most {max_len} characters.'
    return value


def clean_email(body, errs, user=None, required=True):
    value = clean_text(body, 'email', errs, required, 254)
    if not value:
        return None
    try:
        validate_email(value)
    except DjangoValidationError:
        errs['email'] = 'Enter a valid email address.'
        return None
    value = value.lower()
    taken = User.objects.filter(email=value)
    if user is not None:
        taken = taken.exclude(pk=user.pk)
    if taken.exists():
        errs['email'] = 'This email is already in use.'
    return value


def clean_password(body, errs, required=True):
    value = body.get('password')
    if value in (None, ''):
        if required:
            errs['password'] = 'This field is required.'
        return None
    value = str(value)
    if len(value) < 8:
        errs['password'] = 'Use at least 8 characters.'
    return value


def pick(body, key, choices, errs, default=None):
    value = body.get(key)
    if value in (None, ''):
        return default
    wanted = str(value).strip().lower().replace(' ', '_')
    for choice in choices:
        if wanted == choice.lower().replace(' ', '_'):
            return choice
    errs[key] = 'Choose one of: ' + ', '.join(choices)
    return default


def clean_date(body, key, errs):
    value = body.get(key)
    if value in (None, ''):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        errs[key] = 'Use the format YYYY-MM-DD.'
        return None


def clean_time(body, key, errs):
    value = str(body.get(key, '')).strip()
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            pass
    errs[key] = 'Use the format HH:MM.'
    return None


def clean_int(body, key, errs, low, high):
    match = re.match(r'\d+', str(body.get(key, '')).strip())
    if not match or not low <= int(match.group()) <= high:
        errs[key] = f'Enter a number from {low} to {high}.'
        return None
    return int(match.group())


def clean_department(body, errs, key='department', required=True):
    value = body.get(key)
    if value in (None, ''):
        if required:
            errs[key] = 'This field is required.'
        return None
    value = str(value).strip()
    dept = Department.objects.filter(Q(code=value) | Q(name=value)).first()
    if dept is None:
        errs[key] = 'Unknown department.'
    return dept


def clean_faculty(body, errs, key):
    value = body.get(key)
    if value in (None, ''):
        return None
    fac = Faculty.objects.select_related('user').filter(faculty_code=str(value).strip()).first()
    if fac is None:
        errs[key] = 'Unknown teacher ID.'
    return fac


def find_by_code(model, field, value, errs, key):
    obj = model.objects.filter(**{field: str(value or '').strip()}).first()
    if obj is None:
        errs[key] = 'Not found.'
    return obj


# ---------- Students ----------

def study_level(batch):
    semester = min(max((timezone.now().year - int(batch)) * 2 + 1, 1), 8)
    return (semester + 1) // 2, semester


def new_student_code(batch, dept):
    for _ in range(50):
        code = f'{batch[2:]}{random.randint(10000, 99999)}{dept.code}'
        if not Student.objects.filter(student_code=code).exists():
            return code
    raise ApiError('server_error', 'Could not generate a student ID. Try again.', 500)


def check_batch(body, errs):
    batch = clean_text(body, 'batch', errs, max_len=4)
    if batch and not re.fullmatch(r'20\d\d', batch):
        errs['batch'] = 'Use a 4-digit year such as 2025.'
        return None
    return batch


def create_student(request, body):
    errs = {}
    name = clean_text(body, 'name', errs, max_len=150)
    dept = clean_department(body, errs)
    batch = check_batch(body, errs)
    password = clean_password(body, errs)
    email = clean_email(body, errs, required=False)
    phone = clean_text(body, 'phone', errs, required=False, max_len=20)
    status = pick(body, 'status', ['active', 'inactive'], errs, default='active')
    gender = pick(body, 'gender', ['male', 'female'], errs)
    dob = clean_date(body, 'dateOfBirth', errs)
    if errs:
        fail(errs)
    code = new_student_code(batch, dept)
    email = email or f'{code}@student.lotus.edu'
    if User.objects.filter(email=email).exists():
        fail({'email': 'This email is already in use.'})
    user = User(email=email, full_name=name, role='student', is_superuser=0, is_staff=0,
                is_active=1, date_joined=timezone.now())
    user.set_password(password)
    user.save()
    year, semester = study_level(batch)
    return Student.objects.create(user=user, student_code=code, dept=dept, batch=batch,
                                  status=status, phone=phone, gender=gender, date_of_birth=dob,
                                  current_year=year, current_semester=semester)


def update_student(request, s, body):
    errs, u = {}, s.user
    if 'name' in body:
        v = clean_text(body, 'name', errs, max_len=150)
        if v:
            u.full_name = v
    if 'email' in body:
        v = clean_email(body, errs, user=u)
        if v:
            u.email = v
    if 'password' in body:
        v = clean_password(body, errs)
        if v:
            u.set_password(v)
    if 'phone' in body:
        s.phone = clean_text(body, 'phone', errs, required=False, max_len=20)
    if 'status' in body:
        s.status = pick(body, 'status', ['active', 'inactive'], errs, default=s.status)
    if 'gender' in body:
        s.gender = pick(body, 'gender', ['male', 'female'], errs)
    if 'dateOfBirth' in body:
        s.date_of_birth = clean_date(body, 'dateOfBirth', errs)
    if 'department' in body:
        d = clean_department(body, errs)
        if d:
            s.dept = d
    if 'batch' in body:
        v = check_batch(body, errs)
        if v:
            s.batch = v
    if 'year' in body:
        v = clean_int(body, 'year', errs, 1, 6)
        if v is not None:
            s.current_year = v
    if 'semester' in body:
        v = clean_int(body, 'semester', errs, 1, 12)
        if v is not None:
            s.current_semester = v
    if errs:
        fail(errs)
    u.save()
    s.save()
    return s


def delete_student(request, s):
    s.user.delete()


# ---------- Teachers ----------

def new_faculty_code(dept):
    prefix = 'F' + dept.code
    codes = Faculty.objects.filter(faculty_code__startswith=prefix).values_list('faculty_code', flat=True)
    n = max([int(c[3:]) for c in codes if c[3:].isdigit()], default=0) + 1
    while Faculty.objects.filter(faculty_code=f'{prefix}{n:03d}').exists():
        n += 1
    return f'{prefix}{n:03d}'


def create_teacher(request, body):
    errs = {}
    name = clean_text(body, 'name', errs, max_len=150)
    dept = clean_department(body, errs)
    password = clean_password(body, errs)
    email = clean_email(body, errs, required=False)
    designation = clean_text(body, 'designation', errs, required=False, max_len=100)
    phone = clean_text(body, 'phone', errs, required=False, max_len=20)
    joined = clean_date(body, 'joinedOn', errs)
    if errs:
        fail(errs)
    code = new_faculty_code(dept)
    email = email or f'{code.lower()}@lotus.edu'
    if User.objects.filter(email=email).exists():
        fail({'email': 'This email is already in use.'})
    user = User(email=email, full_name=name, role='faculty', is_superuser=0, is_staff=0,
                is_active=1, date_joined=timezone.now())
    user.set_password(password)
    user.save()
    return Faculty.objects.create(user=user, faculty_code=code, dept=dept, designation=designation,
                                  phone=phone, joined_on=joined)


def update_teacher(request, f, body):
    errs, u = {}, f.user
    if 'name' in body:
        v = clean_text(body, 'name', errs, max_len=150)
        if v:
            u.full_name = v
    if 'email' in body:
        v = clean_email(body, errs, user=u)
        if v:
            u.email = v
    if 'password' in body:
        v = clean_password(body, errs)
        if v:
            u.set_password(v)
    if 'status' in body:
        u.is_active = 1 if pick(body, 'status', ['Active', 'Inactive'], errs, default='Active') == 'Active' else 0
    if 'designation' in body:
        f.designation = clean_text(body, 'designation', errs, required=False, max_len=100)
    if 'phone' in body:
        f.phone = clean_text(body, 'phone', errs, required=False, max_len=20)
    if 'joinedOn' in body:
        f.joined_on = clean_date(body, 'joinedOn', errs)
    if 'department' in body:
        d = clean_department(body, errs)
        if d:
            f.dept = d
    if errs:
        fail(errs)
    u.save()
    f.save()
    return f


def delete_teacher(request, f):
    f.user.delete()


# ---------- Departments ----------

def dept_qs():
    return (Department.objects.select_related('head_faculty__user')
            .annotate(student_count=Count('student', distinct=True),
                      teacher_count=Count('faculty', distinct=True)))


def create_department(request, body):
    errs = {}
    name = clean_text(body, 'name', errs, max_len=100)
    code = clean_text(body, 'code', errs, max_len=2)
    if code and not re.fullmatch(r'\d\d', code):
        errs['code'] = 'Use a 2-digit code such as 12.'
    if name and Department.objects.filter(name=name).exists():
        errs['name'] = 'A department with this name already exists.'
    if code and Department.objects.filter(code=code).exists():
        errs['code'] = 'This code is already used.'
    head = clean_faculty(body, errs, 'headId')
    if errs:
        fail(errs)
    return Department.objects.create(name=name, code=code, head_faculty=head)


def update_department(request, d, body):
    errs = {}
    if 'name' in body:
        v = clean_text(body, 'name', errs, max_len=100)
        if v and Department.objects.filter(name=v).exclude(pk=d.pk).exists():
            errs['name'] = 'A department with this name already exists.'
        elif v:
            d.name = v
    if 'headId' in body:
        d.head_faculty = clean_faculty(body, errs, 'headId')
    if errs:
        fail(errs)
    Department.objects.filter(pk=d.pk).update(name=d.name, head_faculty=d.head_faculty)
    return d


def delete_department(request, d):
    Department.objects.filter(pk=d.pk).delete()


# ---------- Courses ----------

def clean_credits(body, errs):
    try:
        value = Decimal(str(body.get('credits'))).quantize(Decimal('0.1'))
    except (InvalidOperation, ValueError):
        errs['credits'] = 'Enter a number such as 3 or 1.5.'
        return None
    if not Decimal('0.5') <= value <= Decimal('9'):
        errs['credits'] = 'Credits must be between 0.5 and 9.'
        return None
    return value


def create_course(request, body):
    errs = {}
    code = clean_text(body, 'code', errs, max_len=20)
    title = clean_text(body, 'title', errs, max_len=150)
    credits = clean_credits(body, errs)
    dept = clean_department(body, errs)
    teacher = clean_faculty(body, errs, 'teacherId')
    if code and Course.objects.filter(code=code).exists():
        errs['code'] = 'This course code already exists.'
    if errs:
        fail(errs)
    return Course.objects.create(code=code, name=title, credit=credits, dept=dept, faculty=teacher)


def update_course(request, c, body):
    errs = {}
    if 'title' in body:
        v = clean_text(body, 'title', errs, max_len=150)
        if v:
            c.name = v
    if 'credits' in body:
        v = clean_credits(body, errs)
        if v is not None:
            c.credit = v
    if 'department' in body:
        d = clean_department(body, errs)
        if d:
            c.dept = d
    if 'teacherId' in body:
        c.faculty = clean_faculty(body, errs, 'teacherId')
    if errs:
        fail(errs)
    c.save()
    return c


def delete_course(request, c):
    c.delete()


# ---------- Enrollments ----------

def create_enrollment(request, body):
    errs = {}
    student = find_by_code(Student, 'student_code', body.get('studentId'), errs, 'studentId')
    course = find_by_code(Course, 'code', body.get('course'), errs, 'course')
    semester = clean_text(body, 'semester', errs, max_len=20)
    if errs:
        fail(errs)
    if Enrollment.objects.filter(student=student, course=course, semester=semester).exists():
        raise ApiError('conflict', 'The student is already enrolled in this course for that semester.', 409)
    return Enrollment.objects.create(student=student, course=course, semester=semester)


def delete_enrollment(request, e):
    e.delete()


# ---------- Schedules ----------

DAY_LOOKUP = {**{k.lower(): k for k in DAY_NAME}, **{v.lower(): k for k, v in DAY_NAME.items()}}


def check_schedule_conflict(course, day, start, end, room, exclude_pk=None):
    clash = Schedule.objects.filter(day=day, start_time__lt=end, end_time__gt=start)
    if exclude_pk:
        clash = clash.exclude(pk=exclude_pk)
    if room and clash.filter(room=room).exists():
        raise ApiError('conflict', f'Room {room} is already booked at that time.', 409, {'room': 'Already booked.'})
    if course.faculty_id and clash.filter(course__faculty_id=course.faculty_id).exists():
        raise ApiError('conflict', 'The teacher already has a class at that time.', 409, {'course': 'Teacher is busy.'})


def create_schedule(request, body):
    errs = {}
    course = find_by_code(Course, 'code', body.get('course'), errs, 'course')
    day = DAY_LOOKUP.get(str(body.get('day', '')).strip().lower())
    if day is None:
        errs['day'] = 'Use a day name such as Sunday.'
    start, end = clean_time(body, 'start', errs), clean_time(body, 'end', errs)
    if start and end and end <= start:
        errs['end'] = 'End time must be after start time.'
    room = clean_text(body, 'room', errs, required=False, max_len=30)
    if errs:
        fail(errs)
    check_schedule_conflict(course, day, start, end, room)
    return Schedule.objects.create(course=course, day=day, start_time=start, end_time=end, room=room)


def update_schedule(request, s, body):
    errs = {}
    if 'course' in body:
        c = find_by_code(Course, 'code', body.get('course'), errs, 'course')
        if c:
            s.course = c
    if 'day' in body:
        day = DAY_LOOKUP.get(str(body.get('day', '')).strip().lower())
        if day is None:
            errs['day'] = 'Use a day name such as Sunday.'
        else:
            s.day = day
    if 'start' in body:
        v = clean_time(body, 'start', errs)
        if v:
            s.start_time = v
    if 'end' in body:
        v = clean_time(body, 'end', errs)
        if v:
            s.end_time = v
    if 'room' in body:
        s.room = clean_text(body, 'room', errs, required=False, max_len=30)
    if s.end_time <= s.start_time:
        errs['end'] = 'End time must be after start time.'
    if errs:
        fail(errs)
    check_schedule_conflict(s.course, s.day, s.start_time, s.end_time, s.room, exclude_pk=s.pk)
    s.save()
    return s


def delete_schedule(request, s):
    s.delete()


# ---------- Notices ----------

NOTICE_CATEGORIES = ['Academic', 'General', 'Event', 'Finance']
AUDIENCE_LOOKUP = {**{k: k for k in AUDIENCE_LABEL}, **{v.lower(): k for k, v in AUDIENCE_LABEL.items()}}


def clean_audience(body, errs, default=None):
    value = body.get('audience')
    if value in (None, ''):
        return default
    key = AUDIENCE_LOOKUP.get(str(value).strip().lower())
    if key is None:
        errs['audience'] = 'Choose: ' + ', '.join(AUDIENCE_LABEL.values())
    return key or default


def create_notice(request, body):
    errs = {}
    title = clean_text(body, 'title', errs, max_len=200)
    text = clean_text(body, 'body', errs, max_len=5000)
    category = pick(body, 'category', NOTICE_CATEGORIES, errs, default='General')
    audience = clean_audience(body, errs, default='all')
    if errs:
        fail(errs)
    return Notice.objects.create(title=title, body=text, category=category, audience=audience,
                                 posted_by=request.user, created_at=timezone.now())


def update_notice(request, n, body):
    errs = {}
    if 'title' in body:
        v = clean_text(body, 'title', errs, max_len=200)
        if v:
            n.title = v
    if 'body' in body:
        v = clean_text(body, 'body', errs, max_len=5000)
        if v:
            n.body = v
    if 'category' in body:
        n.category = pick(body, 'category', NOTICE_CATEGORIES, errs, default=n.category)
    if 'audience' in body:
        n.audience = clean_audience(body, errs, default=n.audience)
    if errs:
        fail(errs)
    n.save()
    return n


def delete_notice(request, n):
    n.delete()


# ---------- Complaints ----------

COMPLAINT_CATEGORIES = ['Academic', 'Facilities', 'Administrative', 'Finance', 'Other']
STATUS_LOOKUP = {**{k: k for k in COMPLAINT_STATUS}, **{v.lower(): k for k, v in COMPLAINT_STATUS.items()}}


def create_complaint(request, body):
    errs = {}
    subject = clean_text(body, 'subject', errs, max_len=200)
    details = clean_text(body, 'details', errs, max_len=5000)
    category = pick(body, 'category', COMPLAINT_CATEGORIES, errs, default='Other')
    if errs:
        fail(errs)
    return Complaint.objects.create(user=request.user, subject=subject, message=details,
                                    category=category, status='pending',
                                    created_at=timezone.now())


def update_complaint(request, c, body):
    errs = {}
    if 'status' in body:
        key = STATUS_LOOKUP.get(str(body.get('status', '')).strip().lower())
        if key is None:
            errs['status'] = 'Choose: ' + ', '.join(COMPLAINT_STATUS.values())
        else:
            c.status = key
    if 'response' in body:
        c.response = clean_text(body, 'response', errs, required=False, max_len=5000)
    if errs:
        fail(errs)
    c.save()
    return c


def delete_complaint(request, c):
    c.delete()



# ---------- Attendance ও Results (admin + teacher) ----------

GRADE_SCALE = [(80, 'A+'), (75, 'A'), (70, 'A-'), (65, 'B+'), (60, 'B'),
               (55, 'B-'), (50, 'C+'), (45, 'C'), (40, 'D')]
ASSESSMENTS = ['Midterm', 'Final', 'Quiz', 'Assignment']


def grade_for(marks):
    """Marks থেকে grade সার্ভার নিজে বের করে, frontend-এর পাঠানো grade বিশ্বাস করা হয় না।"""
    for limit, grade in GRADE_SCALE:
        if marks >= limit:
            return grade
    return 'F'


def check_can_record(request, course, student):
    """Teacher শুধু নিজের কোর্সে লিখতে পারবে, আর student ওই কোর্সে enrolled থাকতে হবে।"""
    if request.user.role == 'faculty':
        me = Faculty.objects.filter(user=request.user).first()
        if me is None or course.faculty_id != me.id:
            raise ApiError('forbidden', 'You can only record data for courses assigned to you.', 403)
    if not Enrollment.objects.filter(student=student, course=course).exists():
        raise ApiError('not_enrolled', 'This student is not enrolled in that course.', 409,
                       {'studentId': 'Not enrolled in this course.'})


def create_attendance(request, body):
    errs = {}
    student = find_by_code(Student, 'student_code', body.get('studentId'), errs, 'studentId')
    course = find_by_code(Course, 'code', body.get('course'), errs, 'course')
    day = clean_date(body, 'date', errs)
    if day is None and 'date' not in errs:
        errs['date'] = 'This field is required.'
    status = pick(body, 'status', ['present', 'absent', 'late'], errs)
    if status is None and 'status' not in errs:
        errs['status'] = 'This field is required.'
    if errs:
        fail(errs)
    check_can_record(request, course, student)
    row = Attendance.objects.filter(student=student, course=course, date=day).first()
    if row:
        row.status = status
        row.save()
        return row
    return Attendance.objects.create(student=student, course=course, date=day, status=status)


def create_result(request, body):
    errs = {}
    student = find_by_code(Student, 'student_code', body.get('studentId'), errs, 'studentId')
    course = find_by_code(Course, 'code', body.get('course'), errs, 'course')
    assessment = pick(body, 'assessment', ASSESSMENTS, errs)
    if assessment is None and 'assessment' not in errs:
        errs['assessment'] = 'This field is required.'
    marks = None
    try:
        marks = Decimal(str(body.get('marks'))).quantize(Decimal('0.01'))
        if not Decimal('0') <= marks <= Decimal('100'):
            raise ValueError
    except (InvalidOperation, ValueError):
        errs['marks'] = 'Enter a number from 0 to 100.'
    if errs:
        fail(errs)
    check_can_record(request, course, student)
    enrollment = Enrollment.objects.filter(student=student, course=course).order_by('-id').first()
    semester = enrollment.semester
    row = Result.objects.filter(student=student, course=course, semester=semester,
                                assessment=assessment).first()
    if row:
        row.marks, row.grade = marks, grade_for(marks)
        row.save()
        return row
    return Result.objects.create(student=student, course=course, semester=semester,
                                 assessment=assessment, marks=marks, grade=grade_for(marks))

# ---------- Resource -> কোন function চলবে ----------

def by_pk(queryset):
    def find(ident):
        try:
            pk = int(ident)
        except (TypeError, ValueError):
            return None
        return queryset().filter(pk=pk).first()
    return find


SPECS = {
    'students': {
        'find': lambda i: Student.objects.select_related('user', 'dept').filter(student_code=i).first(),
        'key': lambda o: o.student_code, 'ser': ser_student,
        'create': create_student, 'update': update_student, 'delete': delete_student},
    'teachers': {
        'find': lambda i: Faculty.objects.select_related('user', 'dept').filter(faculty_code=i).first(),
        'key': lambda o: o.faculty_code, 'ser': ser_teacher,
        'create': create_teacher, 'update': update_teacher, 'delete': delete_teacher},
    'departments': {
        'find': lambda i: dept_qs().filter(code=i).first(),
        'key': lambda o: o.code, 'ser': ser_department,
        'create': create_department, 'update': update_department, 'delete': delete_department},
    'courses': {
        'find': lambda i: Course.objects.select_related('dept', 'faculty__user').filter(code=i).first(),
        'key': lambda o: o.code, 'ser': ser_course,
        'create': create_course, 'update': update_course, 'delete': delete_course},
    'enrollments': {
        'find': by_pk(lambda: Enrollment.objects.select_related('student__user', 'course')),
        'key': lambda o: str(o.pk), 'ser': ser_enrollment,
        'create': create_enrollment, 'delete': delete_enrollment},
    'schedules': {
        'find': by_pk(lambda: Schedule.objects.select_related('course__faculty__user')),
        'key': lambda o: str(o.pk), 'ser': ser_schedule,
        'create': create_schedule, 'update': update_schedule, 'delete': delete_schedule},
    'notices': {
        'find': by_pk(lambda: Notice.objects.select_related('posted_by')),
        'key': lambda o: str(o.pk), 'ser': ser_notice,
        'create': create_notice, 'update': update_notice, 'delete': delete_notice},
    'attendance': {
        'find': by_pk(lambda: Attendance.objects.select_related('student__user', 'course')),
        'key': lambda o: str(o.pk), 'ser': ser_attendance, 'create': create_attendance},
    'results': {
        'find': by_pk(lambda: Result.objects.select_related('student__user', 'course')),
        'key': lambda o: str(o.pk), 'ser': ser_result, 'create': create_result},
    'complaints': {
        'find': by_pk(lambda: Complaint.objects.select_related('user__student')),
        'key': lambda o: str(o.pk), 'ser': ser_complaint,
        'create': create_complaint, 'update': update_complaint, 'delete': delete_complaint},
}


def run(request, resource, action, ident=None):
    spec = SPECS.get(resource)
    if spec is None or action not in spec:
        return error('method_not_allowed', 'This action is not supported for this resource.', 405)
    role = request.user.role
    if resource == 'complaints' and action == 'create':
        allowed = role == 'student'
    elif resource in ('attendance', 'results') and action == 'create':
        allowed = role in ('admin', 'faculty')
    else:
        allowed = role == 'admin'
    if not allowed:
        return forbidden()
    try:
        with transaction.atomic():
            if action == 'create':
                obj, status = spec['create'](request, read_body(request)), 201
            else:
                obj = spec['find'](ident)
                if obj is None:
                    raise ApiError('not_found', 'Record not found.', 404)
                if action == 'delete':
                    spec['delete'](request, obj)
                    return JsonResponse({'ok': True})
                obj, status = spec['update'](request, obj, read_body(request)), 200
            fresh = spec['find'](spec['key'](obj))
            return JsonResponse({'item': spec['ser'](fresh)}, status=status)
    except ApiError as e:
        return JsonResponse({'error': {'code': e.code, 'message': e.message, 'fields': e.fields}},
                            status=e.status)
    except IntegrityError:
        return error('conflict', 'This record is linked to other data or already exists, '
                                 'so the change was refused.', 409)
