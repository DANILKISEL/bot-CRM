from flask import render_template, request, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User

def init_auth_routes(app):
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                login_user(user)
                app.logger.debug(f"User {username} logged in successfully")
                return redirect(url_for('dashboard'))
            else:
                return render_template("login.html", error='Invalid username or password')
        return render_template("login.html")

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            is_agent = bool(request.form.get('is_agent'))
            if User.query.filter_by(username=username).first():
                return render_template("register.html", error='Username already exists')
            user = User(username=username, email=email, is_agent=is_agent)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('dashboard'))
        return render_template("register.html")

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))