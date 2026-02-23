from flask import Flask, render_template, request, redirect

app = Flask(__name__)

students = []   # Temporary storage

@app.route('/')
def home():
    return render_template('index.html')

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

        return redirect('/view')

    return render_template('add_student.html')

@app.route('/view')
def view_students():
    return render_template('view_students.html', students=students)

if __name__ == '__main__':
    app.run(debug=True)