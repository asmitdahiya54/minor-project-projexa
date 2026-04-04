from flask import (Flask, render_template, request, redirect,
                   url_for, flash, jsonify, session)
import sqlite3, os
from datetime import date, datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get("SECRET_KEY", "sims_super_secret_key_2024")
DB = os.path.join(os.path.dirname(__file__), 'sims.db')


# ══════════════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════════════

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        # ── Core tables (unchanged) ────────────────────────────
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
            )''')
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
            )''')
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
            )''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id  INTEGER NOT NULL,
                message     TEXT NOT NULL,
                rating      INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                category    TEXT DEFAULT 'General',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(student_id) REFERENCES students(id)
            )''')

        # ── NEW: Users table ───────────────────────────────────
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT UNIQUE NOT NULL,
                email       TEXT,
                password    TEXT NOT NULL,
                role        TEXT NOT NULL CHECK(role IN ('admin','student')),
                student_id  INTEGER,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(student_id) REFERENCES students(id)
            )''')

        # ── Seed students ──────────────────────────────────────
        if conn.execute('SELECT COUNT(*) FROM students').fetchone()[0] == 0:
            seed = [
                ('CS2024001','Asmit Dahiya',  'asmit@example.com', '2003-05-12','Male',  'Computer Science',      'Third Year', 'Active',   'Delhi',      '2022-07-15'),
                ('CS2024002','Dev Narwal',    'dev@example.com',   '2004-02-18','Male',  'Computer Science',      'Second Year','Active',   'Haryana',    '2023-07-10'),
                ('IT2024001','Manish Chauhan','manish@example.com','2005-09-30','Male',  'Information Technology','First Year', 'Active',   'Punjab',     '2024-07-08'),
                ('IT2024002','Dikshit Kumar', 'dikshit@example.com','2004-11-22','Male', 'Information Technology','Second Year','Active',   'Delhi',      '2023-07-12'),
                ('EC2024001','Gourav Sharma', 'gourav@example.com','2005-03-05','Male',  'Electronics',           'First Year', 'Active',   'Rajasthan',  '2024-07-15'),
                ('ME2024001','Aditya Dangi',  'aditya@example.com','2005-07-19','Male',  'Mechanical Engineering','First Year', 'On Leave', 'MP',         '2024-07-14'),
                ('CS2021001','Priya Mehta',   'priya@example.com', '2002-01-25','Female','Computer Science',      'Fourth Year','Active',   'Mumbai',     '2021-07-10'),
                ('IT2021001','Riya Verma',    'riya@example.com',  '2002-06-14','Female','Information Technology','Third Year', 'Graduated','Pune',       '2021-07-11'),
                ('EC2023001','Sahil Bisht',   'sahil@example.com', '2003-12-01','Male',  'Electronics',           'Second Year','Active',   'Chandigarh', '2023-07-09'),
                ('ME2022001','Neha Rawat',    'neha@example.com',  '2003-04-08','Female','Mechanical Engineering','Third Year', 'Active',   'Dehradun',   '2022-07-13'),
            ]
            conn.executemany('''
                INSERT INTO students
                (student_id,name,email,dob,gender,department,year,status,address,enroll_date)
                VALUES (?,?,?,?,?,?,?,?,?,?)''', seed)
            conn.commit()

        # ── Seed users ─────────────────────────────────────────
        if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
            # Default admin
            conn.execute('''
                INSERT INTO users (username, email, password, role)
                VALUES (?,?,?,?)''',
                ('admin', 'admin@sims.edu',
                 generate_password_hash('admin123'), 'admin'))
            # One student account per seeded student
            for s in conn.execute('SELECT id, student_id, email FROM students').fetchall():
                conn.execute('''
                    INSERT OR IGNORE INTO users
                    (username, email, password, role, student_id)
                    VALUES (?,?,?,?,?)''',
                    (s['student_id'], s['email'],
                     generate_password_hash('student123'), 'student', s['id']))
            conn.commit()


init_db()


# ══════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════

DEPARTMENTS = ['Computer Science', 'Information Technology', 'Electronics',
               'Mechanical Engineering', 'Civil Engineering', 'Business Administration']
YEARS       = ['First Year', 'Second Year', 'Third Year', 'Fourth Year']
STATUSES    = ['Active', 'On Leave', 'Graduated']
SEMESTERS   = ['Semester 1', 'Semester 2', 'Semester 3', 'Semester 4',
               'Semester 5', 'Semester 6', 'Semester 7', 'Semester 8']
EXAM_TYPES  = ['Midterm', 'Final', 'Quiz', 'Assignment', 'Practical']
SUBJECTS    = ['Mathematics', 'Physics', 'Chemistry', 'English',
               'Data Structures', 'Algorithms', 'DBMS', 'Operating Systems',
               'Computer Networks', 'Software Engineering', 'Web Development',
               'Machine Learning', 'Discrete Mathematics', 'Digital Electronics',
               'Circuit Theory', 'Thermodynamics', 'Fluid Mechanics', 'General']
FEEDBACK_CATEGORIES = ['General', 'Teaching Quality', 'Infrastructure',
                       'Canteen', 'Library', 'Sports', 'Administration']


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def calculate_grade(pct):
    if pct >= 90: return 'O'
    if pct >= 80: return 'A+'
    if pct >= 70: return 'A'
    if pct >= 60: return 'B+'
    if pct >= 50: return 'B'
    if pct >= 40: return 'C'
    return 'F'


def get_grade_color(grade):
    return {'O':'#10b981','A+':'#3b82f6','A':'#6366f1',
            'B+':'#f59e0b','B':'#f97316','C':'#ef4444','F':'#dc2626'}.get(grade,'#6b7280')


# ══════════════════════════════════════════════════════════════
#  AUTH DECORATORS
# ══════════════════════════════════════════════════════════════

def login_required(f):
    """Redirect to login if user is not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Allow only admin users; redirect others appropriately."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login', next=request.path))
        if session.get('role') != 'admin':
            flash('Access denied — admin only.', 'error')
            return redirect(url_for('student_dashboard'))
        return f(*args, **kwargs)
    return decorated


def student_required(f):
    """Allow only student users; redirect others appropriately."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        if session.get('role') != 'student':
            flash('Access denied — student area.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════════

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Already logged in → send to correct dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard') if session['role'] == 'admin'
                        else url_for('student_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash('Both username and password are required.', 'error')
            return render_template('login.html')

        with get_db() as conn:
            # Match by username OR email
            user = conn.execute(
                'SELECT * FROM users WHERE username=? OR email=?',
                (username, username)
            ).fetchone()

        if user and check_password_hash(user['password'], password):
            session.clear()
            session['user_id']       = user['id']
            session['username']      = user['username']
            session['role']          = user['role']
            session['student_db_id'] = user['student_id']  # None for admin

            # Fetch display name
            if user['role'] == 'student' and user['student_id']:
                with get_db() as conn:
                    s = conn.execute('SELECT name FROM students WHERE id=?',
                                     (user['student_id'],)).fetchone()
                    session['display_name'] = s['name'] if s else user['username']
            else:
                session['display_name'] = 'Administrator'

            flash(f'Welcome back, {session["display_name"]}!', 'success')

            # Honour ?next= redirect for admin, ignore for students
            nxt = request.args.get('next', '')
            if user['role'] == 'admin':
                return redirect(nxt if nxt and nxt.startswith('/') else url_for('dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid username/email or password.', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    name = session.get('display_name', 'User')
    session.clear()
    flash(f'Goodbye, {name}! You have been logged out.', 'success')
    return redirect(url_for('login'))


# ══════════════════════════════════════════════════════════════
#  STUDENT DASHBOARD  (student-only view of own data)
# ══════════════════════════════════════════════════════════════

@app.route('/student/dashboard')
@student_required
def student_dashboard():
    sid = session['student_db_id']
    with get_db() as conn:
        student   = conn.execute('SELECT * FROM students WHERE id=?', (sid,)).fetchone()
        if not student:
            flash('Student record not found. Contact admin.', 'error')
            return redirect(url_for('logout'))

        # ── Attendance stats ───────────────────────────────────
        att_records = conn.execute(
            'SELECT * FROM attendance WHERE student_id=? ORDER BY date DESC', (sid,)
        ).fetchall()
        att_total   = len(att_records)
        att_present = sum(1 for r in att_records if r['status'] == 'Present')
        att_late    = sum(1 for r in att_records if r['status'] == 'Late')
        att_absent  = att_total - att_present - att_late
        att_pct     = round(((att_present + att_late * 0.5) / att_total * 100), 1) if att_total else 0

        # Monthly attendance breakdown
        monthly = {}
        for r in att_records:
            m = r['date'][:7]
            if m not in monthly:
                monthly[m] = {'present': 0, 'absent': 0, 'late': 0}
            monthly[m][r['status'].lower()] += 1

        # ── Results ────────────────────────────────────────────
        results = conn.execute(
            'SELECT * FROM results WHERE student_id=? ORDER BY semester, subject', (sid,)
        ).fetchall()

        sem_data = {}
        for r in results:
            sem = r['semester']
            if sem not in sem_data:
                sem_data[sem] = {'subjects': [], 'total_marks': 0, 'total_max': 0}
            pct = round(r['marks_obtained'] / r['max_marks'] * 100, 1)
            sem_data[sem]['subjects'].append({
                'subject':   r['subject'],
                'marks':     r['marks_obtained'],
                'max':       r['max_marks'],
                'pct':       pct,
                'grade':     r['grade'],
                'exam_type': r['exam_type'],
                'semester':  r['semester'],
            })
            sem_data[sem]['total_marks'] += r['marks_obtained']
            sem_data[sem]['total_max']   += r['max_marks']

        for sem in sem_data:
            tm = sem_data[sem]['total_marks']
            mx = sem_data[sem]['total_max']
            sem_data[sem]['sem_pct']   = round(tm / mx * 100, 1) if mx else 0
            sem_data[sem]['sem_grade'] = calculate_grade(sem_data[sem]['sem_pct'])

        overall_marks = sum(r['marks_obtained'] for r in results)
        overall_max   = sum(r['max_marks']       for r in results)
        overall_pct   = round(overall_marks / overall_max * 100, 1) if overall_max else 0
        overall_grade = calculate_grade(overall_pct)

        # ── Feedback ───────────────────────────────────────────
        feedbacks = conn.execute(
            'SELECT * FROM feedback WHERE student_id=? ORDER BY created_at DESC', (sid,)
        ).fetchall()
        avg_fb = conn.execute(
            'SELECT AVG(rating) FROM feedback WHERE student_id=?', (sid,)
        ).fetchone()[0]
        avg_fb = round(avg_fb, 1) if avg_fb else 0

    return render_template('student_dashboard.html',
        student=student,
        # attendance
        att_records=att_records[:15],
        att_total=att_total, att_present=att_present,
        att_late=att_late, att_absent=att_absent, att_pct=att_pct,
        monthly=dict(sorted(monthly.items(), reverse=True)),
        # results
        sem_data=sem_data,
        overall_pct=overall_pct, overall_grade=overall_grade,
        overall_marks=overall_marks, overall_max=overall_max,
        # feedback
        feedbacks=feedbacks, avg_fb=avg_fb,
        # helpers
        get_grade_color=get_grade_color, calculate_grade=calculate_grade,
        FEEDBACK_CATEGORIES=FEEDBACK_CATEGORIES,
    )


# ══════════════════════════════════════════════════════════════
#  ADMIN — CORE ROUTES  (unchanged logic, now protected)
# ══════════════════════════════════════════════════════════════

@app.route('/')
@admin_required
def dashboard():
    with get_db() as conn:
        total   = conn.execute('SELECT COUNT(*) FROM students').fetchone()[0]
        active  = conn.execute("SELECT COUNT(*) FROM students WHERE status='Active'").fetchone()[0]
        grad    = conn.execute("SELECT COUNT(*) FROM students WHERE status='Graduated'").fetchone()[0]
        leave   = conn.execute("SELECT COUNT(*) FROM students WHERE status='On Leave'").fetchone()[0]
        dept_counts = {d: conn.execute('SELECT COUNT(*) FROM students WHERE department=?', (d,)).fetchone()[0]
                       for d in DEPARTMENTS}
        year_counts = {y: conn.execute('SELECT COUNT(*) FROM students WHERE year=?', (y,)).fetchone()[0]
                       for y in YEARS}
        recent  = conn.execute('SELECT * FROM students ORDER BY created_at DESC LIMIT 5').fetchall()
        today   = date.today().isoformat()
        att_today     = conn.execute('SELECT COUNT(*) FROM attendance WHERE date=?', (today,)).fetchone()[0]
        present_today = conn.execute("SELECT COUNT(*) FROM attendance WHERE date=? AND status='Present'", (today,)).fetchone()[0]
        results_count = conn.execute('SELECT COUNT(*) FROM results').fetchone()[0]
        feedback_count= conn.execute('SELECT COUNT(*) FROM feedback').fetchone()[0]
        avg_r         = conn.execute('SELECT AVG(rating) FROM feedback').fetchone()[0]
        avg_rating    = round(avg_r, 1) if avg_r else 0
    return render_template('dashboard.html',
        total=total, active=active, grad=grad, leave=leave,
        dept_counts=dept_counts, year_counts=year_counts, recent=recent,
        departments=DEPARTMENTS, years=YEARS,
        att_today=att_today, present_today=present_today,
        results_count=results_count, today=today,
        feedback_count=feedback_count, avg_rating=avg_rating)


@app.route('/students')
@admin_required
def view_students():
    dept   = request.args.get('dept', '')
    year   = request.args.get('year', '')
    status = request.args.get('status', '')
    search = request.args.get('search', '')
    q = 'SELECT * FROM students WHERE 1=1'; p = []
    if dept:   q += ' AND department=?'; p.append(dept)
    if year:   q += ' AND year=?';       p.append(year)
    if status: q += ' AND status=?';     p.append(status)
    if search:
        q += ' AND (name LIKE ? OR student_id LIKE ?)'; p += [f'%{search}%', f'%{search}%']
    q += ' ORDER BY created_at DESC'
    with get_db() as conn:
        students = conn.execute(q, p).fetchall()
    return render_template('view_students.html', students=students,
        departments=DEPARTMENTS, years=YEARS, statuses=STATUSES,
        filters={'dept': dept, 'year': year, 'status': status, 'search': search})


@app.route('/students/add', methods=['GET', 'POST'])
@admin_required
def add_student():
    if request.method == 'POST':
        data = {k: request.form.get(k, '').strip() for k in
                ['student_id', 'name', 'email', 'dob', 'gender',
                 'department', 'year', 'status', 'address', 'enroll_date']}
        if not data['name'] or not data['student_id'] or not data['department'] or not data['year']:
            flash('Name, Student ID, Department and Year are required.', 'error')
            return render_template('add_student.html',
                departments=DEPARTMENTS, years=YEARS, statuses=STATUSES, form=data)
        try:
            with get_db() as conn:
                conn.execute('''INSERT INTO students
                    (student_id,name,email,dob,gender,department,year,status,address,enroll_date)
                    VALUES (:student_id,:name,:email,:dob,:gender,:department,:year,:status,:address,:enroll_date)''',
                    data)
                conn.commit()
                # Auto-create student login account
                new_s = conn.execute('SELECT id FROM students WHERE student_id=?',
                                     (data['student_id'],)).fetchone()
                if new_s:
                    conn.execute('''INSERT OR IGNORE INTO users
                        (username, email, password, role, student_id)
                        VALUES (?,?,?,?,?)''',
                        (data['student_id'], data['email'] or None,
                         generate_password_hash('student123'), 'student', new_s['id']))
                    conn.commit()
            flash(f'{data["name"]} registered! Login: {data["student_id"]} / student123', 'success')
            return redirect(url_for('dashboard'))
        except sqlite3.IntegrityError:
            flash('A student with that ID already exists.', 'error')
    return render_template('add_student.html',
        departments=DEPARTMENTS, years=YEARS, statuses=STATUSES, form={})


@app.route('/students/<int:sid>')
@admin_required
def student_detail(sid):
    with get_db() as conn:
        student    = conn.execute('SELECT * FROM students WHERE id=?', (sid,)).fetchone()
        att_total  = conn.execute('SELECT COUNT(*) FROM attendance WHERE student_id=?', (sid,)).fetchone()[0]
        att_present= conn.execute("SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='Present'", (sid,)).fetchone()[0]
        att_late   = conn.execute("SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='Late'", (sid,)).fetchone()[0]
        att_pct    = round((att_present / att_total * 100), 1) if att_total else 0
        recent_att = conn.execute('SELECT * FROM attendance WHERE student_id=? ORDER BY date DESC LIMIT 10', (sid,)).fetchall()
        results    = conn.execute('SELECT * FROM results WHERE student_id=? ORDER BY semester,subject', (sid,)).fetchall()
    if not student:
        flash('Student not found.', 'error')
        return redirect(url_for('view_students'))
    return render_template('student_detail.html', student=student,
        att_total=att_total, att_present=att_present, att_late=att_late,
        att_pct=att_pct, recent_att=recent_att, results=results)


@app.route('/students/<int:sid>/edit', methods=['GET', 'POST'])
@admin_required
def edit_student(sid):
    with get_db() as conn:
        student = conn.execute('SELECT * FROM students WHERE id=?', (sid,)).fetchone()
    if not student:
        flash('Student not found.', 'error')
        return redirect(url_for('view_students'))
    if request.method == 'POST':
        data = {k: request.form.get(k, '').strip() for k in
                ['name', 'email', 'dob', 'gender', 'department',
                 'year', 'status', 'address', 'enroll_date']}
        data['id'] = sid
        with get_db() as conn:
            conn.execute('''UPDATE students SET
                name=:name,email=:email,dob=:dob,gender=:gender,
                department=:department,year=:year,status=:status,
                address=:address,enroll_date=:enroll_date
                WHERE id=:id''', data)
            conn.commit()
        flash(f'{data["name"]} updated successfully!', 'success')
        return redirect(url_for('student_detail', sid=sid))
    return render_template('edit_student.html', student=student,
        departments=DEPARTMENTS, years=YEARS, statuses=STATUSES)


@app.route('/students/<int:sid>/delete', methods=['POST'])
@admin_required
def delete_student(sid):
    with get_db() as conn:
        s = conn.execute('SELECT name FROM students WHERE id=?', (sid,)).fetchone()
        if s:
            conn.execute('DELETE FROM attendance WHERE student_id=?', (sid,))
            conn.execute('DELETE FROM results    WHERE student_id=?', (sid,))
            conn.execute('DELETE FROM feedback   WHERE student_id=?', (sid,))
            conn.execute('DELETE FROM users      WHERE student_id=?', (sid,))  # remove login too
            conn.execute('DELETE FROM students   WHERE id=?',         (sid,))
            conn.commit()
            flash(f'{s["name"]} and their login account have been removed.', 'success')
    return redirect(url_for('view_students'))


# ── Attendance ─────────────────────────────────────────────────

@app.route('/attendance')
@admin_required
def attendance():
    sel_date    = request.args.get('date', date.today().isoformat())
    sel_dept    = request.args.get('dept', '')
    sel_subject = request.args.get('subject', 'General')
    with get_db() as conn:
        q = "SELECT * FROM students WHERE status='Active'"; p = []
        if sel_dept:
            q += ' AND department=?'; p.append(sel_dept)
        q += ' ORDER BY name'
        students    = conn.execute(q, p).fetchall()
        att_records = conn.execute(
            'SELECT student_id,status FROM attendance WHERE date=? AND subject=?',
            (sel_date, sel_subject)).fetchall()
        att_map      = {r['student_id']: r['status'] for r in att_records}
        total_marked = len(att_map)
        present_ct   = sum(1 for v in att_map.values() if v == 'Present')
        absent_ct    = sum(1 for v in att_map.values() if v == 'Absent')
        late_ct      = sum(1 for v in att_map.values() if v == 'Late')
    return render_template('attendance.html',
        students=students, att_map=att_map, sel_date=sel_date,
        sel_dept=sel_dept, sel_subject=sel_subject,
        total_marked=total_marked, present_ct=present_ct,
        absent_ct=absent_ct, late_ct=late_ct,
        departments=DEPARTMENTS, subjects=SUBJECTS)


@app.route('/attendance/mark', methods=['POST'])
@admin_required
def mark_attendance():
    att_date = request.form.get('date', date.today().isoformat())
    subject  = request.form.get('subject', 'General')
    dept     = request.form.get('dept', '')
    with get_db() as conn:
        students = conn.execute(
            "SELECT id FROM students WHERE status='Active'" + (' AND department=?' if dept else ''),
            ([dept] if dept else [])).fetchall()
        saved = 0
        for s in students:
            sid    = s['id']
            status = request.form.get(f'att_{sid}', '')
            if status in ('Present', 'Absent', 'Late'):
                conn.execute('''
                    INSERT INTO attendance (student_id,date,status,subject)
                    VALUES (?,?,?,?)
                    ON CONFLICT(student_id,date,subject)
                    DO UPDATE SET status=excluded.status''',
                    (sid, att_date, status, subject))
                saved += 1
        conn.commit()
    flash(f'Attendance saved for {saved} students on {att_date}.', 'success')
    return redirect(url_for('attendance', date=att_date, dept=dept, subject=subject))


@app.route('/attendance/report')
@admin_required
def attendance_report():
    sel_dept = request.args.get('dept', '')
    with get_db() as conn:
        q = 'SELECT * FROM students WHERE 1=1'; p = []
        if sel_dept:
            q += ' AND department=?'; p.append(sel_dept)
        q += ' ORDER BY name'
        students = conn.execute(q, p).fetchall()
        report = []
        for s in students:
            sid   = s['id']
            total = conn.execute('SELECT COUNT(*) FROM attendance WHERE student_id=?', (sid,)).fetchone()[0]
            pres  = conn.execute("SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='Present'", (sid,)).fetchone()[0]
            late  = conn.execute("SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='Late'", (sid,)).fetchone()[0]
            pct   = round(((pres + late * 0.5) / total * 100), 1) if total else 0
            report.append({
                'id': sid, 'student_id': s['student_id'], 'name': s['name'],
                'department': s['department'], 'year': s['year'],
                'total': total, 'present': pres, 'late': late, 'absent': total - pres - late,
                'percentage': pct,
                'status_label': ('Excellent' if pct >= 85 else 'Good' if pct >= 75
                                 else 'Average' if pct >= 60 else 'Low'),
            })
    return render_template('attendance_report.html',
        report=report, sel_dept=sel_dept, departments=DEPARTMENTS)


@app.route('/attendance/student/<int:sid>')
@admin_required
def student_attendance(sid):
    with get_db() as conn:
        student = conn.execute('SELECT * FROM students WHERE id=?', (sid,)).fetchone()
        records = conn.execute(
            'SELECT * FROM attendance WHERE student_id=? ORDER BY date DESC', (sid,)).fetchall()
        total   = len(records)
        present = sum(1 for r in records if r['status'] == 'Present')
        late    = sum(1 for r in records if r['status'] == 'Late')
        absent  = total - present - late
        pct     = round(((present + late * 0.5) / total * 100), 1) if total else 0
        monthly = {}
        for r in records:
            m = r['date'][:7]
            if m not in monthly:
                monthly[m] = {'present': 0, 'absent': 0, 'late': 0}
            monthly[m][r['status'].lower()] += 1
    if not student:
        flash('Student not found.', 'error')
        return redirect(url_for('attendance_report'))
    return render_template('student_attendance.html',
        student=student, records=records, total=total,
        present=present, late=late, absent=absent, pct=pct,
        monthly=dict(sorted(monthly.items(), reverse=True)))


@app.route('/attendance/<int:att_id>/delete', methods=['POST'])
@admin_required
def delete_attendance(att_id):
    sid = request.form.get('student_id')
    with get_db() as conn:
        conn.execute('DELETE FROM attendance WHERE id=?', (att_id,))
        conn.commit()
    flash('Attendance record removed.', 'success')
    return redirect(url_for('student_attendance', sid=sid))


# ── Results ────────────────────────────────────────────────────

@app.route('/results')
@admin_required
def results():
    sel_dept = request.args.get('dept', '')
    sel_sem  = request.args.get('semester', '')
    sel_exam = request.args.get('exam', '')
    search   = request.args.get('search', '')
    q = '''SELECT r.*,s.name,s.student_id as sid,s.department,s.year
           FROM results r JOIN students s ON r.student_id=s.id WHERE 1=1'''
    p = []
    if sel_dept: q += ' AND s.department=?'; p.append(sel_dept)
    if sel_sem:  q += ' AND r.semester=?';   p.append(sel_sem)
    if sel_exam: q += ' AND r.exam_type=?';  p.append(sel_exam)
    if search:
        q += ' AND (s.name LIKE ? OR s.student_id LIKE ? OR r.subject LIKE ?)'
        p += [f'%{search}%', f'%{search}%', f'%{search}%']
    q += ' ORDER BY r.created_at DESC'
    with get_db() as conn:
        rows          = conn.execute(q, p).fetchall()
        total_results = conn.execute('SELECT COUNT(*) FROM results').fetchone()[0]
        avg_row       = conn.execute('SELECT AVG(marks_obtained*100.0/max_marks) FROM results').fetchone()[0]
        avg_pct       = round(avg_row, 1) if avg_row else 0
    return render_template('results.html', rows=rows,
        departments=DEPARTMENTS, semesters=SEMESTERS, exam_types=EXAM_TYPES,
        filters={'dept': sel_dept, 'semester': sel_sem, 'exam': sel_exam, 'search': search},
        total_results=total_results, avg_pct=avg_pct)


@app.route('/results/add', methods=['GET', 'POST'])
@admin_required
def add_result():
    if request.method == 'POST':
        try:
            marks    = float(request.form.get('marks_obtained', 0))
            max_m    = float(request.form.get('max_marks', 100))
            pct      = (marks / max_m * 100) if max_m else 0
            grade    = calculate_grade(pct)
            sid      = int(request.form.get('student_id'))
            subject  = request.form.get('subject', '').strip()
            exam_type= request.form.get('exam_type', 'Midterm')
            semester = request.form.get('semester', '').strip()
            remarks  = request.form.get('remarks', '').strip()
            if not subject or not semester:
                flash('Subject and Semester are required.', 'error')
            else:
                with get_db() as conn:
                    conn.execute('''INSERT INTO results
                        (student_id,subject,marks_obtained,max_marks,exam_type,semester,grade,remarks)
                        VALUES (?,?,?,?,?,?,?,?)''',
                        (sid, subject, marks, max_m, exam_type, semester, grade, remarks))
                    conn.commit()
                flash(f'Result added! Grade: {grade}', 'success')
                return redirect(url_for('results'))
        except (ValueError, TypeError):
            flash('Invalid marks entered.', 'error')
    with get_db() as conn:
        students = conn.execute(
            'SELECT id,student_id,name,department FROM students ORDER BY name').fetchall()
    pre_sid = request.args.get('student_id')
    return render_template('add_result.html', students=students,
        semesters=SEMESTERS, exam_types=EXAM_TYPES, subjects=SUBJECTS, pre_sid=pre_sid)


@app.route('/results/student/<int:sid>')
@admin_required
def student_results(sid):
    with get_db() as conn:
        student = conn.execute('SELECT * FROM students WHERE id=?', (sid,)).fetchone()
        results = conn.execute(
            'SELECT * FROM results WHERE student_id=? ORDER BY semester,subject', (sid,)).fetchall()
        sem_data = {}
        for r in results:
            sem = r['semester']
            if sem not in sem_data:
                sem_data[sem] = {'subjects': [], 'total_marks': 0, 'total_max': 0}
            pct = round(r['marks_obtained'] / r['max_marks'] * 100, 1)
            sem_data[sem]['subjects'].append({
                'id': r['id'], 'subject': r['subject'],
                'marks': r['marks_obtained'], 'max': r['max_marks'],
                'pct': pct, 'grade': r['grade'], 'exam_type': r['exam_type'],
            })
            sem_data[sem]['total_marks'] += r['marks_obtained']
            sem_data[sem]['total_max']   += r['max_marks']
        for sem in sem_data:
            tm = sem_data[sem]['total_marks']; mx = sem_data[sem]['total_max']
            sem_data[sem]['sem_pct']   = round(tm / mx * 100, 1) if mx else 0
            sem_data[sem]['sem_grade'] = calculate_grade(sem_data[sem]['sem_pct'])
        overall_marks = sum(r['marks_obtained'] for r in results)
        overall_max   = sum(r['max_marks']       for r in results)
        overall_pct   = round(overall_marks / overall_max * 100, 1) if overall_max else 0
        overall_grade = calculate_grade(overall_pct)
    if not student:
        flash('Student not found.', 'error')
        return redirect(url_for('results'))
    return render_template('student_results.html', student=student,
        sem_data=sem_data, overall_pct=overall_pct, overall_grade=overall_grade,
        overall_marks=overall_marks, overall_max=overall_max,
        calculate_grade=calculate_grade, get_grade_color=get_grade_color)


@app.route('/results/<int:rid>/delete', methods=['POST'])
@admin_required
def delete_result(rid):
    sid = request.form.get('student_id')
    with get_db() as conn:
        conn.execute('DELETE FROM results WHERE id=?', (rid,))
        conn.commit()
    flash('Result deleted.', 'success')
    return redirect(url_for('student_results', sid=sid) if sid else url_for('results'))


@app.route('/results/<int:rid>/edit', methods=['GET', 'POST'])
@admin_required
def edit_result(rid):
    with get_db() as conn:
        result  = conn.execute('SELECT * FROM results WHERE id=?', (rid,)).fetchone()
        student = conn.execute('SELECT * FROM students WHERE id=?',
                               (result['student_id'],)).fetchone() if result else None
    if not result:
        flash('Result not found.', 'error')
        return redirect(url_for('results'))
    if request.method == 'POST':
        try:
            marks = float(request.form.get('marks_obtained', 0))
            max_m = float(request.form.get('max_marks', 100))
            grade = calculate_grade((marks / max_m * 100) if max_m else 0)
            with get_db() as conn:
                conn.execute('''UPDATE results SET
                    subject=?,marks_obtained=?,max_marks=?,
                    exam_type=?,semester=?,grade=?,remarks=?
                    WHERE id=?''',
                    (request.form.get('subject'), marks, max_m,
                     request.form.get('exam_type'), request.form.get('semester'),
                     grade, request.form.get('remarks'), rid))
                conn.commit()
            flash(f'Result updated! Grade: {grade}', 'success')
            return redirect(url_for('student_results', sid=result['student_id']))
        except (ValueError, TypeError):
            flash('Invalid marks.', 'error')
    return render_template('edit_result.html', result=result, student=student,
        semesters=SEMESTERS, exam_types=EXAM_TYPES, subjects=SUBJECTS)


@app.route('/api/students')
@admin_required
def api_students():
    with get_db() as conn:
        rows = conn.execute(
            'SELECT id,student_id,name,department FROM students ORDER BY name').fetchall()
    return jsonify([dict(r) for r in rows])


# ── Feedback ───────────────────────────────────────────────────

@app.route('/feedback')
@admin_required
def feedback():
    sel_rating   = request.args.get('rating', '')
    sel_category = request.args.get('category', '')
    sel_student  = request.args.get('student', '')
    q = '''SELECT f.*, s.name, s.student_id as sid, s.department
           FROM feedback f JOIN students s ON f.student_id=s.id WHERE 1=1'''
    p = []
    if sel_rating:   q += ' AND f.rating=?';   p.append(int(sel_rating))
    if sel_category: q += ' AND f.category=?'; p.append(sel_category)
    if sel_student:
        q += ' AND (s.name LIKE ? OR s.student_id LIKE ?)'; p += [f'%{sel_student}%'] * 2
    q += ' ORDER BY f.created_at DESC'
    with get_db() as conn:
        entries    = conn.execute(q, p).fetchall()
        total      = conn.execute('SELECT COUNT(*) FROM feedback').fetchone()[0]
        avg_r      = conn.execute('SELECT AVG(rating) FROM feedback').fetchone()[0]
        avg_rating = round(avg_r, 1) if avg_r else 0
        dist       = {i: conn.execute('SELECT COUNT(*) FROM feedback WHERE rating=?', (i,)).fetchone()[0]
                      for i in range(1, 6)}
        cat_counts = {c: conn.execute('SELECT COUNT(*) FROM feedback WHERE category=?', (c,)).fetchone()[0]
                      for c in FEEDBACK_CATEGORIES}
    return render_template('feedback.html',
        entries=entries, total=total, avg_rating=avg_rating,
        dist=dist, cat_counts=cat_counts,
        categories=FEEDBACK_CATEGORIES,
        filters={'rating': sel_rating, 'category': sel_category, 'student': sel_student})


@app.route('/feedback/add', methods=['GET', 'POST'])
@admin_required
def add_feedback():
    if request.method == 'POST':
        try:
            sid      = int(request.form.get('student_id'))
            message  = request.form.get('message', '').strip()
            rating   = int(request.form.get('rating', 3))
            category = request.form.get('category', 'General')
            if not message:
                flash('Feedback message cannot be empty.', 'error')
            elif not (1 <= rating <= 5):
                flash('Rating must be between 1 and 5.', 'error')
            else:
                with get_db() as conn:
                    conn.execute('''INSERT INTO feedback (student_id,message,rating,category)
                        VALUES (?,?,?,?)''', (sid, message, rating, category))
                    conn.commit()
                flash('Feedback submitted successfully!', 'success')
                return redirect(url_for('feedback'))
        except (ValueError, TypeError):
            flash('Invalid data submitted.', 'error')
    with get_db() as conn:
        students = conn.execute(
            'SELECT id,student_id,name,department FROM students ORDER BY name').fetchall()
    pre_sid = request.args.get('student_id')
    return render_template('add_feedback.html',
        students=students, categories=FEEDBACK_CATEGORIES, pre_sid=pre_sid)


@app.route('/feedback/<int:fid>/delete', methods=['POST'])
@admin_required
def delete_feedback(fid):
    with get_db() as conn:
        conn.execute('DELETE FROM feedback WHERE id=?', (fid,))
        conn.commit()
    flash('Feedback entry removed.', 'success')
    return redirect(url_for('feedback'))


# ── Charts ─────────────────────────────────────────────────────

@app.route('/charts')
@admin_required
def charts():
    with get_db() as conn:
        students = conn.execute(
            "SELECT id,name FROM students WHERE status='Active' ORDER BY name").fetchall()
        att_data = []
        for s in students:
            total = conn.execute('SELECT COUNT(*) FROM attendance WHERE student_id=?', (s['id'],)).fetchone()[0]
            pres  = conn.execute("SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='Present'", (s['id'],)).fetchone()[0]
            late  = conn.execute("SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='Late'", (s['id'],)).fetchone()[0]
            pct   = round(((pres + late * 0.5) / total * 100), 1) if total else 0
            if total > 0:
                att_data.append({'name': s['name'], 'pct': pct})

        subj_rows = conn.execute('''SELECT subject,
            ROUND(AVG(marks_obtained*100.0/max_marks),1) as avg_pct,
            COUNT(*) as cnt FROM results GROUP BY subject ORDER BY avg_pct DESC''').fetchall()
        subj_data = [dict(r) for r in subj_rows]

        fb_dist  = [conn.execute('SELECT COUNT(*) FROM feedback WHERE rating=?', (i,)).fetchone()[0]
                    for i in range(1, 6)]
        cat_rows = conn.execute('''SELECT category, ROUND(AVG(rating),1) as avg_r
            FROM feedback GROUP BY category''').fetchall()
        cat_data = [dict(r) for r in cat_rows]

        dept_data = [(d, conn.execute('SELECT COUNT(*) FROM students WHERE department=?', (d,)).fetchone()[0])
                     for d in DEPARTMENTS]
        dept_data = [(d, c) for d, c in dept_data if c > 0]

        grade_rows = conn.execute('''SELECT grade,COUNT(*) as cnt
            FROM results GROUP BY grade ORDER BY grade''').fetchall()
        grade_data = [dict(r) for r in grade_rows]

        trend_rows = conn.execute('''SELECT date,
            SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) as present,
            COUNT(*) as total
            FROM attendance GROUP BY date ORDER BY date DESC LIMIT 10''').fetchall()
        trend_data = [dict(r) for r in reversed(list(trend_rows))]

    return render_template('charts.html',
        att_data=att_data, subj_data=subj_data,
        fb_dist=fb_dist, cat_data=cat_data,
        dept_data=dept_data, grade_data=grade_data,
        trend_data=trend_data)


# ── Chart API (admin only) ─────────────────────────────────────

@app.route('/api/charts/attendance')
@admin_required
def chart_attendance():
    with get_db() as conn:
        students = conn.execute(
            "SELECT id,name FROM students WHERE status='Active' ORDER BY name").fetchall()
        data = []
        for s in students:
            total = conn.execute('SELECT COUNT(*) FROM attendance WHERE student_id=?', (s['id'],)).fetchone()[0]
            pres  = conn.execute("SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='Present'", (s['id'],)).fetchone()[0]
            late  = conn.execute("SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='Late'", (s['id'],)).fetchone()[0]
            pct   = round(((pres + late * 0.5) / total * 100), 1) if total else 0
            data.append({'name': s['name'], 'percentage': pct, 'total': total})
    return jsonify(data)


@app.route('/api/charts/results')
@admin_required
def chart_results():
    with get_db() as conn:
        rows = conn.execute('''SELECT subject,
            ROUND(AVG(marks_obtained*100.0/max_marks),1) as avg_pct, COUNT(*) as count
            FROM results GROUP BY subject ORDER BY avg_pct DESC''').fetchall()
    return jsonify([dict(r) for r in rows])


@app.route('/api/charts/feedback')
@admin_required
def chart_feedback():
    with get_db() as conn:
        dist = {str(i): conn.execute('SELECT COUNT(*) FROM feedback WHERE rating=?', (i,)).fetchone()[0]
                for i in range(1, 6)}
        cat_data = conn.execute('''SELECT category, ROUND(AVG(rating),1) as avg_r, COUNT(*) as cnt
            FROM feedback GROUP BY category''').fetchall()
    return jsonify({'distribution': dist, 'by_category': [dict(r) for r in cat_data]})


# ══════════════════════════════════════════════════════════════
#  ENTRYPOINT
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    app.run(debug=False)
