from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "studentinfolite_secret_2024"

DB_PATH = os.path.join(os.path.dirname(__file__), "students.db")

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

    c.execute("SELECT COUNT(*) FROM students")
    count = c.fetchone()[0]

    if count == 0:
        sample_students = [
            ("CS001", "Rahul Sharma", "rahul@email.com", "9876543210", "Computer Science", "First Year", "Active"),
            ("CS002", "Anjali Verma", "anjali@email.com", "9876543211", "Computer Science", "Second Year", "Active"),
            ("IT001", "Amit Singh", "amit@email.com", "9876543212", "Information Technology", "Third Year", "Graduated"),
            ("ME001", "Pooja Yadav", "pooja@email.com", "9876543213", "Mechanical Engineering", "Fourth Year", "On Leave"),
        ]

        for s in sample_students:
            c.execute("""
                INSERT INTO students 
                (student_id, full_name, email, phone, department, academic_year, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, s)

    conn.commit()
    conn.close()

@app.context_processor
def inject_now():
    return {"now": datetime.now().strftime("%d %b %Y")}

@app.route("/")
def dashboard():
    conn = get_db()
    c = conn.cursor()

    total = c.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    active = c.execute("SELECT COUNT(*) FROM students WHERE status='Active'").fetchone()[0]
    graduated = c.execute("SELECT COUNT(*) FROM students WHERE status='Graduated'").fetchone()[0]
    on_leave = c.execute("SELECT COUNT(*) FROM students WHERE status='On Leave'").fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        total=total,
        active=active,
        graduated=graduated,
        on_leave=on_leave
    )
@app.route("/students")
def view_students():

    search = request.args.get("search", "")

    conn = get_db()

    if search:
        students = conn.execute("""
            SELECT * FROM students
            WHERE full_name LIKE ?
            OR student_id LIKE ?
            OR email LIKE ?
            ORDER BY created_at DESC
        """, (f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
    else:
        students = conn.execute(
            "SELECT * FROM students ORDER BY created_at DESC"
        ).fetchall()

    conn.close()

    return render_template("view_students.html", students=students, search=search)

@app.route("/add", methods=["GET", "POST"])
def add_student():

    if request.method == "POST":
        student_id = request.form.get("student_id")
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        department = request.form.get("department")
        academic_year = request.form.get("academic_year")
        status = request.form.get("status")

        # Basic validation
        if not student_id or not full_name:
            flash("Student ID and Name are required!", "error")
            return redirect(url_for("add_student"))

        try:
            conn = get_db()
            conn.execute("""
                INSERT INTO students
                (student_id, full_name, email, phone, department, academic_year, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (student_id, full_name, email, phone, department, academic_year, status))
            conn.commit()
            conn.close()

            flash("Student added successfully!", "success")
            return redirect(url_for("view_students"))

        except sqlite3.IntegrityError:
            flash("Student ID already exists!", "error")
            return redirect(url_for("add_student"))

    return render_template("add_student.html")

@app.route("/delete/<int:id>")
def delete_student(id):

    conn = get_db()

    conn.execute("DELETE FROM students WHERE id=?", (id,))
    conn.commit()
    conn.close()

    flash("Student deleted successfully!", "success")

    return redirect(url_for("view_students"))
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_student(id):

    conn = get_db()

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

    student = conn.execute(
        "SELECT * FROM students WHERE id=?", (id,)
    ).fetchone()

    conn.close()

    return render_template("edit_student.html", student=student)
@app.route("/student/<int:sid>")
def student_detail(sid):

    conn = get_db()
    student = conn.execute(
        "SELECT * FROM students WHERE id=?", (sid,)
    ).fetchone()
    conn.close()

    if not student:
        flash("Student not found.", "error")
        return redirect(url_for("view_students"))

    return render_template("student_detail.html", student=student)
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
@app.route("/students")
def view_students():
    @app.route("/students")
    def view_students():

    department = request.args.get("department")
    year = request.args.get("year")
    status = request.args.get("status")

    conn = get_db()

    query = "SELECT * FROM students WHERE 1=1"
    params = []

    if department:
        query += " AND department=?"
        params.append(department)

    if year:
        query += " AND academic_year=?"
        params.append(year)

    if status:
        query += " AND status=?"
        params.append(status)

    students = conn.execute(query, params).fetchall()

    conn.close()

    return render_template(
        "view_students.html",
        students=students,
        department=department,
        year=year,
        status=status
    )