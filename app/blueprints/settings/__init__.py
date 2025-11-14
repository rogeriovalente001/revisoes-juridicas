"""
Settings blueprint for system configurations
"""

from flask import Blueprint

bp = Blueprint('settings', __name__, url_prefix='/settings')

from . import routes

