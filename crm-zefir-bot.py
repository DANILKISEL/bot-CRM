from flask import Flask, render_template_string, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import os
from datetime import datetime
import threading
import logging
from dotenv import load_dotenv
import sys
import requests
import re

cli = sys.modules['flask.cli']
cli.show_server_banner = lambda *x: None

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

bot = telebot.TeleBot(BOT_TOKEN)


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
        .btn-danger { background-color: #e74c3c; color: white; }
        .alert { padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem; }
        .alert-error { background-color: #e74c3c; color: white; }
        .conversations-list { display: grid; gap: 1rem; }
        .conversation-item { background: white; padding: 1rem; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .conversation-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
        .status-badge { padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
        .status-open { background-color: #e74c3c; color: white; }
        .status-assigned { background-color: #f39c12; color: white; }
        .status-closed { background-color: #27ae60; color: white; }
        .status-contract_process { background-color: #9b59b6; color: white; }
        .chat-container { background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; max-width: 1000px; margin: 0 auto; }
        .chat-header { background-color: #34495e; color: white; padding: 1rem; display: flex; justify-content: space-between; align-items: center; }
        .chat-messages { height: 500px; overflow-y: auto; padding: 1rem; background-color: #f8f9fa; }
        .message { margin-bottom: 1rem; display: flex; }
        .message.user { justify-content: flex-end; }
        .message.agent, .message.ai { justify-content: flex-start; }
        .message-content { max-width: 70%; padding: 0.75rem 1rem; border-radius: 18px; position: relative; }
        .message.user .message-content { 
            background-color: #007bff; 
            color: white; 
            border-bottom-right-radius: 4px;
        }
        .message.agent .message-content { 
            background-color: #28a745; 
            color: white;
            border-bottom-left-radius: 4px;
        }
        .message.ai .message-content { 
            background-color: #6c757d; 
            color: white;
            border-bottom-left-radius: 4px;
        }
        .message-meta { font-size: 0.75rem; margin-top: 0.25rem; opacity: 0.8; }
        .chat-input { padding: 1rem; border-top: 1px solid #eee; background: white; }
        .chat-input textarea { width: 100%; padding: 0.75rem; border: 1px solid #ddd; border-radius: 8px; resize: vertical; font-size: 14px; }
        .chat-input button { margin-top: 0.5rem; padding: 0.75rem 2rem; }

        /* User Management Styles */
        .tabs { display: flex; border-bottom: 2px solid #ddd; margin-bottom: 1rem; }
        .tab-btn { padding: 0.75rem 1.5rem; background: none; border: none; cursor: pointer; border-bottom: 3px solid transparent; font-size: 1rem; }
        .tab-btn.active { border-bottom-color: #3498db; font-weight: bold; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .users-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; margin-top: 1rem; }
        .user-card { background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); border-left: 4px solid #3498db; }
        .user-info h4 { margin: 0 0 0.5rem 0; color: #2c3e50; }
        .user-info p { margin: 0.25rem 0; font-size: 0.9rem; }
        .user-actions { margin-top: 1rem; display: flex; gap: 0.5rem; }
        .search-box input { width: 100%; padding: 0.75rem; border: 1px solid #ddd; border-radius: 4px; font-size: 1rem; }
        .pagination { display: flex; justify-content: center; align-items: center; gap: 1rem; margin-top: 2rem; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
        .stat-card { background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); text-align: center; }
        .stat-number { font-size: 2rem; font-weight: bold; color: #3498db; display: block; }
        .stat-label { color: #7f8c8d; font-size: 0.9rem; }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="nav-container">
            <h1 class="nav-logo">CRM Bot Dashboard</h1>
            <div class="nav-links">
                {% if current_user.is_authenticated %}
                    <span>Welcome, {{ current_user.username }}</span>
                    {% if current_user.is_agent %}
                        <a href="{{ url_for('admin_dashboard') }}">Admin Dashboard</a>
                        <a href="{{ url_for('user_management') }}">User Management</a>
                    {% endif %}
                    <a href="{{ url_for('dashboard') }}">Conversations</a>
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
            <p><strong>Last Message:</strong> {{ conversation.updated_at.strftime('%Y-%m-%d %H:%M') }}</p>
            <a href="{{ url_for('conversation', conversation_id=conversation.id) }}" class="btn btn-secondary">Open Chat</a>
        </div>
        {% else %}
        <div class="conversation-item">
            <p>No conversations found. When users message your Telegram bot, conversations will appear here.</p>
        </div>
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
                <div class="message-sender">
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


# Contract Bot Implementation
class ZefirContractBot:
    def __init__(self, db, telegram_bot_token, TelegramUser, Conversation, Message):
        self.db = db
        self.bot = telebot.TeleBot(telegram_bot_token)
        self.TelegramUser = TelegramUser
        self.Conversation = Conversation
        self.Message = Message

        # User session storage for contract process
        self.user_sessions = {}

        self.setup_handlers()

    def setup_handlers(self):
        """Setup message handlers for contract bot"""
        self.bot.message_handler(commands=['contract'])(self.start_contract_handler)
        self.bot.message_handler(func=lambda message: self.check_contract_session(message))(
            self.contract_message_handler)
        self.bot.callback_query_handler(func=lambda call: call.data.startswith('contract_'))(
            self.contract_callback_handler)

    def check_contract_session(self, message):
        """Check if user is in contract session"""
        return message.from_user.id in self.user_sessions

    def get_or_create_telegram_user(self, user_id: int, username: str, first_name: str, last_name: str = None):
        """Get existing Telegram user or create new one"""
        try:
            telegram_user = self.TelegramUser.query.filter_by(telegram_id=user_id).first()
            if telegram_user:
                # Update user info if changed
                if (telegram_user.username != username or
                        telegram_user.first_name != first_name or
                        telegram_user.last_name != last_name):
                    telegram_user.username = username
                    telegram_user.first_name = first_name
                    telegram_user.last_name = last_name
                    telegram_user.updated_at = datetime.utcnow()
                    self.db.session.commit()
                return telegram_user
            else:
                # Create new user
                telegram_user = self.TelegramUser(
                    telegram_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                self.db.session.add(telegram_user)
                self.db.session.commit()
                return telegram_user
        except Exception as e:
            logger.error(f"Error getting/creating Telegram user: {e}")
            self.db.session.rollback()
            return None

    def create_contract_conversation(self, telegram_user, title="Contract Agreement"):
        """Create a new conversation for contract process"""
        try:
            conversation = self.Conversation(
                telegram_user_id=telegram_user.id,
                title=title,
                status='contract_process'
            )
            self.db.session.add(conversation)
            self.db.session.commit()
            return conversation
        except Exception as e:
            logger.error(f"Error creating conversation: {e}")
            self.db.session.rollback()
            return None

    def save_contract_message(self, conversation, content, sender_type="user", is_ai_response=False):
        """Save message to database"""
        try:
            message = self.Message(
                conversation_id=conversation.id,
                sender_type=sender_type,
                content=content,
                is_ai_response=is_ai_response,
                timestamp=datetime.utcnow()
            )
            self.db.session.add(message)
            self.db.session.commit()
            return message
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            self.db.session.rollback()
            return None

    def start_contract_handler(self, message):
        """Start the contract agreement process"""
        user = message.from_user

        # Get or create Telegram user in database
        telegram_user = self.get_or_create_telegram_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )

        if not telegram_user:
            self.bot.reply_to(message, "❌ Ошибка при создании пользователя. Попробуйте позже.")
            return

        # Create new conversation for contract process
        conversation = self.create_contract_conversation(telegram_user, "Contract Agreement Process")
        if not conversation:
            self.bot.reply_to(message, "❌ Ошибка при создании диалога. Попробуйте позже.")
            return

        # Initialize user session
        self.user_sessions[user.id] = {
            'conversation_id': conversation.id,
            'step': 'waiting_full_name',
            'full_name': None,
            'passport': None
        }

        # Save start message
        self.save_contract_message(conversation, "User started contract process")

        welcome_text = """
🤝 **Добро пожаловать!**

Вы начинаете процесс заключения соглашения с нашей командой Zeffr.

Пожалуйста, введите ваше ФИО полностью:
        """

        # Save bot message
        self.save_contract_message(conversation, welcome_text, sender_type="bot", is_ai_response=True)

        self.bot.reply_to(message, welcome_text, parse_mode='Markdown')

    def contract_message_handler(self, message):
        """Handle text messages during the contract registration process"""
        user = message.from_user
        user_message = message.text

        # Check if user has an active session
        if user.id not in self.user_sessions:
            self.bot.reply_to(message, "Пожалуйста, начните процесс с команды /contract")
            return

        session = self.user_sessions[user.id]
        conversation_id = session.get('conversation_id')

        if not conversation_id:
            self.bot.reply_to(message, "❌ Сессия не найдена. Пожалуйста, начните с /contract")
            return

        # Get conversation
        conversation = self.Conversation.query.get(conversation_id)
        if not conversation:
            self.bot.reply_to(message, "❌ Диалог не найдена. Пожалуйста, начните с /contract")
            return

        # Save user message
        self.save_contract_message(conversation, user_message, sender_type="user")

        current_step = session.get('step')

        if current_step == 'waiting_full_name':
            self.process_full_name(message, user_message, session, conversation)

        elif current_step == 'waiting_passport':
            self.process_passport(message, user_message, session, conversation)
        else:
            # Handle other messages or restart process
            self.bot.reply_to(message, "Пожалуйста, начните процесс с команды /contract")

    def process_full_name(self, message, full_name: str, session: dict, conversation):
        """Process and validate full name"""
        # Basic validation - at least 2 words
        if len(full_name.split()) < 2:
            error_msg = "❌ Пожалуйста, введите ФИО полностью (как минимум имя и фамилию):"
            self.save_contract_message(conversation, error_msg, sender_type="bot", is_ai_response=True)
            self.bot.reply_to(message, error_msg)
            return

        # Store full name in session and update database
        session['full_name'] = full_name
        session['step'] = 'waiting_passport'

        # Update conversation with user's name
        conversation.title = f"Contract: {full_name}"
        self.db.session.commit()

        next_step_text = """
Теперь введите серию и номер вашего паспорта (через пробел):
Например: `4510 123456`
        """

        self.save_contract_message(conversation, next_step_text, sender_type="bot", is_ai_response=True)
        self.bot.reply_to(message, next_step_text, parse_mode='Markdown')

    def process_passport(self, message, passport: str, session: dict, conversation):
        """Process and validate passport data"""
        # Validate passport format (4 digits + space + 6 digits)
        passport_pattern = r'^\d{4}\s\d{6}$'

        if not re.match(passport_pattern, passport):
            error_msg = "❌ Неверный формат паспорта. Пожалуйста, введите серию и номер через пробел (например: `4510 123456`):"
            self.save_contract_message(conversation, error_msg, sender_type="bot", is_ai_response=True)
            self.bot.reply_to(message, error_msg, parse_mode='Markdown')
            return

        # Store passport data in session
        session['passport'] = passport
        session['step'] = 'waiting_agreement'

        full_name = session['full_name']

        confirmation_text = f"""
Спасибо, {full_name}!

Перед началом работы ознакомьтесь с нашей публичной офертой:

**Договор:**  
[https://zeffr-it.ru/contract.html](https://zeffr-it.ru/contract.html)  

**Соглашение об обработке данных:**  
[https://zeffr-it.ru/privacy.html](https://zeffr-it.ru/privacy.html)  

Нажимая кнопку ниже, вы подтверждаете согласие с условиями.
        """

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("✅ Согласен", callback_data="contract_agree_terms"))

        self.save_contract_message(conversation, confirmation_text, sender_type="bot", is_ai_response=True)
        self.bot.reply_to(
            message,
            confirmation_text,
            reply_markup=keyboard,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

    def contract_callback_handler(self, call):
        """Handle contract button callbacks"""
        user = call.from_user
        data = call.data

        # Check if user has an active session
        if user.id not in self.user_sessions:
            self.bot.answer_callback_query(call.id, "Сессия истекла. Начните с /contract")
            return

        session = self.user_sessions[user.id]
        conversation_id = session.get('conversation_id')

        if not conversation_id:
            self.bot.answer_callback_query(call.id, "Сессия не найдена. Начните с /contract")
            return

        conversation = self.Conversation.query.get(conversation_id)
        if not conversation:
            self.bot.answer_callback_query(call.id, "Диалог не найдена. Начните с /contract")
            return

        if data == "contract_agree_terms":
            self.process_contract_agreement(call, session, conversation, user)

        self.bot.answer_callback_query(call.id)

    def process_contract_agreement(self, call, session: dict, conversation, user):
        """Process user agreement and complete contract"""
        full_name = session.get('full_name')
        passport = session.get('passport')

        if not full_name or not passport:
            self.bot.edit_message_text(
                "❌ Данные не найдены. Пожалуйста, начните заново с /contract",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
            return

        # Update conversation status to completed
        conversation.status = 'completed'
        conversation.closed_at = datetime.utcnow()
        self.db.session.commit()

        success_text = f"""
✅ **Спасибо! Вы приняли условия оферты.**

✅ **Договор успешно заключён.**

С уважением, команда Zeffr 🚀

**Ваши данные:**
• ФИО: {full_name}
• Паспорт: {passport}
• Дата заключения: {self.get_current_date()}

Договор вступил в силу. Добро пожаловать в команду!
        """

        # Save success message
        self.save_contract_message(conversation, success_text, sender_type="bot", is_ai_response=True)

        # Remove keyboard and show final message
        self.bot.edit_message_text(
            success_text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode='Markdown',
            reply_markup=None
        )

        # Log contract completion
        self.log_contract_completion(conversation, full_name, passport, user.id)

        # Clean up session
        if user.id in self.user_sessions:
            del self.user_sessions[user.id]

    def log_contract_completion(self, conversation, full_name: str, passport: str, telegram_id: int):
        """Log contract completion"""
        try:
            logger.info(
                f"Contract completed - User: {full_name}, Passport: {passport}, Telegram ID: {telegram_id}, Conversation: {conversation.id}")
        except Exception as e:
            logger.error(f"Error logging contract completion: {e}")

    def get_current_date(self):
        """Get current date in Russian format"""
        months = {
            1: "января", 2: "февраля", 3: "марта", 4: "апреля",
            5: "мая", 6: "июня", 7: "июля", 8: "августа",
            9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
        }
        now = datetime.now()
        return f"{now.day} {months[now.month]} {now.year} года"

    def run(self):
        """Run the contract bot"""
        logger.info("Zefir Contract Bot is starting...")
        try:
            self.bot.infinity_polling()
        except Exception as e:
            logger.error(f"Error in contract bot: {e}")


def init_telegram_bot(app, db, TelegramUser, Conversation, Message):
    """Initialize the Telegram bot with your existing Flask app and models"""
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        return None

    return ZefirContractBot(db, bot_token, TelegramUser, Conversation, Message)


# Telegram Bot Functions
def create_keyboard():
    return None


def get_or_create_conversation(telegram_user_id):
    """Get existing open conversation or create new one"""
    conversation = Conversation.query.filter_by(
        telegram_user_id=telegram_user_id,
        status='open'
    ).first()

    if not conversation:
        conversation = Conversation.query.filter_by(
            telegram_user_id=telegram_user_id,
            status='assigned'
        ).first()

    if not conversation:
        conversation = Conversation(
            telegram_user_id=telegram_user_id,
            title="New Conversation",
            status='open'
        )
        db.session.add(conversation)
        db.session.commit()

    return conversation


def generate_ai_response(user_message, conversation_id):
    try:
        user_message_lower = user_message.lower()

        if any(word in user_message_lower for word in ['hello', 'hi', 'hey']):
            return "Hello! I'm an AI assistant. How can I help you today?"

        elif 'help' in user_message_lower:
            return "I'm here to assist you! Please describe your issue and I'll connect you with a human agent if needed."

        elif any(word in user_message_lower for word in ['price', 'cost', 'how much']):
            return "Our pricing varies based on your needs. I can connect you with a sales agent for detailed pricing information."

        elif any(word in user_message_lower for word in ['thank', 'thanks']):
            return "You're welcome! Is there anything else I can help you with?"

        elif any(word in user_message_lower for word in ['bye', 'goodbye']):
            return "Goodbye! Feel free to reach out if you need more assistance."

        else:
            return "Thank you for your message. I've forwarded it to our support team. An agent will respond shortly. In the meantime, is there any other information I can provide?"

    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        return "I understand you're looking for assistance. Our team will get back to you shortly."


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
            prefix = "" if is_agent else ""
            bot.send_message(tg_user.telegram_id, f"{prefix}{message}")
            logger.info(f"Message sent to user {tg_user.telegram_id}")
    except Exception as e:
        logger.error(f"Error sending message to user {telegram_user_id}: {e}")


# Telegram Bot Handlers
@bot.message_handler(commands=['start', 'help'])
def start_command(message):
    try:
        logger.info(f"Received /start from user {message.from_user.id}")

        with app.app_context():
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
                db.session.commit()
                logger.info(f"New Telegram user registered: {message.from_user.first_name}")
            else:
                logger.info(f"Existing user: {tg_user.first_name}")

        welcome_text = """
🤖 Welcome to CRM Support Bot!
We will reach out shortly!
        """

        bot.send_message(message.chat.id, welcome_text)
        logger.info(f"Welcome message sent to {message.from_user.first_name}")

    except Exception as e:
        logger.error(f"Error in start_command: {str(e)}", exc_info=True)


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        logger.info(f"Processing message from {message.from_user.id}: {message.text}")

        with app.app_context():
            tg_user = TelegramUser.query.filter_by(telegram_id=message.from_user.id).first()
            if not tg_user:
                logger.warning(f"User {message.from_user.id} not found, sending /start instruction")
                bot.send_message(message.chat.id, "Please use /start to begin.")
                return

            logger.info(f"Found user: {tg_user.first_name}")
            conversation = get_or_create_conversation(tg_user.id)
            logger.info(f"Using conversation: {conversation.id}")

            user_message = Message(
                conversation_id=conversation.id,
                sender_type='user',
                sender_id=tg_user.id,
                content=message.text
            )
            db.session.add(user_message)
            conversation.updated_at = datetime.utcnow()
            db.session.commit()
            logger.info(f"Message saved to database")

        ai_response = generate_ai_response(message.text, conversation.id)
        logger.info(f"AI response: {ai_response}")

        if ai_response:
            with app.app_context():
                ai_message = Message(
                    conversation_id=conversation.id,
                    sender_type='ai',
                    sender_id=None,
                    content=ai_response,
                    is_ai_response=True
                )
                db.session.add(ai_message)
                db.session.commit()
                logger.info("AI response saved to database")

            bot.send_message(message.chat.id, ai_response)
            logger.info("AI response sent to user")

        notify_agents(conversation.id, message.text, tg_user)
        logger.info("Agents notified")

    except Exception as e:
        logger.error(f"Error handling message: {str(e)}", exc_info=True)


def start_bot():
    try:
        logger.info("Starting main Telegram bot...")
        bot_info = bot.get_me()
        logger.info(f"✅ Main Bot connected: @{bot_info.username}")
        bot.infinity_polling()
        logging.getLogger('werkzeug').disabled = False
    except Exception as e:
        logger.error(f"Error starting main bot: {e}")


def start_contract_bot():
    try:
        contract_bot = init_telegram_bot(app, db, TelegramUser, Conversation, Message)
        if contract_bot:
            logger.info("Starting Contract Bot...")
            contract_bot.run()
    except Exception as e:
        logger.error(f"Error starting contract bot: {e}")


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

        if User.query.filter_by(username=username).first():
            return render_template_string(REGISTER_HTML, error='Username already exists')

        user = User(username=username, email=email, is_agent=is_agent)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for('dashboard'))

    return render_template_string(REGISTER_HTML)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_agent:
        conversations = Conversation.query.filter(
            (Conversation.assigned_agent_id == current_user.id) |
            (Conversation.assigned_agent_id.is_(None))
        ).order_by(Conversation.updated_at.desc()).all()
    else:
        conversations = Conversation.query.filter_by(assigned_agent_id=current_user.id).order_by(
            Conversation.updated_at.desc()).all()

    return render_template_string(DASHBOARD_HTML, conversations=conversations)


@app.route('/admin')
@login_required
def admin_dashboard():
    """Admin dashboard with statistics"""
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
    """User management page"""
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
    """View all conversations for a specific Telegram user"""
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
    """Add new agent"""
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
    """Delete agent"""
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
    """Search Telegram users"""
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

    # Start both bots in separate threads
    logger.info("Starting Telegram bots...")

    # Start main bot
    main_bot_thread = threading.Thread(target=start_bot, daemon=True)
    main_bot_thread.start()

    # Start contract bot
    contract_bot_thread = threading.Thread(target=start_contract_bot, daemon=True)
    # contract_bot_thread.start()

    logger.info("✅ Both bots started successfully!")
    logger.info("\nPress Ctrl+C to stop")

    logging.getLogger('werkzeug').disabled = False
    # Keep main thread alive
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == '__main__':
    main()