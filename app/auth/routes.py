from datetime import datetime, timedelta
from flask import redirect, request, session, render_template, flash, url_for
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth_bp
from app.extensions import db, bcrypt


# ── Email + contraseña ──────────────────────────────────────────────────────

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    from app.auth.forms import RegisterForm
    from app.models import User, CreditTransaction, CreditPackage

    if current_user.is_authenticated:
        return redirect(url_for('editor.index'))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data.lower(),
            password_hash=bcrypt.generate_password_hash(form.password.data).decode('utf-8'),
        )
        db.session.add(user)
        db.session.flush()  # obtener user.id antes del commit

        # Trial: 10 créditos, 7 días
        trial_pkg = CreditPackage.query.filter_by(name='trial').first()
        trial = CreditTransaction(
            user_id=user.id,
            package_id=trial_pkg.id if trial_pkg else None,
            credits=10,
            amount_mxn=0,
            mp_status='trial',
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        db.session.add(trial)
        db.session.commit()

        login_user(user)
        flash('¡Bienvenido! Tienes 10 créditos de prueba por 7 días.', 'success')
        return redirect(url_for('editor.index'))

    return render_template('auth/register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    from app.auth.forms import LoginForm
    from app.models import User

    if current_user.is_authenticated:
        return redirect(url_for('editor.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and user.password_hash and bcrypt.check_password_hash(user.password_hash, form.password.data):
            if not user.is_active:
                flash('Tu cuenta está desactivada. Contacta a soporte.', 'danger')
                return render_template('auth/login.html', form=form)
            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('editor.index'))
        flash('Correo o contraseña incorrectos.', 'danger')

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada.', 'info')
    return redirect(url_for('auth.login'))


# ── ML OAuth ────────────────────────────────────────────────────────────────

@auth_bp.route('/ml/connect')
@login_required
def ml_connect():
    """Inicia el flujo OAuth con Mercado Libre."""
    from app.editor.meli import MeliClient
    meli = MeliClient()

    proto = request.headers.get('X-Forwarded-Proto', 'http')
    host = request.headers.get('X-Forwarded-Host', request.host)
    callback_url = f"{proto}://{host}/auth/ml/callback"
    session['ml_callback_url'] = callback_url
    return redirect(meli.get_auth_url(callback_url))


@auth_bp.route('/ml/callback')
@login_required
def ml_callback():
    """Recibe el código OAuth de ML, obtiene tokens y los guarda en el usuario actual."""
    from app.editor.meli import MeliClient
    import requests as req_lib

    code = request.args.get('code')
    if not code:
        flash('Error al conectar con Mercado Libre.', 'danger')
        return redirect(url_for('editor.index'))

    callback_url = session.get('ml_callback_url',
                               request.host_url.rstrip('/') + '/auth/ml/callback')
    meli = MeliClient()

    # Intercambio de código por tokens
    r = req_lib.post(meli.TOKEN_URL, data={
        'grant_type': 'authorization_code',
        'client_id': meli.client_id,
        'client_secret': meli.client_secret,
        'code': code,
        'redirect_uri': callback_url,
    })

    if r.status_code != 200:
        flash('No se pudo obtener el token de Mercado Libre.', 'danger')
        return redirect(url_for('editor.index'))

    data = r.json()
    access_token = data.get('access_token', '')
    refresh_token = data.get('refresh_token', '')
    expires_in = data.get('expires_in', 21600)  # segundos (6 horas por defecto)

    # Obtener datos del usuario de ML
    me_r = req_lib.get(
        f"{meli.BASE_URL}/users/me",
        headers={'Authorization': f'Bearer {access_token}', 'Accept': 'application/json'},
        timeout=8,
    )
    ml_user_id = None
    ml_nickname = None
    if me_r.status_code == 200:
        me_data = me_r.json()
        ml_user_id = me_data.get('id')
        ml_nickname = me_data.get('nickname')

    # Guardar en el usuario actual con tokens cifrados con Fernet
    from app.utils.crypto import encrypt_token
    user = current_user._get_current_object()
    user.ml_access_token = encrypt_token(access_token)
    user.ml_refresh_token = encrypt_token(refresh_token)
    user.ml_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    if ml_user_id:
        user.ml_user_id = ml_user_id
    if ml_nickname and not user.nickname:
        user.nickname = ml_nickname
    db.session.commit()

    flash('Cuenta de Mercado Libre conectada correctamente.', 'success')
    return redirect(url_for('editor.index') + '?auth=success')


@auth_bp.route('/ml/disconnect', methods=['POST'])
@login_required
def ml_disconnect():
    user = current_user._get_current_object()
    user.ml_access_token = None
    user.ml_refresh_token = None
    user.ml_token_expires_at = None
    user.ml_user_id = None
    db.session.commit()
    flash('Cuenta de Mercado Libre desconectada.', 'info')
    return redirect(url_for('editor.index'))
