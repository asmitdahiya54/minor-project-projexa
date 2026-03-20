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
        department TEXT,
        academic_year TEXT,
        status TEXT
    )
    """)

    conn.commit()
    conn.close()



@app.route("/")
def dashboard():

    total, active = get_stats()

    return render_template(
        "dashboard.html",
        total=total,
        active=active
    )


@app.route("/student/<int:sid>")
def student_detail(sid):

    conn = get_db()

    student = conn.execute(
        "SELECT * FROM students WHERE id=?",
        (sid,)
    ).fetchone()

    conn.close()
    conn = get_db()

    student = conn.execute(
        "SELECT * FROM students WHERE id=?",
        (sid,)
    ).fetchone()

    conn.close()

    return render_template("student_detail.html", student=student)
    return render_template("student_detail.html", student=student)


@app.route("/delete/<int:id>", methods=["POST"])
def delete_student(id):

    conn = get_db()

    conn.execute(
        "DELETE FROM students WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()
    flash("Student deleted successfully!")
    return redirect(url_for("view_students"))


@app.route("/students")
def view_students():

    conn = get_db()

    students = conn.execute(
    "SELECT * FROM students ORDER BY id DESC"
).fetchall()

    conn.close()
    students = students if students else []

    return render_template("view_students.html", students=students)

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_student(id):

    conn = get_db()

    student = conn.execute(
        "SELECT * FROM students WHERE id=?",
        (id,)
    ).fetchone()

    if request.method == "POST":

        name = request.form.get("full_name")

        conn.execute(
            "UPDATE students SET full_name=? WHERE id=?",
            (name, id)
        )

        conn.commit()
        conn.close()

        flash("Student updated successfully!")
        
        return redirect(url_for("view_students"))

    conn.close()

    return render_template("edit_student.html", student=student)

@app.route("/add", methods=["GET", "POST"])
def add_student():

    if request.method == "POST":
        sid = request.form.get("student_id")
        name = request.form.get("full_name")

        if not sid or not name:
            flash("Student ID and Name required!")
            return redirect(url_for("add_student"))
        conn = get_db()

        conn.execute(
            "INSERT INTO students (student_id, full_name) VALUES (?, ?)",
            (sid, name)
        )

        conn.commit()
        conn.close()

        flash("Student added successfully!")

        return redirect(url_for("dashboard"))

    return render_template("add_student.html")

def get_stats():

    conn = get_db()
    c = conn.cursor()

    total = c.execute("SELECT COUNT(*) FROM students").fetchone()[0]

    active = c.execute(
        "SELECT COUNT(*) FROM students WHERE status='Active'"
    ).fetchone()[0]

    conn.close()

    return total, active


if __name__ == "__main__":
    init_db()
    app.run(debug=True)