"""
Utilitários de segurança e autorização
"""

from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user


def require_action(action: str):
    """
    Decorator para verificar se usuário tem permissão para uma ação.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.connect_auth'))
            
            if action == 'view' and not current_user.can_view():
                flash('Você não tem permissão para visualizar', 'error')
                return redirect(url_for('reviews.list'))
            
            if action == 'edit' and not current_user.can_edit():
                flash('Você não tem permissão para editar', 'error')
                return redirect(url_for('reviews.list'))
            
            if action == 'delete' and not current_user.can_delete():
                flash('Você não tem permissão para excluir', 'error')
                return redirect(url_for('reviews.list'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

