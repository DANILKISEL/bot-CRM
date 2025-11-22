from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from models import User, TelegramUser, Conversation
from utils.decorators import role_required
from config import Config

def init_user_routes(app):
    @app.route('/user-management')
    @login_required
    @role_required(Config.ROLES['SYSTEM_ADMIN'])
    def user_management():
        page = request.args.get('page', 1, type=int)
        per_page = 12

        staff_users = User.query.filter(User.role_level >= Config.ROLES['AGENT']).all()

        telegram_users = TelegramUser.query.order_by(TelegramUser.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return render_template(
            "user_managment.html",
            staff_users=staff_users,
            telegram_users=telegram_users,
            ROLES=Config.ROLES
        )

    @app.route('/user/<int:user_id>/conversations')
    @login_required
    @role_required(Config.ROLES['SYSTEM_ADMIN'])
    def user_conversations(user_id):
        telegram_user = TelegramUser.query.get_or_404(user_id)
        conversations = Conversation.query.filter_by(
            telegram_user_id=user_id
        ).order_by(Conversation.updated_at.desc()).all()

        return render_template(
            "user_conversations.html",
            telegram_user=telegram_user,
            conversations=conversations
        )

    @app.route('/add-user', methods=['POST'])
    @login_required
    @role_required(Config.ROLES['PLATFORM_ADMIN'])
    def add_user():
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'AGENT')

        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'error': 'Username already exists'})

        user = User(username=username, email=email, role_level=Config.ROLES[role])
        user.set_password(password)
        from models import db
        db.session.add(user)
        db.session.commit()

        return jsonify({'success': True})

    @app.route('/update-user-role', methods=['POST'])
    @login_required
    @role_required(Config.ROLES['PLATFORM_ADMIN'])
    def update_user_role():
        user_id = request.json.get('user_id')
        new_role = request.json.get('role')

        if user_id == current_user.id:
            return jsonify({'success': False, 'error': 'Cannot change your own role'})

        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'})

        user.role_level = Config.ROLES[new_role]
        from models import db
        db.session.commit()

        return jsonify({'success': True})

    @app.route('/delete-user', methods=['POST'])
    @login_required
    @role_required(Config.ROLES['PLATFORM_ADMIN'])
    def delete_user():
        user_id = request.json.get('user_id')

        if user_id == current_user.id:
            return jsonify({'success': False, 'error': 'Cannot delete your own account'})

        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'})

        Conversation.query.filter_by(assigned_agent_id=user_id).update({'assigned_agent_id': None})
        from models import db
        db.session.delete(user)
        db.session.commit()

        return jsonify({'success': True})

    @app.route('/search-users')
    @login_required
    @role_required(Config.ROLES['SYSTEM_ADMIN'])
    def search_users():
        query = request.args.get('q', '')
        if not query:
            return jsonify([])

        users = TelegramUser.query.filter(
            (TelegramUser.first_name.ilike(f'%{query}%')) |
            (TelegramUser.last_name.ilike(f'%{query}%')) |
            (TelegramUser.username.ilike(f'%{query}%'))
        ).limit(10).all()

        users_data = []
        for user in users:
            users_data.append({
                'id': user.id,
                'name': f"{user.first_name} {user.last_name or ''}",
                'username': user.username,
                'telegram_id': user.telegram_id,
                'conversations_count': len(user.conversations)
            })

        return jsonify(users_data)