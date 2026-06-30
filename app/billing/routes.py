from flask import render_template
from app.billing import billing_bp


@billing_bp.route('/plans')
def plans():
    return render_template('billing/plans.html')
