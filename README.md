# CRM BOT DKISEL

A comprehensive Customer Relationship Management (CRM) system built with Flask and Telegram Bot API that enables businesses to manage customer conversations, automate responses, and handle contract agreements through Telegram.

[![Build Windows EXE](https://github.com/DANILKISEL/bot-CRM/actions/workflows/build-windows.yaml/badge.svg)](https://github.com/DANILKISEL/bot-CRM/actions/workflows/build-windows.yaml)
[![Crate macOS App](https://github.com/DANILKISEL/bot-CRM/actions/workflows/build-macos.yaml/badge.svg)](https://github.com/DANILKISEL/bot-CRM/actions/workflows/build-macos.yaml)
![Python](https://img.shields.io/badge/python-3.8%2B-green)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-blue)


## 🌟 Features

### 🤖 Telegram Bot Integration
- **Multi-language support** for customer interactions
- **Contract agreement process** with automated workflow
- **Pricing information** display with structured cards
- **AI-powered responses** for common queries
- **Session management** for multi-step processes

### 💼 CRM Dashboard
- **Real-time conversation management**
- **Agent assignment system**
- **Message history tracking**
- **User management interface**
- **Admin dashboard with statistics**

### 🔐 Authentication & Security
- **User authentication** with Flask-Login
- **Role-based access control** (Agents vs Regular Users)
- **Secure password hashing**
- **Session management**

### 📊 Analytics & Management
- **User statistics** and activity tracking
- **Conversation metrics**
- **Agent performance monitoring**
- **Search and filtering capabilities**

## 🚀 Quick Start

### Download Latest Release

Visit the [Releases page](https://github.com/DANILKISEL/bot-CRM/releases) to download the latest pre-built versions:

- **Windows**: `CRM-Bot-Setup.exe` (Installer) or `CRM-Bot.exe` (Portable)
- **macOS**: `CRM-Bot.app` (Application bundle)


### Prerequisites
- **Windows**: Windows 10 or newer
- **macOS**: macOS 10.14 or newer  

- **Telegram Bot Token** ([Get one from @BotFather](https://t.me/BotFather))

### Installation

#### Windows (.exe)
1. Download `CRM-Bot-Setup.exe` from [releases](https://github.com/DANILKISEL/bot-CRM/releases)
2. Run the installer and follow the setup wizard
3. Launch CRM Bot from Start Menu or Desktop
4. Configure your environment variables in the settings

#### macOS (.app)
1. Download `CRM-Bot.app.zip` from [releases](https://github.com/DANILKISEL/bot-CRM/releases)
2. Extract and move to Applications folder
3. Right-click and select "Open" (may require bypassing Gatekeeper first)
4. Configure your bot token in the application settings


### Manual Configuration

After installation, create a `.env` file in the application directory:

```env
SECRET_KEY=your-secret-key-here
TELEGRAM_BOT_TOKEN=your-telegram-bot-token-from-botfather
DATABASE_URL=sqlite:///crm_bot.db
```

## 🏗️ Build from Source

### Prerequisites
- Python 3.8+
- Git
- PostgreSQL or SQLite

### Development Setup

1. **Clone the repository**
```bash
git clone https://github.com/DANILKISEL/bot-CRM.git
cd bot-CRM
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Run the application**
```bash
python app.py
```

### GitHub Actions Build

The project automatically builds executables for all platforms using GitHub Actions:

- **Windows EXE**: Built on every push to main branch
- **macOS App**: Built on every release
- **Automatic Releases**: Pre-built binaries available in Releases

## 📱 Usage

### First Run Setup

1. **Start the application**
2. **Access the web interface** at `http://localhost:2000`
3. **Login with default credentials**:
   - Username: `admin`
   - Password: `admin123`
4. **Configure your Telegram Bot Token** in admin settings
5. **Start chatting** with your bot on Telegram

### Telegram Bot Commands
- `/start` - Welcome message and bot introduction
- `/help` - Get assistance information
- `/contract` - Start contract agreement process
- `/pricing` - View service pricing cards

### Web Dashboard Access
- **Main Dashboard**: http://localhost:2000
- **Admin Panel**: http://localhost:2000/admin
- **User Management**: http://localhost:2000/user-management

## 🏗️ System Architecture

### Database Models
- **User**: System users (agents and administrators)
- **TelegramUser**: Telegram bot users
- **Conversation**: Chat conversations between users and agents
- **Message**: Individual messages within conversations

### Key Components
- **Flask Application**: Web interface and API
- **Telegram Bot**: Customer interaction handler
- **CRM System**: Conversation and user management
- **Authentication System**: Secure access control

## 🔧 Configuration

### Environment Variables
```env
SECRET_KEY=your-flask-secret-key
TELEGRAM_BOT_TOKEN=your-bot-token-from-botfather
DATABASE_URL=sqlite:///crm_bot.db  # or PostgreSQL URL
```

### Bot Configuration
The bot handles:
- Customer inquiries and automated responses
- Contract agreement workflows
- Pricing information delivery
- Multi-step form processing

## 📊 API Endpoints

### Authentication
- `POST /login` - User authentication
- `POST /register` - User registration
- `POST /logout` - User logout

### Conversation Management
- `GET /dashboard` - Conversation dashboard
- `GET /conversation/<id>` - Individual conversation
- `POST /send_message` - Send message to conversation
- `POST /ai_response` - AI-generated responses

### User Management
- `GET /admin` - Admin dashboard
- `GET /user-management` - User management interface
- `POST /add-agent` - Create new agent
- `POST /delete-agent` - Remove agent

## 🛠️ Development

### Project Structure
```
bot-CRM/
├── app.py                 # Main application file
├── models.py             # Database models
├── templates/            # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   └── chat.html
├── .github/
│   └── workflows/        # GitHub Actions
│       ├── build-windows.yaml
│       └── build-macos.yaml
└── requirements.txt     # Python dependencies
```

### Building Executables

The GitHub Actions workflows automatically build:

- **Windows**: Uses PyInstaller to create standalone EXE
- **macOS**: Creates application bundle with proper signing
- **Automatic deployment** to GitHub Releases

## 🔒 Security Features

- Password hashing with Werkzeug
- Session-based authentication
- Role-based access control
- SQL injection prevention
- XSS protection through template escaping

## 📊 Monitoring & Logging

Comprehensive logging system tracks:
- User authentication events
- Conversation activities
- Bot interactions
- System errors and exceptions

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 License

This project is proprietary software. All rights reserved.

## 🆘 Support

For technical support or questions:
1. Check the application logs
2. Verify environment configuration
3. Ensure Telegram bot token is valid
4. Confirm database connectivity

---

**Built with ❤️ using Flask and Telegram Bot API**

*Automatically built for Windows and macOS via GitHub Actions*