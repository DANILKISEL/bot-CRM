import os
import logging
import sys
from dotenv import load_dotenv
import logging.config

# Load environment variables
load_dotenv()

class UnicodeSafeStreamHandler(logging.StreamHandler):
    """A stream handler that safely handles Unicode characters on Windows"""
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # For Windows console, encode with replace to avoid Unicode errors
            if sys.platform == "win32":
                msg = msg.encode('utf-8', 'replace').decode('utf-8')
            stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

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

    # Logging configuration with Unicode-safe handlers
    LOGGING_CONFIG = {
        'version': 1,
        'formatters': {
            'default': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            },
            'simple': {
                'format': '%(levelname)s - %(message)s'
            }
        },
        'handlers': {
            'file': {
                'class': 'logging.FileHandler',
                'filename': 'app.log',
                'formatter': 'default',
                'mode': 'a',
                'encoding': 'utf-8'
            },
            'console': {
                '()': UnicodeSafeStreamHandler,
                'formatter': 'simple',
                'stream': sys.stdout
            }
        },
        'root': {
            'level': 'INFO',
            'handlers': ['file', 'console']
        },
        'loggers': {
            'info-log': {
                'level': 'INFO',
                'handlers': ['file'],
                'propagate': False
            },

            'log': {
                'level': 'INFO',
                'handlers': ['file', 'console'],
                'propagate': False
            },
            'werkzeug': {
                'level': 'INFO',
                'handlers': ['file'],
                'propagate': False
            }
        }
    }

def setup_logging():
    """Configure application logging"""
    logging.config.dictConfig(Config.LOGGING_CONFIG)
    return logging.getLogger("info-log")