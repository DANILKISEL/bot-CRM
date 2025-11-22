from flask import jsonify, request
from flask_login import login_required, current_user
from models import Conversation, TelegramUser, Message
from utils.decorators import role_required
from config import Config

def init_api_routes(app):
    @app.route('/api/conversations')
    @login_required
    @role_required(Config.ROLES['MANAGER'])
    def api_conversations():
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 10, type=int)
            status_filter = request.args.get('status', 'all')
            agent_filter = request.args.get('agent', 'all')
            search_query = request.args.get('search', '')
            sort_by = request.args.get('sort', 'updated_desc')

            query = Conversation.query

            if status_filter != 'all':
                query = query.filter(Conversation.status == status_filter)

            if agent_filter != 'all':
                query = query.filter(Conversation.assigned_agent_id == agent_filter)

            if search_query:
                query = query.join(TelegramUser).filter(
                    (TelegramUser.first_name.ilike(f'%{search_query}%')) |
                    (TelegramUser.last_name.ilike(f'%{search_query}%')) |
                    (TelegramUser.username.ilike(f'%{search_query}%')) |
                    (Conversation.title.ilike(f'%{search_query}%'))
                )

            if sort_by == 'updated_asc':
                query = query.order_by(Conversation.updated_at.asc())
            elif sort_by == 'created_desc':
                query = query.order_by(Conversation.created_at.desc())
            else:
                query = query.order_by(Conversation.updated_at.desc())

            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            conversations = pagination.items

            conversations_data = []
            for conv in conversations:
                conversations_data.append({
                    'id': conv.id,
                    'title': conv.title,
                    'status': conv.status,
                    'created_at': conv.created_at.isoformat(),
                    'updated_at': conv.updated_at.isoformat(),
                    'telegram_user': {
                        'id': conv.telegram_user.id,
                        'first_name': conv.telegram_user.first_name,
                        'last_name': conv.telegram_user.last_name,
                        'username': conv.telegram_user.username
                    },
                    'assigned_agent': {
                        'id': conv.assigned_agent.id,
                        'username': conv.assigned_agent.username,
                        'role': conv.assigned_agent.get_role_name()
                    } if conv.assigned_agent else None,
                    'message_count': len(conv.messages)
                })

            total = Conversation.query.count()
            open_count = Conversation.query.filter_by(status='open').count()
            assigned_count = Conversation.query.filter_by(status='assigned').count()
            closed_count = Conversation.query.filter_by(status='closed').count()

            return jsonify({
                'conversations': conversations_data,
                'pagination': {
                    'page': page,
                    'pages': pagination.pages,
                    'total': pagination.total,
                    'start': (page - 1) * per_page + 1,
                    'end': min(page * per_page, pagination.total)
                },
                'stats': {
                    'total': total,
                    'open': open_count,
                    'assigned': assigned_count,
                    'closed': closed_count
                }
            })

        except Exception as e:
            app.logger.error(f"Error in api_conversations: {str(e)}")
            return jsonify({'error': 'Failed to load conversations'}), 500

    @app.route('/debug/users')
    def debug_users():
        users = User.query.all()
        users_data = []
        for user in users:
            users_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role_level': user.role_level,
                'password_hash': user.password_hash[:20] + '...' if user.password_hash else None
            })

        return jsonify({
            'total_users': len(users),
            'users': users_data
        })

    @app.route('/debug/conversations')
    @login_required
    @role_required(Config.ROLES['SYSTEM_ADMIN'])
    def debug_conversations():
        conversations = Conversation.query.all()
        conversation_data = []

        for conv in conversations:
            conversation_data.append({
                'id': conv.id,
                'telegram_user_id': conv.telegram_user_id,
                'status': conv.status,
                'title': conv.title,
                'assigned_agent_id': conv.assigned_agent_id,
                'created_at': conv.created_at.isoformat() if conv.created_at else None,
                'telegram_user': {
                    'id': conv.telegram_user.id if conv.telegram_user else None,
                    'first_name': conv.telegram_user.first_name if conv.telegram_user else None,
                    'last_name': conv.telegram_user.last_name if conv.telegram_user else None
                } if conv.telegram_user else None,
                'message_count': len(conv.messages)
            })

        return jsonify({
            'total_conversations': len(conversations),
            'conversations': conversation_data
        })

    @app.route('/test/create-sample')
    def create_sample_data():
        try:
            test_user = TelegramUser.query.filter_by(telegram_id=123456789).first()
            if not test_user:
                test_user = TelegramUser(
                    telegram_id=123456789,
                    username='testuser',
                    first_name='Test',
                    last_name='User'
                )
                from models import db
                db.session.add(test_user)
                db.session.commit()

            conversation = Conversation(
                telegram_user_id=test_user.id,
                title='Test Conversation',
                status='open'
            )
            from models import db
            db.session.add(conversation)

            messages = [
                Message(
                    conversation_id=conversation.id,
                    sender_type='user',
                    sender_id=test_user.id,
                    content='Hello, this is a test message from user'
                ),
                Message(
                    conversation_id=conversation.id,
                    sender_type='ai',
                    sender_id=None,
                    content='Hello! This is an AI response',
                    is_ai_response=True
                )
            ]

            for msg in messages:
                from models import db
                db.session.add(msg)

            from models import db
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Sample data created',
                'conversation_id': conversation.id
            })

        except Exception as e:
            app.logger.error(f"Error creating sample data: {str(e)}")
            from models import db
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)})