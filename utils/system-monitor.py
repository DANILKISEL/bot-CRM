import time
import os
from datetime import datetime
from models import TelegramUser, User, Conversation, Message


class SystemMonitor:
    def __init__(self):
        self.start_time = time.time()

    def get_system_uptime(self):
        """Get system uptime in a human-readable format"""
        try:
            uptime_seconds = time.time() - self.start_time
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
        except:
            pass
        return "unknown"

    def get_system_status(self):
        """Get comprehensive system status"""
        try:
            total_users = TelegramUser.query.count()
            total_agents = User.query.filter_by(is_agent=True).count()
            open_conversations = Conversation.query.filter(Conversation.status.in_(['open', 'assigned'])).count()
            closed_conversations = Conversation.query.filter_by(status='closed').count()
            total_messages = Message.query.count()

            recent_messages = Message.query.order_by(Message.timestamp.desc()).limit(5).all()
            recent_conversations = Conversation.query.order_by(Conversation.updated_at.desc()).limit(5).all()

            return {
                'system': {
                    'status': 'healthy',
                    'timestamp': datetime.utcnow().isoformat(),
                    'uptime': self.get_system_uptime(),
                },
                'statistics': {
                    'total_users': total_users,
                    'total_agents': total_agents,
                    'open_conversations': open_conversations,
                    'closed_conversations': closed_conversations,
                    'total_messages': total_messages,
                    'unassigned_conversations': Conversation.query.filter_by(assigned_agent_id=None).count()
                },
                'recent_activity': {
                    'recent_messages': [
                        {
                            'id': msg.id,
                            'content': msg.content[:50] + '...' if len(msg.content) > 50 else msg.content,
                            'timestamp': msg.timestamp.isoformat(),
                            'conversation_id': msg.conversation_id
                        } for msg in recent_messages
                    ],
                    'recent_conversations': [
                        {
                            'id': conv.id,
                            'title': conv.title,
                            'status': conv.status,
                            'updated_at': conv.updated_at.isoformat()
                        } for conv in recent_conversations
                    ]
                },
                'environment': {
                    'database_url': os.getenv('DATABASE_URL', 'sqlite:///crm_bot.db').split('@')[
                                        0] + '***' if '@' in os.getenv('DATABASE_URL', '') else os.getenv(
                        'DATABASE_URL', 'sqlite:///crm_bot.db'),
                    'flask_env': os.getenv('FLASK_ENV', 'production'),
                    'bot_token_set': bool(os.getenv('TELEGRAM_BOT_TOKEN'))
                }
            }
        except Exception as e:
            return {'error': str(e)}