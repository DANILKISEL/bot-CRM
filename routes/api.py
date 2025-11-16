import os
import sys
import time
import signal
import threading
import subprocess
from flask import jsonify, request
from flask_login import login_required, current_user
from utils.system_monitor import SystemMonitor
from utils.helpers import update_env_file

system_monitor = SystemMonitor()

def init_api_routes(app):
    @app.route('/api/status')
    @login_required
    def api_status():
        """API endpoint for system status monitoring"""
        if not current_user.is_agent:
            return jsonify({'error': 'Access denied'}), 403
        try:
            status_data = system_monitor.get_system_status()
            if 'error' in status_data:
                return jsonify({'error': status_data['error']}), 500
            return jsonify(status_data)
        except Exception as e:
            app.logger.error(f"Error in status endpoint: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/environment', methods=['GET', 'POST'])
    @login_required
    def api_environment():
        """Get or update environment variables"""
        if not current_user.is_agent:
            return jsonify({'error': 'Access denied'}), 403
        if request.method == 'GET':
            env_vars = {
                'DATABASE_URL': os.getenv('DATABASE_URL', 'sqlite:///crm_bot.db'),
                'FLASK_ENV': os.getenv('FLASK_ENV', 'production'),
                'TELEGRAM_BOT_TOKEN': '***' + os.getenv('TELEGRAM_BOT_TOKEN', '')[-4:] if os.getenv(
                    'TELEGRAM_BOT_TOKEN') else None,
                'SECRET_KEY': '***' + os.getenv('SECRET_KEY', '')[-4:] if os.getenv('SECRET_KEY') else None,
            }
            return jsonify(env_vars)
        elif request.method == 'POST':
            try:
                data = request.json
                updates = {}
                allowed_vars = ['DATABASE_URL', 'FLASK_ENV']
                for key, value in data.items():
                    if key in allowed_vars:
                        updates[key] = value
                if updates:
                    update_env_file(updates)
                    app.logger.warning(f"Environment variables updated by {current_user.username}: {list(updates.keys())}")
                    return jsonify({'success': True, 'message': 'Environment variables updated. Restart required.'})
                else:
                    return jsonify({'error': 'No valid environment variables to update'}), 400
            except Exception as e:
                app.logger.error(f"Error updating environment: {str(e)}")
                return jsonify({'error': str(e)}), 500

    @app.route('/api/restart', methods=['POST'])
    @login_required
    def api_restart():
        """Restart the application"""
        if not current_user.is_agent:
            return jsonify({'error': 'Access denied'}), 403

        try:
            app.logger.debug(f"Restart initiated by {current_user.username}")
            print("Restarting ...")

            def restart_app():
                time.sleep(2)
                try:
                    python = sys.executable
                    os.execv(python, [python] + sys.argv)
                except Exception as e:
                    print(f"execv failed: {e}, trying subprocess method")
                    try:
                        python = sys.executable
                        script_path = os.path.abspath(sys.argv[0])
                        env = os.environ.copy()
                        process = subprocess.Popen(
                            [python, script_path],
                            env=env,
                            cwd=os.getcwd()
                        )
                        print(f"New process started with PID: {process.pid}")
                        os._exit(0)
                    except Exception as e2:
                        print(f"Subprocess method also failed: {e2}")
                        os._exit(1)

            restart_thread = threading.Thread(target=restart_app)
            restart_thread.start()

            return jsonify({
                'success': True,
                'message': 'Restart initiated. System will restart shortly.'
            })

        except Exception as e:
            app.logger.error(f"Error during restart: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/shutdown', methods=['POST'])
    @login_required
    def api_shutdown():
        """Shutdown the application"""
        if not current_user.is_agent:
            return jsonify({'error': 'Access denied'}), 403

        try:
            app.logger.debug(f"Shutdown initiated by {current_user.username}")
            print("Shutting down...")

            def delayed_shutdown():
                time.sleep(2)
                os.kill(os.getpid(), signal.SIGINT)

            shutdown_thread = threading.Thread(target=delayed_shutdown, daemon=True)
            shutdown_thread.start()

            return jsonify({
                'success': True,
                'message': 'Shutdown initiated. System will stop shortly.'
            })

        except Exception as e:
            app.logger.error(f"Error during shutdown: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/system-monitor')
    @login_required
    def system_monitor():
        """System monitoring dashboard"""
        if not current_user.is_agent:
            return render_template("error.html", error='Access denied'), 403
        return render_template("system-monitor.html")