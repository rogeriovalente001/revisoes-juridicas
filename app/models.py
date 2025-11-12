from flask_login import UserMixin
from .extensions import login_manager


class User(UserMixin):
    def __init__(self, email: str, name: str, profile_name: str = None, actions: list = None):
        self.id = email
        self.email = email
        self.name = name
        self.profile_name = profile_name or 'Usuário'
        self.actions = actions or []
    
    def has_action(self, action: str) -> bool:
        """Verifica se usuário tem uma ação específica"""
        return action in self.actions
    
    def can_edit(self) -> bool:
        """Verifica se usuário pode editar"""
        return self.has_action('edit') or self.has_action('update')
    
    def can_delete(self) -> bool:
        """Verifica se usuário pode excluir"""
        return self.has_action('delete')
    
    def can_view(self) -> bool:
        """Verifica se usuário pode visualizar"""
        return self.has_action('view') or len(self.actions) > 0


@login_manager.user_loader
def load_user(user_id: str):
    """Carrega usuário da sessão"""
    from flask import session
    if 'user_data' in session:
        user_data = session['user_data']
        return User(
            email=user_data.get('email'),
            name=user_data.get('name'),
            profile_name=user_data.get('profile_name'),
            actions=user_data.get('actions', [])
        )
    return None

