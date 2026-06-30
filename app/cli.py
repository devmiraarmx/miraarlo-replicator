import click
from flask import current_app
from flask.cli import with_appcontext
from app.extensions import db


@click.command('generate-fernet-key')
def generate_fernet_key_command():
    """Genera una clave Fernet nueva para FERNET_KEY en .env."""
    from app.utils.crypto import generate_fernet_key
    key = generate_fernet_key()
    click.echo(f"FERNET_KEY={key}")
    click.echo("\nCopia esta línea en tu archivo .env (en producción usa las vars de entorno de Render).")


@click.command('seed-db')
@with_appcontext
def seed_db_command():
    """Inserta datos iniciales: paquetes de créditos y usuario admin."""
    from app.models import CreditPackage, User
    from app.extensions import bcrypt

    # Paquetes de créditos
    packages = [
        {'name': 'trial',    'credits': 10,  'price_mxn': 0.00},
        {'name': 'starter',  'credits': 50,  'price_mxn': 299.00},
        {'name': 'pro',      'credits': 200, 'price_mxn': 799.00},
        {'name': 'business', 'credits': 500, 'price_mxn': 1499.00},
    ]

    inserted = 0
    for pkg_data in packages:
        exists = CreditPackage.query.filter_by(name=pkg_data['name']).first()
        if not exists:
            db.session.add(CreditPackage(**pkg_data))
            inserted += 1

    # Usuario admin por defecto (solo si no existe)
    admin_email = current_app.config.get('ADMIN_EMAIL', 'admin@publicadorzap.com')
    if not User.query.filter_by(email=admin_email).first():
        admin_pw = current_app.config.get('ADMIN_PASSWORD', 'changeme123')
        admin = User(
            email=admin_email,
            password_hash=bcrypt.generate_password_hash(admin_pw).decode('utf-8'),
            nickname='Admin',
            is_admin=True,
        )
        db.session.add(admin)
        click.echo(f"  Usuario admin creado: {admin_email} (cambia la contraseña en producción)")

    db.session.commit()
    click.echo(f"  {inserted} paquete(s) de créditos insertados.")
    click.echo("Seed completado.")
