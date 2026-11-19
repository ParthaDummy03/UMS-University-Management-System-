from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager


class User(AbstractBaseUser):
   
    email = models.CharField(max_length=254, unique=True)
    full_name = models.CharField(max_length=150)
    role = models.CharField(max_length=10)  # admin / faculty / student
    is_superuser = models.IntegerField(default=0)
    is_staff = models.IntegerField(default=0)
    is_active = models.IntegerField(default=1)
    date_joined = models.DateTimeField()

    USERNAME_FIELD = 'email'
    objects = BaseUserManager()

    class Meta:
        managed = False
        db_table = 'users'


class Department(models.Model):
    code = models.CharField(max_length=2, unique=True)
    name = models.CharField(max_length=100, unique=True)
    head_faculty = models.ForeignKey('Faculty', models.DO_NOTHING, db_column='head_faculty_id',
                                     null=True, blank=True, related_name='+')

    class Meta:
        managed = False
        db_table = 'departments'


class Admin(models.Model):
    user = models.OneToOneField(User, models.DO_NOTHING, db_column='user_id')
    admin_code = models.CharField(max_length=10, unique=True)
    designation = models.CharField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'admins'


class Faculty(models.Model):
    user = models.OneToOneField(User, models.DO_NOTHING, db_column='user_id')
    faculty_code = models.CharField(max_length=10, unique=True)
    dept = models.ForeignKey(Department, models.DO_NOTHING, db_column='dept_id')
    designation = models.CharField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    joined_on = models.DateField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'faculty'


class Student(models.Model):
    user = models.OneToOneField(User, models.DO_NOTHING, db_column='user_id')
    student_code = models.CharField(max_length=9, unique=True)
    dept = models.ForeignKey(Department, models.DO_NOTHING, db_column='dept_id')
    batch = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(max_length=10)  # active / inactive
    phone = models.CharField(max_length=20, null=True, blank=True)
    gender = models.CharField(max_length=10, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    current_year = models.IntegerField()
    current_semester = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'students'


class Course(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    credit = models.DecimalField(max_digits=3, decimal_places=1)
    dept = models.ForeignKey(Department, models.DO_NOTHING, db_column='dept_id')
    faculty = models.ForeignKey(Faculty, models.DO_NOTHING, db_column='faculty_id',
                                null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'courses'


class Enrollment(models.Model):
    student = models.ForeignKey(Student, models.DO_NOTHING, db_column='student_id')
    course = models.ForeignKey(Course, models.DO_NOTHING, db_column='course_id')
    semester = models.CharField(max_length=20)

    class Meta:
        managed = False
        db_table = 'enrollments'


class Attendance(models.Model):
    student = models.ForeignKey(Student, models.DO_NOTHING, db_column='student_id')
    course = models.ForeignKey(Course, models.DO_NOTHING, db_column='course_id')
    date = models.DateField()
    status = models.CharField(max_length=10)  # present / absent / late

    class Meta:
        managed = False
        db_table = 'attendance'


class Schedule(models.Model):
    course = models.ForeignKey(Course, models.DO_NOTHING, db_column='course_id')
    day = models.CharField(max_length=3)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=30, null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'schedules'


class Result(models.Model):
    student = models.ForeignKey(Student, models.DO_NOTHING, db_column='student_id')
    course = models.ForeignKey(Course, models.DO_NOTHING, db_column='course_id')
    semester = models.CharField(max_length=20)
    marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    grade = models.CharField(max_length=3, null=True, blank=True)
    assessment = models.CharField(max_length=20)

    class Meta:
        managed = False
        db_table = 'results'


class Complaint(models.Model):
    user = models.ForeignKey(User, models.DO_NOTHING, db_column='user_id')
    message = models.TextField()
    status = models.CharField(max_length=20)  # pending / in_progress / resolved
    response = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField()
    subject = models.CharField(max_length=200)
    category = models.CharField(max_length=20)

    class Meta:
        managed = False
        db_table = 'complaints'


class Notice(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    posted_by = models.ForeignKey(User, models.DO_NOTHING, db_column='posted_by')
    created_at = models.DateTimeField()
    category = models.CharField(max_length=20)
    audience = models.CharField(max_length=20)

    class Meta:
        managed = False
        db_table = 'notices'