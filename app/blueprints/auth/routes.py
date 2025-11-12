"""
Rotas de autenticação
"""

from flask import Blueprint, request, redirect, url_for, session, flash, current_app
from flask_login import login_user, logout_user
from app.models import User
from app.services.token_decryption_service import token_decryption_service

bp = Blueprint('auth', __name__)


@bp.route('/connect', methods=['GET', 'POST'])
def connect_auth():
    """
    Endpoint de autenticação via token do Connect.
    Recebe token via POST e cria sessão local.
    """
    if request.method == 'GET':
        # Se já está autenticado, redirecionar
        from flask_login import current_user
        if current_user and current_user.is_authenticated:
            return redirect(url_for('reviews.dashboard'))
        
        # Se não tem token e não está autenticado, redirecionar para o Connect
        # para evitar loop de redirecionamento (sem mensagem de erro para não interferir no fluxo do Connect)
        connect_url = current_app.config.get('CONNECT_URL', 'http://localhost:5001')
        return redirect(connect_url)
    
    # POST - receber token
    token = request.form.get('token')
    
    if not token:
        flash('Token não fornecido', 'error')
        connect_url = current_app.config.get('CONNECT_URL', 'http://localhost:5001')
        return redirect(connect_url)
    
    try:
        # Descriptografar token
        token_data = token_decryption_service.decrypt_token(token)
        
        # Extrair dados do usuário
        user_email = token_data.get('user_email')
        user_name = token_data.get('user_name')
        profile_name = token_data.get('profile_name', 'Usuário')
        
        # Se 'actions' não existe no token ou é None ou lista vazia, significa que não foram enviadas ações
        # Nesse caso, passar None para permitir todas as ações
        # Se 'actions' existe e tem valores, usar essas ações específicas
        actions = token_data.get('actions')
        if actions is None or (isinstance(actions, list) and len(actions) == 0):
            # Ações não foram enviadas - tratar como None (todas as ações permitidas)
            actions = None
        
        if not user_email:
            flash('Token inválido: email não encontrado', 'error')
            connect_url = current_app.config.get('CONNECT_URL', 'http://localhost:5001')
            return redirect(connect_url)
        
        # Criar objeto User
        user = User(
            email=user_email,
            name=user_name,
            profile_name=profile_name,
            actions=actions
        )
        
        # Debug: log das ações recebidas (apenas em desenvolvimento)
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Usuário autenticado: {user_email} - Ações recebidas: {actions} - Has all permissions: {user.has_all_permissions} - Can edit: {user.can_edit()}")
        
        # Salvar dados na sessão (salvar None se actions for None para manter consistência)
        session['user_data'] = {
            'email': user_email,
            'name': user_name,
            'profile_name': profile_name,
            'actions': actions  # Pode ser None se não houver ações
        }
        
        # Salvar URL de retorno se presente no token
        return_url = token_data.get('return_url')
        if return_url:
            session['return_url'] = return_url
        
        # Fazer login
        login_user(user, remember=True)
        
        # Verificar se já exibiu mensagem de boas-vindas nesta sessão
        if not session.get('welcome_message_shown', False):
            flash(f'Bem-vindo, {user_name}!', 'success')
            session['welcome_message_shown'] = True
        
        return redirect(url_for('reviews.dashboard'))
        
    except ValueError as e:
        flash(f'Erro na autenticação: {str(e)}', 'error')
        connect_url = current_app.config.get('CONNECT_URL', 'http://localhost:5001')
        return redirect(connect_url)
    except Exception as e:
        flash(f'Erro interno na autenticação: {str(e)}', 'error')
        connect_url = current_app.config.get('CONNECT_URL', 'http://localhost:5001')
        return redirect(connect_url)


@bp.route('/logout')
def logout():
    """Fazer logout e redirecionar baseado no parâmetro return_to"""
    # Obter parâmetro return_to da query string
    return_to = request.args.get('return_to', 'connect')
    
    # Obter URL de retorno da sessão ANTES de limpar
    return_url = session.get('return_url')
    
    logout_user()
    session.clear()
    
    # Se return_to for 'dashboard', redirecionar para dashboard
    if return_to == 'dashboard':
        return redirect(url_for('reviews.dashboard'))
    
    # Caso contrário, redirecionar para Connect (comportamento padrão)
    if return_url:
        return redirect(return_url)
    else:
        connect_url = current_app.config.get('CONNECT_URL', 'http://localhost:5001')
        return redirect(connect_url)

