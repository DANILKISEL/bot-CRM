from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from models import User, TelegramUser, Conversation, Message

def init_admin_routes(app):
    @app.route('/admin')
    @login_required
    def admin_dashboard():
        if not current_user.is_agent:
            return render_template("error.html", error='Access denied'), 403
        total_users = TelegramUser.query.count()
        total_agents = User.query.filter_by(is_agent=True).count()
        open_conversations = Conversation.query.filter(Conversation.status.in_(['open', 'assigned'])).count()
        total_messages = Message.query.count()
        recent_users = TelegramUser.query.order_by(TelegramUser.created_at.desc()).limit(6).all()
        return render_template(
            "admin-dash.html",
            total_users=total_users,
            total_agents=total_agents,
            open_conversations=open_conversations,
            total_messages=total_messages,
            recent_users=recent_users
        )

    @app.route('/user-management')
    @login_required
    def user_management():
        if not current_user.is_agent:
            return render_template("error.html", error='Access denied'), 403
        page = request.args.get('page', 1, type=int)
        per_page = 12
        agents = User.query.filter_by(is_agent=True).all()
        telegram_users = TelegramUser.query.order_by(TelegramUser.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        return render_template(
            "user-management.html",
            agents=agents,
            telegram_users=telegram_users
        )

    @app.route('/user/<int:user_id>/conversations')
    @login_required
    def user_conversations(user_id):
        if not current_user.is_agent:
            return render_template("error.html", error='Access denied'), 403
        telegram_user = TelegramUser.query.get_or_404(user_id)
        conversations = Conversation.query.filter_by(
            telegram_user_id=user_id
        ).order_by(Conversation.updated_at.desc()).all()
        return render_template(
            "user-conversations.html",
            telegram_user=telegram_user,
            conversations=conversations
        )

    @app.route('/add-agent', methods=['POST'])
    @login_required
    def add_agent():
        if not current_user.is_agent:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'error': 'Username already exists'})
        user = User(username=username, email=email, is_agent=True)
        user.set_password(password)
        from models import db
        db.session.add(user)
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/delete-agent', methods=['POST'])
    @login_required
    def delete_agent():
        if not current_user.is_agent:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
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
    def search_users():
        if not current_user.is_agent:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
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