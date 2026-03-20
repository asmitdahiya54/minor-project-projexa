from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "studentinfolite_secret_2024"

DB_PATH = os.path.join(os.path.dirname(__file__), "students.db")


# ---------------- DATABASE ----------------
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


# ---------------- STATS ----------------
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

    conn.close()

    return total, active, graduated, on_leave


# ---------------- DASHBOARD ----------------
@app.route("/")
def dashboard():

    total, active, graduated, on_leave = get_stats()

    return render_template(
        "dashboard.html",
        total=total,
        active=active,
        graduated=graduated,
        on_leave=on_leave
    )


# ---------------- VIEW ALL ----------------
@app.route("/students")
def view_students():
    conn = get_db()

    students = conn.execute(
        "SELECT * FROM students ORDER BY id DESC"
    ).fetchall()

    conn.close()

    students = students if students else []

    return render_template("view_students.html", students=students)


# ---------------- ADD ----------------
@app.route("/add", methods=["GET", "POST"])
def add_student():

    if request.method == "POST":
        sid = request.form.get("student_id")
        name = request.form.get("full_name")
        status = request.form.get("status", "Active")  # ✅ NEW

        if not sid or not name:
            flash("Student ID and Name required!")
            return redirect(url_for("add_student"))

        conn = get_db()

        conn.execute(
            "INSERT INTO students (student_id, full_name, status) VALUES (?, ?, ?)",
            (sid, name, status)
        )

        conn.commit()
        conn.close()

        flash("Student added successfully!")

        return redirect(url_for("dashboard"))

    return render_template("add_student.html")


# ---------------- DETAIL ----------------
@app.route("/student/<int:sid>")
def student_detail(sid):

    conn = get_db()

    student = conn.execute(
        "SELECT * FROM students WHERE id=?",
        (sid,)
    ).fetchone()

    conn.close()

    if not student:
        return "Student not found"

    return render_template("student_detail.html", student=student)


# ---------------- EDIT ----------------
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_student(id):

    conn = get_db()

    student = conn.execute(
        "SELECT * FROM students WHERE id=?",
        (id,)
    ).fetchone()

    if request.method == "POST":

        name = request.form.get("full_name")
        status = request.form.get("status")

        conn.execute(
            "UPDATE students SET full_name=?, status=? WHERE id=?",
            (name, status, id)
        )

        conn.commit()
        conn.close()

        flash("Student updated successfully!")

        return redirect(url_for("view_students"))

    conn.close()

    return render_template("edit_student.html", student=student)


# ---------------- DELETE ----------------
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


# ---------------- RUN ----------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)