import sys
import socket
import threading
import time
import telebot
from flask import Flask, render_template_string
from flask_login import LoginManager, current_user
from config import Config, setup_logging
from models import db, User, TelegramUser, Conversation, Message
from routes import init_all_routes
from utils.helpers import kill_process_on_port
from CRMclassbot import CRMTelegramBot

# Disable Flask CLI banner
cli = sys.modules['flask.cli']
cli.show_server_banner = lambda *x: None

# Initialize logging
logger = setup_logging()

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Initialize all routes
init_all_routes(app)

# Error template
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


def init_telegram_bot():
    """Initialize the single Telegram bot"""
    bot_token = app.config['BOT_TOKEN']
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        return None

    return CRMTelegramBot(app, db, bot_token, TelegramUser, Conversation, Message)


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


def run_flask():
    """Run Flask application"""
    socket.socket(socket.AF_INET, socket.SOCK_STREAM).setsockopt(
        socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
    )
    app.run(debug=False, port=2000, use_reloader=False)


def start_flask():
    """Start Flask in a separate thread"""
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("✅ Flask app running at http://localhost:2000")
    logger.debug("✅ Admin Dashboard available at http://localhost:2000/admin")


def start_bot_single():
    """Start the CRM Telegram Bot"""
    logger.info("Starting CRM Telegram Bot...")
    crm_bot = init_telegram_bot()
    if crm_bot:
        bot_thread = threading.Thread(target=crm_bot.run, daemon=True)
        bot_thread.start()
        logger.debug("✅ CRM Telegram Bot started successfully!")
    else:
        logger.error("❌ Failed to start CRM Telegram Bot")


def disable_verbose_loggers():
    """Disable verbose loggers"""
    import logging
    logging.getLogger('werkzeug').disabled = True
    logging.getLogger('CRM').disabled = True
    logging.getLogger('CRM CLASS BOT').disabled = True


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


def keep_alive():
    """Keep main thread alive"""
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")


def main():
    """Main application entry point"""
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