from flask import Flask, render_template, request, redirect, session, flash
import pymysql
import PyPDF2
import os
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = "secret123"

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def get_connection():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='root',
        database='resume_db',
        port=3306,
        cursorclass=pymysql.cursors.DictCursor
    )

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text(filepath):
    text = ""
    try:
        reader = PyPDF2.PdfReader(filepath)
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as e:
        print("PDF Error:", e)
    return text.lower()

def extract_skills(text, skills):
    found = []
    words = text.split()

    for skill in skills:
        skill = skill.strip().lower()
        if skill in text:
            found.append(skill)
        else:
            for word in words:
                if skill in word:
                    found.append(skill)
                    break

    return list(set(found))


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            conn = get_connection()
            cursor = conn.cursor()

            email = request.form['email']
            password = request.form['password']

            cursor.execute(
                "SELECT * FROM users_login WHERE email=%s AND password=%s",
                (email, password)
            )

            user = cursor.fetchone()

            if user:
                session['user'] = email  
                session['user_name'] = user['name']  
                return redirect('/dashboard')
            else:
                flash("Invalid Email or Password ❌")

        except Exception as e:
            print(e)
            flash("Database Error ❌")

        finally:
            conn.close()

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            conn = get_connection()
            cursor = conn.cursor()

            name = request.form['name']
            email = request.form['email']
            password = request.form['password']
            confirm_password = request.form['confirm_password']

           
            if password != confirm_password:
                flash("Passwords do not match ❌")
                return render_template('register.html')

            
            cursor.execute("SELECT * FROM users_login WHERE email=%s", (email,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                flash("Email already registered ❌")
                return render_template('register.html')

            
            cursor.execute(
                "INSERT INTO users_login(name, email, password) VALUES(%s, %s, %s)",
                (name, email, password)
            )
            conn.commit()

            flash("Registered Successfully ✅ Please login")
            return redirect('/')

        except Exception as e:
            print(e)
            flash("Registration Failed ❌")

        finally:
            conn.close()

    return render_template('register.html')


@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM job_roles")
        roles = cursor.fetchall()

    except Exception as e:
        print(e)
        roles = []

    finally:
        conn.close()

    return render_template('dashboard.html', roles=roles)



@app.route('/analyze', methods=['POST'])
def analyze():
    if 'user' not in session:
        return redirect('/')

    file = request.files['resume']
    role_id = request.form['role']

    if file.filename == '':
        flash("No file selected ❌")
        return redirect('/dashboard')

    if not allowed_file(file.filename):
        flash("Only PDF allowed ❌")
        return redirect('/dashboard')

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    text = extract_text(filepath)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT role_name, skills FROM job_roles WHERE id=%s",
            (role_id,)
        )
        data = cursor.fetchone()

        role_name = data['role_name']
        required_skills = data['skills'].lower().split(',')

        user_skills = extract_skills(text, required_skills)

        score = (len(user_skills) / len(required_skills)) * 100 if required_skills else 0
        score = round(score, 2)

        missing = list(set(required_skills) - set(user_skills))

        
        cursor.execute("""
            INSERT INTO results(username, filename, job_role, score, skills, missing_skills)
            VALUES(%s, %s, %s, %s, %s, %s)
        """, (
            session['user'], 
            filename,
            role_name,
            score,
            ",".join(user_skills),
            ",".join(missing)
        ))

        conn.commit()

    except Exception as e:
        print(e)
        flash("Analysis Failed ❌")
        return redirect('/dashboard')

    finally:
        conn.close()

    return render_template(
        'result.html',
        score=score,
        skills=user_skills,
        missing=missing,
        role=role_name
    )


@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('user_name', None)
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)