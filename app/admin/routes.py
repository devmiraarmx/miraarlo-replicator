from flask import render_template
from app.admin import admin_bp


@admin_bp.route('/')
def panel():
    return render_template('admin/panel.html')
