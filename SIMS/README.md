# Student Information Management System (SIMS)

## Project Description
A web-based Student Information Management System developed using Flask and SQLite.
The system allows administrators to manage student records efficiently through a clean and user-friendly web interface.

The application provides features for adding, viewing, editing, and deleting student information, along with a dashboard that displays statistics about student records.

## Objectives
- To understand the fundamentals of web application development
- To build a CRUD (Create, Read, Update, Delete) system
- To design a clean and responsive user interface
- To store and manage data using SQLite database
- To gain hands-on experience with GitHub collaboration

## Technologies Used
- **Python (Flask)** – Backend logic and routing
- **SQLite** – Lightweight database for storing student records
- **HTML (Jinja2 Templates)** – Dynamic web pages
- **CSS** – Styling and responsive design
- **JavaScript** – Small UI actions (date display, auto-submit filters)

## Features
- Dashboard with student statistics
- Add new student records
- View and search student records
- Filter students by department, year, and status
- Edit student information
- Delete student records
- View detailed student information

## Project Structure
```
Minor project projexa(SIMS)/
├── app.py                  # Flask backend – routes & database logic
├── sims.db                 # SQLite database (auto-created on first run)
├── requirements.txt        # Python dependencies
├── .gitignore
├── static/
│   └── style.css           # All styling
└── templates/
    ├── base.html           # Shared layout (sidebar + topbar)
    ├── dashboard.html      # Home dashboard with stats
    ├── view_students.html  # Student list with filters & search
    ├── add_student.html    # Add new student form
    ├── student_detail.html # Full student profile view
    └── edit_student.html   # Edit student form
    
```

## Setup & Installation

```bash
# 1. Clone the repository
git clone https://github.com/asmitdahiya54/minor-project-projexa.git
cd minor-project-projexa

# 2. Create a virtual environment (recommended)
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```

Then open your browser and go to: **http://127.0.0.1:5000**

> The SQLite database (`sims.db`) is created automatically on first run with sample student data.

## Team
- **Team Leader:** Asmit Dahiya
- **Team Members:**
  - Dev Narwal
  - Manish Chauhan
  - Dikshit
  - Gourav
  - Aditya Dangi

## Status
Development in progress.