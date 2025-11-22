from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from models import User, TelegramUser, Conversation, Message
from utils.decorators import role_required
from config import Config

def init_admin_routes(app):
    @app.route('/admin')
    @login_required
    @role_required(Config.ROLES['SYSTEM_ADMIN'])
    def admin_dashboard():
        total_users = TelegramUser.query.count()
        total_agents = User.query.filter(User.role_level >= Config.ROLES['AGENT']).count()
        open_conversations = Conversation.query.filter(Conversation.status.in_(['open', 'assigned'])).count()
        total_messages = Message.query.count()
        recent_users = TelegramUser.query.order_by(TelegramUser.created_at.desc()).limit(6).all()

        return render_template(
            "admin_dashboard.html",
            total_users=total_users,
            total_agents=total_agents,
            open_conversations=open_conversations,
            total_messages=total_messages,
            recent_users=recent_users,
            now=datetime.now()
        )

    @app.route('/conversation-management')
    @login_required
    @role_required(Config.ROLES['MANAGER'])
    def conversation_management():
        page = request.args.get('page', 1, type=int)
        per_page = 20

        conversations = Conversation.query.order_by(Conversation.updated_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        agents = User.query.filter(User.role_level >= Config.ROLES['AGENT']).all()

        # Calculate conversation counts
        open_count = Conversation.query.filter_by(status='open').count()
        assigned_count = Conversation.query.filter_by(status='assigned').count()
        closed_count = Conversation.query.filter_by(status='closed').count()

        return render_template(
            "conversation_management.html",
            conversations=conversations,
            agents=agents,
            open_count=open_count,
            assigned_count=assigned_count,
            closed_count=closed_count
        )

    @app.route('/assign-conversation', methods=['POST'])
    @login_required
    @role_required(Config.ROLES['MANAGER'])
    def assign_conversation():
        conversation_id = request.json.get('conversation_id')
        agent_id = request.json.get('agent_id')

        conversation = Conversation.query.get_or_404(conversation_id)
        agent = User.query.get_or_404(agent_id)

        conversation.assigned_agent_id = agent_id
        conversation.status = 'assigned'
        from models import db
        db.session.commit()

        return jsonify({'success': True})

    @app.route('/close-conversation/<int:conversation_id>', methods=['POST'])
    @login_required
    @role_required(Config.ROLES['MANAGER'])
    def close_conversation(conversation_id):
        try:
            conversation = Conversation.query.get_or_404(conversation_id)
            conversation.status = 'closed'
            conversation.closed_at = datetime.utcnow()
            from models import db
            db.session.commit()

            return jsonify({'success': True})
        except Exception as e:
            app.logger.error(f"Error closing conversation: {str(e)}")
            return jsonify({'error': 'Failed to close conversation'}), 500