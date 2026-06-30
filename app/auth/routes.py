from flask import redirect, request, session, render_template, flash, url_for
from app.auth import auth_bp


@auth_bp.route('/login')
def login():
    return render_template('auth/login.html')


@auth_bp.route('/register')
def register():
    return render_template('auth/register.html')


# ── ML OAuth (prototipo: flujo single-user existente) ──

@auth_bp.route('/ml/connect')
def ml_connect():
    """Inicia el flujo OAuth con Mercado Libre."""
    from app.editor.meli import MeliClient
    meli = MeliClient()

    base_url = request.args.get('base_url', '').rstrip('/')
    if not base_url:
        proto = request.headers.get('X-Forwarded-Proto', 'http')
        host = request.headers.get('X-Forwarded-Host', request.host)
        base_url = f"{proto}://{host}"

    callback_url = base_url + '/auth/ml/callback'
    session['ml_callback_url'] = callback_url
    return redirect(meli.get_auth_url(callback_url))


@auth_bp.route('/ml/callback')
def ml_callback():
    """Callback OAuth de Mercado Libre."""
    from app.editor.meli import MeliClient
    meli = MeliClient()

    code = request.args.get('code')
    if not code:
        flash('Error al conectar con Mercado Libre.', 'danger')
        return redirect(url_for('editor.index') + '?auth=error')

    callback_url = session.get('ml_callback_url',
                               request.host_url.rstrip('/') + '/auth/ml/callback')
    result = meli.exchange_code(code, callback_url)

    if result.get('success'):
        return redirect(url_for('editor.index') + '?auth=success')
    return redirect(url_for('editor.index') + '?auth=error')
