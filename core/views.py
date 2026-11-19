import json
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .models import User, Student, Faculty, Admin

ROLE_MAP = {'admin': 'ADMIN', 'faculty': 'TEACHER', 'student': 'STUDENT'}


def error(code, message, status):
    return JsonResponse({'error': {'code': code, 'message': message}}, status=status)


def user_payload(user):
    """Frontend-কে যে user-এর তথ্য দেওয়া হবে।"""
    code, department = None, None
    if user.role == 'student':
        p = Student.objects.filter(user=user).select_related('dept').first()
        if p:
            code, department = p.student_code, p.dept.name
    elif user.role == 'faculty':
        p = Faculty.objects.filter(user=user).select_related('dept').first()
        if p:
            code, department = p.faculty_code, p.dept.name
    else:
        p = Admin.objects.filter(user=user).first()
        if p:
            code, department = p.admin_code, 'Central Administration'
    return {
        'id': code,
        'name': user.full_name,
        'email': user.email,
        'role': ROLE_MAP[user.role],
        'department': department,
    }


def email_from_identity(identity):
    """Email বা university ID (student/faculty/admin code), যেটাই দেওয়া হোক।"""
    if '@' in identity:
        return identity
    for model, field in ((Student, 'student_code'), (Faculty, 'faculty_code'), (Admin, 'admin_code')):
        p = model.objects.filter(**{field: identity}).select_related('user').first()
        if p:
            return p.user.email
    return None


@csrf_exempt
@ensure_csrf_cookie
@require_http_methods(['POST'])
def login_view(request):
    try:
        body = json.loads(request.body)
        identity = str(body.get('identity', '')).strip()
        password = str(body.get('password', ''))
    except (ValueError, AttributeError):
        return error('bad_request', 'Invalid request.', 400)
    if not identity or not password:
        return error('bad_request', 'Enter your ID or email and password.', 400)

    key = 'login_fail:' + identity.lower()
    if cache.get(key, 0) >= 5:
        return error('too_many_attempts', 'Too many failed attempts. Try again in 15 minutes.', 429)

    email = email_from_identity(identity)
    user = authenticate(request, username=email, password=password) if email else None
    if user is None:
        cache.set(key, cache.get(key, 0) + 1, 900)
        return error('invalid_credentials', 'Incorrect ID/email or password.', 401)

    cache.delete(key)
    login(request, user)
    return JsonResponse({'item': user_payload(user)})


@ensure_csrf_cookie
@require_http_methods(['GET'])
def me_view(request):
    if not request.user.is_authenticated:
        return error('unauthenticated', 'Not signed in.', 401)
    return JsonResponse({'item': user_payload(request.user)})


@csrf_exempt
@require_http_methods(['POST'])
def logout_view(request):
    logout(request)
    return JsonResponse({'ok': True})