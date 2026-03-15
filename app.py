from flask import Flask
from flask import Flask, render_template
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "studentinfolite_secret_2024"

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

if __name__ == "__main__":
    app.run(debug=True)
