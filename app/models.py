from flask_login import UserMixin
from .extensions import login_manager


class User(UserMixin):
    def __init__(self, email: str, name: str, profile_name: str = None, actions: list = None):
        self.id = email
        self.email = email
        self.name = name
        self.profile_name = profile_name or 'Usuário'
        
        # REGRA: Se actions é None ou lista vazia, significa que não foram enviadas ações no token
        # Nesse caso, permitir TODAS as ações (acesso total ao sistema)
        # Se actions tem valores, usar apenas essas ações específicas
        if actions is None or (isinstance(actions, list) and len(actions) == 0):
            # Ações não foram enviadas - permitir todas as ações
            self.actions = None  # None significa "todas as ações permitidas"
            self.has_all_permissions = True
        else:
            # Ações específicas foram enviadas - usar apenas essas
            self.actions = actions if isinstance(actions, list) else []
            self.has_all_permissions = False
    
    def has_action(self, action: str) -> bool:
        """Verifica se usuário tem uma ação específica"""
        # Se has_all_permissions é True, sempre permitir
        if self.has_all_permissions:
            return True
        
        # Mapeamento de ações em inglês para português (do Connect)
        action_mapping = {
            'view': 'consultar',
            'read': 'consultar',
            'edit': 'editar',
            'update': 'editar',
            'write': 'editar',
            'create': 'incluir',
            'include': 'incluir',
            'delete': 'excluir',
            'remove': 'excluir',
            'admin': 'admin'
        }
        
        # Mapeamento reverso (português -> inglês)
        reverse_mapping = {
            'consultar': ['view', 'read'],
            'editar': ['edit', 'update', 'write'],
            'incluir': ['create', 'include'],
            'excluir': ['delete', 'remove'],
            'admin': ['admin']
        }
        
        # Verificar ação original
        if action in self.actions:
            return True
        
        # Verificar ação mapeada (inglês -> português)
        mapped_action = action_mapping.get(action)
        if mapped_action and mapped_action in self.actions:
            return True
        
        # Verificar mapeamento reverso (português -> inglês)
        # Se a ação recebida está em português, verificar se há equivalente em inglês
        for pt_action, en_actions in reverse_mapping.items():
            if pt_action in self.actions and action in en_actions:
                return True
        
        return False
    
    def can_edit(self) -> bool:
        """Verifica se usuário pode editar"""
        if self.has_all_permissions:
            return True
        return self.has_action('edit') or self.has_action('update')
    
    def can_delete(self) -> bool:
        """Verifica se usuário pode excluir"""
        if self.has_all_permissions:
            return True
        return self.has_action('delete')
    
    def can_view(self) -> bool:
        """Verifica se usuário pode visualizar"""
        if self.has_all_permissions:
            return True
        return self.has_action('view') or len(self.actions) > 0


@login_manager.user_loader
def load_user(user_id: str):
    """Carrega usuário da sessão"""
    from flask import session
    if 'user_data' in session:
        user_data = session['user_data']
        # Manter a mesma lógica: se actions é None ou lista vazia, passar None
        # Isso garante que mesmo sessões antigas sejam atualizadas com a nova lógica
        actions = user_data.get('actions')
        if actions is None or (isinstance(actions, list) and len(actions) == 0):
            actions = None
            # Atualizar a sessão para refletir a nova lógica
            session['user_data']['actions'] = None
        
        user = User(
            email=user_data.get('email'),
            name=user_data.get('name'),
            profile_name=user_data.get('profile_name'),
            actions=actions
        )
        
        # Debug: verificar se a lógica está funcionando
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Load user: {user.email} - Actions: {actions} - Has all: {user.has_all_permissions} - Can edit: {user.can_edit()}")
        
        return user
    return None

