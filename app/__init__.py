import os
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

load_dotenv()


def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_prefix=1)

    from app.config import config
    app.config.from_object(config.get(config_name, config['default']))

    _init_extensions(app)
    _register_blueprints(app)

    return app


def _init_extensions(app):
    from app.extensions import db, login_manager, csrf, bcrypt, migrate, limiter

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))


def _register_blueprints(app):
    from app.editor import editor_bp
    from app.auth import auth_bp
    from app.billing import billing_bp
    from app.dashboard import dashboard_bp
    from app.admin import admin_bp

    app.register_blueprint(editor_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)
