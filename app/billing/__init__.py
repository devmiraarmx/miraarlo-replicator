from flask import Blueprint

billing_bp = Blueprint('billing', __name__, url_prefix='/billing')

from app.billing import routes  # noqa: F401, E402
