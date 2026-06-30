from app.extensions import db
from flask_login import UserMixin
from datetime import datetime


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    nickname = db.Column(db.String(100))
    ml_user_id = db.Column(db.BigInteger, unique=True)
    ml_access_token = db.Column(db.Text)
    ml_refresh_token = db.Column(db.Text)
    ml_token_expires_at = db.Column(db.DateTime)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    credit_transactions = db.relationship('CreditTransaction', backref='user', lazy='dynamic')
    publications = db.relationship('Publication', backref='user', lazy='dynamic')


class CreditPackage(db.Model):
    __tablename__ = 'credit_packages'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    credits = db.Column(db.Integer, nullable=False)
    price_mxn = db.Column(db.Numeric(10, 2), nullable=False)
    is_active = db.Column(db.Boolean, default=True)


class CreditTransaction(db.Model):
    __tablename__ = 'credit_transactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    package_id = db.Column(db.Integer, db.ForeignKey('credit_packages.id'))
    credits = db.Column(db.Integer, nullable=False)
    amount_mxn = db.Column(db.Numeric(10, 2), default=0)
    mp_payment_id = db.Column(db.String(100))
    mp_status = db.Column(db.String(50))
    expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Publication(db.Model):
    __tablename__ = 'publications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    source_mlm = db.Column(db.String(20))
    new_mlm = db.Column(db.String(20))
    title = db.Column(db.String(100))
    category_id = db.Column(db.String(20))
    price = db.Column(db.Numeric(12, 2))
    status = db.Column(db.String(20), default='draft')
    credits_used = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
