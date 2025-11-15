#!/bin/bash

echo "🚀 Building Windows EXE using Docker"
echo "===================================="

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not installed"
    echo "Install Docker from https://docker.com"
    exit 1
fi

# Create Dockerfile for Windows build
cat > Dockerfile.windows << 'DOCKERFILE'
FROM python:3.10-windowsservercore

WORKDIR /app
COPY . .

RUN pip install pyinstaller flask flask-sqlalchemy flask-login pytelegrambotapi python-dotenv requests

# Create launcher
COPY << 'EOF' /app/windows_launcher.py
import sys
import os
import threading
import webbrowser
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("Starting CRM Telegram Bot...")
    print("Server: http://127.0.0.1:2000")
    print("Login: admin / admin123")
    print("Press Ctrl+C to stop\\n")

    def open_browser():
        time.sleep(3)
        webbrowser.open('http://127.0.0.1:2000')

    threading.Thread(target=open_browser, daemon=True).start()

    from crm_zefir_bot import main as bot_main
    bot_main()

if __name__ == '__main__':
    main()
EOF

RUN pyinstaller --onefile --console --name CRMTelegramBot ^
    --hidden-import=flask ^
    --hidden-import=flask_sqlalchemy ^
    --hidden-import=flask_login ^
    --hidden-import=telebot ^
    --hidden-import=python_dotenv ^
    --hidden-import=sqlalchemy ^
    --add-data "crm_zefir_bot.py;." ^
    --add-data ".env;." ^
    windows_launcher.py

CMD ["cmd", "/c", "dir dist"]
DOCKERFILE

# Copy and rename main file
cp crm-zefir-bot.py crm_zefir_bot.py

echo "📦 Building Windows EXE in Docker (this will take a while)..."
docker build -f Dockerfile.windows -t crm-bot-builder .

# Create output directory
mkdir -p dist-windows

# Extract the EXE from container
docker create --name crm-bot-extract crm-bot-builder
docker cp crm-bot-extract:/app/dist/CRMTelegramBot.exe ./dist-windows/
docker rm crm-bot-extract

# Cleanup
rm -f Dockerfile.windows
rm -f crm_zefir_bot.py

echo "✅ Windows EXE built: dist-windows/CRMTelegramBot.exe"
echo ""
echo "💡 This EXE will work on any Windows machine!"
echo ""