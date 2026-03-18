from flask import Flask
from flask import Flask, render_template
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
    return render_template("dashboard.html")

if __name__ == "__main__":
    app.run(debug=True)
