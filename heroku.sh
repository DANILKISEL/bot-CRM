#!/bin/bash

# Heroku Flask CRM - Complete Deployment Script
set -e  # Exit on any error

echo "🚀 Building and Deploying Flask CRM from Scratch..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
APP_NAME=""
CRM_MAIN_FILE="app.py"  # Change this if your main file has different name
CRM_DIRECTORY="."        # Change this if your app is in subdirectory

# Detect project structure
detect_structure() {
    print_status "Detecting project structure..."

    # Find main Python file
    if [[ -f "app.py" ]]; then
        CRM_MAIN_FILE="app.py"
    elif [[ -f "main.py" ]]; then
        CRM_MAIN_FILE="main.py"
    elif [[ -f "run.py" ]]; then
        CRM_MAIN_FILE="run.py"
    else
        # Find first Python file that contains Flask app
        for file in *.py; do
            if [[ -f "$file" ]] && grep -q "Flask\|app = Flask" "$file"; then
                CRM_MAIN_FILE="$file"
                break
            fi
        done
    fi

    if [[ -z "$CRM_MAIN_FILE" ]]; then
        print_error "No Flask app found! Looking for files containing 'Flask' or 'app = Flask'"
        find . -name "*.py" -exec grep -l "Flask\|app = Flask" {} \; || true
        exit 1
    fi

    print_status "Detected main file: $CRM_MAIN_FILE"

    # Extract app name from main file
    APP_VAR=$(grep -h "app.*=.*Flask" "$CRM_MAIN_FILE" | head -1 | sed -E 's/^(.*) = Flask.*$/\1/')
    if [[ -n "$APP_VAR" ]]; then
        print_status "Detected Flask app variable: $APP_VAR"
    else
        APP_VAR="app"
        print_warning "Using default app variable: 'app'"
    fi
}

# Create necessary deployment files
create_deployment_files() {
    print_status "Creating deployment files..."

    # 1. Create runtime.txt
    echo "python-3.10.12" > runtime.txt
    print_status "Created runtime.txt with Python 3.10.12"

    # 2. Create Procfile
    echo "web: gunicorn ${CRM_MAIN_FILE%.*}:$APP_VAR" > Procfile
    print_status "Created Procfile with: web: gunicorn ${CRM_MAIN_FILE%.*}:$APP_VAR"

    # 3. Create/update requirements.txt
    create_requirements_file

    # 4. Create .gitignore if not exists
    if [[ ! -f ".gitignore" ]]; then
        cat > .gitignore << EOF
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/
pip-log.txt
pip-delete-this-directory.txt
.tox
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.log
.git
.mypy_cache/
.dmypy.json
dmypy.json
.pytest_cache/
instance/
.webassets-cache
.scrapy
docs/_build/
target/
.ipynb_checkpoints
*.sqlite3
*.db
.DS_Store
Thumbs.db
EOF
        print_status "Created .gitignore file"
    fi
}

# Create requirements.txt
create_requirements_file() {
    print_status "Creating requirements.txt..."

    # Base requirements for Flask deployment
    cat > requirements.txt << EOF
Flask==2.3.3
gunicorn==21.2.0
Werkzeug==2.3.7
EOF

    # Detect and add additional requirements
    detect_dependencies

    print_status "Created requirements.txt with detected dependencies"
}

# Detect Python dependencies
detect_dependencies() {
    print_status "Scanning for dependencies..."

    # Common CRM dependencies
    common_deps=("sqlalchemy" "flask-sqlalchemy" "psycopg2" "psycopg2-binary"
                 "flask-login" "flask-wtf" "wtforms" "flask-mail" "flask-admin"
                 "email-validator" "bcrypt" "passlib" "pillow" "requests")

    # Scan Python files for imports
    for dep in "${common_deps[@]}"; do
        import_name=${dep//-/_}
        if find . -name "*.py" -exec grep -l "import $import_name\|from $import_name" {} \; | grep -q "."; then
            echo "$dep==$(get_latest_version "$dep")" >> requirements.txt
            print_status "Added dependency: $dep"
        fi
    done

    # Check for specific files that indicate dependencies
    if find . -name "requirements.txt" | grep -q "."; then
        print_warning "Found existing requirements.txt - please review auto-generated file"
    fi

    # Add database driver if SQLAlchemy is detected
    if grep -q "sqlalchemy\|SQLAlchemy" requirements.txt; then
        echo "psycopg2-binary==2.9.7" >> requirements.txt
        print_status "Added PostgreSQL driver for SQLAlchemy"
    fi
}

# Get latest version from PyPI (fallback)
get_latest_version() {
    local package=$1
    case $package in
        "flask") echo "2.3.3" ;;
        "flask-sqlalchemy") echo "3.0.5" ;;
        "sqlalchemy") echo "2.0.23" ;;
        "psycopg2-binary") echo "2.9.7" ;;
        "flask-login") echo "0.6.3" ;;
        "flask-wtf") echo "1.1.1" ;;
        "wtforms") echo "3.0.1" ;;
        "flask-mail") echo "0.9.1" ;;
        "flask-admin") echo "1.6.1" ;;
        "email-validator") echo "2.0.0" ;;
        "bcrypt") echo "4.0.1" ;;
        "passlib") echo "1.7.4" ;;
        "pillow") echo "10.0.1" ;;
        "requests") echo "2.31.0" ;;
        *) echo "" ;;
    esac
}

# Verify Flask app structure
verify_flask_app() {
    print_status "Verifying Flask application..."

    if ! grep -q "Flask\|app.*=.*Flask" "$CRM_MAIN_FILE"; then
        print_error "No Flask app found in $CRM_MAIN_FILE!"
        print_error "Please ensure your main file contains: app = Flask(__name__)"
        exit 1
    fi

    # Check if app runs in production mode
    if ! grep -q "0.0.0.0\|PORT" "$CRM_MAIN_FILE"; then
        print_warning "Consider adding Heroku PORT support to your app:"
        print_warning "port = int(os.environ.get('PORT', 5000))"
        print_warning "app.run(host='0.0.0.0', port=port)"
    fi

    print_status "Flask application verified!"
}

# Initialize Git repository
setup_git() {
    print_status "Setting up Git repository..."

    if [[ ! -d ".git" ]]; then
        git init
        print_status "Initialized Git repository"
    fi

    git add .
    git commit -m "Initial commit: Flask CRM deployment" || true
}

# Heroku deployment functions
check_heroku_cli() {
    if ! command -v heroku &> /dev/null; then
        print_error "Heroku CLI not installed!"
        echo "Install from: https://devcenter.heroku.com/articles/heroku-cli"
        exit 1
    fi
}

create_heroku_app() {
    local name=$1
    if [[ -z "$name" ]]; then
        print_status "Creating Heroku app with auto-generated name..."
        heroku create
    else
        print_status "Creating Heroku app: $name"
        heroku create "$name"
    fi

    # Get app name
    HEROKU_APP_NAME=$(heroku apps:info -j 2>/dev/null | python3 -c "import sys, json; print(json.load(sys.stdin)['app']['name'])" || echo "")
    print_status "Heroku app created: $HEROKU_APP_NAME"
}

setup_heroku_config() {
    print_status "Configuring Heroku environment..."

    # Add PostgreSQL database
    heroku addons:create heroku-postgresql:mini

    # Generate and set secret key
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    heroku config:set SECRET_KEY="$SECRET_KEY"
    heroku config:set FLASK_ENV=production

    print_status "Heroku configuration complete!"
}

deploy_to_heroku() {
    print_status "Deploying to Heroku..."

    # Add heroku remote if not exists
    if ! git remote | grep -q heroku; then
        heroku git:remote -a "$HEROKU_APP_NAME"
    fi

    # Deploy
    git push heroku main

    # If main fails, try master
    if [[ $? -ne 0 ]]; then
        print_warning "Main branch failed, trying master..."
        git push heroku master
    fi

    # Scale dyno
    heroku ps:scale web=1
}

post_deploy_checks() {
    print_status "Running post-deployment checks..."

    sleep 10  # Wait for app to start

    # Check app status
    heroku ps

    # Show app URL
    print_status "Your CRM is now live at: https://${HEROKU_APP_NAME}.herokuapp.com"

    # Open in browser
    read -p "Open in browser? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        heroku open
    fi
}

# Main deployment function
main() {
    print_status "Starting complete Flask CRM deployment..."

    # Get app name if provided
    if [[ $# -gt 0 ]]; then
        APP_NAME="$1"
    fi

    # Step 1: Detect project structure
    detect_structure

    # Step 2: Create deployment files
    create_deployment_files

    # Step 3: Verify Flask app
    verify_flask_app

    # Step 4: Setup Git
    setup_git

    # Step 5: Heroku deployment
    check_heroku_cli
    create_heroku_app "$APP_NAME"
    setup_heroku_config
    deploy_to_heroku
    post_deploy_checks

    print_status "🎉 Deployment completed successfully!"
    echo ""
    print_warning "Next steps:"
    echo "  1. Set up your database tables: heroku run python"
    echo "  2. Check logs: heroku logs --tail"
    echo "  3. Configure custom domain if needed"
    echo ""
}

# Quick deploy function
quick_deploy() {
    print_status "Quick deployment mode..."
    detect_structure
    create_deployment_files
    setup_git
    check_heroku_cli
    create_heroku_app "$1"
    git push heroku main || git push heroku master
    heroku ps:scale web=1
    heroku open
}

# Show usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  [app-name]    Deploy with specific Heroku app name"
    echo "  -q, --quick   Quick deployment (minimal prompts)"
    echo "  -h, --help    Show this help"
    echo ""
    echo "Examples:"
    echo "  $0                       # Interactive deployment"
    echo "  $0 my-crm-app           # Deploy to specific app name"
    echo "  $0 --quick              # Quick deployment"
}

# Parse arguments
if [[ $# -gt 0 ]]; then
    case $1 in
        -h|--help) usage; exit 0 ;;
        -q|--quick) quick_deploy "$2"; exit 0 ;;
        *) main "$1"; exit 0 ;;
    esac
else
    main
fi