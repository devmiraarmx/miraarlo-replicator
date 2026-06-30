from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
bcrypt = Bcrypt()
migrate = Migrate()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "60 per hour"])

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Inicia sesión para continuar.'
login_manager.login_message_category = 'warning'
