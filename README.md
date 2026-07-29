# SIMS

## Student Information Management System

SIMS is a web-based Student Information Management System developed using Flask and SQLite. It helps administrators, teachers, and students manage academic records through a secure, modern, and role-based platform.

The system includes student profile management, attendance tracking, results management, feedback collection, analytics dashboards, PDF report generation, and authentication features.

## Features

- Role-based login for admin, teacher, and student
- Student record management
- Add, view, edit, and delete student profiles
- Profile image upload support
- Attendance management with date and subject tracking
- Attendance reports and PDF export
- Results management and academic record tracking
- Report card PDF generation
- Feedback submission and review
- Dashboard with activity summaries
- Analytics charts for attendance, results, and feedback
- Password change feature
- CSRF protection and session security
- Responsive UI

## Technologies Used

- Python
- Flask
- SQLite
- HTML
- CSS
- JavaScript
- Jinja2
- ReportLab

## Project Structure


minor-project-projexa/
│
├── app.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── Procfile
├── sims.db
│
├── static/
│   ├── style.css
│   ├── main.js
│   └── uploads/
│
└── templates/
    ├── base.html
    ├── login.html
    ├── dashboard.html
    ├── student_dashboard.html
    ├── view_students.html
    ├── student_detail.html
    ├── add_student.html
    ├── edit_student.html
    ├── attendance.html
    ├── attendance_report.html
    ├── student_attendance.html
    ├── results.html
    ├── add_result.html
    ├── edit_result.html
    ├── student_results.html
    ├── feedback.html
    ├── add_feedback.html
    ├── charts.html
    └── change_password.html


User Roles
|
├── Admin
|     ├──Manage students
|     ├──View dashboards
|     ├──Manage attendance
|     ├──Manage results
|     ├──Review feedback
|     └──Access analytics
|
├── Teacher
|       ├──View assigned students
|       ├──Manage attendance
|       ├──Add and update results
|       ├──Review feedback
|       └──Access analytics for assigned students
| 
|
└── Student
      ├──View personal dashboard
      ├──Check attendance
      ├──Check results
      ├──Submit feedback
      └──Download reports


## Default Login Credentials

Admin
. Username: admin
. Password: 

Teachers
. Username: teacher_first
Password: 

. Username: teacher_second
Password: 

. Username: teacher_third
Password: 

. Username: teacher_fourth
Password: 

Students

. Username: student ID

Examples:

. CS2024001 / student123
. CS2024002 / student123
. IT2024001 / student123


## Teacher Assignment by Year
 The system automatically assigns one teacher per academic year:

. First Year: Rahul Sharma
. Second Year: Priya Verma
. Third Year: Amit Mehta
. Fourth Year: Neha Singh
If no teacher is selected while creating or editing a student, the system automatically assigns the correct teacher based on the selected year.

## Installation
1.Clone or download the project
2.Open the project folder in terminal
3.Create a virtual environment
  python -m venv venv

4.Activate the virtual environment
  venv\Scripts\activate

5.Install dependencies
  pip install -r requirements.txt

Environment Variables
Create a .env file in the root directory and add:

SECRET_KEY=change-this-to-a-secure-random-secret
FLASK_ENV=development
SIMS_DB_PATH=
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
MAIL_SENDER=

- Run Locally
  (python app.py)

  Then open:

http://127.0.0.1:5000

## Deployment
This project is deployed on platform - Render.
  (https://minor-project-projexa.onrender.com/)

Deployment setup
. Add gunicorn to requirements.txt
. Add Procfile
. Set environment variable SECRET_KEY
. Connect the GitHub repository to Render
. Use:
  Build command:

(pip install -r requirements.txt)

Start command:

(gunicorn app:app)

- Modules
. Authentication and authorization
. Student management
. Attendance management
. Results management
. Feedback management
. Analytics and reporting

-Security Features
. Password hashing
. CSRF token validation
. Role-based access control
. Secure session handling
. File upload validation

- Future Improvements
. Password reset by email
. Better reporting filters
. Student promotion workflow
. PostgreSQL integration
. Notification improvements
. Advanced analytics dashboard

Project Purpose
This project was developed as a minor project for academic use. Its goal is to simplify student data management through a centralized and user-friendly digital system.

License
This project is created for educational purposes.

Team leader - Asmit
Members-Dikshit
        Manish Chauhan
        Dev Narwal
        Aditya Dangi
        Gourav Yadav
