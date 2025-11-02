#!/usr/bin/env python3
"""
CRM Bot System - Single File Version
Combines Flask web dashboard + Telegram bot + PostgreSQL
"""

import os
import sys
import threading
import time
import logging
from datetime import datetime
from dotenv import load_dotenv

# Third-party imports
try:
    from flask import Flask, render_template_string, request, jsonify, redirect, url_for
    from flask_sqlalchemy import SQLAlchemy
    from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
    from werkzeug.security import generate_password_hash, check_password_hash
    import telebot
    from telebot.types import ReplyKeyboardMarkup, KeyboardButton
    import psycopg2
    from sqlalchemy import text
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print(
        "Please install requirements: pip install flask flask-sqlalchemy flask-login pytelegrambotapi psycopg2-binary python-dotenv")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('crm_bot.log')
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'super-secret-key-12345')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///crm_bot.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# Database Models
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    is_agent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assigned_conversations = db.relationship('Conversation', backref='assigned_agent', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class TelegramUser(db.Model):
    __tablename__ = 'telegram_users'
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), nullable=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=True)
    language_code = db.Column(db.String(10), default='en')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    conversations = db.relationship('Conversation', backref='telegram_user', lazy=True, cascade='all, delete-orphan')


class Conversation(db.Model):
    __tablename__ = 'conversations'
    id = db.Column(db.Integer, primary_key=True)
    telegram_user_id = db.Column(db.Integer, db.ForeignKey('telegram_users.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='open', nullable=False, index=True)
    assigned_agent_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)

    messages = db.relationship('Message', backref='conversation', lazy=True, cascade='all, delete-orphan')


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False, index=True)
    sender_type = db.Column(db.String(20), nullable=False)
    sender_id = db.Column(db.Integer, nullable=True)
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default='text')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    is_ai_response = db.Column(db.Boolean, default=False)
    read_by_agent = db.Column(db.Boolean, default=False)


# Telegram Bot
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
    sys.exit(1)

bot = telebot.TeleBot(BOT_TOKEN)

# HTML Templates
BASE_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}CRM Bot Dashboard{% endblock %}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background-color: #f5f5f5; }
        .navbar { background-color: #2c3e50; color: white; padding: 1rem 0; }
        .nav-container { max-width: 1200px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; padding: 0 1rem; }
        .nav-logo { font-size: 1.5rem; }
        .nav-links a { color: white; text-decoration: none; margin-left: 1rem; }
        .main-content { max-width: 1200px; margin: 0 auto; padding: 2rem 1rem; }
        .auth-container { display: flex; justify-content: center; align-items: center; min-height: 80vh; }
        .auth-form { background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); width: 100%; max-width: 400px; }
        .form-group { margin-bottom: 1rem; }
        .form-group label { display: block; margin-bottom: 0.5rem; font-weight: bold; }
        .form-group input { width: 100%; padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; }
        .btn { padding: 0.5rem 1rem; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; }
        .btn-primary { background-color: #3498db; color: white; }
        .btn-secondary { background-color: #95a5a6; color: white; }
        .alert { padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem; }
        .alert-error { background-color: #e74c3c; color: white; }
        .conversations-list { display: grid; gap: 1rem; }
        .conversation-item { background: white; padding: 1rem; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .conversation-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
        .status-badge { padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
        .status-open { background-color: #e74c3c; color: white; }
        .status-assigned { background-color: #f39c12; color: white; }
        .status-closed { background-color: #27ae60; color: white; }
        .chat-container { background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; }
        .chat-header { background-color: #34495e; color: white; padding: 1rem; display: flex; justify-content: space-between; align-items: center; }
        .chat-messages { height: 400px; overflow-y: auto; padding: 1rem; }
        .message { margin-bottom: 1rem; }
        .message-content { display: inline-block; max-width: 70%; padding: 0.5rem 1rem; border-radius: 8px; }
        .message.user .message-content { background-color: #ecf0f1; text-align: left; }
        .message.agent .message-content { background-color: #3498db; color: white; text-align: left; }
        .message.ai .message-content { background-color: #2ecc71; color: white; text-align: left; }
        .chat-input { padding: 1rem; border-top: 1px solid #eee; }
        .chat-input textarea { width: 100%; padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; resize: vertical; }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="nav-container">
            <h1 class="nav-logo">CRM Bot Dashboard</h1>
            <div class="nav-links">
                {% if current_user.is_authenticated %}
                    <span>Welcome, {{ current_user.username }}</span>
                    <a href="{{ url_for('dashboard') }}">Dashboard</a>
                    <a href="{{ url_for('logout') }}">Logout</a>
                {% else %}
                    <a href="{{ url_for('login') }}">Login</a>
                    <a href="{{ url_for('register') }}">Register</a>
                {% endif %}
            </div>
        </div>
    </nav>
    <main class="main-content">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
'''

LOGIN_HTML = '''
{% extends "base.html" %}
{% block content %}
<div class="auth-container">
    <div class="auth-form">
        <h2>Login</h2>
        {% if error %}
        <div class="alert alert-error">
            {{ error }}
        </div>
        {% endif %}
        <form method="POST">
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit" class="btn btn-primary">Login</button>
        </form>
        <p>Don't have an account? <a href="{{ url_for('register') }}">Register here</a></p>
    </div>
</div>
{% endblock %}
'''

REGISTER_HTML = '''
{% extends "base.html" %}
{% block content %}
<div class="auth-container">
    <div class="auth-form">
        <h2>Register</h2>
        {% if error %}
        <div class="alert alert-error">
            {{ error }}
        </div>
        {% endif %}
        <form method="POST">
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="email">Email:</label>
                <input type="email" id="email" name="email" required>
            </div>
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <div class="form-group">
                <label>
                    <input type="checkbox" name="is_agent" value="1">
                    Register as Agent
                </label>
            </div>
            <button type="submit" class="btn btn-primary">Register</button>
        </form>
        <p>Already have an account? <a href="{{ url_for('login') }}">Login here</a></p>
    </div>
</div>
{% endblock %}
'''

DASHBOARD_HTML = '''
{% extends "base.html" %}
{% block content %}
<div class="dashboard">
    <h2>Conversations</h2>

    <div class="conversations-list">
        {% for conversation in conversations %}
        <div class="conversation-item">
            <div class="conversation-header">
                <h3>Conversation #{{ conversation.id }}</h3>
                <span class="status-badge status-{{ conversation.status }}">{{ conversation.status }}</span>
            </div>
            <p><strong>User:</strong> {{ conversation.telegram_user.first_name }} {{ conversation.telegram_user.last_name }}</p>
            <p><strong>Started:</strong> {{ conversation.created_at.strftime('%Y-%m-%d %H:%M') }}</p>
            <a href="{{ url_for('conversation', conversation_id=conversation.id) }}" class="btn btn-secondary">Open Chat</a>
        </div>
        {% else %}
        <p>No conversations found.</p>
        {% endfor %}
    </div>
</div>
{% endblock %}
'''

CHAT_HTML = '''
{% extends "base.html" %}
{% block content %}
<div class="chat-container">
    <div class="chat-header">
        <h2>Conversation with {{ conversation.telegram_user.first_name }}</h2>
        <span class="status-badge status-{{ conversation.status }}">{{ conversation.status }}</span>
    </div>

    <div class="chat-messages" id="chatMessages">
        {% for message in messages %}
        <div class="message {{ message.sender_type }}">
            <div class="message-content">
                <strong>
                    {% if message.sender_type == 'user' %}
                    👤 User
                    {% elif message.sender_type == 'agent' %}
                    👨‍💼 Agent
                    {% else %}
                    🤖 AI
                    {% endif %}
                </strong>
                <p>{{ message.content }}</p>
                <small>{{ message.timestamp.strftime('%H:%M') }}</small>
            </div>
        </div>
        {% endfor %}
    </div>

    <div class="chat-input">
        <textarea id="messageInput" placeholder="Type your message..." rows="3"></textarea>
        <button onclick="sendMessage()" class="btn btn-primary">Send</button>
    </div>
</div>

<script>
function sendMessage() {
    const input = document.getElementById('messageInput');
    const content = input.value.trim();

    if (content) {
        fetch('{{ url_for("send_message") }}', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                conversation_id: {{ conversation.id }},
                content: content
            })
        }).then(response => response.json())
          .then(data => {
              if (data.success) {
                  input.value = '';
                  location.reload();
              }
          });
    }
}

// Auto-refresh messages every 5 seconds
setInterval(() => {
    fetch('{{ url_for("get_messages", conversation_id=conversation.id) }}')
        .then(response => response.json())
        .then(messages => {
            if (messages.length !== {{ messages|length }}) {
                location.reload();
            }
        });
}, 5000);
</script>
{% endblock %}
'''

ERROR_HTML = '''
{% extends "base.html" %}
{% block content %}
<div class="error-container" style="text-align: center; padding: 2rem;">
    <h2>Error</h2>
    <p>{{ error }}</p>
    <a href="{{ url_for('dashboard') }}" class="btn btn-primary">Return to Dashboard</a>
</div>
{% endblock %}
'''


# Flask Routes
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


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

        if not username or not password:
            return render_template_string(LOGIN_HTML, error='Username and password are required')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            logger.info(f"User {username} logged in successfully")
            return redirect(url_for('dashboard'))
        else:
            return render_template_string(LOGIN_HTML, error='Invalid username or password')

    return render_template_string(LOGIN_HTML)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        is_agent = bool(request.form.get('is_agent'))

        if not username or not email or not password:
            return render_template_string(REGISTER_HTML, error='All fields are required')

        try:
            if User.query.filter_by(username=username).first():
                return render_template_string(REGISTER_HTML, error='Username already exists')

            if User.query.filter_by(email=email).first():
                return render_template_string(REGISTER_HTML, error='Email already exists')

            user = User(username=username, email=email, is_agent=is_agent)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            logger.info(f"New user registered: {username} (Agent: {is_agent})")
            login_user(user)
            return redirect(url_for('dashboard'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error during registration: {e}")
            return render_template_string(REGISTER_HTML, error='An error occurred during registration')

    return render_template_string(REGISTER_HTML)


@app.route('/logout')
@login_required
def logout():
    logger.info(f"User {current_user.username} logged out")
    logout_user()
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    try:
        if current_user.is_agent:
            conversations = Conversation.query.filter(
                Conversation.status.in_(['open', 'assigned'])
            ).order_by(Conversation.updated_at.desc()).all()
        else:
            conversations = Conversation.query.filter_by(
                assigned_agent_id=current_user.id
            ).order_by(Conversation.updated_at.desc()).all()

        return render_template_string(DASHBOARD_HTML, conversations=conversations, is_agent=current_user.is_agent)

    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        return render_template_string(ERROR_HTML, error='Error loading dashboard')


@app.route('/conversation/<int:conversation_id>')
@login_required
def conversation(conversation_id):
    try:
        conv = Conversation.query.get_or_404(conversation_id)

        if not current_user.is_agent and conv.assigned_agent_id != current_user.id:
            return render_template_string(ERROR_HTML, error='Access denied'), 403

        if current_user.is_agent and not conv.assigned_agent_id:
            conv.assigned_agent_id = current_user.id
            conv.status = 'assigned'
            db.session.commit()

        messages = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.timestamp).all()
        return render_template_string(CHAT_HTML, conversation=conv, messages=messages)

    except Exception as e:
        logger.error(f"Error loading conversation {conversation_id}: {e}")
        return render_template_string(ERROR_HTML, error='Error loading conversation')


@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    try:
        conversation_id = request.json.get('conversation_id')
        content = request.json.get('content')

        if not content or not content.strip():
            return jsonify({'success': False, 'error': 'Message content is required'})

        conv = Conversation.query.get_or_404(conversation_id)

        if not current_user.is_agent and conv.assigned_agent_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        message = Message(
            conversation_id=conversation_id,
            sender_type='agent',
            sender_id=current_user.id,
            content=content.strip()
        )
        db.session.add(message)
        conv.updated_at = datetime.utcnow()
        db.session.commit()

        broadcast_to_user(conv.telegram_user_id, content.strip(), is_agent=True)

        logger.info(f"Agent {current_user.username} sent message to conversation {conversation_id}")
        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error sending message: {e}")
        return jsonify({'success': False, 'error': 'Failed to send message'})


@app.route('/get_messages/<int:conversation_id>')
@login_required
def get_messages(conversation_id):
    try:
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

    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
        return jsonify({'error': 'Failed to fetch messages'}), 500


# Telegram Bot Functions
def create_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton('🆘 Get Help'),
        KeyboardButton('📞 Contact Agent'),
        KeyboardButton('ℹ️ Status'),
        KeyboardButton('❌ Close Conversation')
    )
    return keyboard


@bot.message_handler(commands=['start', 'help'])
def start_command(message):
    try:
        with db.session.begin():
            tg_user = TelegramUser.query.filter_by(telegram_id=message.from_user.id).first()
            if not tg_user:
                tg_user = TelegramUser(
                    telegram_id=message.from_user.id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name,
                    language_code=message.from_user.language_code
                )
                db.session.add(tg_user)
                logger.info(f"New Telegram user: {message.from_user.first_name}")

        welcome_text = """
🤖 Welcome to CRM Support Bot!

I'm here to help you with:
• Customer support
• Product information
• Technical assistance

Use the buttons below or type your question!
        """

        bot.send_message(message.chat.id, welcome_text, reply_markup=create_keyboard())

    except Exception as e:
        logger.error(f"Error in start_command: {e}")


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        with db.session.begin():
            tg_user = TelegramUser.query.filter_by(telegram_id=message.from_user.id).first()
            if not tg_user:
                bot.send_message(message.chat.id, "Please use /start to begin.")
                return

            conversation = Conversation.query.filter_by(
                telegram_user_id=tg_user.id,
                status='open'
            ).first()

            if not conversation:
                conversation = Conversation.query.filter_by(
                    telegram_user_id=tg_user.id,
                    status='assigned'
                ).first()

            if not conversation:
                conversation = Conversation(
                    telegram_user_id=tg_user.id,
                    title=f"Chat with {tg_user.first_name}",
                    status='open'
                )
                db.session.add(conversation)
                db.session.commit()

            user_message = Message(
                conversation_id=conversation.id,
                sender_type='user',
                sender_id=tg_user.id,
                content=message.text
            )
            db.session.add(user_message)
            conversation.updated_at = datetime.utcnow()
            db.session.commit()

        ai_response = generate_ai_response(message.text, conversation.id)

        if ai_response:
            with db.session.begin():
                ai_message = Message(
                    conversation_id=conversation.id,
                    sender_type='ai',
                    sender_id=None,
                    content=ai_response,
                    is_ai_response=True
                )
                db.session.add(ai_message)
                db.session.commit()

            bot.send_message(message.chat.id, ai_response)

        notify_agents(conversation.id, message.text, tg_user)

    except Exception as e:
        logger.error(f"Error handling message: {e}")


def generate_ai_response(user_message, conversation_id):
    try:
        user_message_lower = user_message.lower()

        if user_message_lower in ['❌ close conversation', '/close']:
            return close_conversation(conversation_id)

        if user_message_lower in ['🆘 get help', 'help']:
            return "I'm here to help! Please describe your issue and I'll connect you with a human agent if needed."

        if user_message_lower in ['📞 contact agent', 'agent']:
            return "I've notified our support agents. A human agent will join this conversation shortly!"

        if user_message_lower in ['ℹ️ status', 'status']:
            return "Our support team is available 24/7. Current response time is usually within 5-10 minutes."

        if any(word in user_message_lower for word in ['hello', 'hi', 'hey']):
            return "Hello! I'm an AI assistant. How can I help you today?"

        elif 'help' in user_message_lower:
            return "I'm here to assist you! Please describe your issue."

        elif any(word in user_message_lower for word in ['price', 'cost', 'how much']):
            return "Our pricing varies based on your needs. I can connect you with a sales agent for detailed pricing."

        elif any(word in user_message_lower for word in ['thank', 'thanks']):
            return "You're welcome! Is there anything else I can help you with?"

        elif any(word in user_message_lower for word in ['bye', 'goodbye']):
            return "Goodbye! Feel free to reach out if you need more assistance."

        else:
            return "Thank you for your message. I've forwarded it to our support team. An agent will respond shortly."

    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        return "I understand you're looking for assistance. Our team will get back to you shortly."


def close_conversation(conversation_id):
    try:
        with db.session.begin():
            conversation = Conversation.query.get(conversation_id)
            if conversation and conversation.status != 'closed':
                conversation.status = 'closed'
                conversation.closed_at = datetime.utcnow()
                db.session.commit()
                return "Conversation closed. Thank you for contacting us!"
            else:
                return "No active conversation found."
    except Exception as e:
        logger.error(f"Error closing conversation: {e}")
        return "Sorry, I couldn't close the conversation."


def notify_agents(conversation_id, message, tg_user):
    try:
        logger.info(f"New message from {tg_user.first_name}: {message}")
        print(f"🔔 Conversation #{conversation_id}: {tg_user.first_name} - {message}")
    except Exception as e:
        logger.error(f"Error notifying agents: {e}")


def broadcast_to_user(telegram_user_id, message, is_agent=False):
    try:
        tg_user = TelegramUser.query.get(telegram_user_id)
        if tg_user:
            if is_agent:
                prefix = "👨‍💼 Agent: "
            else:
                prefix = "🤖 AI: "

            bot.send_message(tg_user.telegram_id, f"{prefix}{message}")
            logger.info(f"Message sent to user {tg_user.telegram_id}")
    except Exception as e:
        logger.error(f"Error sending message to user {telegram_user_id}: {e}")


def start_bot():
    try:
        logger.info("Starting Telegram bot...")
        print("🤖 Telegram Bot is starting...")
        bot.infinity_polling()
    except Exception as e:
        logger.error(f"Error starting bot: {e}")


def run_flask_app():
    try:
        logger.info("Starting Flask web application...")
        print("🌐 Web Dashboard: http://localhost:5000")
        app.run(debug=False, port=5000, host='0.0.0.0', use_reloader=False)
    except Exception as e:
        logger.error(f"Error running Flask app: {e}")


def init_db():
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created successfully!")

            admin_user = User.query.filter_by(username='admin').first()
            if not admin_user:
                admin_user = User(
                    username='admin',
                    email='admin@crmbot.com',
                    is_agent=True
                )
                admin_user.set_password('admin123')
                db.session.add(admin_user)
                db.session.commit()
                logger.info("Default admin user created: admin / admin123")

        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise


def check_dependencies():
    missing_vars = []

    if not os.getenv('TELEGRAM_BOT_TOKEN'):
        missing_vars.append('TELEGRAM_BOT_TOKEN')

    if not os.getenv('DATABASE_URL'):
        missing_vars.append('DATABASE_URL')

    if missing_vars:
        print("❌ Missing environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease create a .env file with these variables.")
        return False

    return True


def main():
    print("🚀 Starting CRM Bot System...")

    if not check_dependencies():
        sys.exit(1)

    print("Initializing database...")

    try:
        init_db()
        print("✅ Database initialized!")

        flask_thread = threading.Thread(target=run_flask_app, daemon=True)
        flask_thread.start()

        time.sleep(2)

        print("✅ Flask app running at http://localhost:5000")
        print("✅ Telegram bot starting...")
        print("\n📋 Services:")
        print("   • Web Dashboard: http://localhost:5000")
        print("   • Telegram Bot: Active")
        print("   • Database: PostgreSQL")
        print("\nDefault admin: admin / admin123")
        print("Press Ctrl+C to stop")

        start_bot()

    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"❌ Error: {e}")


if __name__ == '__main__':
    main()