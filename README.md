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


Default Login Credentials

Admin
. Username: admin
. Password: admin123

Teachers
. Username: teacher_first
Password: teacher123

. Username: teacher_second
Password: teacher123

. Username: teacher_third
Password: teacher123

. Username: teacher_fourth
Password: teacher123

Students

. Username: student ID
  Password: student123

Examples:

. CS2024001 / student123
. CS2024002 / student123
. IT2024001 / student123