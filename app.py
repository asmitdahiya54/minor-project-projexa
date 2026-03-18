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
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
@app.route("/")
def dashboard():
    return render_template("dashboard.html")

if __name__ == "__main__":
    app.run(debug=True)
