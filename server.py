#!/usr/bin/env python3
"""Lotus University UMS: same-origin static server and SQLite-backed API."""

from __future__ import annotations

import hashlib
import hmac
import http.cookies
import json
import os
import re
import secrets
import sqlite3
import sys
import threading
import time
import uuid
from datetime import date, datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("UMS_DB_PATH", ROOT / "data" / "lotus_ums.sqlite3"))
SESSION_COOKIE = "lotus_ums_session"
SESSION_TTL = 12 * 60 * 60
MAX_BODY_BYTES = 1_000_000
PASSWORD_ITERATIONS = 600_000
ALLOWED_ROLES = {"ADMIN", "TEACHER", "STUDENT"}
COOKIE_SECURE = os.environ.get("UMS_COOKIE_SECURE", "0") == "1"
ALLOW_INITIAL_SETUP = os.environ.get("UMS_ALLOW_INITIAL_SETUP", "1") == "1"
ATTEMPTS_LOCK = threading.Lock()


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, fields: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.fields = fields or {}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 15000")
    return connection


def init_db() -> None:
    with connect_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            university_id TEXT NOT NULL UNIQUE COLLATE NOCASE,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('ADMIN','TEACHER','STUDENT')),
            password_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active','Inactive')),
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions(expires_at);
        CREATE TABLE IF NOT EXISTS login_attempts (
            attempt_key TEXT PRIMARY KEY,
            attempts INTEGER NOT NULL,
            window_started INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS departments (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            code TEXT NOT NULL UNIQUE,
            head TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY,
            user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL DEFAULT '',
            department_id TEXT REFERENCES departments(id) ON UPDATE CASCADE,
            year TEXT NOT NULL DEFAULT '', semester TEXT NOT NULL DEFAULT '',
            section TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'Active', phone TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS teachers (
            id TEXT PRIMARY KEY,
            user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL DEFAULT '',
            department_id TEXT REFERENCES departments(id) ON UPDATE CASCADE,
            designation TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'Active'
        );
        CREATE TABLE IF NOT EXISTS courses (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            department_id TEXT REFERENCES departments(id) ON UPDATE CASCADE,
            teacher_id TEXT REFERENCES teachers(id) ON UPDATE CASCADE,
            credits INTEGER NOT NULL DEFAULT 3 CHECK(credits BETWEEN 1 AND 10),
            semester TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL REFERENCES students(id) ON UPDATE CASCADE ON DELETE RESTRICT,
            course_id TEXT NOT NULL REFERENCES courses(id) ON UPDATE CASCADE ON DELETE RESTRICT,
            semester TEXT NOT NULL DEFAULT '', section TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active','Withdrawn')),
            UNIQUE(student_id, course_id, semester)
        );
        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id TEXT NOT NULL REFERENCES courses(id) ON UPDATE CASCADE ON DELETE RESTRICT,
            day TEXT NOT NULL CHECK(day IN ('Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday')),
            start_time TEXT NOT NULL, end_time TEXT NOT NULL, room TEXT NOT NULL DEFAULT '', section TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id INTEGER NOT NULL REFERENCES enrollments(id) ON DELETE RESTRICT,
            class_date TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Present','Absent','Late')),
            marked_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            UNIQUE(enrollment_id, class_date)
        );
        CREATE TABLE IF NOT EXISTS grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id INTEGER NOT NULL REFERENCES enrollments(id) ON DELETE RESTRICT,
            assessment TEXT NOT NULL, marks REAL NOT NULL CHECK(marks BETWEEN 0 AND 100),
            grade TEXT NOT NULL, point REAL NOT NULL,
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            UNIQUE(enrollment_id, assessment)
        );
        CREATE TABLE IF NOT EXISTS notices (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL,
            audience TEXT NOT NULL CHECK(audience IN ('All users','Students','Faculty','Students and Faculty')),
            body TEXT NOT NULL, published_at TEXT NOT NULL, author_id INTEGER REFERENCES users(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS complaints (
            id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL REFERENCES students(id) ON UPDATE CASCADE ON DELETE RESTRICT,
            subject TEXT NOT NULL, category TEXT NOT NULL, details TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Submitted' CHECK(status IN ('Submitted','In Review','Resolved')),
            created_at TEXT NOT NULL
        );
        """)
        seed_sample_records(db)


def seed_sample_records(db: sqlite3.Connection) -> None:
    if db.execute("SELECT COUNT(*) FROM departments").fetchone()[0]:
        return
    departments = [
        ("D01", "Computer Science & Engineering", "CSE", "Dr. Nadia Rahman"),
        ("D02", "Business Administration", "BBA", "Dr. Farhan Ahmed"),
        ("D03", "Electrical Engineering", "EEE", "Dr. Samira Karim"),
        ("D04", "Economics", "ECO", "Dr. Imran Hossain"),
        ("D05", "English", "ENG", "Dr. Tania Islam"),
    ]
    db.executemany("INSERT INTO departments(id,name,code,head) VALUES(?,?,?,?)", departments)
    students = [
        ("LU-2024-0841", "Sophia Rodriguez", "sophia.r@lotusuniversity.edu", "D01", "3rd Year", "6th", "CSE 6A", "Active", "+880 1712-000841"),
        ("LU-2025-0840", "James Wilson", "james.w@lotusuniversity.edu", "D02", "2nd Year", "4th", "BBA 4A", "Active", "+880 1712-000840"),
        ("LU-2023-0839", "Emily Chen", "emily.c@lotusuniversity.edu", "D04", "4th Year", "8th", "ECO 8A", "Pending", "+880 1712-000839"),
        ("LU-2026-0838", "Michael Taylor", "michael.t@lotusuniversity.edu", "D03", "1st Year", "2nd", "EEE 2A", "Active", "+880 1712-000838"),
        ("LU-2024-0712", "Ayesha Rahman", "ayesha.r@lotusuniversity.edu", "D01", "3rd Year", "6th", "CSE 6A", "Active", "+880 1811-000712"),
        ("LU-2025-0650", "Tanvir Hasan", "tanvir.h@lotusuniversity.edu", "D05", "2nd Year", "4th", "ENG 4A", "Active", "+880 1911-000650"),
    ]
    db.executemany("""INSERT INTO students(id,name,email,department_id,year,semester,section,status,phone)
        VALUES(?,?,?,?,?,?,?,?,?)""", students)
    teachers = [
        ("FAC-001", "Dr. Nadia Rahman", "nadia.r@lotusuniversity.edu", "D01", "Associate Professor", "Active"),
        ("FAC-002", "Prof. Farhan Ahmed", "farhan.a@lotusuniversity.edu", "D02", "Professor", "Active"),
        ("FAC-003", "Dr. Samira Karim", "samira.k@lotusuniversity.edu", "D03", "Assistant Professor", "Active"),
        ("FAC-004", "Mr. Imran Hossain", "imran.h@lotusuniversity.edu", "D04", "Lecturer", "Active"),
    ]
    db.executemany("""INSERT INTO teachers(id,name,email,department_id,designation,status)
        VALUES(?,?,?,?,?,?)""", teachers)
    courses = [
        ("CSE-310", "Data Structures & Algorithms", "D01", "FAC-001", 3, "6th"),
        ("CSE-322", "Database Management Systems", "D01", "FAC-001", 3, "6th"),
        ("CSE-201", "Object Oriented Programming", "D01", "FAC-001", 3, "4th"),
        ("BBA-210", "Principles of Marketing", "D02", "FAC-002", 3, "4th"),
        ("EEE-330", "Digital Signal Processing", "D03", "FAC-003", 3, "6th"),
    ]
    db.executemany("""INSERT INTO courses(id,title,department_id,teacher_id,credits,semester)
        VALUES(?,?,?,?,?,?)""", courses)
    enrollments = [
        ("LU-2024-0841", "CSE-310", "6th", "CSE 6A"),
        ("LU-2024-0841", "CSE-322", "6th", "CSE 6A"),
        ("LU-2024-0712", "CSE-310", "6th", "CSE 6A"),
        ("LU-2024-0712", "CSE-322", "6th", "CSE 6A"),
        ("LU-2025-0840", "BBA-210", "4th", "BBA 4A"),
    ]
    db.executemany("INSERT INTO enrollments(student_id,course_id,semester,section) VALUES(?,?,?,?)", enrollments)
    schedule_rows = [
        ("CSE-310", "Sunday", "09:00", "10:30", "Room 402", "CSE 6A"),
        ("CSE-322", "Sunday", "11:00", "12:30", "Lab 3", "CSE 6A"),
        ("CSE-310", "Monday", "10:00", "11:30", "Room 402", "CSE 6A"),
        ("CSE-322", "Tuesday", "09:00", "10:30", "Lab 3", "CSE 6A"),
        ("CSE-201", "Tuesday", "13:00", "14:30", "Room 205", "CSE 4B"),
        ("CSE-310", "Wednesday", "11:00", "12:30", "Room 402", "CSE 6A"),
        ("CSE-322", "Thursday", "10:00", "11:30", "Lab 3", "CSE 6A"),
        ("BBA-210", "Monday", "12:00", "13:30", "Room 104", "BBA 4A"),
    ]
    db.executemany("INSERT INTO schedule(course_id,day,start_time,end_time,room,section) VALUES(?,?,?,?,?,?)", schedule_rows)
    enrollment_ids = {
        (row["student_id"], row["course_id"]): row["id"]
        for row in db.execute("SELECT id,student_id,course_id FROM enrollments")
    }
    attendance = [
        ("LU-2024-0841", "CSE-310", "2026-11-16", "Present"),
        ("LU-2024-0712", "CSE-310", "2026-11-16", "Present"),
        ("LU-2024-0841", "CSE-322", "2026-11-15", "Absent"),
        ("LU-2024-0712", "CSE-322", "2026-11-15", "Present"),
        ("LU-2024-0841", "CSE-310", "2026-11-14", "Present"),
        ("LU-2025-0840", "BBA-210", "2026-11-16", "Present"),
    ]
    db.executemany("INSERT INTO attendance(enrollment_id,class_date,status) VALUES(?,?,?)",
        [(enrollment_ids[(student, course)], class_date, status) for student, course, class_date, status in attendance])
    grades = [
        ("LU-2024-0841", "CSE-310", "Midterm", 86, "A", 3.75),
        ("LU-2024-0841", "CSE-322", "Midterm", 91, "A+", 4.0),
        ("LU-2024-0712", "CSE-310", "Midterm", 78, "A-", 3.5),
        ("LU-2025-0840", "BBA-210", "Midterm", 82, "A-", 3.5),
    ]
    db.executemany("""INSERT INTO grades(enrollment_id,assessment,marks,grade,point)
        VALUES(?,?,?,?,?)""", [(enrollment_ids[(student, course)], assessment, marks, grade, point)
        for student, course, assessment, marks, grade, point in grades])
    notices = [
        ("N-101", "Fall semester examination schedule published", "Academic", "All users", "The final examination schedule is now available from the examination office.", "2026-11-16"),
        ("N-102", "Campus maintenance announcement", "General", "All users", "Selected campus facilities will undergo scheduled maintenance this weekend.", "2026-11-14"),
        ("N-103", "Annual research symposium registration", "Event", "Students and Faculty", "Registration is open for the annual research symposium.", "2026-11-12"),
        ("N-104", "Faculty meeting", "Academic", "Faculty", "Faculty members are invited to the academic planning meeting.", "2026-11-12"),
    ]
    db.executemany("""INSERT INTO notices(id,title,category,audience,body,published_at)
        VALUES(?,?,?,?,?,?)""", notices)
    complaints = [
        ("CMP-001", "LU-2024-0841", "Classroom projector issue", "Facilities", "The projector in Room 402 is not working.", "In Review", "2026-11-13"),
        ("CMP-002", "LU-2024-0712", "Course registration question", "Academic", "Please clarify the prerequisite for CSE-322.", "Resolved", "2026-11-10"),
    ]
    db.executemany("""INSERT INTO complaints(id,student_id,subject,category,details,status,created_at)
        VALUES(?,?,?,?,?,?,?)""", complaints)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def clean_text(value, field: str, maximum: int = 160, required: bool = True) -> str:
    if value is None:
        value = ""
    if not isinstance(value, (str, int, float)):
        raise AppError(400, "VALIDATION_ERROR", f"{field} must be text.", {field: "Invalid value."})
    value = str(value).strip()
    if required and not value:
        raise AppError(400, "VALIDATION_ERROR", f"{field} is required.", {field: "Required."})
    if len(value) > maximum:
        raise AppError(400, "VALIDATION_ERROR", f"{field} is too long.", {field: f"Maximum {maximum} characters."})
    return value


def required_password(value) -> str:
    if not isinstance(value, str) or len(value) < 12 or len(value) > 128:
        raise AppError(400, "VALIDATION_ERROR", "Use a password with at least 12 characters.", {"password": "Minimum 12 characters."})
    return value


def email_text(value, required: bool = True) -> str:
    email = clean_text(value, "email", 160, required).lower()
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise AppError(400, "VALIDATION_ERROR", "Enter a valid email address.", {"email": "Invalid email."})
    return email


def department_id(db: sqlite3.Connection, name: str) -> str:
    row = db.execute("SELECT id FROM departments WHERE name=? OR code=? OR id=?", (name, name, name)).fetchone()
    if not row:
        raise AppError(400, "VALIDATION_ERROR", "Select a valid department.", {"department": "Unknown department."})
    return row["id"]


def grade_for(marks: float) -> tuple[str, float]:
    if marks >= 90: return "A+", 4.0
    if marks >= 85: return "A", 3.75
    if marks >= 80: return "A-", 3.5
    if marks >= 75: return "B+", 3.25
    if marks >= 70: return "B", 3.0
    if marks >= 60: return "C", 2.0
    return "F", 0.0


class UMSHandler(SimpleHTTPRequestHandler):
    server_version = "LotusUMS/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'")
        super().end_headers()

    def log_message(self, fmt, *args):
        # Keep request logs useful without leaking request bodies or credentials.
        super().log_message(fmt, *args)

    def do_GET(self):
        if urlparse(self.path).path.startswith("/api/"):
            self.handle_api("GET")
            return
        requested = unquote(urlparse(self.path).path).lstrip("/")
        resolved = (ROOT / requested).resolve()
        if ROOT not in resolved.parents and resolved != ROOT:
            self.send_error(404, "Not found.")
            return
        if resolved != ROOT and not resolved.is_file():
            self.send_error(404, "Not found.")
            return
        allowed_extensions = {".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".woff", ".woff2"}
        if resolved != ROOT and (resolved.suffix.lower() not in allowed_extensions or "__pycache__" in resolved.parts or "data" in resolved.relative_to(ROOT).parts):
            self.send_error(404, "Not found.")
            return
        super().do_GET()

    def do_POST(self): self.handle_api("POST")
    def do_PATCH(self): self.handle_api("PATCH")
    def do_DELETE(self): self.handle_api("DELETE")

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > MAX_BODY_BYTES:
            raise AppError(413, "PAYLOAD_TOO_LARGE", "Request body is too large.")
        if not length:
            return {}
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise AppError(400, "INVALID_JSON", "Request body must be valid JSON.")
        if not isinstance(value, dict):
            raise AppError(400, "INVALID_JSON", "Request body must be a JSON object.")
        return value

    def send_json(self, status: int, payload: dict, headers: list[tuple[str, str]] | None = None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for name, value in headers or []:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, error: AppError):
        self.send_json(error.status, {"error": {"code": error.code, "message": str(error), "fields": error.fields}})

    def validate_origin(self):
        origin = self.headers.get("Origin")
        if origin:
            expected = f"http://{self.headers.get('Host', '')}"
            if COOKIE_SECURE:
                expected = f"https://{self.headers.get('Host', '')}"
            if origin.rstrip("/") != expected.rstrip("/"):
                raise AppError(403, "ORIGIN_DENIED", "Cross-origin request denied.")

    def session_user(self, required: bool = True):
        cookie = http.cookies.SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        morsel = cookie.get(SESSION_COOKIE)
        token = morsel.value if morsel else ""
        if not token:
            if required: raise AppError(401, "UNAUTHENTICATED", "Sign in to continue.")
            return None
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = int(time.time())
        with connect_db() as db:
            row = db.execute("""SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
                WHERE s.token_hash=? AND s.expires_at>? AND u.status='Active'""", (token_hash, now)).fetchone()
            if row:
                if row["role"] == "STUDENT":
                    active_profile = db.execute("SELECT status FROM students WHERE user_id=?", (row["id"],)).fetchone()
                    if not active_profile or active_profile["status"] != "Active":
                        db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
                        if required: raise AppError(401, "ACCOUNT_INACTIVE", "This account is inactive. Contact an administrator.")
                        return None
                if row["role"] == "TEACHER":
                    active_profile = db.execute("SELECT status FROM teachers WHERE user_id=?", (row["id"],)).fetchone()
                    if not active_profile or active_profile["status"] != "Active":
                        db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
                        if required: raise AppError(401, "ACCOUNT_INACTIVE", "This account is inactive. Contact an administrator.")
                        return None
                db.execute("UPDATE sessions SET expires_at=? WHERE token_hash=?", (now + SESSION_TTL, token_hash))
                return self.user_payload(db, row)
            db.execute("DELETE FROM sessions WHERE token_hash=? OR expires_at<=?", (token_hash, now))
        if required: raise AppError(401, "UNAUTHENTICATED", "Your session has expired. Sign in again.")
        return None

    @staticmethod
    def user_payload(db: sqlite3.Connection, user: sqlite3.Row) -> dict:
        profile = None
        if user["role"] == "STUDENT":
            profile = db.execute("""SELECT s.*,d.name AS department FROM students s
                LEFT JOIN departments d ON d.id=s.department_id WHERE s.user_id=?""", (user["id"],)).fetchone()
        elif user["role"] == "TEACHER":
            profile = db.execute("""SELECT t.*,d.name AS department FROM teachers t
                LEFT JOIN departments d ON d.id=t.department_id WHERE t.user_id=?""", (user["id"],)).fetchone()
        return {
            "accountId": user["id"],
            "id": profile["id"] if profile else user["university_id"],
            "universityId": user["university_id"],
            "name": user["name"], "email": user["email"], "role": user["role"], "status": user["status"],
            "department": profile["department"] if profile else "Central Administration",
            "year": profile["year"] if user["role"] == "STUDENT" and profile else "",
            "semester": profile["semester"] if user["role"] == "STUDENT" and profile else "",
            "section": profile["section"] if user["role"] == "STUDENT" and profile else "",
            "phone": profile["phone"] if user["role"] == "STUDENT" and profile else "",
            "designation": profile["designation"] if user["role"] == "TEACHER" and profile else "",
        }

    def create_session(self, db: sqlite3.Connection, user_id: int):
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires = int(time.time()) + SESSION_TTL
        db.execute("DELETE FROM sessions WHERE expires_at<=?", (int(time.time()),))
        db.execute("INSERT INTO sessions(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)",
            (token_hash, user_id, expires, utc_now()))
        secure = "; Secure" if COOKIE_SECURE else ""
        return ("Set-Cookie", f"{SESSION_COOKIE}={token}; Path=/; Max-Age={SESSION_TTL}; HttpOnly; SameSite=Strict{secure}")

    @staticmethod
    def require_role(user: dict, *roles: str):
        if user["role"] not in roles:
            raise AppError(403, "FORBIDDEN", "You do not have permission to perform this action.")

    def route_bootstrap(self, user: dict) -> dict:
        role = user["role"]
        with connect_db() as db:
            data = {"user": user}
            data["departments"] = self.departments(db) if role in ("ADMIN", "TEACHER") else []
            data["students"] = self.students(db, user) if role in ("ADMIN", "TEACHER", "STUDENT") else []
            data["teachers"] = self.teachers(db) if role in ("ADMIN", "TEACHER") else []
            data["courses"] = self.courses(db, user)
            data["enrollments"] = self.enrollments(db, user)
            data["schedule"] = self.schedules(db, user)
            data["attendance"] = self.attendance(db, user)
            data["grades"] = self.grades(db, user)
            data["notices"] = self.notices(db, user)
            data["complaints"] = self.complaints(db, user) if role in ("ADMIN", "STUDENT") else []
            data["users"] = self.accounts(db) if role == "ADMIN" else []
            return data

    @staticmethod
    def departments(db: sqlite3.Connection) -> list[dict]:
        rows = db.execute("""SELECT d.*,COUNT(DISTINCT s.id) AS students
            FROM departments d LEFT JOIN students s ON s.department_id=d.id
            GROUP BY d.id ORDER BY d.name""").fetchall()
        return [{"id": r["id"], "name": r["name"], "code": r["code"], "head": r["head"], "students": r["students"]} for r in rows]

    @staticmethod
    def students(db: sqlite3.Connection, user: dict | None = None) -> list[dict]:
        where, args = "", []
        if user and user["role"] == "STUDENT":
            where, args = "WHERE s.user_id=?", [user["accountId"]]
        rows = db.execute(f"""SELECT s.*,d.name AS department FROM students s
            LEFT JOIN departments d ON d.id=s.department_id {where} ORDER BY s.name""", args).fetchall()
        return [{"id": r["id"], "name": r["name"], "email": r["email"], "department": r["department"] or "",
            "year": r["year"], "semester": r["semester"], "section": r["section"], "status": r["status"], "phone": r["phone"]} for r in rows]

    @staticmethod
    def teachers(db: sqlite3.Connection) -> list[dict]:
        rows = db.execute("""SELECT t.*,d.name AS department FROM teachers t
            LEFT JOIN departments d ON d.id=t.department_id ORDER BY t.name""").fetchall()
        return [{"id": r["id"], "name": r["name"], "email": r["email"], "department": r["department"] or "",
            "designation": r["designation"], "status": r["status"]} for r in rows]

    @staticmethod
    def courses(db: sqlite3.Connection, user: dict | None = None) -> list[dict]:
        sql = """SELECT c.*,d.name AS department,t.name AS teacher FROM courses c
            LEFT JOIN departments d ON d.id=c.department_id LEFT JOIN teachers t ON t.id=c.teacher_id"""
        args = []
        if user and user["role"] == "TEACHER":
            sql += " WHERE c.teacher_id=(SELECT id FROM teachers WHERE user_id=?)"
            args.append(user["accountId"])
        elif user and user["role"] == "STUDENT":
            sql += " JOIN enrollments e ON e.course_id=c.id JOIN students s ON s.id=e.student_id WHERE s.user_id=? AND e.status='Active'"
            args.append(user["accountId"])
        sql += " ORDER BY c.id"
        return [{"id": r["id"], "title": r["title"], "department": r["department"] or "", "teacherId": r["teacher_id"],
            "teacher": r["teacher"] or "Unassigned", "credits": r["credits"], "semester": r["semester"]} for r in db.execute(sql, args).fetchall()]

    @staticmethod
    def enrollments(db: sqlite3.Connection, user: dict | None = None) -> list[dict]:
        sql = """SELECT e.*,s.name AS student,c.title AS course FROM enrollments e
            JOIN students s ON s.id=e.student_id JOIN courses c ON c.id=e.course_id"""
        args = []
        if user and user["role"] == "STUDENT":
            sql += " WHERE s.user_id=?"
            args.append(user["accountId"])
        elif user and user["role"] == "TEACHER":
            sql += " WHERE c.teacher_id=(SELECT id FROM teachers WHERE user_id=?)"
            args.append(user["accountId"])
        sql += " ORDER BY s.name,c.id"
        return [{"id": r["id"], "studentId": r["student_id"], "student": r["student"], "courseId": r["course_id"],
            "course": r["course"], "semester": r["semester"], "section": r["section"], "status": r["status"]}
            for r in db.execute(sql, args).fetchall()]

    @staticmethod
    def schedules(db: sqlite3.Connection, user: dict | None = None) -> list[dict]:
        sql = """SELECT sc.*,c.title AS course,c.teacher_id AS teacherId,t.name AS teacher
            FROM schedule sc JOIN courses c ON c.id=sc.course_id LEFT JOIN teachers t ON t.id=c.teacher_id"""
        args = []
        if user and user["role"] == "TEACHER":
            sql += " WHERE c.teacher_id=(SELECT id FROM teachers WHERE user_id=?)"
            args.append(user["accountId"])
        elif user and user["role"] == "STUDENT":
            sql += " JOIN enrollments e ON e.course_id=c.id JOIN students s ON s.id=e.student_id WHERE s.user_id=? AND e.status='Active' AND (sc.section='' OR sc.section=e.section)"
            args.append(user["accountId"])
        sql += " ORDER BY CASE sc.day WHEN 'Sunday' THEN 1 WHEN 'Monday' THEN 2 WHEN 'Tuesday' THEN 3 WHEN 'Wednesday' THEN 4 WHEN 'Thursday' THEN 5 ELSE 6 END,sc.start_time"
        return [{"id": r["id"], "day": r["day"], "start": r["start_time"], "end": r["end_time"], "course": r["course"],
            "code": r["course_id"], "room": r["room"], "teacherId": r["teacherId"], "teacher": r["teacher"] or "Unassigned", "group": r["section"]}
            for r in db.execute(sql, args).fetchall()]

    @staticmethod
    def attendance(db: sqlite3.Connection, user: dict | None = None) -> list[dict]:
        sql = """SELECT a.*,e.student_id AS studentId,e.course_id AS course,s.name AS student
            FROM attendance a JOIN enrollments e ON e.id=a.enrollment_id JOIN students s ON s.id=e.student_id"""
        args = []
        if user and user["role"] == "STUDENT":
            sql += " WHERE s.user_id=?"
            args.append(user["accountId"])
        sql += " ORDER BY a.class_date DESC,a.id DESC"
        return [{"id": r["id"], "date": r["class_date"], "studentId": r["studentId"], "student": r["student"], "course": r["course"], "status": r["status"]} for r in db.execute(sql, args).fetchall()]

    @staticmethod
    def grades(db: sqlite3.Connection, user: dict | None = None) -> list[dict]:
        sql = """SELECT g.*,e.student_id AS studentId,e.course_id AS course,s.name AS student
            FROM grades g JOIN enrollments e ON e.id=g.enrollment_id JOIN students s ON s.id=e.student_id"""
        args = []
        if user and user["role"] == "STUDENT":
            sql += " WHERE s.user_id=?"
            args.append(user["accountId"])
        sql += " ORDER BY g.id DESC"
        return [{"id": r["id"], "studentId": r["studentId"], "student": r["student"], "course": r["course"],
            "assessment": r["assessment"], "marks": r["marks"], "grade": r["grade"], "point": r["point"]} for r in db.execute(sql, args).fetchall()]

    @staticmethod
    def notices(db: sqlite3.Connection, user: dict | None = None) -> list[dict]:
        sql = "SELECT * FROM notices"
        args = []
        if user and user["role"] == "STUDENT":
            sql += " WHERE audience IN ('All users','Students','Students and Faculty')"
        elif user and user["role"] == "TEACHER":
            sql += " WHERE audience IN ('All users','Faculty','Students and Faculty')"
        sql += " ORDER BY published_at DESC"
        return [{"id": r["id"], "title": r["title"], "category": r["category"], "date": r["published_at"],
            "audience": r["audience"], "body": r["body"]} for r in db.execute(sql, args).fetchall()]

    @staticmethod
    def complaints(db: sqlite3.Connection, user: dict | None = None) -> list[dict]:
        sql = "SELECT c.* FROM complaints c"
        args = []
        if user and user["role"] == "STUDENT":
            sql += " JOIN students s ON s.id=c.student_id WHERE s.user_id=?"
            args.append(user["accountId"])
        sql += " ORDER BY c.created_at DESC"
        return [{"id": r["id"], "studentId": r["student_id"], "subject": r["subject"], "category": r["category"],
            "details": r["details"], "status": r["status"], "date": r["created_at"]} for r in db.execute(sql, args).fetchall()]

    @staticmethod
    def accounts(db: sqlite3.Connection) -> list[dict]:
        rows = db.execute("""SELECT u.*,COALESCE(s.department_id,t.department_id) AS department_id,
            d.name AS department,COALESCE(s.year,'') AS year,COALESCE(s.semester,'') AS semester,
            COALESCE(s.section,'') AS section,COALESCE(s.phone,'') AS phone,COALESCE(t.designation,'') AS designation
            FROM users u LEFT JOIN students s ON s.user_id=u.id LEFT JOIN teachers t ON t.user_id=u.id
            LEFT JOIN departments d ON d.id=COALESCE(s.department_id,t.department_id) ORDER BY u.id""").fetchall()
        return [{"accountId": r["id"], "id": r["university_id"], "universityId": r["university_id"], "name": r["name"],
            "email": r["email"], "role": r["role"], "status": r["status"], "department": r["department"] or "",
            "year": r["year"], "semester": r["semester"], "section": r["section"], "phone": r["phone"], "designation": r["designation"]} for r in rows]

    def handle_api(self, method: str):
        try:
            self.validate_origin() if method in ("POST", "PATCH", "DELETE") else None
            path = unquote(urlparse(self.path).path)
            body = self.read_json() if method in ("POST", "PATCH") else {}
            status, payload, headers = self.dispatch(method, path, body)
            self.send_json(status, payload, headers)
        except AppError as error:
            self.send_error_json(error)
        except sqlite3.IntegrityError as error:
            message = "This record conflicts with existing data or is still in use."
            self.send_error_json(AppError(409, "CONFLICT", message))
        except Exception:
            self.log_error("Unhandled API error")
            self.send_error_json(AppError(500, "INTERNAL_ERROR", "The server could not complete the request."))

    def dispatch(self, method: str, path: str, body: dict):
        if path == "/api/health" and method == "GET":
            return 200, {"ok": True}, []
        if path == "/api/auth/setup-status" and method == "GET":
            with connect_db() as db:
                required = ALLOW_INITIAL_SETUP and db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
                return 200, {"required": required}, []
        if path == "/api/auth/setup-admin" and method == "POST":
            return self.setup_admin(body)
        if path == "/api/auth/login" and method == "POST":
            return self.login(body)
        if path == "/api/auth/me" and method == "GET":
            return 200, {"user": self.session_user()}, []
        if path == "/api/auth/logout" and method == "POST":
            self.logout()
            return 200, {"ok": True}, [("Set-Cookie", f"{SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict")]

        user = self.session_user()
        if path == "/api/bootstrap" and method == "GET":
            return 200, self.route_bootstrap(user), []
        if path == "/api/reports/overview" and method == "GET":
            self.require_role(user, "ADMIN", "TEACHER")
            with connect_db() as db:
                summary = {
                    "studentCount": db.execute("SELECT COUNT(*) FROM students").fetchone()[0],
                    "teacherCount": db.execute("SELECT COUNT(*) FROM teachers").fetchone()[0],
                    "attendanceCount": db.execute("SELECT COUNT(*) FROM attendance").fetchone()[0],
                    "gradeCount": db.execute("SELECT COUNT(*) FROM grades").fetchone()[0],
                }
                return 200, {"item": summary}, []

        match = re.fullmatch(r"/api/([a-z-]+)(?:/([^/]+))?", path)
        if not match:
            raise AppError(404, "NOT_FOUND", "API route not found.")
        resource, item_id = match.group(1), match.group(2)
        resource = {"results": "grades", "schedules": "schedule"}.get(resource, resource)
        allowed = {"users", "students", "teachers", "departments", "courses", "enrollments", "schedule", "attendance", "grades", "notices", "complaints"}
        if resource not in allowed:
            raise AppError(404, "NOT_FOUND", "API route not found.")

        if method == "GET":
            return self.get_resource(resource, item_id, user)
        if method == "POST":
            return self.create_resource(resource, user, body)
        if method == "PATCH":
            if item_id is None: raise AppError(404, "NOT_FOUND", "Record route not found.")
            return self.update_resource(resource, item_id, user, body)
        if method == "DELETE":
            if item_id is None: raise AppError(404, "NOT_FOUND", "Record route not found.")
            return self.delete_resource(resource, item_id, user)
        raise AppError(405, "METHOD_NOT_ALLOWED", "Method not allowed.")

    def setup_admin(self, body: dict):
        if not ALLOW_INITIAL_SETUP:
            raise AppError(403, "SETUP_DISABLED", "Initial administrator setup is disabled on this server.")
        name = clean_text(body.get("name"), "name")
        university_id = clean_text(body.get("universityId"), "universityId", 40)
        email = email_text(body.get("email"))
        password = required_password(body.get("password"))
        with connect_db() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
                raise AppError(409, "SETUP_COMPLETE", "An administrator account has already been created.")
            cursor = db.execute("""INSERT INTO users(university_id,email,name,role,password_hash,status,created_at)
                VALUES(?,?,?,'ADMIN',?,'Active',?)""", (university_id, email, name, hash_password(password), utc_now()))
            cookie = self.create_session(db, cursor.lastrowid)
            row = db.execute("SELECT * FROM users WHERE id=?", (cursor.lastrowid,)).fetchone()
            return 201, {"user": self.user_payload(db, row)}, [cookie]

    def login(self, body: dict):
        identity = clean_text(body.get("identity"), "identity", 160).lower()
        password = body.get("password")
        if not isinstance(password, str) or len(password) > 128:
            raise AppError(400, "VALIDATION_ERROR", "Enter a valid password.", {"password": "Invalid password."})
        ip = self.client_address[0] if self.client_address else "local"
        key = hashlib.sha256(f"{ip}|{identity}".encode()).hexdigest()
        now = int(time.time())
        with connect_db() as db:
            attempt = db.execute("SELECT * FROM login_attempts WHERE attempt_key=?", (key,)).fetchone()
            if attempt and now - attempt["window_started"] < 900 and attempt["attempts"] >= 8:
                raise AppError(429, "RATE_LIMITED", "Too many sign-in attempts. Try again in 15 minutes.")
            user = db.execute("""SELECT * FROM users WHERE (lower(email)=? OR lower(university_id)=?)
                AND status='Active'""", (identity, identity)).fetchone()
            valid = bool(user and verify_password(password, user["password_hash"]))
            if valid and user["role"] == "STUDENT":
                profile = db.execute("SELECT status FROM students WHERE user_id=?", (user["id"],)).fetchone()
                valid = bool(profile and profile["status"] == "Active")
            if valid and user["role"] == "TEACHER":
                profile = db.execute("SELECT status FROM teachers WHERE user_id=?", (user["id"],)).fetchone()
                valid = bool(profile and profile["status"] == "Active")
            if not valid:
                if not attempt or now - attempt["window_started"] >= 900:
                    db.execute("INSERT OR REPLACE INTO login_attempts(attempt_key,attempts,window_started) VALUES(?,?,?)", (key, 1, now))
                else:
                    db.execute("UPDATE login_attempts SET attempts=attempts+1 WHERE attempt_key=?", (key,))
            else:
                db.execute("DELETE FROM login_attempts WHERE attempt_key=?", (key,))
                cookie = self.create_session(db, user["id"])
                return 200, {"user": self.user_payload(db, user)}, [cookie]
        raise AppError(401, "INVALID_CREDENTIALS", "The email/ID or password is incorrect.")

    def logout(self):
        cookie = http.cookies.SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        morsel = cookie.get(SESSION_COOKIE)
        if morsel:
            token_hash = hashlib.sha256(morsel.value.encode()).hexdigest()
            with connect_db() as db:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))

    def get_resource(self, resource: str, item_id: str | None, user: dict):
        if resource == "users": self.require_role(user, "ADMIN")
        elif resource == "teachers": self.require_role(user, "ADMIN")
        elif resource == "departments": self.require_role(user, "ADMIN", "TEACHER")
        elif resource == "complaints": self.require_role(user, "ADMIN", "STUDENT")
        with connect_db() as db:
            if item_id is not None:
                row = self.lookup_item(db, resource, item_id, user)
                return 200, {"item": row}, []
            getter = {
                "users": lambda: self.accounts(db), "students": lambda: self.students(db, user),
                "teachers": lambda: self.teachers(db), "departments": lambda: self.departments(db),
                "courses": lambda: self.courses(db, user), "enrollments": lambda: self.enrollments(db, user),
                "schedule": lambda: self.schedules(db, user), "attendance": lambda: self.attendance(db, user),
                "grades": lambda: self.grades(db, user), "notices": lambda: self.notices(db, user),
                "complaints": lambda: self.complaints(db, user),
            }[resource]
            items = getter()
            return 200, {"items": items, "total": len(items)}, []

    def lookup_item(self, db: sqlite3.Connection, resource: str, item_id: str, user: dict) -> dict:
        items = {
            "students": self.students(db, user), "teachers": self.teachers(db), "departments": self.departments(db),
            "courses": self.courses(db, user), "enrollments": self.enrollments(db, user),
            "schedule": self.schedules(db, user), "attendance": self.attendance(db, user),
            "grades": self.grades(db, user), "notices": self.notices(db, user), "complaints": self.complaints(db, user),
            "users": self.accounts(db),
        }[resource]
        key = "accountId" if resource == "users" else "id"
        found = next((item for item in items if str(item.get(key)) == str(item_id)), None)
        if not found: raise AppError(404, "NOT_FOUND", "Record not found.")
        return found

    def create_resource(self, resource: str, user: dict, body: dict):
        if resource in {"students", "teachers", "departments", "courses", "enrollments", "schedule", "notices", "users"}:
            self.require_role(user, "ADMIN")
        elif resource in {"attendance", "grades"}:
            self.require_role(user, "ADMIN", "TEACHER")
        elif resource == "complaints":
            self.require_role(user, "STUDENT")
        with connect_db() as db:
            if resource == "students": item = self.create_student(db, body)
            elif resource == "teachers": item = self.create_teacher(db, body)
            elif resource == "departments": item = self.create_department(db, body)
            elif resource == "courses": item = self.create_course(db, body)
            elif resource == "enrollments": item = self.create_enrollment(db, body)
            elif resource == "schedule": item = self.create_schedule(db, body)
            elif resource == "attendance": item = self.create_attendance(db, body, user)
            elif resource == "grades": item = self.create_grade(db, body, user)
            elif resource == "notices": item = self.create_notice(db, body, user)
            elif resource == "complaints": item = self.create_complaint(db, body, user)
            elif resource == "users": item = self.create_user(db, body)
            else: raise AppError(404, "NOT_FOUND", "Resource not found.")
            return 201, {"item": item}, []

    def update_resource(self, resource: str, item_id: str, user: dict, body: dict):
        if resource == "attendance": self.require_role(user, "ADMIN", "TEACHER")
        elif resource == "grades": self.require_role(user, "ADMIN", "TEACHER")
        elif resource == "complaints": self.require_role(user, "ADMIN")
        else: self.require_role(user, "ADMIN")
        with connect_db() as db:
            if resource == "users":
                try: account_id = int(item_id)
                except ValueError: raise AppError(400,"VALIDATION_ERROR","Invalid account ID.")
                item = self.update_user(db, account_id, body, user)
            elif resource == "students": item = self.update_student(db, item_id, body)
            elif resource == "teachers": item = self.update_teacher(db, item_id, body)
            elif resource == "departments": item = self.update_department(db, item_id, body)
            elif resource == "courses": item = self.update_course(db, item_id, body)
            elif resource == "enrollments": item = self.update_enrollment(db, int(item_id), body)
            elif resource == "schedule": item = self.update_schedule(db, int(item_id), body)
            elif resource == "attendance": item = self.update_attendance(db, int(item_id), body, user)
            elif resource == "grades": item = self.update_grade(db, int(item_id), body, user)
            elif resource == "notices": item = self.update_notice(db, item_id, body)
            elif resource == "complaints": item = self.update_complaint(db, item_id, body)
            else: raise AppError(404, "NOT_FOUND", "Resource not found.")
            return 200, {"item": item}, []

    def delete_resource(self, resource: str, item_id: str, user: dict):
        self.require_role(user, "ADMIN")
        with connect_db() as db:
            if resource == "users":
                try: account_id = int(item_id)
                except ValueError: raise AppError(400,"VALIDATION_ERROR","Invalid account ID.")
                if account_id == user["accountId"]:
                    raise AppError(400, "SELF_DEACTIVATION", "You cannot deactivate your own account.")
                row = db.execute("SELECT role FROM users WHERE id=?", (account_id,)).fetchone()
                if not row: raise AppError(404, "NOT_FOUND", "Account not found.")
                if row["role"] == "ADMIN" and db.execute("SELECT COUNT(*) FROM users WHERE role='ADMIN' AND status='Active'").fetchone()[0] <= 1:
                    raise AppError(400, "LAST_ADMIN", "The last active admin account cannot be deactivated.")
                db.execute("UPDATE users SET status='Inactive' WHERE id=?", (account_id,))
                return 200, {"ok": True}, []
            table = {"students": "students", "teachers": "teachers", "departments": "departments", "courses": "courses",
                "enrollments": "enrollments", "schedule": "schedule", "attendance": "attendance", "grades": "grades", "notices": "notices"}.get(resource)
            if not table: raise AppError(405, "METHOD_NOT_ALLOWED", "This record cannot be deleted.")
            if resource in ("students", "teachers"):
                db.execute(f"UPDATE {table} SET status='Inactive' WHERE id=?", (item_id,))
                if db.total_changes == 0: raise AppError(404, "NOT_FOUND", "Record not found.")
            else:
                cursor = db.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
                if cursor.rowcount == 0: raise AppError(404, "NOT_FOUND", "Record not found.")
            return 200, {"ok": True}, []

    def create_student(self, db, body):
        sid = clean_text(body.get("id"), "id", 40)
        name = clean_text(body.get("name"), "name")
        email = email_text(body.get("email"), False)
        dept = department_id(db, clean_text(body.get("department"), "department"))
        year = clean_text(body.get("year"), "year", 40, False)
        semester = clean_text(body.get("semester"), "semester", 40, False)
        section = clean_text(body.get("section"), "section", 40, False)
        status = clean_text(body.get("status", "Active"), "status", 20)
        if status not in ("Active", "Pending", "Inactive"): raise AppError(400, "VALIDATION_ERROR", "Invalid student status.")
        phone = clean_text(body.get("phone"), "phone", 40, False)
        db.execute("""INSERT INTO students(id,name,email,department_id,year,semester,section,status,phone)
            VALUES(?,?,?,?,?,?,?,?,?)""", (sid,name,email,dept,year,semester,section,status,phone))
        return next(row for row in self.students(db) if row["id"] == sid)

    def update_student(self, db, sid, body):
        row = db.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
        if not row: raise AppError(404, "NOT_FOUND", "Student not found.")
        values = {
            "name": clean_text(body.get("name",row["name"]),"name"),
            "email": email_text(body.get("email",row["email"]),False),
            "department_id": department_id(db, clean_text(body.get("department",row["department_id"]),"department")),
            "year": clean_text(body.get("year",row["year"]),"year",40,False),
            "semester": clean_text(body.get("semester",row["semester"]),"semester",40,False),
            "section": clean_text(body.get("section",row["section"]),"section",40,False),
            "status": clean_text(body.get("status",row["status"]),"status",20),
            "phone": clean_text(body.get("phone",row["phone"]),"phone",40,False),
        }
        if values["status"] not in ("Active","Pending","Inactive"): raise AppError(400,"VALIDATION_ERROR","Invalid student status.")
        db.execute("""UPDATE students SET name=:name,email=:email,department_id=:department_id,year=:year,
            semester=:semester,section=:section,status=:status,phone=:phone WHERE id=:id""", {**values,"id":sid})
        return next(row for row in self.students(db) if row["id"] == sid)

    def create_teacher(self, db, body):
        tid = clean_text(body.get("id"), "id", 40)
        name = clean_text(body.get("name"), "name")
        email = email_text(body.get("email"), False)
        dept = department_id(db, clean_text(body.get("department"), "department"))
        designation = clean_text(body.get("designation"), "designation", 100, False)
        status = clean_text(body.get("status", "Active"), "status", 20)
        db.execute("INSERT INTO teachers(id,name,email,department_id,designation,status) VALUES(?,?,?,?,?,?)",
            (tid,name,email,dept,designation,status))
        return next(row for row in self.teachers(db) if row["id"] == tid)

    def update_teacher(self, db, tid, body):
        row = db.execute("SELECT * FROM teachers WHERE id=?", (tid,)).fetchone()
        if not row: raise AppError(404,"NOT_FOUND","Teacher not found.")
        dept = department_id(db, clean_text(body.get("department",row["department_id"]),"department"))
        name = clean_text(body.get("name",row["name"]),"name")
        email = email_text(body.get("email",row["email"]),False)
        designation = clean_text(body.get("designation",row["designation"]),"designation",100,False)
        status = clean_text(body.get("status",row["status"]),"status",20)
        db.execute("UPDATE teachers SET name=?,email=?,department_id=?,designation=?,status=? WHERE id=?",
            (name,email,dept,designation,status,tid))
        return next(row for row in self.teachers(db) if row["id"] == tid)

    def create_department(self, db, body):
        did=clean_text(body.get("id"),"id",40); name=clean_text(body.get("name"),"name"); code=clean_text(body.get("code"),"code",20).upper(); head=clean_text(body.get("head"),"head",120,False)
        db.execute("INSERT INTO departments(id,name,code,head) VALUES(?,?,?,?)",(did,name,code,head))
        return next(row for row in self.departments(db) if row["id"]==did)

    def update_department(self, db, did, body):
        row=db.execute("SELECT * FROM departments WHERE id=?",(did,)).fetchone()
        if not row: raise AppError(404,"NOT_FOUND","Department not found.")
        name=clean_text(body.get("name",row["name"]),"name"); code=clean_text(body.get("code",row["code"]),"code",20).upper(); head=clean_text(body.get("head",row["head"]),"head",120,False)
        db.execute("UPDATE departments SET name=?,code=?,head=? WHERE id=?",(name,code,head,did))
        return next(row for row in self.departments(db) if row["id"]==did)

    def create_course(self, db, body):
        cid=clean_text(body.get("id"),"id",40).upper(); title=clean_text(body.get("title"),"title"); dept=department_id(db,clean_text(body.get("department"),"department")); teacher=clean_text(body.get("teacherId"),"teacherId",40,False) or None
        try: credits=int(body.get("credits",3))
        except (TypeError,ValueError): raise AppError(400,"VALIDATION_ERROR","Credits must be a whole number.")
        if credits < 1 or credits > 10: raise AppError(400,"VALIDATION_ERROR","Credits must be between 1 and 10.")
        semester=clean_text(body.get("semester"),"semester",40,False)
        db.execute("INSERT INTO courses(id,title,department_id,teacher_id,credits,semester) VALUES(?,?,?,?,?,?)",(cid,title,dept,teacher,credits,semester))
        return next(row for row in self.courses(db) if row["id"]==cid)

    def update_course(self, db, cid, body):
        row=db.execute("SELECT * FROM courses WHERE id=?",(cid,)).fetchone()
        if not row: raise AppError(404,"NOT_FOUND","Course not found.")
        title=clean_text(body.get("title",row["title"]),"title"); dept=department_id(db,clean_text(body.get("department",row["department_id"]),"department")); teacher=clean_text(body.get("teacherId",row["teacher_id"] or ""),"teacherId",40,False) or None
        try: credits=int(body.get("credits",row["credits"]))
        except (TypeError,ValueError): raise AppError(400,"VALIDATION_ERROR","Credits must be a whole number.")
        if credits < 1 or credits > 10: raise AppError(400,"VALIDATION_ERROR","Credits must be between 1 and 10.")
        semester=clean_text(body.get("semester",row["semester"]),"semester",40,False)
        db.execute("UPDATE courses SET title=?,department_id=?,teacher_id=?,credits=?,semester=? WHERE id=?",(title,dept,teacher,credits,semester,cid))
        return next(row for row in self.courses(db) if row["id"]==cid)

    def create_enrollment(self, db, body):
        student=clean_text(body.get("studentId"),"studentId",40); course=clean_text(body.get("courseId"),"courseId",40)
        course_row=db.execute("SELECT semester FROM courses WHERE id=?",(course,)).fetchone()
        student_row=db.execute("SELECT section,semester FROM students WHERE id=?",(student,)).fetchone()
        if not course_row or not student_row: raise AppError(400,"VALIDATION_ERROR","Choose an existing student and course.")
        semester=clean_text(body.get("semester") or course_row["semester"] or student_row["semester"],"semester",40)
        section=clean_text(body.get("section") or student_row["section"],"section",40,False)
        db.execute("INSERT INTO enrollments(student_id,course_id,semester,section) VALUES(?,?,?,?)",(student,course,semester,section))
        return next(row for row in self.enrollments(db) if row["studentId"]==student and row["courseId"]==course and row["semester"]==semester)

    def update_enrollment(self, db, enrollment_id, body):
        row=db.execute("SELECT * FROM enrollments WHERE id=?",(enrollment_id,)).fetchone()
        if not row: raise AppError(404,"NOT_FOUND","Enrollment not found.")
        semester=clean_text(body.get("semester",row["semester"]),"semester",40); section=clean_text(body.get("section",row["section"]),"section",40,False); status=clean_text(body.get("status",row["status"]),"status",20)
        if status not in ("Active","Withdrawn"): raise AppError(400,"VALIDATION_ERROR","Invalid enrollment status.")
        db.execute("UPDATE enrollments SET semester=?,section=?,status=? WHERE id=?",(semester,section,status,enrollment_id))
        return next(row for row in self.enrollments(db) if row["id"]==enrollment_id)

    def create_schedule(self, db, body):
        course=clean_text(body.get("courseId"),"courseId",40); day=clean_text(body.get("day"),"day",20); start=clean_text(body.get("start"),"start",5); end=clean_text(body.get("end"),"end",5); room=clean_text(body.get("room"),"room",80,False); section=clean_text(body.get("section"),"section",40,False)
        self.validate_times(start,end)
        db.execute("INSERT INTO schedule(course_id,day,start_time,end_time,room,section) VALUES(?,?,?,?,?,?)",(course,day,start,end,room,section))
        return next(row for row in self.schedules(db) if row["id"]==db.execute("SELECT last_insert_rowid()").fetchone()[0])

    @staticmethod
    def validate_times(start,end):
        try:
            start_time=datetime.strptime(start,"%H:%M").time()
            end_time=datetime.strptime(end,"%H:%M").time()
        except ValueError:
            raise AppError(400,"VALIDATION_ERROR","Enter valid class start and end times.")
        if end_time <= start_time:
            raise AppError(400,"VALIDATION_ERROR","Class end time must be after its start time.")

    def update_schedule(self, db, schedule_id, body):
        row=db.execute("SELECT * FROM schedule WHERE id=?",(schedule_id,)).fetchone()
        if not row: raise AppError(404,"NOT_FOUND","Schedule entry not found.")
        course=clean_text(body.get("courseId",row["course_id"]),"courseId",40); day=clean_text(body.get("day",row["day"]),"day",20); start=clean_text(body.get("start",row["start_time"]),"start",5); end=clean_text(body.get("end",row["end_time"]),"end",5); room=clean_text(body.get("room",row["room"]),"room",80,False); section=clean_text(body.get("section",row["section"]),"section",40,False)
        self.validate_times(start,end)
        db.execute("UPDATE schedule SET course_id=?,day=?,start_time=?,end_time=?,room=?,section=? WHERE id=?",(course,day,start,end,room,section,schedule_id))
        return next(item for item in self.schedules(db) if item["id"]==schedule_id)

    def enrollment_for_write(self, db, course_id, student_id, user):
        row=db.execute("""SELECT e.id FROM enrollments e WHERE e.course_id=? AND e.student_id=? AND e.status='Active'""",(course_id,student_id)).fetchone()
        if not row: raise AppError(403,"NOT_ENROLLED","The student is not enrolled in this course.")
        if user["role"]=="TEACHER":
            assigned=db.execute("SELECT 1 FROM courses c JOIN teachers t ON t.id=c.teacher_id WHERE c.id=? AND t.user_id=?",(course_id,user["accountId"])).fetchone()
            if not assigned: raise AppError(403,"COURSE_NOT_ASSIGNED","This course is not assigned to you.")
        return row["id"]

    def create_attendance(self, db, body, user):
        student=clean_text(body.get("studentId"),"studentId",40); course=clean_text(body.get("course"),"course",40); class_date=clean_text(body.get("date"),"date",10)
        try: date.fromisoformat(class_date)
        except ValueError: raise AppError(400,"VALIDATION_ERROR","Enter a valid class date.")
        status=clean_text(body.get("status"),"status",20)
        if status not in ("Present","Absent","Late"): raise AppError(400,"VALIDATION_ERROR","Invalid attendance status.")
        enrollment_id=self.enrollment_for_write(db,course,student,user)
        db.execute("""INSERT INTO attendance(enrollment_id,class_date,status,marked_by) VALUES(?,?,?,?)
            ON CONFLICT(enrollment_id,class_date) DO UPDATE SET status=excluded.status,marked_by=excluded.marked_by""",(enrollment_id,class_date,status,user["accountId"]))
        return next(row for row in self.attendance(db) if row["studentId"]==student and row["course"]==course and row["date"]==class_date)

    def update_attendance(self, db, attendance_id, body, user):
        row=db.execute("SELECT a.*,e.student_id,e.course_id FROM attendance a JOIN enrollments e ON e.id=a.enrollment_id WHERE a.id=?",(attendance_id,)).fetchone()
        if not row: raise AppError(404,"NOT_FOUND","Attendance record not found.")
        self.enrollment_for_write(db,row["course_id"],row["student_id"],user)
        status=clean_text(body.get("status"),"status",20)
        if status not in ("Present","Absent","Late"): raise AppError(400,"VALIDATION_ERROR","Invalid attendance status.")
        db.execute("UPDATE attendance SET status=?,marked_by=? WHERE id=?",(status,user["accountId"],attendance_id))
        return next(item for item in self.attendance(db) if item["id"]==attendance_id)

    def create_grade(self, db, body, user):
        student=clean_text(body.get("studentId"),"studentId",40); course=clean_text(body.get("course"),"course",40); assessment=clean_text(body.get("assessment"),"assessment",80)
        try: marks=float(body.get("marks"))
        except (TypeError,ValueError): raise AppError(400,"VALIDATION_ERROR","Marks must be a number.")
        if marks < 0 or marks > 100: raise AppError(400,"VALIDATION_ERROR","Marks must be between 0 and 100.")
        enrollment_id=self.enrollment_for_write(db,course,student,user); grade,point=grade_for(marks)
        db.execute("""INSERT INTO grades(enrollment_id,assessment,marks,grade,point,created_by)
            VALUES(?,?,?,?,?,?) ON CONFLICT(enrollment_id,assessment) DO UPDATE SET marks=excluded.marks,grade=excluded.grade,point=excluded.point,created_by=excluded.created_by""",
            (enrollment_id,assessment,marks,grade,point,user["accountId"]))
        return next(row for row in self.grades(db) if row["studentId"]==student and row["course"]==course and row["assessment"]==assessment)

    def update_grade(self, db, grade_id, body, user):
        row=db.execute("SELECT g.*,e.student_id,e.course_id FROM grades g JOIN enrollments e ON e.id=g.enrollment_id WHERE g.id=?",(grade_id,)).fetchone()
        if not row: raise AppError(404,"NOT_FOUND","Result not found.")
        self.enrollment_for_write(db,row["course_id"],row["student_id"],user)
        try: marks=float(body.get("marks",row["marks"]))
        except (TypeError,ValueError): raise AppError(400,"VALIDATION_ERROR","Marks must be a number.")
        assessment=clean_text(body.get("assessment",row["assessment"]),"assessment",80)
        if marks < 0 or marks > 100: raise AppError(400,"VALIDATION_ERROR","Marks must be between 0 and 100.")
        grade,point=grade_for(marks)
        db.execute("UPDATE grades SET marks=?,grade=?,point=?,assessment=?,created_by=? WHERE id=?",(marks,grade,point,assessment,user["accountId"],grade_id))
        return next(item for item in self.grades(db) if item["id"]==grade_id)

    def create_notice(self, db, body, user):
        title=clean_text(body.get("title"),"title",160); category=clean_text(body.get("category"),"category",40); audience=clean_text(body.get("audience"),"audience",40); content=clean_text(body.get("body"),"body",5000)
        if audience not in ("All users","Students","Faculty","Students and Faculty"): raise AppError(400,"VALIDATION_ERROR","Choose a valid notice audience.")
        notice_id=f"N-{uuid.uuid4().hex[:10].upper()}"; published=utc_now()[:10]
        db.execute("INSERT INTO notices(id,title,category,audience,body,published_at,author_id) VALUES(?,?,?,?,?,?,?)",(notice_id,title,category,audience,content,published,user["accountId"]))
        return next(row for row in self.notices(db) if row["id"]==notice_id)

    def update_notice(self, db, notice_id, body):
        row=db.execute("SELECT * FROM notices WHERE id=?",(notice_id,)).fetchone()
        if not row: raise AppError(404,"NOT_FOUND","Notice not found.")
        title=clean_text(body.get("title",row["title"]),"title",160); category=clean_text(body.get("category",row["category"]),"category",40); audience=clean_text(body.get("audience",row["audience"]),"audience",40); content=clean_text(body.get("body",row["body"]),"body",5000)
        if audience not in ("All users","Students","Faculty","Students and Faculty"): raise AppError(400,"VALIDATION_ERROR","Choose a valid notice audience.")
        db.execute("UPDATE notices SET title=?,category=?,audience=?,body=? WHERE id=?",(title,category,audience,content,notice_id))
        return next(item for item in self.notices(db) if item["id"]==notice_id)

    def create_complaint(self, db, body, user):
        student=db.execute("SELECT id FROM students WHERE user_id=?",(user["accountId"],)).fetchone()
        if not student: raise AppError(403,"STUDENT_PROFILE_REQUIRED","Your account has no linked student profile.")
        complaint_id=f"CMP-{uuid.uuid4().hex[:10].upper()}"; subject=clean_text(body.get("subject"),"subject",160); category=clean_text(body.get("category"),"category",40); details=clean_text(body.get("details"),"details",4000)
        db.execute("INSERT INTO complaints(id,student_id,subject,category,details,status,created_at) VALUES(?,?,?,?,?,'Submitted',?)",(complaint_id,student["id"],subject,category,details,utc_now()[:10]))
        return next(row for row in self.complaints(db,user) if row["id"]==complaint_id)

    def update_complaint(self, db, complaint_id, body):
        status=clean_text(body.get("status"),"status",20)
        if status not in ("Submitted","In Review","Resolved"): raise AppError(400,"VALIDATION_ERROR","Invalid complaint status.")
        cursor=db.execute("UPDATE complaints SET status=? WHERE id=?",(status,complaint_id))
        if cursor.rowcount==0: raise AppError(404,"NOT_FOUND","Complaint not found.")
        return next(row for row in self.complaints(db) if row["id"]==complaint_id)

    def create_user(self, db, body):
        university_id=clean_text(body.get("universityId"),"universityId",40); name=clean_text(body.get("name"),"name"); email=email_text(body.get("email")); role=clean_text(body.get("role"),"role",20).upper(); password=required_password(body.get("password"))
        if role not in ALLOWED_ROLES: raise AppError(400,"VALIDATION_ERROR","Choose Admin, Teacher or Student.")
        department=clean_text(body.get("department"),"department",120,False)
        dept_id=department_id(db,department) if department else None
        cur=db.execute("INSERT INTO users(university_id,email,name,role,password_hash,status,created_at) VALUES(?,?,?,?,?,'Active',?)",
            (university_id,email,name,role,hash_password(password),utc_now()))
        account_id=cur.lastrowid
        if role=="STUDENT":
            existing=db.execute("SELECT id FROM students WHERE id=?",(university_id,)).fetchone()
            if existing:
                db.execute("UPDATE students SET user_id=?,name=?,email=?,department_id=COALESCE(?,department_id),status='Active' WHERE id=?",(account_id,name,email,dept_id,university_id))
            else:
                db.execute("INSERT INTO students(id,user_id,name,email,department_id,year,semester,section,status,phone) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (university_id,account_id,name,email,dept_id,clean_text(body.get("year"),"year",40,False),clean_text(body.get("semester"),"semester",40,False),clean_text(body.get("section"),"section",40,False),"Active",clean_text(body.get("phone"),"phone",40,False)))
        elif role=="TEACHER":
            existing=db.execute("SELECT id FROM teachers WHERE id=?",(university_id,)).fetchone()
            if existing:
                db.execute("UPDATE teachers SET user_id=?,name=?,email=?,department_id=COALESCE(?,department_id),status='Active' WHERE id=?",(account_id,name,email,dept_id,university_id))
            else:
                db.execute("INSERT INTO teachers(id,user_id,name,email,department_id,designation,status) VALUES(?,?,?,?,?,?,?)",
                    (university_id,account_id,name,email,dept_id,clean_text(body.get("designation"),"designation",100,False),"Active"))
        row=db.execute("SELECT * FROM users WHERE id=?",(account_id,)).fetchone()
        return self.user_payload(db,row)

    def update_user(self, db, account_id, body, acting_user):
        row=db.execute("SELECT * FROM users WHERE id=?",(account_id,)).fetchone()
        if not row: raise AppError(404,"NOT_FOUND","Account not found.")
        name=clean_text(body.get("name",row["name"]),"name"); email=email_text(body.get("email",row["email"])); status=clean_text(body.get("status",row["status"]),"status",20)
        if status not in ("Active","Inactive"): raise AppError(400,"VALIDATION_ERROR","Invalid account status.")
        if status == "Inactive" and account_id == acting_user["accountId"]:
            raise AppError(400,"SELF_DEACTIVATION","You cannot deactivate your own account.")
        if status == "Inactive" and row["role"] == "ADMIN" and db.execute("SELECT COUNT(*) FROM users WHERE role='ADMIN' AND status='Active'").fetchone()[0] <= 1:
            raise AppError(400,"LAST_ADMIN","The last active admin account cannot be deactivated.")
        password=body.get("password")
        if password:
            db.execute("UPDATE users SET name=?,email=?,status=?,password_hash=? WHERE id=?",(name,email,status,hash_password(required_password(password)),account_id))
            if account_id != acting_user["accountId"]:
                db.execute("DELETE FROM sessions WHERE user_id=?",(account_id,))
        else:
            db.execute("UPDATE users SET name=?,email=?,status=? WHERE id=?",(name,email,status,account_id))
        department=clean_text(body.get("department"),"department",120,False)
        if department:
            did=department_id(db,department)
            if row["role"]=="STUDENT": db.execute("UPDATE students SET department_id=? WHERE user_id=?",(did,account_id))
            if row["role"]=="TEACHER": db.execute("UPDATE teachers SET department_id=? WHERE user_id=?",(did,account_id))
        if row["role"]=="STUDENT":
            db.execute("UPDATE students SET name=?,email=?,year=?,semester=?,section=?,phone=? WHERE user_id=?",
                (name,email,clean_text(body.get("year"),"year",40,False),clean_text(body.get("semester"),"semester",40,False),clean_text(body.get("section"),"section",40,False),clean_text(body.get("phone"),"phone",40,False),account_id))
        if row["role"]=="TEACHER":
            db.execute("UPDATE teachers SET name=?,email=?,designation=? WHERE user_id=?",(name,email,clean_text(body.get("designation"),"designation",100,False),account_id))
        updated=db.execute("SELECT * FROM users WHERE id=?",(account_id,)).fetchone()
        return self.user_payload(db,updated)


def main():
    init_db()
    host = os.environ.get("UMS_HOST", "127.0.0.1")
    port = int(os.environ.get("UMS_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), UMSHandler)
    print(f"Lotus University UMS running at http://{host}:{port}")
    print(f"SQLite database: {DB_PATH}")
    print("On first run, open the site to create the initial administrator account.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Lotus UMS.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
