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


@click.command('create-admin')
@click.option('--email', required=True, help='Email del usuario admin a crear.')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True,
              help='Contraseña (si se omite se pide de forma interactiva y oculta).')
@click.option('--nickname', default='Admin', show_default=True, help='Nombre visible del usuario.')
@with_appcontext
def create_admin_command(email, password, nickname):
    """Crea (o promueve) un usuario admin de prueba con el email/contraseña dados."""
    from app.models import User
    from app.extensions import bcrypt

    email = email.strip().lower()
    pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    user = User.query.filter_by(email=email).first()
    if user:
        # Ya existe: le fijamos contraseña, lo hacemos admin y lo reactivamos.
        user.password_hash = pw_hash
        user.is_admin = True
        user.is_active = True
        db.session.commit()
        click.echo(f"Usuario existente actualizado: {email} (ahora es admin, contraseña restablecida).")
        return

    user = User(
        email=email,
        password_hash=pw_hash,
        nickname=nickname,
        is_admin=True,
        is_active=True,
    )
    db.session.add(user)
    db.session.commit()
    click.echo(f"Usuario admin creado: {email}")


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
