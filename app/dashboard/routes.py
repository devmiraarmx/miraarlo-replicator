from flask import render_template
from app.dashboard import dashboard_bp


@dashboard_bp.route('/')
def home():
    return render_template('dashboard/home.html')
