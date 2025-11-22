from flask import render_template_string, request, jsonify, redirect, url_for, render_template
from flask_login import login_user, logout_user, login_required, current_user
import telebot
import threading
import signal
import time
import requests
import subprocess
import socket
import os
import sys
from CRMclassbot import CRMTelegramBot
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from flask_login import LoginManager
import logging

global starttime
starttime = time.time()

cli = sys.modules['flask.cli']
cli.show_server_banner = lambda *x: None

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.basicConfig(
    filename='app.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='a'
)
logger = logging.getLogger("CRM")

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///crm_bot.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize Telegram bot
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
    exit(1)

def init_telegram_bot(app, db, TelegramUser, Conversation, Message):
    """Initialize the single Telegram bot"""
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        return None

    return CRMTelegramBot(app, db, bot_token, TelegramUser, Conversation, Message)

# models.py ------
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

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
# end models.py ------

# HTML Templates (keep your existing HTML templates as they are)
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

SYSTEM_MONITOR_HTML = ""
# Helper functions
def kill_process_on_port(port):
    """Kill process using specified port"""
    try:
        if os.name == 'posix':  # Linux/Mac
            result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid and pid != str(os.getpid()):
                        os.kill(int(pid), 9)
                        print(f"Killed process {pid} on port {port}")
                        time.sleep(1)  # Give it a moment to release the port
    except Exception as e:
        print(f"Error killing process on port {port}: {e}")

# Telegram bot broadcast function
def broadcast_to_user(telegram_user_id, message, is_agent=False):
    """Send message to Telegram user with app context"""
    try:
        with app.app_context():
            tg_user = TelegramUser.query.get(telegram_user_id)
            if tg_user:
                prefix = ""  # "👨‍💼 Agent: " if is_agent else ""
                bot = telebot.TeleBot(BOT_TOKEN)
                bot.send_message(tg_user.telegram_id, f"{prefix}{message}")
                logger.debug(f"Message sent to user {tg_user.telegram_id}")
    except Exception as e:
        logger.error(f"Error sending message to user {telegram_user_id}: {e}")

def get_system_uptime():
    """Get system uptime in a human-readable format"""
    try:
        uptime_seconds = time.time() - starttime
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        return f"{hours}h {minutes}m"
    except:
        pass
    return "unknown"

def update_env_file(updates):
    """Update .env file with new values"""
    env_file = '.env'
    env_vars = {}
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    env_vars.update(updates)
    with open(env_file, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")

# Flask Routes
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

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
            logger.debug(f"User {username} logged in successfully")
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

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        logger.debug(f"Dashboard accessed by user: {current_user.username}")
        if current_user.is_agent:
            conversations = Conversation.query.filter(
                (Conversation.assigned_agent_id == current_user.id) |
                (Conversation.assigned_agent_id.is_(None))
            ).order_by(Conversation.updated_at.desc()).all()
        else:
            conversations = Conversation.query.filter_by(
                assigned_agent_id=current_user.id
            ).order_by(Conversation.updated_at.desc()).all()
        logger.debug(f"Found {len(conversations)} conversations for user {current_user.username}")
        return render_template("dashboard.html", conversations=conversations)
    except Exception as e:
        logger.error(f"Error in dashboard: {str(e)}", exc_info=True)
        return render_template_string(ERROR_HTML, error=f'Error loading dashboard: {str(e)}')

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_agent:
        return render_template_string(ERROR_HTML, error='Access denied'), 403
    total_users = TelegramUser.query.count()
    total_agents = User.query.filter_by(is_agent=True).count()
    open_conversations = Conversation.query.filter(Conversation.status.in_(['open', 'assigned'])).count()
    total_messages = Message.query.count()
    recent_users = TelegramUser.query.order_by(TelegramUser.created_at.desc()).limit(6).all()
    return render_template(
        "admin_dashboard.html",
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
        return render_template_string(ERROR_HTML, error='Access denied'), 403
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
        return render_template_string(ERROR_HTML, error='Access denied'), 403
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

@app.route('/conversation/<int:conversation_id>')
@login_required
def conversation(conversation_id):
    conv = Conversation.query.get_or_404(conversation_id)
    if not current_user.is_agent and conv.assigned_agent_id != current_user.id:
        return render_template_string(ERROR_HTML, error='Access denied'), 403
    if current_user.is_agent and not conv.assigned_agent_id:
        conv.assigned_agent_id = current_user.id
        conv.status = 'assigned'
        db.session.commit()
    messages = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.timestamp).all()
    return render_template("chat.html", conversation=conv, messages=messages)

@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    conversation_id = request.json.get('conversation_id')
    content = request.json.get('content')
    conv = Conversation.query.get_or_404(conversation_id)
    message = Message(
        conversation_id=conversation_id,
        sender_type='agent',
        sender_id=current_user.id,
        content=content
    )
    db.session.add(message)
    conv.updated_at = datetime.utcnow()
    db.session.commit()
    broadcast_to_user(conv.telegram_user_id, content, is_agent=True)
    return jsonify({'success': True})

@app.route('/get_messages/<int:conversation_id>')
@login_required
def get_messages(conversation_id):
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
    message = Message(
        conversation_id=conversation_id,
        sender_type='ai',
        sender_id=None,
        content=content,
        is_ai_response=True
    )
    db.session.add(message)
    db.session.commit()
    return jsonify({'success': True})

# New System Management Endpoints
@app.route('/api/status')
@login_required
def api_status():
    """API endpoint for system status monitoring"""
    if not current_user.is_agent:
        return jsonify({'error': 'Access denied'}), 403
    try:
        total_users = TelegramUser.query.count()
        total_agents = User.query.filter_by(is_agent=True).count()
        open_conversations = Conversation.query.filter(Conversation.status.in_(['open', 'assigned'])).count()
        closed_conversations = Conversation.query.filter_by(status='closed').count()
        total_messages = Message.query.count()
        recent_messages = Message.query.order_by(Message.timestamp.desc()).limit(5).all()
        recent_conversations = Conversation.query.order_by(Conversation.updated_at.desc()).limit(5).all()
        bot_status = "unknown"
        try:
            bot = telebot.TeleBot(BOT_TOKEN)
            bot_info = bot.get_me()
            bot_status = "running" if bot_info else "error"
        except Exception as e:
            bot_status = f"error: {str(e)}"
        status_data = {
            'system': {
                'status': 'healthy',
                'timestamp': datetime.utcnow().isoformat(),
                'uptime': get_system_uptime(),
                'bot_status': bot_status
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
                                    0] + '***' if '@' in os.getenv('DATABASE_URL', '') else os.getenv('DATABASE_URL',
                                                                                                      'sqlite:///crm_bot.db'),
                'flask_env': os.getenv('FLASK_ENV', 'production'),
                'bot_token_set': bool(os.getenv('TELEGRAM_BOT_TOKEN'))
            }
        }
        return jsonify(status_data)
    except Exception as e:
        logger.error(f"Error in status endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/environment', methods=['GET', 'POST'])
@login_required
def api_environment():
    """Get or update environment variables"""
    if not current_user.is_agent:
        return jsonify({'error': 'Access denied'}), 403
    if request.method == 'GET':
        env_vars = {
            'DATABASE_URL': os.getenv('DATABASE_URL', 'sqlite:///crm_bot.db'),
            'FLASK_ENV': os.getenv('FLASK_ENV', 'production'),
            'TELEGRAM_BOT_TOKEN': '***' + os.getenv('TELEGRAM_BOT_TOKEN', '')[-4:] if os.getenv(
                'TELEGRAM_BOT_TOKEN') else None,
            'SECRET_KEY': '***' + os.getenv('SECRET_KEY', '')[-4:] if os.getenv('SECRET_KEY') else None,
        }
        return jsonify(env_vars)
    elif request.method == 'POST':
        try:
            data = request.json
            updates = {}
            allowed_vars = ['DATABASE_URL', 'FLASK_ENV']
            for key, value in data.items():
                if key in allowed_vars:
                    updates[key] = value
            if updates:
                update_env_file(updates)
                logger.warning(f"Environment variables updated by {current_user.username}: {list(updates.keys())}")
                return jsonify({'success': True, 'message': 'Environment variables updated. Restart required.'})
            else:
                return jsonify({'error': 'No valid environment variables to update'}), 400
        except Exception as e:
            logger.error(f"Error updating environment: {str(e)}")
            return jsonify({'error': str(e)}), 500


@app.route('/api/restart', methods=['POST'])
@login_required
def api_restart():
    """Restart the application"""
    if not current_user.is_agent:
        return jsonify({'error': 'Access denied'}), 403

    try:
        logger.debug(f"Restart initiated by {current_user.username}")
        print("Restarting ...")

        def restart_app():
            time.sleep(2)
            try:
                # Method 1: Use os.execv (replaces current process)
                python = sys.executable
                os.execv(python, [python] + sys.argv)
            except Exception as e:
                print(f"execv failed: {e}, trying subprocess method")
                try:
                    # Method 2: Use subprocess with environment preservation
                    python = sys.executable
                    script_path = os.path.abspath(sys.argv[0])

                    # Create a new process with the same environment
                    env = os.environ.copy()

                    # Start the new process
                    process = subprocess.Popen(
                        [python, script_path],
                        env=env,
                        cwd=os.getcwd()
                    )

                    print(f"New process started with PID: {process.pid}")

                    # Exit current process
                    os._exit(0)

                except Exception as e2:
                    print(f"Subprocess method also failed: {e2}")
                    # Last resort: just exit and let external process manager restart
                    os._exit(1)

        restart_thread = threading.Thread(target=restart_app)
        restart_thread.start()

        return jsonify({
            'success': True,
            'message': 'Restart initiated. System will restart shortly.'
        })

    except Exception as e:
        logger.error(f"Error during restart: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/shutdown', methods=['POST'])
@login_required
def api_shutdown():
    """Shutdown the application"""
    if not current_user.is_agent:
        return jsonify({'error': 'Access denied'}), 403

    try:
        logger.debug(f"Shutdown initiated by {current_user.username}")
        print("Shutting down...")

        def delayed_shutdown():
            time.sleep(2)
            os.kill(os.getpid(), signal.SIGINT)

        shutdown_thread = threading.Thread(target=delayed_shutdown, daemon=True)
        shutdown_thread.start()

        return jsonify({
            'success': True,
            'message': 'Shutdown initiated. System will stop shortly.'
        })

    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/system-monitor')
@login_required
def system_monitor():
    """System monitoring dashboard"""
    if not current_user.is_agent:
        return render_template_string(ERROR_HTML, error='Access denied'), 403
    return render_template_("system-monitor.html")

# Debug routes
@app.route('/debug/conversations')
@login_required
def debug_conversations():
    if not current_user.is_agent:
        return jsonify({'error': 'Access denied'}), 403
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
            db.session.add(test_user)
            db.session.commit()
        conversation = Conversation(
            telegram_user_id=test_user.id,
            title='Test Conversation',
            status='open'
        )
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
            db.session.add(msg)
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Sample data created',
            'conversation_id': conversation.id
        })
    except Exception as e:
        logger.error(f"Error creating sample data: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

def print_header():
    print("""
           __    __   _____   _____    __  __    ____     ____    _______  __    __   
          / /   / /  / ____| |  __ \  |  \/  |  |  _ \   / __ \  |__   __| \ \   \ \  
         / /   / /  | |      | |__) | | \  / |  | |_) | | |  | |    | |     \ \   \ \ 
        < <   < <   | |      |  _  /  | |\/| |  |  _ <  | |  | |    | |      > >   > >
         \ \   \ \  | |____  | | \ \  | |  | |  | |_) | | |__| |    | |     / /   / / 
          \_\   \_\  \_____| |_|  \_\ |_|  |_|  |____/   \____/     |_|    /_/   /_/  

        """)
def print_localhost_header():
    print("""
    _____           _              _                 _ _               _   
  / ____|         | |            | |               | | |             | |  
 | |  __  ___     | |_ ___       | | ___   ___ __ _| | |__   ___  ___| |_ 
 | | |_ |/ _ \    | __/ _ \      | |/ _ \ / __/ _` | | '_ \ / _ \/ __| __|
 | |__| | (_) |   | || (_) |     | | (_) | (_| (_| | | | | | (_) \__ \ |_ 
  \_____|\___/     \__\___/      |_|\___/ \___\__,_|_|_| |_|\___/|___/\__|
""")

def init_db():
    with app.app_context():
        db.create_all()
        logger.debug("✅ Database initialized!")
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
            logger.info("✅ Default admin user created: admin / admin123")

def get_public_ip_urllib():
    return requests.get('https://4.indent.me', verify=False)

def run_flask():
    # Allow socket reuse to prevent "Address already in use" errors
    socket.socket(socket.AF_INET, socket.SOCK_STREAM).setsockopt(
        socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
    )
    app.run(debug=False, port=2000, use_reloader=False)

def start_flask():
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("✅ Flask app running at http://localhost:2000")
    logger.debug("✅ Admin Dashboard available at http://localhost:2000/admin")
    logger.debug("✅ User Management available at http://localhost:2000/user-management")
    logger.debug("✅ System Monitor available at http://localhost:2000/system-monitor")

def disable_verbose_loggers():
    logging.getLogger('werkzeug').disabled = True
    logging.getLogger('CRM').disabled = True
    logging.getLogger('CRM CLASS BOT').disabled = True


def start_bot_single():
    logger.info("Starting CRM Telegram Bot...")
    crm_bot = init_telegram_bot(app, db, TelegramUser, Conversation, Message)
    if crm_bot:
        bot_thread = threading.Thread(target=crm_bot.run, daemon=True)
        bot_thread.start()
        logger.debug("✅ CRM Telegram Bot started successfully!")
    else:
        logger.error("❌ Failed to start CRM Telegram Bot")

def keep_alive():
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")


def main():
    print_header()
    print_localhost_header()
    print("🚀 Starting CRM Bot System...")

    # Initialize database
    init_db()

    # Start Flask
    start_flask()

    # Start the single bot
    start_bot_single()

    logger.info("✅ System started successfully!")
    logger.info("\nPress Ctrl+C to stop")

    # Keep main thread alive
    keep_alive()

if __name__ == '__main__':
    main()