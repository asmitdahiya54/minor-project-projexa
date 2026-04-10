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
def attendance_summary(student_id):
    row = db().execute(
        """
        SELECT
            COUNT(*) total,
            SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) present,
            SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END) absent,
            SUM(CASE WHEN status='Late' THEN 1 ELSE 0 END) late
        FROM attendance
        WHERE student_id=?
        """,
        (student_id,),
    ).fetchone()
    total = row["total"] or 0
    present = row["present"] or 0
    rate = round((present / total) * 100, 1) if total else 0
    return {
        "total": total,
        "present": present,
        "absent": row["absent"] or 0,
        "late": row["late"] or 0,
        "rate": rate,
    }
def recent_results(student_id=None, limit=5):
    if student_id:
        return db().execute(
            """
            SELECT results.*, students.name, students.student_id AS enrollment_no
            FROM results
            JOIN students ON students.id = results.student_id
            WHERE students.id=?
            ORDER BY datetime(results.created_at) DESC
            LIMIT ?
            """,
            (student_id, limit),
        ).fetchall()

    where, params = visible_clause("students")
    return db().execute(
        f"""
        SELECT results.*, students.name, students.student_id AS enrollment_no
        FROM results
        JOIN students ON students.id = results.student_id
        WHERE {where}
        ORDER BY datetime(results.created_at) DESC
        LIMIT ?
        """,
        params + [limit],
    ).fetchall()
def build_notifications():
    if not session.get("user_id"):
        return []
    conn = db()
    role = session.get("role")
    notes = []

    if role == "student":
        sid = session.get("student_db_id")
        summary = attendance_summary(sid)
        if summary["total"] and summary["rate"] < 75:
            notes.append({
                "type": "warning",
                "title": "Low attendance alert",
                "message": f"Your attendance is {summary['rate']}%. Aim for at least 75%.",
            })
        for r in conn.execute(
            "SELECT subject, grade, created_at FROM results WHERE student_id=? ORDER BY datetime(created_at) DESC LIMIT 3",
            (sid,),
        ).fetchall():
            notes.append({
                "type": "info",
                "title": "New result published",
                "message": f"{r['subject']} graded {r['grade'] or 'Pending'} on {fmt_date(r['created_at'])}.",
            })
        return notes[:5]

    where, params = visible_clause("students")
    for r in conn.execute(
        f"""
        SELECT students.name,
               ROUND(100.0 * SUM(CASE WHEN attendance.status='Present' THEN 1 ELSE 0 END) / NULLIF(COUNT(attendance.id),0), 1) rate
        FROM students
        LEFT JOIN attendance ON attendance.student_id = students.id
        WHERE {where}
        GROUP BY students.id, students.name
        HAVING COUNT(attendance.id) > 0 AND rate < 75
        ORDER BY rate ASC
        LIMIT 4
        """,
        params,
    ).fetchall():
        notes.append({
            "type": "warning",
            "title": "Low attendance alert",
            "message": f"{r['name']} is at {r['rate']}% attendance.",
        })

    for r in conn.execute(
        f"""
        SELECT students.name, results.subject, results.grade
        FROM results
        JOIN students ON students.id = results.student_id
        WHERE {where}
        ORDER BY datetime(results.created_at) DESC
        LIMIT 4
        """,
        params,
    ).fetchall():
        notes.append({
            "type": "info",
            "title": "New result added",
            "message": f"{r['subject']} for {r['name']} was recorded with grade {r['grade'] or 'Pending'}.",
        })

    return notes[:6]


def login_required(fn):
    @wraps(fn)
    def wrap(*a, **kw):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return fn(*a, **kw)
    return wrap


def roles_required(*roles):
    def dec(fn):
        @wraps(fn)
        def wrap(*a, **kw):
            if "user_id" not in session:
                flash("Please log in to continue.", "error")
                return redirect(url_for("login"))
            if session.get("role") not in roles:
                flash("You do not have access to that page.", "error")
                return redirect(url_for("student_dashboard" if session.get("role") == "student" else "dashboard"))
            return fn(*a, **kw)
        return wrap
    return dec


def student_payload(form, files, editing=False, current=None):
    data = {
        "student_id": clean(form.get("student_id"), 32).upper(),
        "name": clean(form.get("name"), 120),
        "email": clean(form.get("email"), 120).lower(),
        "dob": clean(form.get("dob"), 20),
        "gender": clean(form.get("gender"), 20),
        "department": clean(form.get("department"), 80),
        "year": clean(form.get("year"), 40),
        "status": clean(form.get("status"), 40) or "Active",
        "address": clean(form.get("address"), 200),
        "enroll_date": clean(form.get("enroll_date"), 20),
        "assigned_teacher_id": to_int(form.get("assigned_teacher_id")),
    }
    errs = []
    available_teachers = teachers()
    teacher_ids = {teacher["id"] for teacher in available_teachers}

    if editing and current:
        data["student_id"] = current["student_id"]
    if not editing and not data["student_id"]:
        errs.append("Student ID is required.")
    if not data["name"]:
        errs.append("Student name is required.")
    if data["department"] not in DEPARTMENTS:
        errs.append("Select a valid department.")
    if data["year"] not in YEARS:
        errs.append("Select a valid academic year.")
    if data["status"] not in STATUSES:
        errs.append("Select a valid student status.")
    if not valid_email(data["email"]):
        errs.append("Enter a valid email address.")
    if data["student_id"] and not re.fullmatch(r"[A-Z0-9-]+", data["student_id"]):
        errs.append("Student ID should contain only letters, numbers, and hyphens.")
    if data["assigned_teacher_id"] and data["assigned_teacher_id"] not in teacher_ids:
        errs.append("Select a valid assigned teacher.")

    if not data["assigned_teacher_id"] and available_teachers:
        teacher_by_year = {
            "First Year": available_teachers[0]["id"] if len(available_teachers) > 0 else None,
            "Second Year": available_teachers[1]["id"] if len(available_teachers) > 1 else available_teachers[0]["id"],
            "Third Year": available_teachers[2]["id"] if len(available_teachers) > 2 else available_teachers[-1]["id"],
            "Fourth Year": available_teachers[3]["id"] if len(available_teachers) > 3 else available_teachers[-1]["id"],
        }
        data["assigned_teacher_id"] = teacher_by_year.get(data["year"])

    try:
        data["profile_image"] = save_image(files.get("profile_image"), current["profile_image"] if current else None)
    except ValueError as exc:
        errs.append(str(exc))

    return data, errs
def dashboard_ctx():
    where, params = visible_clause("students")
    conn = db()
    totals = conn.execute(
        f"""
        SELECT
            COUNT(*) total,
            SUM(CASE WHEN status='Active' THEN 1 ELSE 0 END) active,
            SUM(CASE WHEN status='On Leave' THEN 1 ELSE 0 END) leave_count,
            SUM(CASE WHEN status='Graduated' THEN 1 ELSE 0 END) graduated
        FROM students
        WHERE {where}
        """,
        params,
    ).fetchone()

    feedback_avg = conn.execute(
        f"""
        SELECT ROUND(AVG(feedback.rating),1) avg_rating, COUNT(feedback.id) feedback_count
        FROM feedback
        JOIN students ON students.id = feedback.student_id
        WHERE {where}
        """,
        params,
    ).fetchone()

    result_count = conn.execute(
        f"""
        SELECT COUNT(results.id) result_count
        FROM results
        JOIN students ON students.id = results.student_id
        WHERE {where}
        """,
        params,
    ).fetchone()
    recent_students = conn.execute(
        f"""
        SELECT students.*, users.full_name AS teacher_name
        FROM students
        LEFT JOIN users ON users.id = students.assigned_teacher_id
        WHERE {where}
        ORDER BY datetime(students.created_at) DESC
        LIMIT 6
        """,
        params,
    ).fetchall()

    return {
        "stats": {
            "total_students": totals["total"] or 0,
            "active_students": totals["active"] or 0,
            "leave_students": totals["leave_count"] or 0,
            "graduated_students": totals["graduated"] or 0,
            "result_count": result_count["result_count"] or 0,
            "feedback_count": feedback_avg["feedback_count"] or 0,
            "avg_rating": feedback_avg["avg_rating"] or 0,
        },
        "recent_students": recent_students,
        "recent_results": recent_results(limit=6),
        "dashboard_role_label": session.get("role", "").title(),
    }
def student_dash_ctx(student_id):
    student = student_or_404(student_id)
    conn = db()
    results = conn.execute(
        "SELECT * FROM results WHERE student_id=? ORDER BY datetime(created_at) DESC LIMIT 6",
        (student_id,),
    ).fetchall()
    feedback_rows = conn.execute(
        "SELECT * FROM feedback WHERE student_id=? ORDER BY datetime(created_at) DESC LIMIT 6",
        (student_id,),
    ).fetchall()
    scores = [(r["marks_obtained"] / r["max_marks"]) * 10 for r in results if r["max_marks"]]
    return {
        "student": student,
        "attendance_summary": attendance_summary(student_id),
        "recent_results": results,
        "feedback_entries": feedback_rows,
        "cgpa_estimate": round(sum(scores) / len(scores), 2) if scores else 0.0,
    }
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("student_dashboard" if session["role"] == "student" else "dashboard"))

    if request.method == "POST":
        username = clean(request.form.get("username"), 120)
        password = request.form.get("password") or ""

        if not username or not password:
            return respond(False, "Username and password are required.", url_for("login"), 400)

        user = db().execute(
            "SELECT * FROM users WHERE username=? OR email=?",
            (username, username.lower())
        ).fetchone()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["_csrf_token"] = secrets.token_urlsafe(32)
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["student_db_id"] = user["student_id"]

            if user["role"] == "student" and user["student_id"]:
                s = db().execute("SELECT name FROM students WHERE id=?", (user["student_id"],)).fetchone()
                session["display_name"] = s["name"] if s else user["username"]
            else:
                session["display_name"] = clean(user["full_name"], 120) or user["username"].title()

            return respond(
                True,
                f"Welcome back, {session['display_name']}.",
                url_for("student_dashboard" if user["role"] == "student" else "dashboard")
            )

        return respond(False, "Invalid username or password.", url_for("login"), 401)

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out securely.", "success")
    return redirect(url_for("login"))
@app.route("/")
@login_required
def dashboard():
    if session.get("role") == "student":
        return redirect(url_for("student_dashboard"))
    return render_template("dashboard.html", **dashboard_ctx())


@app.route("/student/dashboard")
@roles_required("student")
def student_dashboard():
    return render_template("student_dashboard.html", **student_dash_ctx(session["student_db_id"]))


@app.route("/students")
@roles_required("admin", "teacher")
def view_students():
    filters = {
        "search": clean(request.args.get("search"), 100),
        "dept": clean(request.args.get("dept"), 80),
        "year": clean(request.args.get("year"), 40),
        "status": clean(request.args.get("status"), 40),
    }
    return render_template(
        "view_students.html",
        students=visible_students(filters),
        filters=filters,
        teachers=teachers(),
    )
@app.route("/api/students/search")
@roles_required("admin", "teacher")
def student_search_api():
    q = clean(request.args.get("q"), 100)
    if len(q) < 2:
        return jsonify({"items": []})
    where, params = visible_clause("students")
    rows = db().execute(
        f"""
        SELECT students.id, students.name, students.student_id, students.department, students.year
        FROM students
        WHERE {where} AND (students.name LIKE ? OR students.student_id LIKE ?)
        ORDER BY students.name ASC
        LIMIT 6
        """,
        params + [f"%{q}%", f"%{q}%"],
    ).fetchall()
    return jsonify({"items": [dict(r) for r in rows]})


@app.route("/export_students")
@roles_required("admin", "teacher")
def export_students():
    filters = {
        "search": clean(request.args.get("search"), 100),
        "dept": clean(request.args.get("dept"), 80),
        "year": clean(request.args.get("year"), 40),
        "status": clean(request.args.get("status"), 40),
    }
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student ID", "Name", "Email", "Department", "Year", "Status"])
    for r in visible_students(filters):
        writer.writerow([r["student_id"], r["name"], r["email"], r["department"], r["year"], r["status"]])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=students_export.csv"})


@app.route("/students/add", methods=["GET", "POST"])
@roles_required("admin")
def add_student():
    if request.method == "POST":
        data, errs = student_payload(request.form, request.files)
        if errs:
            if wants_json():
                return jsonify({"success": False, "message": " ".join(errs)}), 400
            flash(" ".join(errs), "error")
            return render_template("add_student.html", form=request.form, teachers=teachers(), departments=DEPARTMENTS, years=YEARS, statuses=STATUSES)

        try:
            conn = db()
            cur = conn.execute(
                """
                INSERT INTO students (
                    student_id,name,email,dob,gender,department,year,status,address,enroll_date,profile_image,assigned_teacher_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    data["student_id"], data["name"], data["email"], data["dob"], data["gender"],
                    data["department"], data["year"], data["status"], data["address"],
                    data["enroll_date"], data["profile_image"], data["assigned_teacher_id"]
                ),
            )
            conn.execute(
                "INSERT INTO users (username,email,password,role,student_id) VALUES (?, ?, ?, 'student', ?)",
                (data["student_id"], data["email"], generate_password_hash("student123"), cur.lastrowid),
            )
            conn.commit()
            return respond(True, f"{data['name']} added successfully. Default student password is student123.", url_for("view_students"))
        except sqlite3.IntegrityError:
            return respond(False, "A student with that ID already exists.", url_for("add_student"), 400)

    return render_template("add_student.html", form={}, teachers=teachers(), departments=DEPARTMENTS, years=YEARS, statuses=STATUSES)
@app.route("/students/<int:student_id>")
@login_required
def student_detail(student_id):
    student = student_or_404(student_id)
    if session.get("role") == "student" and student["id"] != session.get("student_db_id"):
        abort(403)
    results = db().execute(
        "SELECT * FROM results WHERE student_id=? ORDER BY datetime(created_at) DESC LIMIT 5",
        (student_id,),
    ).fetchall()
    feedback_rows = db().execute(
        "SELECT * FROM feedback WHERE student_id=? ORDER BY datetime(created_at) DESC LIMIT 5",
        (student_id,),
    ).fetchall()
    return render_template(
        "student_detail.html",
        student=student,
        attendance_summary=attendance_summary(student_id),
        results=results,
        feedback_entries=feedback_rows,
    )


@app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def edit_student(student_id):
    student = student_or_404(student_id)
    if request.method == "POST":
        data, errs = student_payload(request.form, request.files, True, student)
        if errs:
            if wants_json():
                return jsonify({"success": False, "message": " ".join(errs)}), 400
            flash(" ".join(errs), "error")
            return render_template("edit_student.html", student=student, teachers=teachers(), departments=DEPARTMENTS, years=YEARS, statuses=STATUSES)

        db().execute(
            """
            UPDATE students
            SET name=?, email=?, dob=?, gender=?, department=?, year=?, status=?, address=?, enroll_date=?, profile_image=?, assigned_teacher_id=?
            WHERE id=?
            """,
            (
                data["name"], data["email"], data["dob"], data["gender"], data["department"],
                data["year"], data["status"], data["address"], data["enroll_date"],
                data["profile_image"], data["assigned_teacher_id"], student_id
            ),
        )
        db().execute("UPDATE users SET email=? WHERE student_id=? AND role='student'", (data["email"], student_id))
        db().commit()
        return respond(True, f"{data['name']} updated successfully.", url_for("student_detail", student_id=student_id))

    return render_template("edit_student.html", student=student, teachers=teachers(), departments=DEPARTMENTS, years=YEARS, statuses=STATUSES)


@app.route("/students/<int:student_id>/delete", methods=["POST"])
@roles_required("admin")
def delete_student(student_id):
    student = student_or_404(student_id)
    conn = db()
    conn.execute("DELETE FROM users WHERE student_id=?", (student_id,))
    conn.execute("DELETE FROM feedback WHERE student_id=?", (student_id,))
    conn.execute("DELETE FROM results WHERE student_id=?", (student_id,))
    conn.execute("DELETE FROM attendance WHERE student_id=?", (student_id,))
    conn.execute("DELETE FROM students WHERE id=?", (student_id,))
    conn.commit()
    return respond(True, f"{student['name']} was deleted successfully.", url_for("view_students"))


@app.route("/attendance")
@roles_required("admin", "teacher")
def attendance():
    filters = {
        "date": clean(request.args.get("date"), 20) or date.today().isoformat(),
        "dept": clean(request.args.get("dept"), 80),
        "subject": clean(request.args.get("subject"), 80) or "General",
        "year": clean(request.args.get("year"), 40),
    }
    students = visible_students({"dept": filters["dept"], "year": filters["year"], "status": "Active"})
    current = {
        r["student_id"]: r["status"]
        for r in db().execute(
            "SELECT student_id,status FROM attendance WHERE date=? AND subject=?",
            (filters["date"], filters["subject"])
        ).fetchall()
    }
    return render_template("attendance.html", students=students, current_records=current, filters=filters, departments=DEPARTMENTS, years=YEARS, subjects=SUBJECTS)


@app.route("/attendance/mark", methods=["POST"])
@roles_required("admin", "teacher")
def mark_attendance():
    att_date = clean(request.form.get("date"), 20) or date.today().isoformat()
    subject = clean(request.form.get("subject"), 80) or "General"
    conn = db()
    saved = 0

    students = visible_students({"status": "Active"})
    for student in students:
        value = clean(request.form.get(f"att_{student['id']}"), 20)
        if value not in {"Present", "Absent", "Late"}:
            continue
        student_or_404(student["id"])
        conn.execute(
            """
            INSERT INTO attendance (student_id,date,status,subject)
            VALUES (?,?,?,?)
            ON CONFLICT(student_id,date,subject)
            DO UPDATE SET status=excluded.status
            """,
            (student["id"], att_date, value, subject),
        )
        saved += 1

    conn.commit()
    return respond(True, f"Attendance saved for {saved} student(s).", url_for("attendance", date=att_date, subject=subject))


@app.route("/attendance/report")
@roles_required("admin", "teacher")
def attendance_report():
    filters = {"dept": clean(request.args.get("dept"), 80), "year": clean(request.args.get("year"), 40)}
    students = visible_students({"dept": filters["dept"], "year": filters["year"]})
    rows = [{"student": s, "summary": attendance_summary(s["id"])} for s in students]
    return render_template("attendance_report.html", rows=rows, filters=filters, departments=DEPARTMENTS, years=YEARS)


@app.route("/attendance/student/<int:student_id>")
@login_required
def student_attendance(student_id):
    student = student_or_404(student_id)
    if session.get("role") == "student" and student_id != session.get("student_db_id"):
        abort(403)
    rows = db().execute(
        "SELECT * FROM attendance WHERE student_id=? ORDER BY date DESC, subject ASC",
        (student_id,),
    ).fetchall()
    return render_template("student_attendance.html", student=student, rows=rows, attendance_summary=attendance_summary(student_id))


@app.route("/attendance/<int:attendance_id>/delete", methods=["POST"])
@roles_required("admin", "teacher")
def delete_attendance(attendance_id):
    row = db().execute("SELECT * FROM attendance WHERE id=?", (attendance_id,)).fetchone()
    if row:
        student_or_404(row["student_id"])
        db().execute("DELETE FROM attendance WHERE id=?", (attendance_id,))
        db().commit()
    return respond(True, "Attendance record removed.", url_for("attendance_report"))


@app.route("/results")
@roles_required("admin", "teacher")
def results():
    filters = {"dept": clean(request.args.get("dept"), 80), "year": clean(request.args.get("year"), 40)}
    where, params = visible_clause("students")
    clauses = [where]
    if filters["dept"]:
        clauses.append("students.department = ?")
        params.append(filters["dept"])
    if filters["year"]:
        clauses.append("students.year = ?")
        params.append(filters["year"])

    rows = db().execute(
        f"""
        SELECT results.*, students.name, students.student_id AS enrollment_no, students.department, students.year
        FROM results
        JOIN students ON students.id = results.student_id
        WHERE {' AND '.join(clauses)}
        ORDER BY datetime(results.created_at) DESC
        """,
        params,
    ).fetchall()
    return render_template("results.html", rows=rows, filters=filters, departments=DEPARTMENTS, years=YEARS)


@app.route("/results/add", methods=["GET", "POST"])
@roles_required("admin", "teacher")
def add_result():
    students = visible_students({"status": "Active"})
    selected_student = to_int(request.args.get("student_id")) or to_int(request.form.get("student_id"))

    if request.method == "POST":
        sid = to_int(request.form.get("student_id"))
        subject = clean(request.form.get("subject"), 80)
        exam_type = clean(request.form.get("exam_type"), 40) or "Midterm"
        semester = clean(request.form.get("semester"), 40)
        marks = to_float(request.form.get("marks_obtained"))
        max_marks = to_float(request.form.get("max_marks"), 100)
        remarks = clean(request.form.get("remarks"), 200)

        if not sid or subject not in SUBJECTS or semester not in SEMESTERS:
            return respond(False, "Provide a valid student, subject, and semester.", url_for("add_result"), 400)
        if not max_marks or marks is None or marks < 0 or marks > max_marks:
            return respond(False, "Marks must be between 0 and the maximum marks.", url_for("add_result"), 400)

        student = student_or_404(sid)
        grade = calc_grade((marks / max_marks) * 100)
        conn = db()
        cur = conn.execute(
            """
            INSERT INTO results (student_id,subject,marks_obtained,max_marks,exam_type,semester,grade,remarks)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (sid, subject, marks, max_marks, exam_type, semester, grade, remarks),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM results WHERE id=?", (cur.lastrowid,)).fetchone()

        notify_email(
            student["email"],
            "New result published",
            f"Hello {student['name']},\n\nYour result for {row['subject']} has been published.\nScore: {row['marks_obtained']} / {row['max_marks']}\nGrade: {row['grade']}\n\nRegards,\nSIMS Pro"
        )

        return respond(True, f"Result added for {student['name']} with grade {grade}.", url_for("student_results", student_id=sid))

    return render_template("add_result.html", students=students, selected_student=selected_student, subjects=SUBJECTS, exam_types=EXAM_TYPES, semesters=SEMESTERS)


@app.route("/results/student/<int:student_id>")
@login_required
def student_results(student_id):
    student = student_or_404(student_id)
    if session.get("role") == "student" and student_id != session.get("student_db_id"):
        abort(403)
    rows = db().execute(
        "SELECT * FROM results WHERE student_id=? ORDER BY datetime(created_at) DESC",
        (student_id,),
    ).fetchall()
    return render_template("student_results.html", student=student, rows=rows, grade_color=grade_color)


@app.route("/results/<int:result_id>/edit", methods=["GET", "POST"])
@roles_required("admin", "teacher")
def edit_result(result_id):
    row = db().execute("SELECT * FROM results WHERE id=?", (result_id,)).fetchone()
    if not row:
        abort(404)
    student = student_or_404(row["student_id"])

    if request.method == "POST":
        subject = clean(request.form.get("subject"), 80)
        exam_type = clean(request.form.get("exam_type"), 40) or "Midterm"
        semester = clean(request.form.get("semester"), 40)
        marks = to_float(request.form.get("marks_obtained"))
        max_marks = to_float(request.form.get("max_marks"), 100)
        remarks = clean(request.form.get("remarks"), 200)

        if subject not in SUBJECTS or semester not in SEMESTERS:
            return respond(False, "Provide a valid subject and semester.", url_for("edit_result", result_id=result_id), 400)
        if not max_marks or marks is None or marks < 0 or marks > max_marks:
            return respond(False, "Marks must be between 0 and the maximum marks.", url_for("edit_result", result_id=result_id), 400)

        grade = calc_grade((marks / max_marks) * 100)
        db().execute(
            """
            UPDATE results
            SET subject=?, exam_type=?, semester=?, marks_obtained=?, max_marks=?, grade=?, remarks=?
            WHERE id=?
            """,
            (subject, exam_type, semester, marks, max_marks, grade, remarks, result_id),
        )
        db().commit()
        return respond(True, f"Result updated with grade {grade}.", url_for("student_results", student_id=student["id"]))

    return render_template("edit_result.html", result=row, student=student, subjects=SUBJECTS, exam_types=EXAM_TYPES, semesters=SEMESTERS)


@app.route("/results/<int:result_id>/delete", methods=["POST"])
@roles_required("admin", "teacher")
def delete_result(result_id):
    row = db().execute("SELECT * FROM results WHERE id=?", (result_id,)).fetchone()
    if row:
        student = student_or_404(row["student_id"])
        db().execute("DELETE FROM results WHERE id=?", (result_id,))
        db().commit()
        return respond(True, "Result deleted successfully.", url_for("student_results", student_id=student["id"]))
    return respond(True, "Result deleted successfully.", url_for("results"))


@app.route("/feedback")
@login_required
def feedback():
    if session.get("role") == "student":
        rows = db().execute(
            """
            SELECT feedback.*, students.name, students.student_id AS enrollment_no
            FROM feedback
            JOIN students ON students.id = feedback.student_id
            WHERE students.id=?
            ORDER BY datetime(feedback.created_at) DESC
            """,
            (session["student_db_id"],),
        ).fetchall()
        students = [student_or_404(session["student_db_id"])]
    else:
        where, params = visible_clause("students")
        rows = db().execute(
            f"""
            SELECT feedback.*, students.name, students.student_id AS enrollment_no
            FROM feedback
            JOIN students ON students.id = feedback.student_id
            WHERE {where}
            ORDER BY datetime(feedback.created_at) DESC
            """,
            params,
        ).fetchall()
        students = visible_students({"status": "Active"})

    return render_template("feedback.html", rows=rows, students=students, categories=FEEDBACK_CATEGORIES)


@app.route("/feedback/add", methods=["GET", "POST"])
@login_required
def add_feedback():
    students = [student_or_404(session["student_db_id"])] if session.get("role") == "student" else visible_students({"status": "Active"})

    if request.method == "POST":
        sid = session.get("student_db_id") if session.get("role") == "student" else to_int(request.form.get("student_id"))
        student = student_or_404(sid)
        rating = to_int(request.form.get("rating"))
        category = clean(request.form.get("category"), 80) or "General"
        message = clean(request.form.get("message"), 500)

        if not message:
            return respond(False, "Feedback message cannot be empty.", url_for("add_feedback"), 400)
        if rating not in {1, 2, 3, 4, 5}:
            return respond(False, "Rating must be between 1 and 5.", url_for("add_feedback"), 400)
        if category not in FEEDBACK_CATEGORIES:
            return respond(False, "Select a valid feedback category.", url_for("add_feedback"), 400)

        db().execute(
            "INSERT INTO feedback (student_id,message,rating,category) VALUES (?,?,?,?)",
            (student["id"], message, rating, category),
        )
        db().commit()
        return respond(True, "Feedback submitted successfully.", url_for("student_dashboard" if session.get("role") == "student" else "feedback"))

    return render_template("add_feedback.html", students=students, categories=FEEDBACK_CATEGORIES)


@app.route("/feedback/<int:feedback_id>/delete", methods=["POST"])
@roles_required("admin", "teacher")
def delete_feedback(feedback_id):
    row = db().execute("SELECT * FROM feedback WHERE id=?", (feedback_id,)).fetchone()
    if row:
        student_or_404(row["student_id"])
        db().execute("DELETE FROM feedback WHERE id=?", (feedback_id,))
        db().commit()
    return respond(True, "Feedback removed.", url_for("feedback"))


@app.route("/charts")
@roles_required("admin", "teacher")
def charts():
    return render_template("charts.html", departments=DEPARTMENTS, years=YEARS)


def chart_where():
    where, params = visible_clause("students")
    clauses = [where]
    dept = clean(request.args.get("dept"), 80)
    year = clean(request.args.get("year"), 40)
    if dept:
        clauses.append("students.department = ?")
        params.append(dept)
    if year:
        clauses.append("students.year = ?")
        params.append(year)
    return " AND ".join(clauses), params
@app.route("/api/charts/attendance")
@roles_required("admin", "teacher")
def chart_attendance():
    where, params = chart_where()
    bars = db().execute(
        f"""
        SELECT students.name,
               ROUND(100.0 * SUM(CASE WHEN attendance.status='Present' THEN 1 ELSE 0 END) / NULLIF(COUNT(attendance.id),0), 1) AS attendance_rate
        FROM students
        LEFT JOIN attendance ON attendance.student_id = students.id
        WHERE {where}
        GROUP BY students.id, students.name
        HAVING COUNT(attendance.id) > 0
        ORDER BY attendance_rate ASC
        """,
        params,
    ).fetchall()
    trend = db().execute(
        f"""
        SELECT attendance.date,
               SUM(CASE WHEN attendance.status='Present' THEN 1 ELSE 0 END) AS present_count,
               COUNT(attendance.id) AS total_count
        FROM attendance
        JOIN students ON students.id = attendance.student_id
        WHERE {where}
        GROUP BY attendance.date
        ORDER BY attendance.date DESC
        LIMIT 10
        """,
        params,
    ).fetchall()
    return jsonify({"attendance_by_student": [dict(r) for r in bars], "attendance_trend": [dict(r) for r in reversed(trend)]})


@app.route("/api/charts/results")
@roles_required("admin", "teacher")
def chart_results():
    where, params = chart_where()
    avg_rows = db().execute(
        f"""
        SELECT results.subject, ROUND(AVG((results.marks_obtained / results.max_marks) * 100), 1) AS average_score
        FROM results
        JOIN students ON students.id = results.student_id
        WHERE {where}
        GROUP BY results.subject
        ORDER BY average_score DESC
        """,
        params,
    ).fetchall()
    dist = db().execute(
        f"""
        SELECT results.grade, COUNT(results.id) AS total
        FROM results
        JOIN students ON students.id = results.student_id
        WHERE {where}
        GROUP BY results.grade
        ORDER BY results.grade ASC
        """,
        params,
    ).fetchall()
    return jsonify({"subject_average": [dict(r) for r in avg_rows], "grade_distribution": [dict(r) for r in dist]})


@app.route("/api/charts/feedback")
@roles_required("admin", "teacher")
def chart_feedback():
    where, params = chart_where()
    dist = db().execute(
        f"""
        SELECT feedback.rating, COUNT(feedback.id) AS total
        FROM feedback
        JOIN students ON students.id = feedback.student_id
        WHERE {where}
        GROUP BY feedback.rating
        ORDER BY feedback.rating ASC
        """,
        params,
    ).fetchall()
    cat = db().execute(
        f"""
        SELECT feedback.category, ROUND(AVG(feedback.rating), 1) AS average_rating
        FROM feedback
        JOIN students ON students.id = feedback.student_id
        WHERE {where}
        GROUP BY feedback.category
        ORDER BY average_rating DESC
        """,
        params,
    ).fetchall()
    dept = db().execute(
        f"""
        SELECT students.department, COUNT(students.id) AS total
        FROM students
        WHERE {where}
        GROUP BY students.department
        ORDER BY total DESC
        """,
        params,
    ).fetchall()
    return jsonify({
        "rating_distribution": [dict(r) for r in dist],
        "category_breakdown": [dict(r) for r in cat],
        "department_split": [dict(r) for r in dept],
    })


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password") or ""
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        user = db().execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()

        if not current_password or not password or not confirm:
            return respond(False, "All password fields are required.", url_for("change_password"), 400)
        if not check_password_hash(user["password"], current_password):
            return respond(False, "Current password is incorrect.", url_for("change_password"), 400)
        if len(password) < 8:
            return respond(False, "New password must be at least 8 characters long.", url_for("change_password"), 400)
        if password != confirm:
            return respond(False, "New password and confirmation do not match.", url_for("change_password"), 400)

        db().execute("UPDATE users SET password=? WHERE id=?", (generate_password_hash(password), session["user_id"]))
        db().commit()
        return respond(True, "Password updated successfully.", url_for("dashboard"))

    return render_template("change_password.html")


def report_pdf(student, rows, report_type="results"):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        return None

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="SIMS Report")
    styles = getSampleStyleSheet()
    title = "Student Report Card" if report_type == "results" else "Attendance Report"
    elements = [
        Paragraph(title, styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Name: {student['name']}", styles["BodyText"]),
        Paragraph(f"Enrollment No: {student['student_id']}", styles["BodyText"]),
        Paragraph(f"Department: {student['department']} | Year: {student['year']}", styles["BodyText"]),
        Spacer(1, 12),
    ]

    table_data = [["Subject", "Semester", "Exam", "Score", "Grade"]] if report_type == "results" else [["Date", "Subject", "Status", "Remarks"]]
    for r in rows:
        if report_type == "results":
            table_data.append([r["subject"], r["semester"], r["exam_type"], f"{r['marks_obtained']} / {r['max_marks']}", r["grade"]])
        else:
            table_data.append([r["date"], r["subject"], r["status"], r["remarks"] or "-"])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)
    doc.build(elements)
    buf.seek(0)
    return buf


@app.route("/students/<int:student_id>/report-card.pdf")
@login_required
def report_card_pdf(student_id):
    student = student_or_404(student_id)
    if session.get("role") == "student" and student_id != session.get("student_db_id"):
        abort(403)
    rows = db().execute("SELECT * FROM results WHERE student_id=? ORDER BY semester, subject", (student_id,)).fetchall()
    pdf = report_pdf(student, rows, "results")
    if pdf is None:
        flash("PDF export requires the reportlab package. Add it from requirements.txt.", "error")
        return redirect(url_for("student_results", student_id=student_id))
    return send_file(pdf, as_attachment=True, download_name=f"{student['student_id']}_report_card.pdf")
@app.route("/attendance/student/<int:student_id>/report.pdf")
@login_required
def attendance_pdf(student_id):
    student = student_or_404(student_id)
    if session.get("role") == "student" and student_id != session.get("student_db_id"):
        abort(403)
    rows = db().execute("SELECT * FROM attendance WHERE student_id=? ORDER BY date DESC", (student_id,)).fetchall()
    pdf = report_pdf(student, rows, "attendance")
    if pdf is None:
        flash("PDF export requires the reportlab package. Add it from requirements.txt.", "error")
        return redirect(url_for("student_attendance", student_id=student_id))
    return send_file(pdf, as_attachment=True, download_name=f"{student['student_id']}_attendance_report.pdf")


@app.errorhandler(400)
def bad_request(error):
    message = getattr(error, "description", "The request could not be processed.")
    if wants_json():
        return jsonify({"success": False, "message": message}), 400
    flash(message, "error")
    if session.get("user_id"):
        return redirect(url_for("student_dashboard" if session.get("role") == "student" else "dashboard"))
    return redirect(url_for("login"))


@app.errorhandler(403)
def forbidden(_):
    flash("You do not have permission to access that resource.", "error")
    if session.get("user_id"):
        return redirect(url_for("student_dashboard" if session.get("role") == "student" else "dashboard"))
    return redirect(url_for("login"))


@app.errorhandler(404)
def not_found(_):
    flash("The requested resource could not be found.", "error")
    if session.get("user_id"):
        return redirect(url_for("student_dashboard" if session.get("role") == "student" else "dashboard"))
    return redirect(url_for("login"))


init_db()


if __name__ == "__main__":
    app.run(debug=False)