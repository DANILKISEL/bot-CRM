#!/bin/bash

# CRM Telegram Bot .app Builder Script
set -e  # Exit on error

echo "
🚀 CRM Telegram Bot .app Builder
================================
"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}📦 $1${NC}"
}

# Check if we're on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    print_error "This script only works on macOS!"
    exit 1
fi
print_status "Running on macOS"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    print_error "Python3 is not installed!"
    exit 1
fi
print_status "Python3 found"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    print_error "pip3 is not installed!"
    exit 1
fi
print_status "pip3 found"

# Check if main file exists
if [ ! -f "crm-zefir-bot.py" ]; then
    print_error "Main file 'crm-zefir-bot.py' not found!"
    exit 1
fi
print_status "Main file found"

# Check if .env exists
if [ ! -f ".env" ]; then
    print_warning ".env file not found! Make sure to create one with TELEGRAM_BOT_TOKEN"
else
    print_status ".env file found"
fi

# Install/check dependencies
print_info "Checking dependencies..."

install_package() {
    if pip3 show "$1" &> /dev/null; then
        print_status "$1 already installed"
    else
        print_info "Installing $1..."
        pip3 install "$1"
    fi
}

# Install required packages
install_package pyinstaller
install_package flask
install_package flask-sqlalchemy
install_package flask-login
install_package pytelegrambotapi
install_package python-dotenv
install_package pywebview
install_package requests

print_status "All dependencies installed"

# Create launcher script
print_info "Creating launcher script..."

cat > launcher.py << 'EOF'
import webview
import threading
import time
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_flask():
    """Run Flask app in a separate thread"""
    try:
        # Import and run your main application
        from crm_zefir_bot import app, main

        # Run the main function which starts Flask and the bot
        main()
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("🚀 Starting CRM Telegram Bot...")

    # Start Flask server in a separate thread
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()

    # Wait for server to start
    time.sleep(5)

    print("✅ Opening web interface...")

    # Create GUI window that opens the dashboard
    try:
        webview.create_window(
            'CRM Telegram Bot',
            'http://127.0.0.1:2000',
            width=1200,
            height=800,
            min_size=(800, 600)
        )
        webview.start()
    except Exception as e:
        print(f"Error creating window: {e}")
        input("Press Enter to exit...")
EOF

print_status "Launcher script created"

# Create copy of main file with proper name
print_info "Creating main file copy..."
cp crm-zefir-bot.py crm_zefir_bot.py
print_status "Main file copy created"

# Create PyInstaller spec file
print_info "Creating PyInstaller spec file..."

cat > crm_bot.spec << 'EOF'
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('crm_zefir_bot.py', '.'),
        ('.env', '.'),
    ],
    hiddenimports=[
        'flask',
        'flask_sqlalchemy',
        'flask_login',
        'flask.wrappers',
        'werkzeug.security',
        'telebot',
        'python_dotenv',
        'sqlalchemy',
        'sqlalchemy.orm',
        'sqlalchemy.ext',
        'sqlalchemy.sql.default_comparator',
        'datetime',
        'threading',
        'logging',
        'os',
        'sys',
        'json',
        'requests',
        'webview',
        'jinja2',
        'markupsafe',
        'itsdangerous'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name='CRM Telegram Bot Server.app',
    icon=None,
    bundle_identifier='com.yourcompany.crmtelegrambot',
    info_plist={
        'CFBundleName': 'CRMTelegramBot',
        'CFBundleDisplayName': 'CRM Telegram Bot',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleExecutable': 'launcher',
        'CFBundleDevelopmentRegion': 'en',
        'CFBundlePackageType': 'APPL',
        'NSHighResolutionCapable': 'True',
        'LSMinimumSystemVersion': '10.13',
    },
)
EOF

print_status "Spec file created"

# Build the application
print_info "Building .app bundle with PyInstaller..."

if python3 -m PyInstaller crm_bot.spec --clean --noconfirm; then
    print_status "Build successful!"
else
    print_error "Build failed!"
    exit 1
fi

# Verify the build
print_info "Verifying build..."

if [ -d "dist/CRMTelegramBot.app" ]; then
    print_status ".app bundle created at: dist/CRMTelegramBot.app"

    # Check important files
    if [ -f "dist/CRMTelegramBot.app/Contents/MacOS/launcher" ]; then
        print_status "Executable found"
    else
        print_error "Executable missing!"
    fi

    if [ -f "dist/CRMTelegramBot.app/Contents/Info.plist" ]; then
        print_status "Info.plist found"
    else
        print_error "Info.plist missing!"
    fi

else
    print_error ".app bundle not found in dist/ directory!"
    exit 1
fi

# Create DMG if requested
read -p "Create DMG for distribution? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Creating DMG file..."

    # Check if create-dmg is installed
    if command -v create-dmg &> /dev/null; then
        if create-dmg \
            --volname "CRM Telegram Bot" \
            --window-pos 200 120 \
            --window-size 800 400 \
            --icon-size 100 \
            --icon "CRMTelegramBot.app" 200 190 \
            --hide-extension "CRMTelegramBot.app" \
            --app-drop-link 600 185 \
            "CRMTelegramBot.dmg" \
            "dist/CRMTelegramBot.app" 2>/dev/null; then

            print_status "DMG file created: CRMTelegramBot.dmg"
        else
            print_warning "Failed to create DMG. You can install create-dmg with: brew install create-dmg"
        fi
    else
        print_warning "create-dmg not installed. Install with: brew install create-dmg"
    fi
fi

# Cleanup
read -p "Clean up temporary build files? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Cleaning up temporary files..."

    # Remove temporary files
    rm -f launcher.py
    rm -f crm_zefir_bot.py
    rm -f crm_bot.spec
    rm -rf build-shell

    print_status "Temporary files cleaned up"
else
    print_info "Temporary files kept: launcher.py, crm_zefir_bot.py, crm_bot.spec, build/"
fi

print_status "Build completed successfully!"
echo ""
echo "🎉 Your CRM Telegram Bot.app is ready!"
echo ""
echo "📋 Next steps:"
echo "   1. Test the app: open 'dist/CRMTelegramBot.app'"
echo "   2. Make sure your .env file has TELEGRAM_BOT_TOKEN"
echo "   3. Default login: admin / admin123"
echo "   4. Web interface: http://127.0.0.1:2000"
echo ""
echo "⚠️  Important: The .app bundle includes your .env file"
echo "   Make sure it doesn't contain sensitive data before distribution!"
echo ""