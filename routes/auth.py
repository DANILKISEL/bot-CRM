from flask import render_template, request, redirect, url_for, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
from config import Config

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
            app.logger.info(f"Login attempt for username: {username}")

            user = User.query.filter_by(username=username).first()

            if user:
                app.logger.info(f"User found: {user.username}")
                password_correct = user.check_password(password)
                app.logger.info(f"Password correct: {password_correct}")

                if password_correct:
                    login_user(user)
                    app.logger.info(f"✅ User {username} logged in successfully")
                    next_page = request.args.get('next')
                    return redirect(next_page) if next_page else redirect(url_for('dashboard'))
                else:
                    app.logger.warning(f"❌ Invalid password for user: {username}")
            else:
                app.logger.warning(f"❌ User not found: {username}")

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
            role = request.form.get('role', 'AGENT')

            if User.query.filter_by(username=username).first():
                return render_template("register.html", error='Username already exists')

            user = User(username=username, email=email, role_level=Config.ROLES[role])
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            login_user(user)
            return redirect(url_for('dashboard'))

        return render_template("register.html", roles=Config.ROLES)

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))

    @app.route('/reset-admin-password')
    def reset_admin_password():
        """Route to reset admin password for testing"""
        try:
            admin_user = User.query.filter_by(username='admin').first()
            if admin_user:
                admin_user.set_password('admin123')
                db.session.commit()
                app.logger.info("✅ Admin password reset to 'admin123'")
                return jsonify({'success': True, 'message': 'Admin password reset to admin123'})
            else:
                return jsonify({'success': False, 'error': 'Admin user not found'})
        except Exception as e:
            app.logger.error(f"Error resetting admin password: {str(e)}")
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/test-login', methods=['POST'])
    def test_login():
        """Test login endpoint"""
        username = request.json.get('username')
        password = request.json.get('password')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'role_level': user.role_level
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Login failed',
                'user_exists': user is not None
            })