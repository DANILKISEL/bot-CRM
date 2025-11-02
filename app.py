from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, TelegramUser, Conversation, Message
from telegram_bot import broadcast_to_agents
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///crm_bot.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


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
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))

    return render_template('login.html')


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
            return "Username already exists"

        user = User(username=username, email=email, is_agent=is_agent)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for('dashboard'))

    return render_template('register.html')


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
        ).all()
    else:
        conversations = Conversation.query.filter_by(assigned_agent_id=current_user.id).all()

    return render_template('dashboard.html', conversations=conversations)


@app.route('/conversation/<int:conversation_id>')
@login_required
def conversation(conversation_id):
    conv = Conversation.query.get_or_404(conversation_id)

    # Check if user has access to this conversation
    if not current_user.is_agent and conv.assigned_agent_id != current_user.id:
        return "Access denied", 403

    # If agent and conversation not assigned, assign it
    if current_user.is_agent and not conv.assigned_agent_id:
        conv.assigned_agent_id = current_user.id
        conv.status = 'assigned'
        db.session.commit()

    messages = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.timestamp).all()
    return render_template('chat.html', conversation=conv, messages=messages)


@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    conversation_id = request.json.get('conversation_id')
    content = request.json.get('content')

    conv = Conversation.query.get_or_404(conversation_id)

    # Create message
    message = Message(
        conversation_id=conversation_id,
        sender_type='agent',
        sender_id=current_user.id,
        content=content
    )
    db.session.add(message)
    db.session.commit()

    # Broadcast to Telegram bot (you'll need to implement this)
    broadcast_to_agents(conv.telegram_user_id, content, is_agent=True)

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
    """Endpoint for AI agent to send responses"""
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


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)