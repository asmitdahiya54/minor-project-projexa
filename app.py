from flask import Flask
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)

@app.route("/")
def home():
    return "StudentInfoLite"

if __name__ == "__main__":
    app.run(debug=True)