import os


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-change-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True

    ML_CLIENT_ID = os.getenv('ML_CLIENT_ID', '3509386763056859')
    ML_CLIENT_SECRET = os.getenv('ML_CLIENT_SECRET', '')
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
    FERNET_KEY = os.getenv('FERNET_KEY', '')
    MP_ACCESS_TOKEN = os.getenv('MP_ACCESS_TOKEN', '')
    MP_PUBLIC_KEY = os.getenv('MP_PUBLIC_KEY', '')


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///dev.db')


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


class StagingConfig(ProductionConfig):
    pass


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'staging': StagingConfig,
    'default': DevelopmentConfig,
}
