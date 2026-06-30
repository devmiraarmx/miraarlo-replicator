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
    _register_cli(app)

    return app


_CSP = {
    'default-src': ["'self'"],
    'script-src': ["'self'", "'unsafe-inline'", "https://unpkg.com"],
    'style-src': ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
    'font-src': ["'self'", "https://fonts.gstatic.com"],
    'img-src': ["'self'", "data:", "https://*.mlstatic.com", "https://http2.mlstatic.com",
                "https://*.mercadolibre.com", "https://*.mercadolibre.com.mx"],
    'connect-src': ["'self'", "https://api.mercadolibre.com", "https://unpkg.com",
                    "https://www.mercadopago.com", "https://*.mercadopago.com"],
    'frame-src': ["https://www.mercadopago.com", "https://*.mercadopago.com"],
    'manifest-src': ["'self'"],
    'object-src': ["'none'"],
    'base-uri': ["'self'"],
}


def _init_extensions(app):
    from app.extensions import db, login_manager, csrf, bcrypt, migrate, limiter, talisman

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    is_prod = not app.debug
    talisman.init_app(
        app,
        force_https=is_prod,
        strict_transport_security=is_prod,
        strict_transport_security_max_age=31536000,
        strict_transport_security_include_subdomains=True,
        content_security_policy=_CSP,
        content_security_policy_nonce_in=[],
        referrer_policy='strict-origin-when-cross-origin',
        feature_policy={},
        session_cookie_secure=is_prod,
        frame_options='DENY',
        x_content_type_options=True,
        x_xss_protection=True,
    )

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))


def _register_cli(app):
    from app.cli import seed_db_command, generate_fernet_key_command
    app.cli.add_command(seed_db_command)
    app.cli.add_command(generate_fernet_key_command)


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
