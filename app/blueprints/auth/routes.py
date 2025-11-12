"""
Rotas de autenticação
"""

from flask import Blueprint, request, redirect, url_for, session, flash
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
            return redirect(url_for('reviews.list'))
        
        # Se não tem token, mostrar mensagem
        return redirect(url_for('auth.connect_auth'))
    
    # POST - receber token
    token = request.form.get('token')
    
    if not token:
        flash('Token não fornecido', 'error')
        return redirect(url_for('auth.connect_auth'))
    
    try:
        # Descriptografar token
        token_data = token_decryption_service.decrypt_token(token)
        
        # Extrair dados do usuário
        user_email = token_data.get('user_email')
        user_name = token_data.get('user_name')
        profile_name = token_data.get('profile_name', 'Usuário')
        actions = token_data.get('actions', [])
        
        if not user_email:
            flash('Token inválido: email não encontrado', 'error')
            return redirect(url_for('auth.connect_auth'))
        
        # Criar objeto User
        user = User(
            email=user_email,
            name=user_name,
            profile_name=profile_name,
            actions=actions
        )
        
        # Salvar dados na sessão
        session['user_data'] = {
            'email': user_email,
            'name': user_name,
            'profile_name': profile_name,
            'actions': actions
        }
        
        # Fazer login
        login_user(user, remember=True)
        
        flash(f'Bem-vindo, {user_name}!', 'success')
        return redirect(url_for('reviews.list'))
        
    except ValueError as e:
        flash(f'Erro na autenticação: {str(e)}', 'error')
        return redirect(url_for('auth.connect_auth'))
    except Exception as e:
        flash(f'Erro interno na autenticação: {str(e)}', 'error')
        return redirect(url_for('auth.connect_auth'))


@bp.route('/logout')
def logout():
    """Fazer logout"""
    logout_user()
    session.clear()
    flash('Logout realizado com sucesso', 'info')
    return redirect(url_for('auth.connect_auth'))

