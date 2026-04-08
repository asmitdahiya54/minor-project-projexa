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