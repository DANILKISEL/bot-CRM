from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)  # <-- Make sure this exists
    password_hash = db.Column(db.String(128))
    is_agent = db.Column(db.Boolean, default=False)


    conversations_assigned = db.relationship('Conversation', backref='assigned_agent', lazy=True,
                                             foreign_keys='Conversation.assigned_agent_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class TelegramUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False)
    username = db.Column(db.String(80))
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    conversations = db.relationship('Conversation', backref='telegram_user', lazy=True)

    def __repr__(self):
        return f'<TelegramUser {self.username or self.telegram_id}>'


class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_user_id = db.Column(db.Integer, db.ForeignKey('telegram_user.id'), nullable=False)
    status = db.Column(db.String(20), default='open')  # open, assigned, closed
    assigned_agent_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship('Message', backref='conversation', lazy=True)

    def __repr__(self):
        return f'<Conversation {self.id} status={self.status}>'


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    sender_type = db.Column(db.String(20), nullable=False)  # 'user', 'agent', 'ai'
    sender_id = db.Column(db.Integer, nullable=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_ai_response = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Message {self.id} from {self.sender_type}>'

    def get_sender(self):
        if self.sender_type == 'user':
            return User.query.get(self.sender_id)
        elif self.sender_type == 'agent':
            return User.query.get(self.sender_id)
        elif self.sender_type == 'ai':
            return None  # AI responses may not have a sender object
        else:
            return None