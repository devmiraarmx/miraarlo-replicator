from functools import wraps
from flask import render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from app.admin import admin_bp
from app.extensions import db


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ── Panel principal ───────────────────────────────────────────────────────────

@admin_bp.route('/')
@admin_required
def panel():
    from app.models import User, CreditTransaction, Publication

    # Stats globales
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    total_pubs = Publication.query.filter_by(status='published').count()

    revenue_row = db.session.execute(
        db.text("SELECT COALESCE(SUM(amount_mxn), 0) FROM credit_transactions WHERE mp_status = 'approved' AND amount_mxn > 0")
    ).fetchone()
    total_revenue = float(revenue_row[0]) if revenue_row else 0.0

    credits_sold_row = db.session.execute(
        db.text("SELECT COALESCE(SUM(credits), 0) FROM credit_transactions WHERE mp_status = 'approved'")
    ).fetchone()
    credits_sold = int(credits_sold_row[0]) if credits_sold_row else 0

    credits_used_row = db.session.execute(
        db.text("SELECT COALESCE(SUM(credits_used), 0) FROM publications WHERE status = 'published'")
    ).fetchone()
    credits_used = int(credits_used_row[0]) if credits_used_row else 0

    # Últimas transacciones aprobadas
    recent_txns = (
        CreditTransaction.query
        .filter(CreditTransaction.mp_status.in_(['approved', 'trial']))
        .order_by(CreditTransaction.created_at.desc())
        .limit(10)
        .all()
    )

    # Top usuarios por publicaciones
    top_users = db.session.execute(db.text("""
        SELECT u.email, u.nickname, COUNT(p.id) as pub_count
        FROM users u
        LEFT JOIN publications p ON p.user_id = u.id AND p.status = 'published'
        GROUP BY u.id, u.email, u.nickname
        ORDER BY pub_count DESC
        LIMIT 10
    """)).fetchall()

    return render_template(
        'admin/panel.html',
        total_users=total_users,
        active_users=active_users,
        total_pubs=total_pubs,
        total_revenue=total_revenue,
        credits_sold=credits_sold,
        credits_used=credits_used,
        recent_txns=recent_txns,
        top_users=top_users,
    )


# ── Lista de usuarios ─────────────────────────────────────────────────────────

@admin_bp.route('/users')
@admin_required
def users():
    from app.models import User

    q = request.args.get('q', '').strip()
    filter_active = request.args.get('active', '')

    query = User.query
    if q:
        query = query.filter(User.email.ilike(f'%{q}%'))
    if filter_active == '1':
        query = query.filter_by(is_active=True)
    elif filter_active == '0':
        query = query.filter_by(is_active=False)

    users_list = query.order_by(User.created_at.desc()).limit(200).all()

    # Añadir balance a cada usuario
    balances = {}
    for u in users_list:
        row = db.session.execute(
            db.text("SELECT available_credits FROM user_credit_balance WHERE user_id = :uid"),
            {'uid': u.id}
        ).fetchone()
        balances[u.id] = int(row[0]) if row else 0

    return render_template('admin/users.html', users=users_list, balances=balances, q=q, filter_active=filter_active)


# ── Detalle de usuario ────────────────────────────────────────────────────────

@admin_bp.route('/users/<int:user_id>')
@admin_required
def user_detail(user_id):
    from app.models import User, Publication, CreditTransaction

    user = User.query.get_or_404(user_id)

    row = db.session.execute(
        db.text("SELECT available_credits FROM user_credit_balance WHERE user_id = :uid"),
        {'uid': user.id}
    ).fetchone()
    available = int(row[0]) if row else 0

    publications = (
        Publication.query.filter_by(user_id=user.id)
        .order_by(Publication.created_at.desc()).limit(30).all()
    )
    transactions = (
        CreditTransaction.query.filter_by(user_id=user.id)
        .order_by(CreditTransaction.created_at.desc()).limit(20).all()
    )

    return render_template(
        'admin/user_detail.html',
        user=user, available=available,
        publications=publications, transactions=transactions,
    )


# ── Activar / desactivar usuario ─────────────────────────────────────────────

@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user(user_id):
    from app.models import User

    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('No puedes desactivar tu propia cuenta.', 'danger')
        return redirect(url_for('admin.user_detail', user_id=user_id))

    user.is_active = not user.is_active
    db.session.commit()
    action = 'activado' if user.is_active else 'desactivado'
    flash(f'Usuario {user.email} {action}.', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


# ── Otorgar créditos (cortesía) ───────────────────────────────────────────────

@admin_bp.route('/users/<int:user_id>/grant-credits', methods=['POST'])
@admin_required
def grant_credits(user_id):
    from app.models import User, CreditTransaction

    user = User.query.get_or_404(user_id)

    try:
        amount = int(request.form.get('credits', 0))
    except (ValueError, TypeError):
        amount = 0

    if amount <= 0 or amount > 10000:
        flash('Cantidad inválida (1–10 000 créditos).', 'danger')
        return redirect(url_for('admin.user_detail', user_id=user_id))

    txn = CreditTransaction(
        user_id=user.id,
        package_id=None,
        credits=amount,
        amount_mxn=0,
        mp_status='approved',
    )
    db.session.add(txn)
    db.session.commit()
    flash(f'{amount} crédito(s) de cortesía otorgados a {user.email}.', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


# ── 403 handler ──────────────────────────────────────────────────────────────

@admin_bp.app_errorhandler(403)
def forbidden(e):
    return render_template('admin/403.html'), 403
