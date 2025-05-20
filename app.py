from flask import Flask, render_template, redirect, url_for, flash, request, Response, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func
from extensions import db
from forms import RegisterForm, LoginForm, EditProfileForm, ChangePasswordForm
from models import User, AnswerHistory, QuizAttempt
from PIL import Image
import random
import csv
from io import StringIO
import os
from datetime import datetime, date

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cami.db'

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_pw = generate_password_hash(form.password.data)
        new_user = User(
            username=form.username.data,
            email=form.email.data,
            password=hashed_pw
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            user.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(obj=current_user)

    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data

        if form.profile_image.data:
            filename = secure_filename(form.profile_image.data.filename)
            ext = filename.rsplit('.', 1)[-1].lower()
            new_filename = f'user_{current_user.id}.{ext}'
            filepath = os.path.join('static/profile_pics', new_filename)

            image = Image.open(form.profile_image.data)
            image = image.convert('RGB')
            image.thumbnail((150, 150))
            image.save(filepath)

            current_user.profile_image = new_filename

        db.session.commit()
        flash("✅ Profile updated successfully!", "success")
        return redirect(url_for('profile'))

    return render_template('edit_profile.html', form=form)

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if check_password_hash(current_user.password, form.current_password.data):
            current_user.password = generate_password_hash(form.new_password.data)
            db.session.commit()
            flash('✅ Password updated successfully.', 'success')
            return redirect(url_for('profile'))
        else:
            flash('❌ Incorrect current password.', 'danger')
    return render_template('change_password.html', form=form)

@app.route('/reset_score', methods=['POST'])
@login_required
def reset_score():
    current_user.score = 0
    db.session.commit()
    flash("✅ Your score has been reset to zero.", "success")
    return redirect(url_for('dashboard'))

@app.route('/leaderboard')
@login_required
def leaderboard():
    users = User.query.order_by(User.score.desc()).limit(10).all()
    return render_template('leaderboard.html', users=users)

@app.route('/practice', methods=['GET', 'POST'])
@login_required
def practice():
    result = ""
    question = ""
    correct_answer = ""
    selected_difficulty = request.form.get('difficulty', 'easy')

    if request.method == 'POST' and request.form.get('answer'):
        question = request.form.get('question')
        user_answer = request.form.get('answer')

        is_correct = False
        try:
            correct_answer = eval(question)
            if user_answer and int(user_answer) == correct_answer:
                is_correct = True
                result = "✅ Correct!"
                current_user.score += 1
            else:
                result = f"❌ Incorrect. The correct answer was {correct_answer}."
        except:
            result = "⚠️ Invalid answer."

        history = AnswerHistory(
            user_id=current_user.id,
            question=question,
            user_answer=user_answer,
            correct_answer=str(correct_answer),
            is_correct=is_correct
        )
        db.session.add(history)
        db.session.commit()

    if selected_difficulty == 'easy':
        a, b = random.randint(1, 10), random.randint(1, 10)
        op = random.choice(['+', '-'])
    elif selected_difficulty == 'medium':
        a, b = random.randint(10, 50), random.randint(1, 10)
        op = random.choice(['+', '-', '*'])
    else:
        a, b = random.randint(10, 100), random.randint(2, 12)
        op = random.choice(['+', '-', '*', '/'])

    question = f"{a} {op} {b}"
    return render_template("practice.html", question=question, result=result, user=current_user, selected_difficulty=selected_difficulty)

@app.route('/history')
@login_required
def history():
    answers = AnswerHistory.query.filter_by(user_id=current_user.id).order_by(AnswerHistory.id.desc()).all()
    return render_template('history.html', answers=answers)

@app.route('/clear_history', methods=['POST'])
@login_required
def clear_history():
    AnswerHistory.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash("✅ Your answer history has been cleared.", "success")
    return redirect(url_for('history'))

@app.route('/download_history')
@login_required
def download_history():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Question', 'Your Answer', 'Correct Answer', 'Result'])

    history = AnswerHistory.query.filter_by(user_id=current_user.id).order_by(AnswerHistory.id).all()

    for item in history:
        writer.writerow([
            item.question,
            item.user_answer,
            item.correct_answer,
            'Correct' if item.is_correct else 'Incorrect'
        ])

    output.seek(0)
    return Response(
        output,
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=answer_history.csv"}
    )

@app.route('/quiz')
@login_required
def quiz():
    session['quiz_score'] = 0
    session['quiz_total'] = 0
    return redirect(url_for('quiz_question'))

@app.route('/quiz_question', methods=['GET', 'POST'])
@login_required
def quiz_question():
    if 'quiz_score' not in session:
        return redirect(url_for('quiz'))

    if request.method == 'POST':
        question = request.form.get('question')
        answer = request.form.get('answer')
        try:
            correct = eval(question)
            if int(answer) == correct:
                session['quiz_score'] += 1
        except:
            pass
        session['quiz_total'] += 1

    if session['quiz_total'] >= 5:
        return redirect(url_for('quiz_summary'))

    a, b = random.randint(1, 20), random.randint(1, 20)
    op = random.choice(['+', '-', '*'])
    question = f"{a} {op} {b}"
    return render_template('quiz.html', question=question, question_num=session['quiz_total'] + 1)

@app.route('/quiz_summary')
@login_required
def quiz_summary():
    score = session.get('quiz_score', 0)
    total = session.get('quiz_total', 0)
    percent = int((score / total) * 100) if total > 0 else 0

    attempt = QuizAttempt(
        user_id=current_user.id,
        score=score,
        total=total,
        percent=percent
    )
    db.session.add(attempt)
    db.session.commit()

    session.pop('quiz_score', None)
    session.pop('quiz_total', None)
    return render_template('quiz_summary.html', score=score, total=total, percent=percent)

@app.route('/quiz_history')
@login_required
def quiz_history():
    attempts = QuizAttempt.query.filter_by(user_id=current_user.id).order_by(QuizAttempt.timestamp.desc()).all()

    if attempts:
        best_score = max(a.score for a in attempts)
        best_percent = max(a.percent for a in attempts)
        avg_percent = sum(a.percent for a in attempts) // len(attempts)
    else:
        best_score = 0
        best_percent = 0
        avg_percent = 0

    return render_template(
        'quiz_history.html',
        attempts=attempts,
        best_score=best_score,
        best_percent=best_percent,
        avg_percent=avg_percent
    )

@app.route('/admin/stats')
@login_required
def admin_stats():
    if not current_user.is_admin:
        flash("⛔ Access denied.", "danger")
        return redirect(url_for('dashboard'))

    today = date.today()
    total_users = User.query.count()
    new_users_today = User.query.filter(func.date(User.registered_on) == today).count()
    logins_today = User.query.filter(func.date(User.last_login) == today).count()
    total_quiz_attempts = QuizAttempt.query.count()

    return render_template('admin_stats.html', 
                           total_users=total_users,
                           new_users_today=new_users_today,
                           logins_today=logins_today,
                           total_quiz_attempts=total_quiz_attempts)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)