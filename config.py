import os
import logging
from dotenv import load_dotenv
import logging.config


# Load environment variables
load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///crm_bot.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

    # Role definitions
    ROLES = {
        'AGENT': 1,
        'MANAGER': 2,
        'SYSTEM_ADMIN': 3,
        'PLATFORM_ADMIN': 4
    }

    import sys

    # Logging configuration with optional console output
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
                'formatter': 'default',
                'stream': sys.stdout
            }
        },
        'root': {
            'level': 'INFO',
            'handlers': ['file', 'console'] if sys.stdout.isatty() else ['file']
        }
    }

def setup_logging():
    """Configure application logging"""
    logging.config.dictConfig(Config.LOGGING_CONFIG)
    return logging.getLogger("CRM")