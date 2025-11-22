import functools
from flask import render_template_string
from flask_login import login_required, current_user
from config import Config

ERROR_HTML = '''
{% extends "base.html" %}
{% block content %}
<div class="error-container" style="text-align: center; padding: 2rem;">
    <h2>Error</h2>
    <p>{{ error }}</p>
    <a href="{{ url_for('dashboard') }}" class="btn btn-primary">Return to Dashboard</a>
</div>
{% endblock %}
'''

def role_required(required_role):
    """Decorator to check if user has required role"""
    def decorator(f):
        @functools.wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role_level < required_role:
                return render_template_string(ERROR_HTML, error='Access denied'), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator