from functools import wraps

from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import (Attendance, Complaint, Course, Department, Enrollment,
                     Faculty, Notice, Result, Schedule, Student)
from .views import error


# ---------- সাহায্যকারী ----------

def api_login(view):
    """Sign-in না থাকলে 401 দেয়।"""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return error('unauthenticated', 'Not signed in.', 401)
        return view(request, *args, **kwargs)
    return wrapper


def forbidden():
    return error('forbidden', 'You do not have access to this resource.', 403)


def paginate(request, qs, serialize):
    try:
        page = max(int(request.GET.get('page', 1)), 1)
        size = min(max(int(request.GET.get('page_size', 50)), 1), 200)
    except ValueError:
        return error('bad_request', 'page and page_size must be numbers.', 400)
    total = qs.count()
    items = [serialize(row) for row in qs[(page - 1) * size: page * size]]
    return JsonResponse({'items': items, 'total': total, 'page': page, 'page_size': size})


def ordinal(n):
    return {1: '1st', 2: '2nd', 3: '3rd'}.get(n, f'{n}th')


GRADE_POINT = {'A+': 4.0, 'A': 3.75, 'A-': 3.5, 'B+': 3.25, 'B': 3.0,
               'B-': 2.75, 'C+': 2.5, 'C': 2.25, 'D': 2.0, 'F': 0.0}
DAY_NAME = {'Sat': 'Saturday', 'Sun': 'Sunday', 'Mon': 'Monday', 'Tue': 'Tuesday',
            'Wed': 'Wednesday', 'Thu': 'Thursday', 'Fri': 'Friday'}
AUDIENCE_LABEL = {'all': 'All users', 'students': 'Students', 'faculty': 'Faculty',
                  'students_faculty': 'Students and Faculty'}
COMPLAINT_STATUS = {'pending': 'Pending', 'in_progress': 'In Review', 'resolved': 'Resolved'}


# ---------- Serializer: DB row -> frontend-এর JSON ----------

def ser_student(s):
    return {'id': s.student_code, 'name': s.user.full_name, 'email': s.user.email,
            'department': s.dept.name, 'batch': s.batch,
            'year': f'{ordinal(s.current_year)} Year', 'semester': ordinal(s.current_semester),
            'status': s.status.title(), 'phone': s.phone, 'gender': s.gender}


def ser_teacher(f):
    return {'id': f.faculty_code, 'name': f.user.full_name, 'email': f.user.email,
            'department': f.dept.name, 'designation': f.designation, 'phone': f.phone,
            'status': 'Active' if f.user.is_active else 'Inactive'}


def ser_department(d):
    head = d.head_faculty.user.full_name if d.head_faculty else None
    return {'id': d.code, 'code': d.code, 'name': d.name, 'head': head,
            'students': d.student_count, 'teachers': d.teacher_count}


def ser_course(c):
    return {'id': c.code, 'title': c.name, 'department': c.dept.name,
            'teacher': c.faculty.user.full_name if c.faculty else None,
            'credits': float(c.credit)}


def ser_schedule(s):
    c = s.course
    return {'day': DAY_NAME[s.day], 'start': s.start_time.strftime('%H:%M'),
            'end': s.end_time.strftime('%H:%M'), 'course': c.name, 'code': c.code,
            'room': s.room, 'teacher': c.faculty.user.full_name if c.faculty else None}


def ser_enrollment(e):
    return {'id': e.id, 'studentId': e.student.student_code, 'student': e.student.user.full_name,
            'course': e.course.code, 'courseTitle': e.course.name, 'semester': e.semester}


def ser_attendance(a):
    return {'date': a.date.isoformat(), 'studentId': a.student.student_code,
            'student': a.student.user.full_name, 'course': a.course.code,
            'status': a.status.title()}


def ser_result(r):
    return {'studentId': r.student.student_code, 'student': r.student.user.full_name,
            'course': r.course.code, 'semester': r.semester, 'assessment': r.assessment,
            'marks': float(r.marks) if r.marks is not None else None, 'grade': r.grade,
            'point': GRADE_POINT.get(r.grade)}


def ser_notice(n):
    return {'id': n.id, 'title': n.title, 'category': n.category,
            'date': n.created_at.date().isoformat(), 'audience': AUDIENCE_LABEL[n.audience],
            'body': n.body, 'postedBy': n.posted_by.full_name}


def ser_complaint(c):
    s = getattr(c.user, 'student', None)
    return {'id': c.id, 'studentId': s.student_code if s else None, 'name': c.user.full_name,
            'subject': c.subject, 'category': c.category, 'details': c.message,
            'status': COMPLAINT_STATUS[c.status], 'response': c.response,
            'date': c.created_at.date().isoformat()}


# ---------- প্রতিটা resource: কে কী দেখবে ----------

def list_students(request):
    role, user = request.user.role, request.user
    qs = Student.objects.select_related('user', 'dept')
    if role == 'student':
        qs = qs.filter(user=user)
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(student_code__icontains=q) | Q(user__full_name__icontains=q) |
                       Q(user__email__icontains=q))
    if request.GET.get('status'):
        qs = qs.filter(status=request.GET['status'].lower())
    return paginate(request, qs.order_by('student_code'), ser_student)


def list_teachers(request):
    if request.user.role == 'student':
        return forbidden()
    qs = Faculty.objects.select_related('user', 'dept')
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(faculty_code__icontains=q) | Q(user__full_name__icontains=q) |
                       Q(user__email__icontains=q))
    return paginate(request, qs.order_by('faculty_code'), ser_teacher)


def list_departments(request):
    qs = (Department.objects.select_related('head_faculty__user')
          .annotate(student_count=Count('student', distinct=True),
                    teacher_count=Count('faculty', distinct=True)))
    return paginate(request, qs.order_by('code'), ser_department)


def my_profile(request):
    """student হলে নিজের Student row, faculty হলে নিজের Faculty row।"""
    if hasattr(request, '_profile'):
        return request._profile
    user = request.user
    profile = None
    if user.role == 'student':
        profile = Student.objects.filter(user=user).first()
    elif user.role == 'faculty':
        profile = Faculty.objects.filter(user=user).first()
    request._profile = profile
    return profile


def list_courses(request):
    role, me = request.user.role, my_profile(request)
    qs = Course.objects.select_related('dept', 'faculty__user')
    if role == 'faculty':
        qs = qs.filter(faculty=me)
    elif role == 'student':
        qs = qs.filter(enrollment__student=me).distinct()
    return paginate(request, qs.order_by('code'), ser_course)


def list_schedules(request):
    role, me = request.user.role, my_profile(request)
    qs = Schedule.objects.select_related('course__faculty__user')
    if role == 'faculty':
        qs = qs.filter(course__faculty=me)
    elif role == 'student':
        qs = qs.filter(course__enrollment__student=me).distinct()
    return paginate(request, qs.order_by('course__code', 'id'), ser_schedule)


def list_enrollments(request):
    role, me = request.user.role, my_profile(request)
    qs = Enrollment.objects.select_related('student__user', 'course')
    if role == 'faculty':
        qs = qs.filter(course__faculty=me)
    elif role == 'student':
        qs = qs.filter(student=me)
    if request.GET.get('course'):
        qs = qs.filter(course__code=request.GET['course'])
    return paginate(request, qs.order_by('id'), ser_enrollment)


def list_attendance(request):
    role, me = request.user.role, my_profile(request)
    qs = Attendance.objects.select_related('student__user', 'course')
    if role == 'student':
        qs = qs.filter(student=me)
    if request.GET.get('course'):
        qs = qs.filter(course__code=request.GET['course'])
    if request.GET.get('student') and role != 'student':
        qs = qs.filter(student__student_code=request.GET['student'])
    if request.GET.get('date'):
        qs = qs.filter(date=request.GET['date'])
    return paginate(request, qs.order_by('-date', 'id'), ser_attendance)


def list_results(request):
    role, me = request.user.role, my_profile(request)
    qs = Result.objects.select_related('student__user', 'course')
    if role == 'student':
        qs = qs.filter(student=me)
    if request.GET.get('course'):
        qs = qs.filter(course__code=request.GET['course'])
    if request.GET.get('student') and role != 'student':
        qs = qs.filter(student__student_code=request.GET['student'])
    if request.GET.get('assessment'):
        qs = qs.filter(assessment=request.GET['assessment'])
    return paginate(request, qs.order_by('student__student_code', 'course__code', 'assessment'),
                    ser_result)


def list_notices(request):
    role = request.user.role
    qs = Notice.objects.select_related('posted_by')
    if role == 'student':
        qs = qs.filter(audience__in=['all', 'students', 'students_faculty'])
    elif role == 'faculty':
        qs = qs.filter(audience__in=['all', 'faculty', 'students_faculty'])
    return paginate(request, qs.order_by('-created_at', '-id'), ser_notice)


def list_complaints(request):
    role = request.user.role
    if role == 'faculty':
        return forbidden()
    qs = Complaint.objects.select_related('user__student')
    if role == 'student':
        qs = qs.filter(user=request.user)
    return paginate(request, qs.order_by('-created_at', '-id'), ser_complaint)


RESOURCES = {
    'students': list_students, 'teachers': list_teachers, 'departments': list_departments,
    'courses': list_courses, 'schedules': list_schedules, 'enrollments': list_enrollments,
    'attendance': list_attendance, 'results': list_results, 'notices': list_notices,
    'complaints': list_complaints,
}


@api_login
@require_http_methods(['GET', 'POST'])
def resource_list(request, resource):
    if request.method == 'POST':
        from . import writes
        return writes.run(request, resource, 'create')
    handler = RESOURCES.get(resource)
    if handler is None:
        return error('not_found', 'Unknown resource.', 404)
    if request.user.role in ('student', 'faculty') and my_profile(request) is None:
        return error('no_profile', 'No profile is linked to this account.', 403)
    return handler(request)


@api_login
@require_http_methods(['PATCH', 'PUT', 'DELETE'])
def resource_item(request, resource, ident):
    from . import writes
    action = 'delete' if request.method == 'DELETE' else 'update'
    return writes.run(request, resource, action, ident)


# ---------- Reports (admin ও teacher) ----------

@api_login
@require_http_methods(['GET'])
def reports_overview(request):
    if request.user.role == 'student':
        return forbidden()
    att = Attendance.objects.aggregate(total=Count('id'), present=Count('id', filter=Q(status='present')))
    rate = round(att['present'] * 100 / att['total'], 1) if att['total'] else 0
    avg = Result.objects.filter(assessment='Final').aggregate(a=Avg('marks'))['a']
    departments = [{'name': d.name, 'students': d.student_count, 'teachers': d.teacher_count}
                   for d in Department.objects.annotate(
                       student_count=Count('student', distinct=True),
                       teacher_count=Count('faculty', distinct=True)).order_by('code')]
    return JsonResponse({'item': {
        'students': Student.objects.count(), 'teachers': Faculty.objects.count(),
        'departments': Department.objects.count(), 'courses': Course.objects.count(),
        'attendanceRate': rate, 'averageMarks': round(float(avg), 1) if avg is not None else None,
        'departmentSummary': departments}})
