from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
    

https://github.com/asmitdahiya54/minor-project-projexa#:~:text=Settings-,minor%2Dproject%2Dprojexa,-Public