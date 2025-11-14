from flask import render_template_string, request, jsonify, redirect, url_for, render_template
from flask_login import login_user, logout_user, login_required, current_user
import telebot
import os
from datetime import datetime
import threading
import logging
import requests
from models import User, Conversation, TelegramUser, Message
from CRMclassbot import CRMTelegramBot
from initmodule import init
db, app, logger, login_manager, BOT_TOKEN = init()


def init_telegram_bot(app, db, TelegramUser, Conversation, Message):
    """Initialize the single Telegram bot"""
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        return None

    return CRMTelegramBot(app, db, bot_token, TelegramUser, Conversation, Message)


# HTML Templates
CHAT_HTML = '''
{% extends "base.html" %}
{% block content %}
<div class="chat-container">
    <div class="chat-header">
        <h2>Conversation with {{ conversation.telegram_user.first_name }}</h2>
        <div>
            <span class="status-badge status-{{ conversation.status }}">{{ conversation.status }}</span>
            {% if conversation.assigned_agent %}
            <span style="margin-left: 10px;">Assigned to: {{ conversation.assigned_agent.username }}</span>
            {% endif %}
        </div>
    </div>

    <div class="chat-messages" id="chatMessages">
        {% for message in messages %}
        <div class="message {{ message.sender_type }}">
            <div class="message-content">
                <div class="message-sender" style="display:none;">
                    {% if message.sender_type == 'user' %}
                    👤 <strong>User</strong>
                    {% elif message.sender_type == 'agent' %}
                    👨‍💼 <strong>Agent</strong>
                    {% else %}
                    🤖 <strong>AI Assistant</strong>
                    {% endif %}
                </div>
                <div class="message-text">{{ message.content }}</div>
                <div class="message-meta">{{ message.timestamp.strftime('%H:%M') }}</div>
            </div>
        </div>
        {% endfor %}
    </div>

    <div class="chat-input">
        <textarea id="messageInput" placeholder="Type your message to the user..." rows="3"></textarea>
        <button onclick="sendMessage()" class="btn btn-primary">Send Message</button>
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
              } else {
                  alert('Failed to send message: ' + (data.error || 'Unknown error'));
              }
          })
          .catch(error => {
              alert('Error sending message: ' + error);
          });
    }
}

// Auto-scroll to bottom
function scrollToBottom() {
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Scroll to bottom on page load
window.addEventListener('load', scrollToBottom);

// Auto-refresh messages every 3 seconds
setInterval(() => {
    fetch('{{ url_for("get_messages", conversation_id=conversation.id) }}')
        .then(response => response.json())
        .then(messages => {
            if (messages.length !== {{ messages|length }}) {
                location.reload();
            }
        });
}, 3000);
</script>
{% endblock %}
'''

ADMIN_DASHBOARD_HTML = '''
{% extends "base.html" %}
{% block content %}
<div class="dashboard">
    <h2>Admin Dashboard</h2>

    <!-- Statistics Cards -->
    <div class="stats-grid">
        <div class="stat-card">
            <span class="stat-number">{{ total_users }}</span>
            <span class="stat-label">Total Telegram Users</span>
        </div>
        <div class="stat-card">
            <span class="stat-number">{{ total_agents }}</span>
            <span class="stat-label">Agents</span>
        </div>
        <div class="stat-card">
            <span class="stat-number">{{ open_conversations }}</span>
            <span class="stat-label">Open Conversations</span>
        </div>
        <div class="stat-card">
            <span class="stat-number">{{ total_messages }}</span>
            <span class="stat-label">Total Messages</span>
        </div>
    </div>

    <!-- Quick Actions -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin: 2rem 0;">
        <a href="{{ url_for('user_management') }}" class="btn btn-primary" style="text-align: center; padding: 1.5rem;">
            👥 User Management
        </a>
        <a href="{{ url_for('dashboard') }}" class="btn btn-secondary" style="text-align: center; padding: 1.5rem;">
            💬 Conversation Dashboard
        </a>
    </div>

    <!-- Recent Activity -->
    <div class="recent-activity" style="background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
        <h3>Recent User Registrations</h3>
        <div class="users-grid" style="margin-top: 1rem;">
            {% for user in recent_users %}
            <div class="user-card">
                <div class="user-info">
                    <h4>{{ user.first_name }} {{ user.last_name or '' }}</h4>
                    <p><strong>Username:</strong> @{{ user.username or 'N/A' }}</p>
                    <p><strong>Joined:</strong> {{ user.created_at.strftime('%Y-%m-%d %H:%M') }}</p>
                </div>
            </div>
            {% else %}
            <p>No recent users.</p>
            {% endfor %}
        </div>
    </div>
</div>
{% endblock %}
'''

USER_MANAGEMENT_HTML = '''
{% extends "base.html" %}
{% block content %}
<div class="dashboard">
    <h2>User Management</h2>

    <div class="tabs" style="margin-bottom: 2rem;">
        <button class="tab-btn active" onclick="openTab('agents')">Agents</button>
        <button class="tab-btn" onclick="openTab('telegram-users')">Telegram Users</button>
        <button class="tab-btn" onclick="openTab('add-user')">Add New Agent</button>
    </div>

    <!-- Agents Tab -->
    <div id="agents" class="tab-content active">
        <h3>Agent Management</h3>
        <div class="users-grid">
            {% for user in agents %}
            <div class="user-card">
                <div class="user-info">
                    <h4>{{ user.username }}</h4>
                    <p><strong>Email:</strong> {{ user.email }}</p>
                    <p><strong>Registered:</strong> {{ user.created_at.strftime('%Y-%m-%d') }}</p>
                    <p><strong>Assigned Conversations:</strong> {{ user.assigned_conversations|length }}</p>
                </div>
                <div class="user-actions">
                    <button onclick="deleteUser({{ user.id }})" class="btn btn-danger">Delete</button>
                </div>
            </div>
            {% else %}
            <p>No agents found.</p>
            {% endfor %}
        </div>
    </div>

    <!-- Telegram Users Tab -->
    <div id="telegram-users" class="tab-content">
        <h3>Telegram Users ({{ telegram_users.total }})</h3>

        <div class="search-box" style="margin-bottom: 1rem;">
            <input type="text" id="searchInput" placeholder="Search by name or username..." onkeyup="searchUsers()">
        </div>

        <div class="users-grid">
            {% for user in telegram_users.items %}
            <div class="user-card">
                <div class="user-info">
                    <h4>{{ user.first_name }} {{ user.last_name or '' }}</h4>
                    <p><strong>Username:</strong> @{{ user.username or 'N/A' }}</p>
                    <p><strong>Telegram ID:</strong> {{ user.telegram_id }}</p>
                    <p><strong>Language:</strong> {{ user.language_code }}</p>
                    <p><strong>Joined:</strong> {{ user.created_at.strftime('%Y-%m-%d %H:%M') }}</p>
                    <p><strong>Conversations:</strong> {{ user.conversations|length }}</p>
                </div>
                <div class="user-actions">
                    <a href="{{ url_for('user_conversations', user_id=user.id) }}" class="btn btn-secondary">View Conversations</a>
                </div>
            </div>
            {% else %}
            <p>No Telegram users found.</p>
            {% endfor %}
        </div>

        <!-- Pagination -->
        <div class="pagination">
            {% if telegram_users.has_prev %}
            <a href="{{ url_for('user_management', page=telegram_users.prev_num) }}" class="btn">Previous</a>
            {% endif %}

            <span>Page {{ telegram_users.page }} of {{ telegram_users.pages }}</span>

            {% if telegram_users.has_next %}
            <a href="{{ url_for('user_management', page=telegram_users.next_num) }}" class="btn">Next</a>
            {% endif %}
        </div>
    </div>

    <!-- Add User Tab -->
    <div id="add-user" class="tab-content">
        <h3>Add New Agent</h3>
        <form method="POST" action="{{ url_for('add_agent') }}" class="auth-form">
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
            <button type="submit" class="btn btn-primary">Add Agent</button>
        </form>
    </div>
</div>

<script>
function openTab(tabName) {
    // Hide all tab contents
    var tabContents = document.getElementsByClassName("tab-content");
    for (var i = 0; i < tabContents.length; i++) {
        tabContents[i].classList.remove("active");
    }

    // Remove active class from all buttons
    var tabButtons = document.getElementsByClassName("tab-btn");
    for (var i = 0; i < tabButtons.length; i++) {
        tabButtons[i].classList.remove("active");
    }

    // Show the selected tab and mark button as active
    document.getElementById(tabName).classList.add("active");
    event.currentTarget.classList.add("active");
}

function searchUsers() {
    var input = document.getElementById('searchInput');
    var filter = input.value.toLowerCase();
    var userCards = document.querySelectorAll('#telegram-users .user-card');

    userCards.forEach(function(card) {
        var text = card.textContent.toLowerCase();
        if (text.includes(filter)) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
}

function deleteUser(userId) {
    if (confirm('Are you sure you want to delete this agent? This action cannot be undone.')) {
        fetch('{{ url_for("delete_agent") }}', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: userId
            })
        }).then(response => response.json())
          .then(data => {
              if (data.success) {
                  location.reload();
              } else {
                  alert('Failed to delete user: ' + (data.error || 'Unknown error'));
              }
          })
          .catch(error => {
              alert('Error deleting user: ' + error);
          });
    }
}
</script>
{% endblock %}
'''

USER_CONVERSATIONS_HTML = '''
{% extends "base.html" %}
{% block content %}
<div class="dashboard">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
        <h2>Conversations with {{ telegram_user.first_name }}</h2>
        <a href="{{ url_for('user_management') }}" class="btn btn-secondary">← Back to User Management</a>
    </div>

    <div class="user-info-card" style="background: white; padding: 1.5rem; border-radius: 8px; margin-bottom: 2rem; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
        <h3>User Information</h3>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-top: 1rem;">
            <div>
                <strong>Name:</strong> {{ telegram_user.first_name }} {{ telegram_user.last_name or '' }}
            </div>
            <div>
                <strong>Username:</strong> @{{ telegram_user.username or 'N/A' }}
            </div>
            <div>
                <strong>Telegram ID:</strong> {{ telegram_user.telegram_id }}
            </div>
            <div>
                <strong>Joined:</strong> {{ telegram_user.created_at.strftime('%Y-%m-%d %H:%M') }}
            </div>
        </div>
    </div>

    <div class="conversations-list">
        {% for conversation in conversations %}
        <div class="conversation-item">
            <div class="conversation-header">
                <h3>Conversation #{{ conversation.id }}</h3>
                <span class="status-badge status-{{ conversation.status }}">{{ conversation.status }}</span>
            </div>
            <p><strong>Started:</strong> {{ conversation.created_at.strftime('%Y-%m-%d %H:%M') }}</p>
            <p><strong>Last Activity:</strong> {{ conversation.updated_at.strftime('%Y-%m-%d %H:%M') }}</p>
            <p><strong>Messages:</strong> {{ conversation.messages|length }}</p>
            {% if conversation.assigned_agent %}
            <p><strong>Assigned Agent:</strong> {{ conversation.assigned_agent.username }}</p>
            {% endif %}
            <a href="{{ url_for('conversation', conversation_id=conversation.id) }}" class="btn btn-primary">Open Conversation</a>
        </div>
        {% else %}
        <div class="conversation-item">
            <p>No conversations found for this user.</p>
        </div>
        {% endfor %}
    </div>
</div>
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


# Telegram bot broadcast function
def broadcast_to_user(telegram_user_id, message, is_agent=False):
    """Send message to Telegram user with app context"""
    try:
        with app.app_context():
            tg_user = TelegramUser.query.get(telegram_user_id)
            if tg_user:
                prefix = "" # "👨‍💼 Agent: " if is_agent else ""
                bot = telebot.TeleBot(BOT_TOKEN)
                bot.send_message(tg_user.telegram_id, f"{prefix}{message}")
                logger.info(f"Message sent to user {tg_user.telegram_id}")
    except Exception as e:
        logger.error(f"Error sending message to user {telegram_user_id}: {e}")


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
            logger.info(f"User {username} logged in successfully")
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
    #TOHTML_2
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
        logger.info(f"Dashboard accessed by user: {current_user.username}")

        if current_user.is_agent:
            conversations = Conversation.query.filter(
                (Conversation.assigned_agent_id == current_user.id) |
                (Conversation.assigned_agent_id.is_(None))
            ).order_by(Conversation.updated_at.desc()).all()
        else:
            conversations = Conversation.query.filter_by(
                assigned_agent_id=current_user.id
            ).order_by(Conversation.updated_at.desc()).all()

        logger.info(f"Found {len(conversations)} conversations for user {current_user.username}")

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

    return render_template_string(
        ADMIN_DASHBOARD_HTML,
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

    return render_template_string(
        USER_MANAGEMENT_HTML,
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

    return render_template_string(
        USER_CONVERSATIONS_HTML,
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
    return render_template_string(CHAT_HTML, conversation=conv, messages=messages)


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


def init_db():
    with app.app_context():
        db.create_all()
        logger.info("✅ Database initialized!")

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
    app.run(debug=False, port=2000, use_reloader=False)


def main():
    print("""
       __    __   _____   _____    __  __    ____     ____    _______  __    __   
      / /   / /  / ____| |  __ \  |  \/  |  |  _ \   / __ \  |__   __| \ \   \ \  
     / /   / /  | |      | |__) | | \  / |  | |_) | | |  | |    | |     \ \   \ \ 
    < <   < <   | |      |  _  /  | |\/| |  |  _ <  | |  | |    | |      > >   > >
     \ \   \ \  | |____  | | \ \  | |  | |  | |_) | | |__| |    | |     / /   / / 
      \_\   \_\  \_____| |_|  \_\ |_|  |_|  |____/   \____/     |_|    /_/   /_/  

    _____           _              _                 _ _               _   
  / ____|         | |            | |               | | |             | |  
 | |  __  ___     | |_ ___       | | ___   ___ __ _| | |__   ___  ___| |_ 
 | | |_ |/ _ \    | __/ _ \      | |/ _ \ / __/ _` | | '_ \ / _ \/ __| __|
 | |__| | (_) |   | || (_) |     | | (_) | (_| (_| | | | | | (_) \__ \ |_ 
  \_____|\___/     \__\___/      |_|\___/ \___\__,_|_|_| |_|\___/|___/\__|

    """)
    logging.getLogger('werkzeug').disabled = True
    logging.getLogger('__main__').disabled = True
    print("🚀 Starting CRM Bot System...")

    # Initialize database
    init_db()

    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("✅ Flask app running at http://localhost:2000")
    print("✅ Admin Dashboard available at http://localhost:2000/admin")
    print("✅ User Management available at http://localhost:2000/user-management")

    # Start the single bot
    logger.info("Starting CRM Telegram Bot...")
    crm_bot = init_telegram_bot(app, db, TelegramUser, Conversation, Message)
    if crm_bot:
        bot_thread = threading.Thread(target=crm_bot.run, daemon=True)
        bot_thread.start()
        logger.info("✅ CRM Telegram Bot started successfully!")
    else:
        logger.error("❌ Failed to start CRM Telegram Bot")

    logger.info("✅ System started successfully!")
    logger.info("\nPress Ctrl+C to stop")

    # Keep main thread alive
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == '__main__':
    main()