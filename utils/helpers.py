import os
import time
import subprocess
import telebot
from flask import current_app

# Use relative import for models
try:
    from ..models import TelegramUser
except ImportError:
    # Fallback for direct execution
    from models import TelegramUser

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

def broadcast_to_user(telegram_user_id, message, is_agent=False):
    """Send message to Telegram user with app context"""
    try:
        from app import app
        with app.app_context():
            tg_user = TelegramUser.query.get(telegram_user_id)
            if tg_user:
                prefix = ""  # "👨‍💼 Agent: " if is_agent else ""
                bot = telebot.TeleBot(current_app.config['BOT_TOKEN'])
                bot.send_message(tg_user.telegram_id, f"{prefix}{message}")
                current_app.logger.debug(f"Message sent to user {tg_user.telegram_id}")
    except Exception as e:
        current_app.logger.error(f"Error sending message to user {telegram_user_id}: {e}")

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