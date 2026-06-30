from flask import Blueprint

editor_bp = Blueprint('editor', __name__)

from app.editor import routes  # noqa: F401, E402
