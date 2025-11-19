import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///crm_bot.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

    # Logging configuration
    LOGGING_CONFIG = {
        'version': 1,
        'formatters': {
            'default': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            }
        },
        'handlers': {
            'file': {
                'class': 'logging.FileHandler',
                'filename': 'app.log',
                'formatter': 'default',
                'mode': 'a'
            },
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'default'
            }
        },
        'root': {
            'level': 'DEBUG',
            'handlers': ['file', 'console']
        }
    }


def setup_logging():
    """Configure application logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename='app.log',
        filemode='a',
        encoding='utf-8'
    )
    return logging.getLogger("CRM")