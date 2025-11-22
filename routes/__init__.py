from .auth import init_auth_routes
from .admin import init_admin_routes
from .conversations import init_conversation_routes
from .users import init_user_routes
from .api import init_api_routes

def init_all_routes(app):
    init_auth_routes(app)
    init_admin_routes(app)
    init_conversation_routes(app)
    init_user_routes(app)
    init_api_routes(app)