from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "studentinfolite_secret_2024"

DB_PATH = os.path.join(os.path.dirname(__file__), "students.db")

DEPARTMENTS = [
    'Computer Science',
    'Information Technology',
    'Electronics',
    'Mechanical Engineering',
    'Civil Engineering',
    'Business Administration',
    'Other'
]

YEARS = [
    'First Year',
    'Second Year',
    'Third Year',
    'Fourth Year'
]

STATUSES = [
    'Active',
    'Graduated',
    'On Leave',
    'Inactive'
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        department TEXT NOT NULL,
        academic_year TEXT NOT NULL,
        status TEXT DEFAULT 'Active',
        address TEXT,
        date_of_birth TEXT,
        enrollment_date TEXT,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


@app.context_processor
def inject_now():
    return {"now": datetime.now().strftime("%d %b %Y")}


def get_stats():

    conn = get_db()
    c = conn.cursor()

    total = c.execute("SELECT COUNT(*) FROM students").fetchone()[0]

    active = c.execute(
        "SELECT COUNT(*) FROM students WHERE status='Active'"
    ).fetchone()[0]

    graduated = c.execute(
        "SELECT COUNT(*) FROM students WHERE status='Graduated'"
    ).fetchone()[0]

    on_leave = c.execute(
        "SELECT COUNT(*) FROM students WHERE status='On Leave'"
    ).fetchone()[0]

    dept_counts = {
        d: c.execute(
            "SELECT COUNT(*) FROM students WHERE department=?",
            (d,)
        ).fetchone()[0] for d in DEPARTMENTS
    }

    year_counts = {
        y: c.execute(
            "SELECT COUNT(*) FROM students WHERE academic_year=?",
            (y,)
        ).fetchone()[0] for y in YEARS
    }

    conn.close()

    return total, active, graduated, on_leave, dept_counts, year_counts


@app.route("/")
def dashboard():

    total, active, graduated, on_leave, dept_counts, year_counts = get_stats()

    conn = get_db()

    recent = conn.execute(
        "SELECT * FROM students ORDER BY created_at DESC LIMIT 8"
    ).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        total=total,
        active=active,
        graduated=graduated,
        on_leave=on_leave,
        dept_counts=dept_counts,
        year_counts=year_counts,
        recent=recent,
        departments=DEPARTMENTS,
        years=YEARS
    )


@app.route("/students")
def view_students():

    df = request.args.get("department")
    yf = request.args.get("year")
    sf = request.args.get("status")
    search = request.args.get("search")

    query = "SELECT * FROM students WHERE 1=1"
    params = []

    if df:
        query += " AND department=?"
        params.append(df)

    if yf:
        query += " AND academic_year=?"
        params.append(yf)

    if sf:
        query += " AND status=?"
        params.append(sf)

    if search:
        query += " AND (full_name LIKE ? OR student_id LIKE ? OR email LIKE ?)"
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]

    query += " ORDER BY created_at DESC"

    conn = get_db()
    students = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        "view_students.html",
        students=students,
        departments=DEPARTMENTS,
        years=YEARS,
        statuses=STATUSES,
        dept_filter=df,
        year_filter=yf,
        status_filter=sf,
        search=search
    )


@app.route("/add", methods=["GET", "POST"])
def add_student():

    if request.method == "POST":

        sid = request.form.get("student_id")
        name = request.form.get("full_name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        dept = request.form.get("department")
        year = request.form.get("academic_year")
        status = request.form.get("status")

        if not sid or not name:
            flash("Student ID and Name are required!", "error")
            return redirect(url_for("add_student"))

        try:

            conn = get_db()

            conn.execute("""
            INSERT INTO students
            (student_id, full_name, email, phone, department, academic_year, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (sid, name, email, phone, dept, year, status))

            conn.commit()
            conn.close()

            flash("Student added successfully!", "success")
            return redirect(url_for("view_students"))

        except sqlite3.IntegrityError:

            flash("Student ID already exists!", "error")

    return render_template(
        "add_student.html",
        departments=DEPARTMENTS,
        years=YEARS,
        statuses=STATUSES
    )


@app.route("/student/<int:sid>")
def student_detail(sid):

    conn = get_db()

    student = conn.execute(
        "SELECT * FROM students WHERE id=?",
        (sid,)
    ).fetchone()

    conn.close()

    if not student:
        flash("Student not found.", "error")
        return redirect(url_for("view_students"))

    return render_template("student_detail.html", student=student)


@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_student(id):

    conn = get_db()

    student = conn.execute(
        "SELECT * FROM students WHERE id=?",
        (id,)
    ).fetchone()

    if request.method == "POST":

        full_name = request.form.get("full_name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        department = request.form.get("department")
        academic_year = request.form.get("academic_year")
        status = request.form.get("status")

        conn.execute("""
        UPDATE students
        SET full_name=?, email=?, phone=?, department=?, academic_year=?, status=?
        WHERE id=?
        """, (full_name, email, phone, department, academic_year, status, id))

        conn.commit()
        conn.close()

        flash("Student updated successfully!", "success")
        return redirect(url_for("view_students"))

    conn.close()

    return render_template(
        "edit_student.html",
        student=student,
        departments=DEPARTMENTS,
        years=YEARS,
        statuses=STATUSES
    )


@app.route("/delete/<int:id>", methods=["POST"])
def delete_student(id):

    conn = get_db()

    conn.execute("DELETE FROM students WHERE id=?", (id,))
    conn.commit()

    conn.close()

    flash("Student deleted successfully!", "success")

    return redirect(url_for("view_students"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)