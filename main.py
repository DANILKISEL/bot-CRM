from threading import Thread
from app import app
from telegram_bot import start_bot
from models import db
from flask_migrate import Migrate

migrate = Migrate(app, db)

def run_flask():
    # You don't need to call create_all() if using migrations
    app.run(debug=True, port=5000, use_reloader=False)

def run_telegram_bot():
    start_bot()

if __name__ == '__main__':
    # Start Flask app in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    # Start Telegram bot in main thread
    bot_thread = Thread(target=run_telegram_bot)
    bot_thread.start()

    print("🤖 Bot started!")