from flask import render_template
from flask_login import login_required, current_user
from app.dashboard import dashboard_bp
from app.extensions import db


@dashboard_bp.route('/')
@login_required
def home():
    from app.models import Publication, CreditTransaction

    publications = (
        Publication.query
        .filter_by(user_id=current_user.id)
        .order_by(Publication.created_at.desc())
        .limit(50)
        .all()
    )

    transactions = (
        CreditTransaction.query
        .filter_by(user_id=current_user.id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(20)
        .all()
    )

    row = db.session.execute(
        db.text("SELECT available_credits FROM user_credit_balance WHERE user_id = :uid"),
        {'uid': current_user.id}
    ).fetchone()
    available = int(row[0]) if row else 0

    total_published = sum(1 for p in publications if p.status == 'published')
    credits_used = sum(p.credits_used for p in publications if p.status == 'published')
    credits_bought = sum(
        int(t.credits) for t in transactions
        if t.mp_status in ('approved', 'trial')
    )

    return render_template(
        'dashboard/home.html',
        publications=publications,
        transactions=transactions,
        available=available,
        total_published=total_published,
        credits_used=credits_used,
        credits_bought=credits_bought,
    )
