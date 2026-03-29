from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3, os
from datetime import date, datetime

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get("SECRET_KEY", "dev_key")
DB = os.path.join(os.path.dirname(__file__), 'sims.db')

# ── DB SETUP ──────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id  TEXT UNIQUE NOT NULL,
                name        TEXT NOT NULL,
                email       TEXT,
                dob         TEXT,
                gender      TEXT,
                department  TEXT NOT NULL,
                year        TEXT NOT NULL,
                status      TEXT DEFAULT 'Active',
                address     TEXT,
                enroll_date TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id  INTEGER NOT NULL,
                date        TEXT NOT NULL,
                status      TEXT NOT NULL CHECK(status IN ('Present','Absent','Late')),
                subject     TEXT DEFAULT 'General',
                remarks     TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(student_id, date, subject),
                FOREIGN KEY(student_id) REFERENCES students(id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS results (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id      INTEGER NOT NULL,
                subject         TEXT NOT NULL,
                marks_obtained  REAL NOT NULL,
                max_marks       REAL NOT NULL DEFAULT 100,
                exam_type       TEXT DEFAULT 'Midterm',
                semester        TEXT NOT NULL,
                grade           TEXT,
                remarks         TEXT,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(student_id) REFERENCES students(id)
            )
        ''')
        # ── NEW: Feedback table ───────────────────────────────
        conn.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id  INTEGER NOT NULL,
                message     TEXT NOT NULL,
                rating      INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                category    TEXT DEFAULT 'General',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(student_id) REFERENCES students(id)
            )
        ''')

        cur = conn.execute('SELECT COUNT(*) FROM students')
        if cur.fetchone()[0] == 0:
            seed = [
                ('CS2024001','Asmit Dahiya','asmit@example.com','2003-05-12','Male','Computer Science','Third Year','Active','Delhi','2022-07-15'),
                ('CS2024002','Dev Narwal','dev@example.com','2004-02-18','Male','Computer Science','Second Year','Active','Haryana','2023-07-10'),
                ('IT2024001','Manish Chauhan','manish@example.com','2005-09-30','Male','Information Technology','First Year','Active','Punjab','2024-07-08'),
                ('IT2024002','Dikshit Kumar','dikshit@example.com','2004-11-22','Male','Information Technology','Second Year','Active','Delhi','2023-07-12'),
                ('EC2024001','Gourav Sharma','gourav@example.com','2005-03-05','Male','Electronics','First Year','Active','Rajasthan','2024-07-15'),
                ('ME2024001','Aditya Dangi','aditya@example.com','2005-07-19','Male','Mechanical Engineering','First Year','On Leave','MP','2024-07-14'),
                ('CS2021001','Priya Mehta','priya@example.com','2002-01-25','Female','Computer Science','Fourth Year','Active','Mumbai','2021-07-10'),
                ('IT2021001','Riya Verma','riya@example.com','2002-06-14','Female','Information Technology','Third Year','Graduated','Pune','2021-07-11'),
                ('EC2023001','Sahil Bisht','sahil@example.com','2003-12-01','Male','Electronics','Second Year','Active','Chandigarh','2023-07-09'),
                ('ME2022001','Neha Rawat','neha@example.com','2003-04-08','Female','Mechanical Engineering','Third Year','Active','Dehradun','2022-07-13'),
            ]
            conn.executemany('''
                INSERT INTO students
                (student_id,name,email,dob,gender,department,year,status,address,enroll_date)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            ''', seed)
            conn.commit()

init_db()

DEPARTMENTS = ['Computer Science','Information Technology','Electronics',
               'Mechanical Engineering','Civil Engineering','Business Administration']
YEARS      = ['First Year','Second Year','Third Year','Fourth Year']
STATUSES   = ['Active','On Leave','Graduated']
SEMESTERS  = ['Semester 1','Semester 2','Semester 3','Semester 4',
              'Semester 5','Semester 6','Semester 7','Semester 8']
EXAM_TYPES = ['Midterm','Final','Quiz','Assignment','Practical']
SUBJECTS   = ['Mathematics','Physics','Chemistry','English','Data Structures',
              'Algorithms','DBMS','Operating Systems','Computer Networks',
              'Software Engineering','Web Development','Machine Learning',
              'Discrete Mathematics','Digital Electronics','Circuit Theory',
              'Thermodynamics','Fluid Mechanics','General']

def calculate_grade(pct):
    if pct >= 90: return 'O'
    if pct >= 80: return 'A+'
    if pct >= 70: return 'A'
    if pct >= 60: return 'B+'
    if pct >= 50: return 'B'
    if pct >= 40: return 'C'
    return 'F'

def get_grade_color(grade):
    colors = {'O':'#10b981','A+':'#3b82f6','A':'#6366f1',
              'B+':'#f59e0b','B':'#f97316','C':'#ef4444','F':'#dc2626'}
    return colors.get(grade,'#6b7280')


# ── ROUTES ────────────────────────────────────────────────

@app.route('/')
def dashboard():
    with get_db() as conn:
        total   = conn.execute('SELECT COUNT(*) FROM students').fetchone()[0]
        active  = conn.execute("SELECT COUNT(*) FROM students WHERE status='Active'").fetchone()[0]
        grad    = conn.execute("SELECT COUNT(*) FROM students WHERE status='Graduated'").fetchone()[0]
        leave   = conn.execute("SELECT COUNT(*) FROM students WHERE status='On Leave'").fetchone()[0]

        dept_counts = {d: conn.execute(
            'SELECT COUNT(*) FROM students WHERE department=?', (d,)
        ).fetchone()[0] for d in DEPARTMENTS}

        year_counts = {y: conn.execute(
            'SELECT COUNT(*) FROM students WHERE year=?', (y,)
        ).fetchone()[0] for y in YEARS}

        recent = conn.execute(
            'SELECT * FROM students ORDER BY created_at DESC LIMIT 5'
        ).fetchall()

    return render_template('dashboard.html',
        total=total, active=active, grad=grad, leave=leave,
        dept_counts=dept_counts, year_counts=year_counts,
        recent=recent, departments=DEPARTMENTS, years=YEARS
    )


@app.route('/students')
def view_students():
    dept   = request.args.get('dept', '')
    year   = request.args.get('year', '')
    status = request.args.get('status', '')
    search = request.args.get('search', '')

    query  = 'SELECT * FROM students WHERE 1=1'
    params = []
    if dept:   query += ' AND department=?';  params.append(dept)
    if year:   query += ' AND year=?';        params.append(year)
    if status: query += ' AND status=?';      params.append(status)
    if search:
        query += ' AND (name LIKE ? OR student_id LIKE ?)'
        params += [f'%{search}%', f'%{search}%']
    query += ' ORDER BY created_at DESC'

    with get_db() as conn:
        students = conn.execute(query, params).fetchall()

    return render_template('view_students.html',
        students=students, departments=DEPARTMENTS,
        years=YEARS, statuses=STATUSES,
        filters={'dept': dept, 'year': year, 'status': status, 'search': search}
    )


@app.route('/students/add', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        data = {k: request.form.get(k, '').strip() for k in [
            'student_id','name','email','dob','gender',
            'department','year','status','address','enroll_date'
        ]}
        if not data['name'] or not data['student_id'] or not data['department'] or not data['year']:
            flash('Name, Student ID, Department and Year are required.', 'error')
            return render_template('add_student.html', departments=DEPARTMENTS, years=YEARS, statuses=STATUSES, form=data)

        try:
            with get_db() as conn:
                conn.execute('''
                    INSERT INTO students
                    (student_id,name,email,dob,gender,department,year,status,address,enroll_date)
                    VALUES (:student_id,:name,:email,:dob,:gender,:department,:year,:status,:address,:enroll_date)
                ''', data)
                conn.commit()
            flash(f'{data["name"]} has been registered successfully!', 'success')
            return redirect(url_for('dashboard'))
        except sqlite3.IntegrityError:
            flash('A student with that ID already exists.', 'error')

    return render_template('add_student.html', departments=DEPARTMENTS, years=YEARS, statuses=STATUSES, form={})


@app.route('/students/<int:sid>')
def student_detail(sid):
    with get_db() as conn:
        student = conn.execute('SELECT * FROM students WHERE id=?', (sid,)).fetchone()
    if not student:
        flash('Student not found.', 'error')
        return redirect(url_for('view_students'))
    return render_template('student_detail.html', student=student)


@app.route('/students/<int:sid>/edit', methods=['GET', 'POST'])
def edit_student(sid):
    with get_db() as conn:
        student = conn.execute('SELECT * FROM students WHERE id=?', (sid,)).fetchone()
    if not student:
        flash('Student not found.', 'error')
        return redirect(url_for('view_students'))

    if request.method == 'POST':
        data = {k: request.form.get(k, '').strip() for k in [
            'name','email','dob','gender',
            'department','year','status','address','enroll_date'
        ]}
        data['id'] = sid
        with get_db() as conn:
            conn.execute('''
                UPDATE students SET
                  name=:name, email=:email, dob=:dob, gender=:gender,
                  department=:department, year=:year, status=:status,
                  address=:address, enroll_date=:enroll_date
                WHERE id=:id
            ''', data)
            conn.commit()
        flash(f'{data["name"]} updated successfully!', 'success')
        return redirect(url_for('student_detail', sid=sid))

    return render_template('edit_student.html',
        student=student, departments=DEPARTMENTS, years=YEARS, statuses=STATUSES
    )


@app.route('/students/<int:sid>/delete', methods=['POST'])
def delete_student(sid):
    with get_db() as conn:
        s = conn.execute('SELECT name FROM students WHERE id=?', (sid,)).fetchone()
        if s:
            conn.execute('DELETE FROM students WHERE id=?', (sid,))
            conn.commit()
            flash(f'{s["name"]} has been removed.', 'success')
    return redirect(url_for('view_students'))


if __name__ == '__main__':
    app.run(debug=True)
