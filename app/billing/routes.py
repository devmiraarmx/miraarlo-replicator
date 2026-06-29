from flask import render_template, jsonify
from flask_login import login_required, current_user
from app.billing import billing_bp
from app.extensions import db


@billing_bp.route('/plans')
@login_required
def plans():
    return render_template('billing/plans.html')


@billing_bp.route('/balance')
@login_required
def balance():
    """Devuelve los créditos disponibles del usuario actual."""
    result = db.session.execute(
        db.text("SELECT available_credits FROM user_credit_balance WHERE user_id = :uid"),
        {'uid': current_user.id}
    ).fetchone()
    available = int(result[0]) if result else 0
    return jsonify({'available': available, 'user_id': current_user.id})
