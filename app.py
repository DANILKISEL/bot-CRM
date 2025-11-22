import sys
import os
import threading
import time
from colorama import init, Fore
from pyfiglet import figlet_format
import logging

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_login import LoginManager
from config import Config, setup_logging
from models import db, User, TelegramUser, Conversation, Message
from routes import init_all_routes


# Disable Flask CLI banner
cli = sys.modules['flask.cli']
cli.show_server_banner = lambda *x: None

# Initialize colorama
init()

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

def init_telegram_bot():
    """Initialize the single Telegram bot"""
    from CRMclassbot import CRMTelegramBot
    bot_token = app.config['BOT_TOKEN']
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        return None

    return CRMTelegramBot(app, db, bot_token, TelegramUser, Conversation, Message)

def init_db():
    with app.app_context():
        try:
            db.create_all()
            logger.info("✅ Database initialized!")

            # Create default platform admin
            admin_user = User.query.filter_by(username='admin').first()
            if not admin_user:
                admin_user = User(
                    username='admin',
                    email='admin@crmbot.com',
                    role_level=Config.ROLES['PLATFORM_ADMIN']
                )
                admin_user.set_password('admin123')
                db.session.add(admin_user)
                db.session.commit()
                logger.info("✅ Default platform admin created: admin / admin123")

                verified_admin = User.query.filter_by(username='admin').first()
                if verified_admin:
                    logger.info(f"✅ Admin user verified: {verified_admin.username}, role_level: {verified_admin.role_level}")
                else:
                    logger.error("❌ Admin user creation failed!")
            else:
                logger.info("✅ Admin user already exists")

        except Exception as e:
            logger.error(f"❌ Error initializing database: {str(e)}")
            db.session.rollback()

def run_flask():
    app.run(debug=False, port=80, use_reloader=False, host='0.0.0.0')

def main():
    # Generate ASCII art banner
    banner = figlet_format("< <   C R M   B O T   > > ", font="big")
    print(Fore.CYAN + banner + Fore.RESET)

    print(Fore.CYAN + """
    _____           _              _                 _ _               _   
  / ____|         | |            | |               | | |             | |  
 | |  __  ___     | |_ ___       | | ___   ___ __ _| | |__   ___  ___| |_ 
 | | |_ |/ _ \    | __/ _ \      | |/ _ \ / __/ _` | | '_ \ / _ \/ __| __|
 | |__| | (_) |   | || (_) |     | | (_) | (_| (_| | | | | | (_) \__ \ |_ 
  \_____|\___/     \__\___/      |_|\___/ \___\__,_|_|_| |_|\___/|___/\__|
    """ + Fore.RESET)

    logging.getLogger('werkzeug').disabled = False
    logging.getLogger('CRM').disabled = False
    print(Fore.GREEN + "🚀 Starting CRM Bot System..." + Fore.RESET)

    # Initialize database
    init_db()

    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print(Fore.CYAN + "✅ Flask app running at http://localhost:80")
    print(" ✅ Admin Dashboard available at http://localhost:80/admin")
    print(" ✅ User Management available at http://localhost:80/user-management")
    print(" ✅ Conversation Management available at http://localhost:80/conversation-management")
    print("")
    print(" 🔐 Default Admin Login:")
    print("    Username: admin")
    print("    Password: admin123")
    print("")
    print(" 🐛 Debug Routes:")
    print("    http://localhost:80/debug/users - Check all users")
    print("    http://localhost:80/debug/conversations - Check all conversations")
    print(Fore.RESET)

    # Start the single bot
    logger.info("Starting CRM Telegram Bot...")
    crm_bot = init_telegram_bot()
    if crm_bot:
        bot_thread = threading.Thread(target=crm_bot.run, daemon=True)
        bot_thread.start()
        logger.info("✅ CRM Telegram Bot started successfully!")
    else:
        logger.error("❌ Failed to start CRM Telegram Bot")

    logger.info("✅ System started successfully!")
    logger.info("\nPress Ctrl+C to stop")

    # Show external IP
    ip = 0 #get_ip()
    if ip:
        print(Fore.YELLOW + f"🌐 External Access: http://{ip}:80" + Fore.RESET)
    else:
        print(Fore.YELLOW + "🌐 Could not determine external IP address" + Fore.RESET)

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")

if __name__ == '__main__':
    main()