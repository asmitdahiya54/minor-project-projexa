import csv, io, os, re, secrets, smtplib, sqlite3, uuid
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from flask import Flask, Response, abort, flash, g, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent
if load_dotenv:
    load_dotenv(BASE_DIR / ".env")

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
    DATABASE=str(BASE_DIR / "sims.db"),
    UPLOAD_FOLDER=str(BASE_DIR / "static" / "uploads"),
    MAX_CONTENT_LENGTH=4 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)

DEPARTMENTS = [
    "Computer Science",
    "Information Technology",
    "Electronics",
    "Mechanical Engineering",
    "Civil Engineering",
    "Business Administration",
]
YEARS = ["First Year", "Second Year", "Third Year", "Fourth Year"]
STATUSES = ["Active", "On Leave", "Graduated"]
SEMESTERS = [
    "Semester 1", "Semester 2", "Semester 3", "Semester 4",
    "Semester 5", "Semester 6", "Semester 7", "Semester 8"
]
EXAM_TYPES = ["Midterm", "Final", "Quiz", "Assignment", "Practical"]
SUBJECTS = [
    "Mathematics", "Physics", "Chemistry", "English", "Data Structures",
    "Algorithms", "DBMS", "Operating Systems", "Computer Networks",
    "Software Engineering", "Web Development", "Machine Learning",
    "Discrete Mathematics", "Digital Electronics", "Circuit Theory",
    "Thermodynamics", "Fluid Mechanics", "General"
]
FEEDBACK_CATEGORIES = [
    "General", "Teaching Quality", "Infrastructure",
    "Canteen", "Library", "Sports", "Administration"
]
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def pick_database_path():
    preferred = Path(os.environ.get("SIMS_DB_PATH", app.config["DATABASE"]))
    try:
        preferred.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(preferred)
        conn.execute("CREATE TABLE IF NOT EXISTS __db_healthcheck(id INTEGER)")
        conn.commit()
        conn.close()
        return str(preferred)
    except sqlite3.OperationalError:
        fallback = Path(os.environ.get("TEMP", BASE_DIR)) / "sims_runtime.db"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        return str(fallback)


app.config["DATABASE"] = pick_database_path()


def db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_e):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def col_exists(conn, table, column):
    return any(r["name"] == column for r in conn.execute(f"PRAGMA table_info({table})").fetchall())

def ensure_col(conn, table, sql):
    name = sql.split()[0]
    if not col_exists(conn, table, name):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {sql}")


def migrate_users(conn):
    ensure_col(conn, "users", "full_name TEXT")

    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
    if row and row["sql"] and "teacher" in row["sql"].lower():
        return
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','teacher','student')),
            student_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    """)
    if row:
        conn.execute("""
            INSERT INTO users_new (id,username,email,password,role,student_id,created_at)
            SELECT id,username,email,password,role,student_id,created_at FROM users
        """)
        conn.execute("DROP TABLE users")
        conn.execute("ALTER TABLE users_new RENAME TO users")
    conn.execute("PRAGMA foreign_keys = ON")

    conn.execute("UPDATE users SET full_name='Rahul Sharma' WHERE username='teacher'")

    def init_db():
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row

    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            dob TEXT,
            gender TEXT,
            department TEXT NOT NULL,
            year TEXT NOT NULL,
            status TEXT DEFAULT 'Active',
            address TEXT,
            enroll_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Present','Absent','Late')),
            subject TEXT DEFAULT 'General',
            remarks TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id,date,subject),
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            marks_obtained REAL NOT NULL,
            max_marks REAL NOT NULL DEFAULT 100,
            exam_type TEXT DEFAULT 'Midterm',
            semester TEXT NOT NULL,
            grade TEXT,
            remarks TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            category TEXT DEFAULT 'General',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','teacher','student')),
            student_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    """)

    migrate_users(conn)
    ensure_col(conn, "students", "profile_image TEXT")
    ensure_col(conn, "students", "assigned_teacher_id INTEGER")

    if conn.execute("SELECT COUNT(*) c FROM students").fetchone()["c"] == 0:
        seed = [
            ("CS2024001", "Asmit Dahiya", "asmit@example.com", "2003-05-12", "Male", "Computer Science", "Third Year", "Active", "Delhi", "2022-07-15"),
            ("CS2024002", "Dev Narwal", "dev@example.com", "2004-02-18", "Male", "Computer Science", "Second Year", "Active", "Haryana", "2023-07-10"),
            ("IT2024001", "Manish Chauhan", "manish@example.com", "2005-09-30", "Male", "Information Technology", "First Year", "Active", "Punjab", "2024-07-08"),
            ("IT2024002", "Dikshit Kumar", "dikshit@example.com", "2004-11-22", "Male", "Information Technology", "Second Year", "Active", "Delhi", "2023-07-12"),
            ("EC2024001", "Gourav Sharma", "gourav@example.com", "2005-03-05", "Male", "Electronics", "First Year", "Active", "Rajasthan", "2024-07-15"),
            ("ME2024001", "Aditya Dangi", "aditya@example.com", "2005-07-19", "Male", "Mechanical Engineering", "First Year", "On Leave", "MP", "2024-07-14"),
        ]
        conn.executemany("""
            INSERT INTO students (student_id,name,email,dob,gender,department,year,status,address,enroll_date)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, seed)

    usernames = {r["username"] for r in conn.execute("SELECT username FROM users").fetchall()}

    if "admin" not in usernames:
        conn.execute(
            "INSERT INTO users (username,email,password,role) VALUES (?,?,?,?)",
            ("admin", "admin@sims.edu", generate_password_hash("admin123"), "admin"),
        )

    if "teacher" not in usernames:
        conn.execute(
            "INSERT INTO users (username,email,password,role,full_name) VALUES (?,?,?,?,?)",
            ("teacher", "teacher@sims.edu", generate_password_hash("teacher123"), "teacher", "Rahul Sharma")
        )
        conn.execute("UPDATE users SET full_name='Rahul Sharma' WHERE username='teacher'")

    teacher = conn.execute("SELECT id FROM users WHERE username='teacher' LIMIT 1").fetchone()

    for s in conn.execute("SELECT id,student_id,email FROM students").fetchall():
        exists = conn.execute(
            "SELECT 1 FROM users WHERE username=? LIMIT 1",
            (s["student_id"],)
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO users (username,email,password,role,student_id) VALUES (?,?,?,?,?)",
                (s["student_id"], s["email"], generate_password_hash("student123"), "student", s["id"]),
            )

            if "admin" not in usernames:
        conn.execute(
            "INSERT INTO users (username,email,password,role) VALUES (?,?,?,?)",
            ("admin", "admin@sims.edu", generate_password_hash("admin123"), "admin"),
        )

    if "teacher" not in usernames:
        conn.execute(
            "INSERT INTO users (username,email,password,role,full_name) VALUES (?,?,?,?,?)",
            ("teacher", "teacher@sims.edu", generate_password_hash("teacher123"), "teacher", "Rahul Sharma")
        )
        conn.execute("UPDATE users SET full_name='Rahul Sharma' WHERE username='teacher'")

    teacher = conn.execute("SELECT id FROM users WHERE username='teacher' LIMIT 1").fetchone()

    for s in conn.execute("SELECT id,student_id,email FROM students").fetchall():
        exists = conn.execute(
            "SELECT 1 FROM users WHERE username=? LIMIT 1",
            (s["student_id"],)
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO users (username,email,password,role,student_id) VALUES (?,?,?,?,?)",
                (s["student_id"], s["email"], generate_password_hash("student123"), "student", s["id"]),
            )

            if teacher:
        conn.execute(
            "UPDATE students SET assigned_teacher_id = COALESCE(assigned_teacher_id, ?)",
            (teacher["id"],)
        )

    conn.commit()
    conn.close()


def wants_json():
    return (
        "application/json" in request.headers.get("Accept", "") or
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )

def respond(ok, message, target, status=200, extra=None):
    payload = {"success": ok, "message": message, "redirect": target}
    if extra:
        payload.update(extra)
    if wants_json():
        return jsonify(payload), status
    flash(message, "success" if ok else "error")
    return redirect(target)


def csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return session["_csrf_token"]


app.jinja_env.globals["csrf_token"] = csrf_token

@app.before_request
def setup_req():
    session.permanent = True
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
        if token != session.get("_csrf_token"):
            abort(400, description="Invalid CSRF token.")


@app.context_processor
def inject_globals():
    return {
        "current_role": session.get("role"),
        "app_name": "SIMS Pro",
        "global_notifications": build_notifications() if session.get("role") else [],
    }

def clean(value, max_len=255):
    value = (value or "").strip()
    return value[:max_len]


def valid_email(value):
    return not value or bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value))


def to_int(value, default=None):
    try:
        return int(value)
    except Exception:
        return default
    
    def to_float(value, default=None):
    try:
        return float(value)
    except Exception:
        return default


def calc_grade(pct):
    if pct >= 90:
        return "O"
    if pct >= 80:
        return "A+"
    if pct >= 70:
        return "A"
    if pct >= 60:
        return "B+"
    if pct >= 50:
        return "B"
    if pct >= 40:
        return "C"
    return "F"


def grade_color(grade):
    return {
        "O": "#14b8a6",
        "A+": "#3b82f6",
        "A": "#6366f1",
        "B+": "#f59e0b",
        "B": "#f97316",
        "C": "#ef4444",
        "F": "#dc2626",
    }.get(grade, "#64748b")

def visible_clause(alias="students"):
    role = session.get("role")
    if role == "admin":
        return "1=1", []
    if role == "teacher":
        return f"{alias}.assigned_teacher_id = ?", [session["user_id"]]
    if role == "student":
        return f"{alias}.id = ?", [session["student_db_id"]]
    return "1=0", []


def teachers():
    return db().execute(
        """
        SELECT
            id,
            username,
            COALESCE(NULLIF(full_name, ''), username) AS full_name
        FROM users
        WHERE role='teacher'
        ORDER BY COALESCE(NULLIF(full_name, ''), username) ASC
        """
    ).fetchall()


def save_image(fs, old=None):
    if not fs or not fs.filename:
        return old
    ext = fs.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Allowed image types are PNG, JPG, JPEG, and WEBP.")
    name = secure_filename(f"{uuid.uuid4().hex}.{ext}")
    fs.save(Path(app.config["UPLOAD_FOLDER"]) / name)
    if old:
        old_path = Path(app.config["UPLOAD_FOLDER"]) / old
        if old_path.exists():
            old_path.unlink()
    return name


def notify_email(to_email, subject, body):
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USERNAME")
    pwd = os.environ.get("SMTP_PASSWORD")
    port = to_int(os.environ.get("SMTP_PORT"), 587)
    sender = os.environ.get("MAIL_SENDER", user)
    if not all([to_email, host, user, pwd, sender]):
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, port, timeout=15) as s:
            s.starttls()
            s.login(user, pwd)
            s.send_message(msg)
        return True
    except Exception:
        return False


def fmt_date(value):
    try:
        return datetime.fromisoformat(str(value)).strftime("%d %b %Y")
    except Exception:
        return str(value or "-")


def student_or_404(student_id):
    where, params = visible_clause("students")
    row = db().execute(
        f"""
        SELECT students.*, users.full_name AS teacher_name
        FROM students
        LEFT JOIN users ON users.id = students.assigned_teacher_id
        WHERE students.id = ? AND {where}
        """,
        [student_id] + params,
    ).fetchone()
    if not row:
        abort(404)
    return row
def visible_students(filters=None):
    filters = filters or {}
    where, params = visible_clause("students")
    clauses = [where]

    if filters.get("search"):
        t = f"%{filters['search']}%"
        clauses.append("(students.name LIKE ? OR students.student_id LIKE ?)")
        params += [t, t]
    if filters.get("dept"):
        clauses.append("students.department = ?")
        params.append(filters["dept"])
    if filters.get("year"):
        clauses.append("students.year = ?")
        params.append(filters["year"])
    if filters.get("status"):
        clauses.append("students.status = ?")
        params.append(filters["status"])

    return db().execute(
        f"""
        SELECT students.*, users.full_name AS teacher_name
        FROM students
        LEFT JOIN users ON users.id = students.assigned_teacher_id
        WHERE {' AND '.join(clauses)}
        ORDER BY students.created_at DESC, students.name ASC
        """,
        params,
    ).fetchall()