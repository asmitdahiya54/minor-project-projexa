from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

students = []

@app.route('/')
def home():
    return render_template('dashboard.html')

@app.route('/add', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        course = request.form['course']

        students.append({
            'name': name,
            'email': email,
            'course': course
        })

        return redirect(url_for('view_students'))

    return render_template('add_student.html')

@app.route('/view')
def view_students():
    return render_template('view_students.html',
                           students=students,
                           count=len(students))

@app.route('/delete/<int:index>')
def delete_student(index):
    if 0 <= index < len(students):
        students.pop(index)
    return redirect(url_for('view_students'))

if __name__ == '__main__':
    app.run(debug=True)