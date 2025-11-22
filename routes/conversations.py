from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from models import Conversation, Message, TelegramUser
from utils.decorators import role_required
from utils.helpers import broadcast_to_user
from config import Config

def init_conversation_routes(app):
    @app.route('/dashboard')
    @login_required
    def dashboard():
        try:
            app.logger.info(f"Dashboard accessed by user: {current_user.username}")

            # Role-based conversation access
            if current_user.has_role('MANAGER'):
                conversations = Conversation.query.order_by(Conversation.updated_at.desc()).all()
            else:
                conversations = Conversation.query.filter_by(
                    assigned_agent_id=current_user.id
                ).order_by(Conversation.updated_at.desc()).all()

            app.logger.info(f"Found {len(conversations)} conversations for user {current_user.username}")

            return render_template("dashboard.html", conversations=conversations, ROLES=Config.ROLES)

        except Exception as e:
            app.logger.error(f"Error in dashboard: {str(e)}", exc_info=True)
            from utils.decorators import ERROR_HTML
            return render_template_string(ERROR_HTML, error=f'Error loading dashboard: {str(e)}')

    @app.route('/conversation/<int:conversation_id>')
    @login_required
    def conversation(conversation_id):
        conv = Conversation.query.get_or_404(conversation_id)

        if not current_user.has_role('MANAGER') and conv.assigned_agent_id != current_user.id:
            from utils.decorators import ERROR_HTML
            return render_template_string(ERROR_HTML, error='Access denied'), 403

        if current_user.has_role('MANAGER') and not conv.assigned_agent_id:
            conv.assigned_agent_id = current_user.id
            conv.status = 'assigned'
            from models import db
            db.session.commit()

        messages = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.timestamp).all()
        return render_template("chat.html", conversation=conv, messages=messages)

    @app.route('/send_message', methods=['POST'])
    @login_required
    def send_message():
        conversation_id = request.json.get('conversation_id')
        content = request.json.get('content')

        conv = Conversation.query.get_or_404(conversation_id)

        if not current_user.has_role('MANAGER') and conv.assigned_agent_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        message = Message(
            conversation_id=conversation_id,
            sender_type='agent',
            sender_id=current_user.id,
            content=content
        )
        from models import db
        db.session.add(message)
        conv.updated_at = datetime.utcnow()
        db.session.commit()

        broadcast_to_user(conv.telegram_user_id, content, is_agent=True)

        return jsonify({'success': True})

    @app.route('/get_messages/<int:conversation_id>')
    @login_required
    def get_messages(conversation_id):
        conv = Conversation.query.get_or_404(conversation_id)

        if not current_user.has_role('MANAGER') and conv.assigned_agent_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        messages = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.timestamp).all()
        messages_data = []

        for msg in messages:
            messages_data.append({
                'id': msg.id,
                'sender_type': msg.sender_type,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat(),
                'is_ai_response': msg.is_ai_response
            })

        return jsonify(messages_data)

    @app.route('/ai_response', methods=['POST'])
    @login_required
    def ai_response():
        conversation_id = request.json.get('conversation_id')
        content = request.json.get('content')

        conv = Conversation.query.get_or_404(conversation_id)

        if not current_user.has_role('MANAGER') and conv.assigned_agent_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        message = Message(
            conversation_id=conversation_id,
            sender_type='ai',
            sender_id=None,
            content=content,
            is_ai_response=True
        )
        from models import db
        db.session.add(message)
        db.session.commit()

        return jsonify({'success': True})