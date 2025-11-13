"""
Rotas de revisões
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, session, current_app
from flask_login import login_required, current_user
from app.repositories import reviews_repository, review_viewers_repository, review_approvals_repository, review_documents_repository
from app.services.connect_api_service import connect_api_service
from app.services.email_service import email_service
from app.services.export_service import export_service
from app.utils.file_upload import validate_file, save_uploaded_file
from app.utils.security import require_action
import os
from datetime import datetime
from io import BytesIO

bp = Blueprint('reviews', __name__)


def get_return_url(review_id, default='detail'):
    """Determina a URL de retorno baseado no parâmetro return_to"""
    return_to = request.args.get('return_to') or request.form.get('return_to', '')
    if return_to == 'manage':
        return url_for('reviews.manage')
    else:
        return url_for('reviews.detail', review_id=review_id)


@bp.route('/')
@login_required
@require_action('view')
def dashboard():
    """Dashboard principal com estatísticas de revisões"""
    stats = reviews_repository.get_dashboard_stats(current_user.email)
    recent_reviews = reviews_repository.get_recent_reviews_list(current_user.email, limit=5)
    return render_template('reviews/dashboard.html', stats=stats, recent_reviews=recent_reviews)


@bp.route('/manage')
@login_required
@require_action('view')
def manage():
    """Lista revisões com filtros (Gerenciamento de Revisões)"""
    filters = {
        'status': request.args.get('status'),
        'search': request.args.get('search'),
        'approvers': request.args.getlist('approvers'),
        'reviewers': request.args.getlist('reviewers')
    }
    
    reviews = reviews_repository.list_reviews(current_user.email, filters)
    
    # Obter apenas aprovadores e responsáveis que têm revisões
    approvers = reviews_repository.get_approvers_with_reviews(current_user.email)
    reviewers = reviews_repository.get_reviewers_with_reviews(current_user.email)
    
    return render_template('reviews/list.html', reviews=reviews, filters=filters, approvers=approvers, reviewers=reviewers)


@bp.route('/new', methods=['GET', 'POST'])
@login_required
@require_action('edit')
def new():
    """Cria nova revisão"""
    if request.method == 'POST':
        try:
            # Validar dados
            document_data = {
                'title': request.form.get('title', '').strip(),
                'summary': '',  # Campo removido - sempre vazio
                'description': request.form.get('description', '').strip()
            }
            
            review_data = {
                'comments': ''  # Não usado mais - usar review_comments
            }
            
            # Processar múltiplas revisões
            review_comments_list = []
            comments_texts = request.form.getlist('review_comments[]')
            for comment_text in comments_texts:
                if comment_text.strip():
                    review_comments_list.append({
                        'reviewer_email': current_user.email,
                        'reviewer_name': current_user.name,
                        'comments': comment_text.strip(),
                        'review_date': datetime.now()
                    })
            
            # Processar riscos
            risks_data = []
            risk_texts = request.form.getlist('risk_text[]')
            legal_suggestions = request.form.getlist('legal_suggestion[]')
            final_definitions = request.form.getlist('final_definition[]')
            
            for i in range(len(risk_texts)):
                if risk_texts[i].strip():
                    risks_data.append({
                        'risk_text': risk_texts[i].strip(),
                        'legal_suggestion': legal_suggestions[i].strip() if i < len(legal_suggestions) else '',
                        'final_definition': final_definitions[i].strip() if i < len(final_definitions) else ''
                    })
            
            observations = request.form.get('observations', '').strip()
            
            # Criar revisão
            review_id = reviews_repository.create_review(
                document_data, review_data, risks_data, observations,
                current_user.email, current_user.name
            )
            
            # Salvar múltiplos comentários de revisão
            if review_comments_list:
                reviews_repository.add_review_comments(review_id, review_comments_list)
            
            # Adicionar criador automaticamente como viewer
            review_viewers_repository.add_viewers(review_id, [current_user.email])
            
            # Processar uploads
            if 'files' in request.files:
                files = request.files.getlist('files')
                for file in files:
                    if file.filename:
                        if validate_file(file):
                            save_uploaded_file(file, review_id, current_user.email)
            
            # Redirecionar para seleção de visualizadores (fluxo original)
            flash('Revisão criada com sucesso!', 'success')
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f'Revisão {review_id} criada com sucesso. Redirecionando para select_viewers.')
            return redirect(url_for('reviews.select_viewers', review_id=review_id))
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Erro ao criar revisão: {str(e)}', exc_info=True)
            flash(f'Erro ao criar revisão: {str(e)}', 'error')
    
    return render_template('reviews/form.html', review=None)


@bp.route('/<int:review_id>/edit', methods=['GET', 'POST'])
@login_required
@require_action('edit')
def edit(review_id):
    """Edita revisão (cria nova versão)"""
    review = reviews_repository.get_review_by_id(review_id, current_user.email)
    
    if not review:
        flash('Revisão não encontrada ou sem permissão', 'error')
        return redirect(url_for('reviews.manage'))
    
    if request.method == 'POST':
        try:
            import logging
            logger = logging.getLogger(__name__)
            
            document_data = {
                'title': request.form.get('title', '').strip(),
                'summary': '',  # Campo removido - sempre vazio
                'description': request.form.get('description', '').strip()
            }
            
            review_data = {
                'comments': ''  # Não usado mais - usar review_comments
            }
            
            # Processar múltiplas revisões - pegar comentários da versão anterior para comparar
            old_review_comments = reviews_repository.get_review_comments(review_id)
            old_comments_texts = {c.get('comments', '').strip() for c in old_review_comments}
            
            # Processar apenas comentários NOVOS (que não existiam na versão anterior)
            review_comments_list = []
            comments_texts = request.form.getlist('review_comments[]')
            for comment_text in comments_texts:
                comment_text_stripped = comment_text.strip()
                if comment_text_stripped and comment_text_stripped not in old_comments_texts:
                    # Este é um comentário novo, adicionar à lista
                    review_comments_list.append({
                        'reviewer_email': current_user.email,
                        'reviewer_name': current_user.name,
                        'comments': comment_text_stripped,
                        'review_date': datetime.now()
                    })
            
            # Processar riscos - pegar riscos da versão anterior para comparar
            old_risks = reviews_repository.get_review_risks(review_id)
            old_risk_texts = {r.get('risk_text', '').strip() for r in old_risks}
            
            # Processar apenas riscos NOVOS (que não existiam na versão anterior)
            risks_data = []
            risk_texts = request.form.getlist('risk_text[]')
            legal_suggestions = request.form.getlist('legal_suggestion[]')
            final_definitions = request.form.getlist('final_definition[]')
            
            for i in range(len(risk_texts)):
                risk_text_stripped = risk_texts[i].strip()
                if risk_text_stripped and risk_text_stripped not in old_risk_texts:
                    # Este é um risco novo, adicionar à lista
                    risks_data.append({
                        'risk_text': risk_text_stripped,
                        'legal_suggestion': legal_suggestions[i].strip() if i < len(legal_suggestions) else '',
                        'final_definition': final_definitions[i].strip() if i < len(final_definitions) else ''
                    })
            
            observations = request.form.get('observations', '').strip()
            
            # Determinar se há novos comentários ou riscos
            has_new_comments = len(review_comments_list) > 0
            has_new_risks = len(risks_data) > 0
            
            # Atualizar revisão com versionamento independente
            new_review_id = reviews_repository.update_review(
                review_id, document_data, review_data, risks_data, observations,
                current_user.email, current_user.name,
                has_new_comments=has_new_comments,
                has_new_risks=has_new_risks
            )
            
            if not new_review_id or new_review_id == 0:
                flash('Erro ao atualizar revisão', 'error')
                return redirect(url_for('reviews.edit', review_id=review_id))
            
            # Salvar múltiplos comentários de revisão (se houver novos)
            if has_new_comments and review_comments_list:
                reviews_repository.add_review_comments(new_review_id, review_comments_list)
            
            # Buscar viewers para envio de email
            viewers = review_viewers_repository.get_viewers(new_review_id)
            viewer_emails = [v['user_email'] for v in viewers]
            
            # Buscar dados da nova versão criada (DEPOIS de adicionar viewers)
            new_review = reviews_repository.get_review_by_id(new_review_id, current_user.email)
            
            if not new_review:
                flash('Erro ao buscar nova versão criada', 'error')
                return redirect(url_for('reviews.manage'))
            
            # has_new_risks já foi determinado na linha 211
            logger.info(f"Detecção de novos riscos: {has_new_risks}")
            
            # Fluxo baseado em detecção de novos riscos
            if has_new_risks:
                # Redirecionar para escolha de aprovação
                flash('Revisão atualizada com sucesso! Novos riscos detectados.', 'success')
                logger.info(f"Redirecionando para choose_approval (novos riscos detectados)")
                return redirect(url_for('reviews.choose_approval', review_id=new_review_id))
            else:
                # Sem novos riscos: enviar e-mail para visualizadores e redirecionar
                try:
                    if viewer_emails:
                        # Construir URL de visualização
                        reviews_base_url = os.getenv('REVIEWS_BASE_URL')
                        if not reviews_base_url:
                            server_name = current_app.config.get('SERVER_NAME')
                            preferred_scheme = current_app.config.get('PREFERRED_URL_SCHEME', 'http')
                            if server_name:
                                reviews_base_url = f"{preferred_scheme}://{server_name}"
                            else:
                                host_url = request.host_url.rstrip('/')
                                if ':5001' in host_url:
                                    reviews_base_url = host_url.replace(':5001', ':5002')
                                else:
                                    reviews_base_url = host_url
                        else:
                            reviews_base_url = reviews_base_url.rstrip('/')
                        
                        review_url = f"{reviews_base_url}{url_for('reviews.detail', review_id=new_review_id)}"
                        
                        # Enviar e-mails para visualizadores (nova versão)
                        previous_version = new_review['version'] - 1
                        result = email_service.send_emails_to_viewers(
                            viewer_emails, new_review, review_url,
                            is_new_document=False,
                            previous_version=previous_version
                        )
                        
                        logger.info(f"E-mails enviados para {len(result['sent'])} visualizador(es)")
                        if result['failed']:
                            logger.warning(f"Falha ao enviar para {len(result['failed'])} visualizador(es)")
                except Exception as e:
                    logger.error(f"Erro ao enviar e-mails para visualizadores: {str(e)}", exc_info=True)
                
                flash('Revisão atualizada com sucesso!', 'success')
                return redirect(url_for('reviews.detail', review_id=new_review_id))
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Erro ao atualizar revisão: {str(e)}', exc_info=True)
            flash(f'Erro ao atualizar revisão: {str(e)}', 'error')
    
    # Carregar dados para edição
    risks = reviews_repository.get_review_risks(review_id)
    observations_obj = reviews_repository.get_review_observations(review_id)
    review_comments = reviews_repository.get_review_comments(review_id)
    
    review['risks'] = risks
    review['observations'] = observations_obj.get('observations', '') if observations_obj else ''
    review['review_comments'] = review_comments
    
    return render_template('reviews/form.html', review=review)


@bp.route('/<int:review_id>')
@login_required
@require_action('view')
def detail(review_id):
    """Detalhes da revisão"""
    review = reviews_repository.get_review_by_id(review_id, current_user.email)
    
    if not review:
        flash('Revisão não encontrada ou sem permissão', 'error')
        return redirect(url_for('reviews.manage'))
    
    # Carregar dados relacionados
    risks = reviews_repository.get_review_risks(review_id)
    observations = reviews_repository.get_review_observations(review_id)
    approvals = review_approvals_repository.get_review_approvals(review_id)
    
    # Carregar históricos completos
    all_versions = reviews_repository.get_all_document_versions(
        review['document_id'], current_user.email
    )
    versions_with_comments = reviews_repository.get_all_versions_with_comments(
        review['document_id'], current_user.email
    )
    versions_with_risks = reviews_repository.get_all_versions_with_risks(
        review['document_id'], current_user.email
    )
    
    review['risks'] = risks
    review['observations'] = observations.get('observations', '') if observations else ''
    review['approvals'] = approvals
    review['documents'] = review_documents_repository.get_review_documents(review_id)
    review['all_versions'] = all_versions
    review['versions_with_comments'] = versions_with_comments
    review['versions_with_risks'] = versions_with_risks
    
    return render_template('reviews/detail.html', review=review)


@bp.route('/<int:review_id>/delete', methods=['POST'])
@login_required
@require_action('delete')
def delete(review_id):
    """Exclui revisão (hard delete)"""
    review = reviews_repository.get_review_by_id(review_id, current_user.email)
    
    if not review:
        flash('Revisão não encontrada ou sem permissão', 'error')
        return redirect(url_for('reviews.manage'))
    
    try:
        # Excluir arquivos do servidor
        documents = review_documents_repository.get_review_documents(review_id)
        for doc in documents:
            review_documents_repository.delete_document_file(doc['id'])
        
        # Excluir revisão (CASCADE excluirá registros relacionados)
        reviews_repository.delete_review(review_id)
        
        flash('Revisão excluída com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao excluir revisão: {str(e)}', 'error')
    
    return redirect(url_for('reviews.manage'))


@bp.route('/pending-approvals')
@login_required
@require_action('view')
def pending_approvals():
    """Lista revisões pendentes de aprovação do usuário logado"""
    reviews = reviews_repository.get_pending_approvals_for_user(current_user.email)
    return render_template('reviews/pending_approvals.html', reviews=reviews)


@bp.route('/<int:review_id>/submit-approval', methods=['POST'])
@login_required
@require_action('edit')
def submit_approval(review_id):
    """Submete revisão à aprovação sem criar nova versão"""
    review = reviews_repository.get_review_by_id(review_id, current_user.email)
    
    if not review:
        flash('Revisão não encontrada ou sem permissão', 'error')
        return redirect(url_for('reviews.manage'))
    
    # Redirecionar para tela de escolha de aprovadores, mantendo return_to
    return_to = request.args.get('return_to') or request.form.get('return_to', '')
    if return_to:
        return redirect(url_for('reviews.request_approval', review_id=review_id, return_to=return_to))
    else:
        return redirect(url_for('reviews.request_approval', review_id=review_id))


@bp.route('/<int:review_id>/manage-viewers', methods=['GET', 'POST'])
@login_required
@require_action('edit')
def manage_viewers(review_id):
    """Gerencia visualizadores de uma revisão sem editar"""
    review = reviews_repository.get_review_by_id(review_id, current_user.email)
    
    if not review:
        flash('Revisão não encontrada ou sem permissão', 'error')
        return redirect(url_for('reviews.manage'))
    
    if request.method == 'POST':
        viewer_emails = request.form.getlist('viewers[]')
        
        # Sempre incluir o criador da revisão como viewer
        if current_user.email not in viewer_emails:
            viewer_emails.append(current_user.email)
        
        if viewer_emails:
            # Obter visualizadores atuais antes de atualizar
            current_viewers = review_viewers_repository.get_viewers(review_id)
            current_viewer_emails = {v['user_email'] for v in current_viewers}
            new_viewer_emails = set(viewer_emails)
            
            # Remover visualizadores que não estão mais na lista
            viewers_to_remove = current_viewer_emails - new_viewer_emails
            for email in viewers_to_remove:
                review_viewers_repository.remove_viewer(review_id, email)
            
            # Adicionar/atualizar visualizadores selecionados
            review_viewers_repository.add_viewers(review_id, viewer_emails)
            flash('Visualizadores atualizados com sucesso!', 'success')
            return redirect(get_return_url(review_id))
        else:
            flash('Selecione pelo menos um visualizador', 'error')
    
    # Obter lista de usuários do Connect
    try:
        users = connect_api_service.get_users(request_context=request)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Erro ao obter lista de usuários: {str(e)}', exc_info=True)
        users = []
        flash('Erro ao carregar lista de usuários. Tente novamente.', 'error')
    
    current_viewers = review_viewers_repository.get_viewers(review_id)
    viewer_emails = [v['user_email'] for v in current_viewers]
    return_to = request.args.get('return_to', '')
    
    return render_template('reviews/manage_viewers.html', review=review, users=users, viewer_emails=viewer_emails, return_to=return_to)


@bp.route('/<int:review_id>/select-viewers', methods=['GET', 'POST'])
@login_required
@require_action('edit')
def select_viewers(review_id):
    """Seleciona visualizadores da revisão"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f'Acessando select_viewers para revisão {review_id} - usuário: {current_user.email}')
    
    review = reviews_repository.get_review_by_id(review_id, current_user.email)
    
    if not review:
        logger.warning(f'Revisão {review_id} não encontrada para usuário {current_user.email}')
        flash('Revisão não encontrada', 'error')
        return redirect(url_for('reviews.manage'))
    
    if request.method == 'POST':
        viewer_emails = request.form.getlist('viewers[]')
        
        # Sempre incluir o criador da revisão como viewer
        if current_user.email not in viewer_emails:
            viewer_emails.append(current_user.email)
        
        if viewer_emails:
            review_viewers_repository.add_viewers(review_id, viewer_emails)
            flash('Visualizadores definidos com sucesso!', 'success')
            
            # Redirecionar para tela de escolha (enviar para aprovação ou não)
            return redirect(url_for('reviews.choose_approval', review_id=review_id))
        else:
            flash('Selecione pelo menos um visualizador', 'error')
    
    # Obter lista de usuários do Connect
    try:
        # Passar contexto da requisição para incluir cookies de sessão
        users = connect_api_service.get_users(request_context=request)
        logger.info(f'Lista de usuários obtida: {len(users)} usuários')
        if len(users) == 0:
            logger.warning('Lista de usuários vazia - verifique se o Connect está acessível e autenticado')
            flash('Nenhum usuário encontrado. Verifique a conexão com o Connect.', 'warning')
    except Exception as e:
        logger.error(f'Erro ao obter lista de usuários: {str(e)}', exc_info=True)
        users = []
        flash('Erro ao carregar lista de usuários. Tente novamente.', 'error')
    
    current_viewers = review_viewers_repository.get_viewers(review_id)
    viewer_emails = [v['user_email'] for v in current_viewers]
    logger.info(f'Visualizadores atuais: {viewer_emails}')
    
    return render_template('reviews/select_viewers.html', review=review, users=users, viewer_emails=viewer_emails)


@bp.route('/<int:review_id>/choose-approval', methods=['GET', 'POST'])
@login_required
@require_action('edit')
def choose_approval(review_id):
    """Tela intermediária para escolher se deseja enviar para aprovação"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f'Acessando choose_approval para revisão {review_id} - usuário: {current_user.email}')
    
    review = reviews_repository.get_review_by_id(review_id, current_user.email)
    
    if not review:
        logger.warning(f'Revisão {review_id} não encontrada para usuário {current_user.email}')
        flash('Revisão não encontrada', 'error')
        return redirect(url_for('reviews.manage'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        return_to = request.args.get('return_to') or request.form.get('return_to', '')
        
        if action == 'yes':
            # Usuário escolheu enviar para aprovação
            if return_to:
                return redirect(url_for('reviews.request_approval', review_id=review_id, return_to=return_to))
            else:
                return redirect(url_for('reviews.request_approval', review_id=review_id))
        elif action == 'no':
            # Usuário escolheu não enviar para aprovação agora
            # Enviar e-mail para visualizadores
            try:
                viewers = review_viewers_repository.get_viewers(review_id)
                viewer_emails = [v['user_email'] for v in viewers]
                
                if viewer_emails:
                    # Construir URL de visualização
                    reviews_base_url = os.getenv('REVIEWS_BASE_URL')
                    if not reviews_base_url:
                        server_name = current_app.config.get('SERVER_NAME')
                        preferred_scheme = current_app.config.get('PREFERRED_URL_SCHEME', 'http')
                        if server_name:
                            reviews_base_url = f"{preferred_scheme}://{server_name}"
                        else:
                            host_url = request.host_url.rstrip('/')
                            if ':5001' in host_url:
                                reviews_base_url = host_url.replace(':5001', ':5002')
                            else:
                                reviews_base_url = host_url
                    else:
                        reviews_base_url = reviews_base_url.rstrip('/')
                    
                    review_url = f"{reviews_base_url}{url_for('reviews.detail', review_id=review_id)}"
                    
                    # Determinar se é novo documento ou nova versão
                    is_new_document = (review['version'] == 1)
                    previous_version = review['version'] - 1 if review['version'] > 1 else None
                    
                    # Enviar e-mails
                    result = email_service.send_emails_to_viewers(
                        viewer_emails, review, review_url,
                        is_new_document=is_new_document,
                        previous_version=previous_version
                    )
                    
                    logger.info(f"E-mails enviados para {len(result['sent'])} visualizador(es)")
                    if result['failed']:
                        logger.warning(f"Falha ao enviar para {len(result['failed'])} visualizador(es)")
            except Exception as e:
                logger.error(f"Erro ao enviar e-mails para visualizadores: {str(e)}", exc_info=True)
            
            flash('Revisão criada com sucesso! Você pode solicitar aprovação mais tarde.', 'success')
            return redirect(get_return_url(review_id))
    
    return_to = request.args.get('return_to', '')
    return render_template('reviews/choose_approval.html', review=review, return_to=return_to)


@bp.route('/<int:review_id>/request-approval', methods=['GET', 'POST'])
@login_required
@require_action('edit')
def request_approval(review_id):
    """Solicita aprovação da revisão"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f'Acessando request_approval para revisão {review_id} - usuário: {current_user.email}')
    
    review = reviews_repository.get_review_by_id(review_id, current_user.email)
    
    if not review:
        logger.warning(f'Revisão {review_id} não encontrada para usuário {current_user.email}')
        flash('Revisão não encontrada', 'error')
        return redirect(url_for('reviews.manage'))
    
    if request.method == 'POST':
        approver_emails = request.form.getlist('approvers[]')
        
        if approver_emails:
            try:
                # Criar solicitação de aprovação
                review_approvals_repository.create_approval_request(
                    review_id, current_user.email, approver_emails
                )
                logger.info(f'Solicitação de aprovação criada para revisão {review_id} com {len(approver_emails)} aprovador(es)')
                
                # Enviar emails
                from flask import url_for, current_app
                
                # Obter URL base do sistema de revisões jurídicas (não do Connect)
                # Prioridade: variável de ambiente REVIEWS_BASE_URL > SERVER_NAME configurado > request.host_url
                reviews_base_url = os.getenv('REVIEWS_BASE_URL')
                if not reviews_base_url:
                    # Tentar usar SERVER_NAME da configuração do sistema de revisões
                    server_name = current_app.config.get('SERVER_NAME')
                    preferred_scheme = current_app.config.get('PREFERRED_URL_SCHEME', 'http')
                    if server_name:
                        reviews_base_url = f"{preferred_scheme}://{server_name}"
                    else:
                        # Fallback: usar host_url da requisição atual (sistema de revisões)
                        # Garantir que não está usando URL do Connect
                        host_url = request.host_url.rstrip('/')
                        # Se host_url contém porta do Connect (5001), usar porta padrão de revisões (5002)
                        if ':5001' in host_url:
                            reviews_base_url = host_url.replace(':5001', ':5002')
                        else:
                            reviews_base_url = host_url
                else:
                    reviews_base_url = reviews_base_url.rstrip('/')
                
                logger.info(f'URL base do sistema de revisões para links de aprovação: {reviews_base_url}')
                
                # Buscar lista de usuários uma vez
                users = connect_api_service.get_users(request_context=request)
                emails_sent = []
                emails_failed = []
                
                for approver_email in approver_emails:
                    try:
                        # Buscar nome do aprovador do Connect
                        approver_name = next((u.get('name', approver_email) for u in users if u.get('email') == approver_email), approver_email)
                        
                        # Gerar token de aprovação
                        from itsdangerous import URLSafeTimedSerializer
                        serializer = URLSafeTimedSerializer(os.getenv('SECRET_KEY'))
                        token = serializer.dumps({'review_id': review_id, 'approver_email': approver_email})
                        
                        # Construir URL de aprovação (token será removido da URL após primeira chamada)
                        approve_path = url_for('reviews.approve', review_id=review_id, token=token)
                        approval_url = f"{reviews_base_url}{approve_path}"
                        
                        # Enviar email para o aprovador
                        email_sent = email_service.send_approval_request_email(
                            approver_email, approver_name, review, approval_url
                        )
                        
                        if email_sent:
                            emails_sent.append(approver_email)
                            logger.info(f'Email de solicitação enviado para aprovador: {approver_email}')
                        else:
                            emails_failed.append(approver_email)
                            logger.warning(f'Falha ao enviar email para aprovador: {approver_email}')
                    except Exception as e:
                        emails_failed.append(approver_email)
                        logger.error(f'Erro ao enviar email para aprovador {approver_email}: {str(e)}', exc_info=True)
                
                # Enviar email de confirmação para o solicitante
                try:
                    reviewer_name = current_user.name or current_user.email
                    reviewer_email = current_user.email
                    
                    # Buscar nomes dos aprovadores para o email
                    approver_names_list = []
                    for approver_email in approver_emails:
                        approver_name = next((u.get('name', approver_email) for u in users if u.get('email') == approver_email), approver_email)
                        approver_names_list.append(approver_name)
                    
                    approvers_text = ', '.join(approver_names_list) if approver_names_list else 'os aprovadores selecionados'
                    
                    # Criar template de confirmação de submissão
                    confirmation_subject = f"Revisão Jurídica Submetida para Aprovação - {review.get('title', 'Documento')}"
                    confirmation_html = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>Revisão Submetida para Aprovação</title>
                    </head>
                    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f0f0f0;">
                        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #f0f0f0; padding: 20px;">
                            <tr>
                                <td align="center">
                                    <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width: 600px; background-color: #ffffff; border-radius: 15px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                        <tr>
                                            <td style="background: linear-gradient(135deg, #8B5CF6 0%, #7C3AED 100%); color: #ffffff; padding: 30px; text-align: center;">
                                                <h1 style="margin: 0; font-size: 28px; font-weight: bold;">Revisão Submetida</h1>
                                                <p style="margin: 10px 0 0 0; font-size: 16px;">Sistema de Revisões Jurídicas</p>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 40px;">
                                                <h2 style="margin: 0 0 15px 0; font-size: 24px; color: #333;">Olá, {reviewer_name}!</h2>
                                                <p style="margin: 0 0 25px 0; font-size: 16px; color: #333;">
                                                    Sua revisão jurídica foi submetida para aprovação com sucesso.
                                                </p>
                                                
                                                <div style="background-color: #f8f9fa; border-left: 4px solid #8B5CF6; padding: 20px; margin: 20px 0; border-radius: 4px;">
                                                    <h3 style="margin: 0 0 10px 0; font-size: 18px; color: #333;">Informações da Revisão</h3>
                                                    <p style="margin: 5px 0;"><strong>Título:</strong> {review.get('title', 'N/A')}</p>
                                                    <p style="margin: 5px 0;"><strong>Versão:</strong> v{review.get('version', 'N/A')}</p>
                                                    <p style="margin: 5px 0;"><strong>Aprovador(es):</strong> {approvers_text}</p>
                                                    <p style="margin: 5px 0;"><strong>Data/Hora:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
                                                </div>
                                                
                                                <p style="margin: 20px 0 0 0; font-size: 14px; color: #666;">
                                                    Você será notificado quando a revisão for aprovada ou rejeitada.
                                                </p>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                        </table>
                    </body>
                    </html>
                    """
                    
                    email_service._send_email(reviewer_email, confirmation_subject, confirmation_html)
                    logger.info(f'Email de confirmação enviado para solicitante: {reviewer_email}')
                except Exception as e:
                    logger.error(f'Erro ao enviar email de confirmação para solicitante: {str(e)}', exc_info=True)
                
                # Enviar e-mails para visualizadores informando nova versão/documento
                try:
                    viewers = review_viewers_repository.get_viewers(review_id)
                    viewer_emails = [v['user_email'] for v in viewers]
                    
                    if viewer_emails:
                        review_url = f"{reviews_base_url}{url_for('reviews.detail', review_id=review_id)}"
                        
                        # Determinar se é novo documento ou nova versão
                        is_new_document = (review['version'] == 1)
                        previous_version = review['version'] - 1 if review['version'] > 1 else None
                        
                        # Enviar e-mails
                        viewer_result = email_service.send_emails_to_viewers(
                            viewer_emails, review, review_url,
                            is_new_document=is_new_document,
                            previous_version=previous_version
                        )
                        
                        logger.info(f"E-mails enviados para {len(viewer_result['sent'])} visualizador(es)")
                        if viewer_result['failed']:
                            logger.warning(f"Falha ao enviar para {len(viewer_result['failed'])} visualizador(es)")
                except Exception as e:
                    logger.error(f"Erro ao enviar e-mails para visualizadores: {str(e)}", exc_info=True)
                
                # Mensagem de sucesso com informações sobre os emails
                if emails_sent:
                    if emails_failed:
                        flash(f'Solicitação de aprovação criada! Emails enviados para {len(emails_sent)} aprovador(es), mas falhou para {len(emails_failed)}.', 'warning')
                    else:
                        flash('Solicitação de aprovação enviada com sucesso! Emails enviados para todos os aprovadores.', 'success')
                else:
                    flash('Solicitação de aprovação criada, mas nenhum email foi enviado. Verifique as configurações de email.', 'warning')
                
                return redirect(get_return_url(review_id))
                
            except Exception as e:
                logger.error(f'Erro ao solicitar aprovação: {str(e)}', exc_info=True)
                flash(f'Erro ao solicitar aprovação: {str(e)}', 'error')
        else:
            flash('Selecione pelo menos um aprovador', 'error')
    
    # Obter lista de usuários do Connect
    try:
        # Passar contexto da requisição para incluir cookies de sessão
        users = connect_api_service.get_users(request_context=request)
        logger.info(f'Lista de usuários obtida para aprovação: {len(users)} usuários')
        if len(users) == 0:
            logger.warning('Lista de usuários vazia para aprovação - verifique se o Connect está acessível e autenticado')
            flash('Nenhum usuário encontrado. Verifique a conexão com o Connect.', 'warning')
    except Exception as e:
        logger.error(f'Erro ao obter lista de usuários: {str(e)}', exc_info=True)
        users = []
        flash('Erro ao carregar lista de usuários. Tente novamente.', 'error')
    
    return_to = request.args.get('return_to', '')
    return render_template('reviews/request_approval.html', review=review, users=users, return_to=return_to)


@bp.route('/<int:review_id>/approve/switch-user', methods=['GET', 'POST'])
def approve_switch_user_redirect(review_id):
    """Redireciona rota antiga (removida) para rota de aprovação direta"""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Tentativa de acesso à rota antiga approve_switch_user para revisão {review_id}. Redirecionando para approve.")
    
    # Se há token na URL, redirecionar para approve com token
    token = request.args.get('token') or request.form.get('token')
    if token:
        return redirect(url_for('reviews.approve', review_id=review_id, token=token), code=301)
    else:
        # Sem token, redirecionar para approve sem token
        return redirect(url_for('reviews.approve', review_id=review_id), code=301)


@bp.route('/<int:review_id>/approve', methods=['GET', 'POST'])
def approve(review_id):
    """Aprova ou rejeita revisão - sempre requer autenticação via Connect"""
    import logging
    logger = logging.getLogger(__name__)
    from flask import current_app
    from flask_login import logout_user
    from urllib.parse import quote
    
    # Se for POST (submissão do formulário), processar diretamente
    # O usuário já está autenticado quando acessa a página
    if request.method == 'POST':
        # Verificar se usuário está autenticado
        if not current_user.is_authenticated:
            flash('Você precisa estar autenticado para aprovar/rejeitar revisões.', 'error')
            return redirect(url_for('reviews.pending_approvals'))
        
        # Processar aprovação/rejeição diretamente
        action = request.form.get('action')
        comments = request.form.get('comments', '').strip()
        
        if not comments:
            flash('Comentário é obrigatório', 'error')
            # Recarregar página de aprovação - usar token da sessão se disponível
            token = session.get('approval_token')
            if token:
                return redirect(url_for('reviews.approve', review_id=review_id))
            else:
                return redirect(url_for('reviews.pending_approvals'))
        
        # Obter revisão
        from app.db import fetchone
        review = fetchone("""
            SELECT r.*, d.title, d.summary, d.description
            FROM revisoes_juridicas.reviews r
            INNER JOIN revisoes_juridicas.documents d ON r.document_id = d.id
            WHERE r.id = %s
        """, (review_id,))
        
        if not review:
            flash('Revisão não encontrada', 'error')
            return redirect(url_for('reviews.pending_approvals'))
        
        approver_email = current_user.email
        
        # Verificar se há aprovação pendente
        approval = review_approvals_repository.get_approval_by_token(review_id, approver_email)
        
        if not approval or approval.get('status') != 'pending':
            flash('Aprovação não encontrada ou já processada', 'error')
            return redirect(url_for('reviews.pending_approvals'))
        
        # Buscar nome do aprovador do Connect
        users = connect_api_service.get_users(request_context=request)
        approver_name = next((u.get('name', approver_email) for u in users if u.get('email') == approver_email), approver_email)
        
        if action == 'approve':
            review_approvals_repository.approve_review(review_id, approver_email, approver_name, comments)
            status = 'approved'
        elif action == 'reject':
            review_approvals_repository.reject_review(review_id, approver_email, approver_name, comments)
            status = 'rejected'
        else:
            flash('Ação inválida', 'error')
            token = session.get('approval_token')
            if token:
                return redirect(url_for('reviews.approve', review_id=review_id))
            else:
                return redirect(url_for('reviews.pending_approvals'))
        
        # Enviar email de confirmação ao responsável pela revisão
        reviewer_email = review.get('reviewer_email')
        reviewer_name = review.get('reviewer_name')
        
        if reviewer_email:
            email_service.send_approval_confirmation_email(
                reviewer_email, reviewer_name, approver_name, review, status, comments
            )
        
        flash(f'Revisão {status} com sucesso!', 'success')
        return redirect(url_for('reviews.pending_approvals'))
    
    # GET - Validar token e autenticação antes de mostrar a página
    # Primeiro, tentar obter email do aprovador do token
    # Se token vem via GET (URL), armazenar na sessão e redirecionar sem token na URL
    token_from_url = request.args.get('token')
    if token_from_url:
        # Armazenar token na sessão e redirecionar para a mesma rota sem token na URL
        session['approval_token'] = token_from_url
        session['approval_review_id'] = review_id
        return redirect(url_for('reviews.approve', review_id=review_id), code=307)
    
    # Prioridade: sessão > form > args (apenas para compatibilidade)
    token = session.get('approval_token') or request.form.get('token') or request.args.get('token')
    approver_email_from_token = None
    approver_email_no_token = None
    
    if token:
        try:
            from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
            serializer = URLSafeTimedSerializer(os.getenv('SECRET_KEY'))
            token_data = serializer.loads(token, max_age=86400)  # 24 horas
            approver_email_from_token = token_data.get('approver_email')
        except Exception as e:
            logger.error(f"Erro ao decodificar token: {str(e)}")
    
    # Se não há token, verificar se usuário está autenticado
    if not token:
        # Se usuário já está autenticado, permitir acesso direto
        if current_user.is_authenticated:
            logger.info(f"Usuário {current_user.email} acessando aprovação sem token (já autenticado)")
            approver_email_no_token = current_user.email
        else:
            # Se não está autenticado, redirecionar para Connect
            logger.info("Token não fornecido e usuário não autenticado. Redirecionando para Connect.")
            connect_url = current_app.config.get('CONNECT_URL', 'http://localhost:5001')
            
            # Construir URL de retorno após autenticação
            reviews_base_url = os.getenv('REVIEWS_BASE_URL')
            if not reviews_base_url:
                server_name = current_app.config.get('SERVER_NAME')
                preferred_scheme = current_app.config.get('PREFERRED_URL_SCHEME', 'http')
                if server_name:
                    reviews_base_url = f"{preferred_scheme}://{server_name}"
                else:
                    reviews_base_url = request.host_url.rstrip('/')
                    if ':5001' in reviews_base_url:
                        reviews_base_url = reviews_base_url.replace(':5001', ':5002')
            else:
                reviews_base_url = reviews_base_url.rstrip('/')
            
            approval_path = url_for('reviews.approve', review_id=review_id)
            return_url = f"{reviews_base_url}{approval_path}"
            encoded_return_url = quote(return_url, safe='')
            
            return redirect(f"{connect_url}?return_url={encoded_return_url}")
    
    # Se há token mas usuário não está autenticado, redirecionar para Connect
    if not current_user.is_authenticated:
        logger.info(f"Usuário não autenticado. Redirecionando para Connect para autenticação do aprovador: {approver_email_from_token}")
        
        # Armazenar token na sessão para usar após autenticação
        session['approval_token'] = token
        session['approval_review_id'] = review_id
        
        connect_url = current_app.config.get('CONNECT_URL', 'http://localhost:5001')
        
        # Construir URL de retorno após autenticação
        reviews_base_url = os.getenv('REVIEWS_BASE_URL')
        if not reviews_base_url:
            server_name = current_app.config.get('SERVER_NAME')
            preferred_scheme = current_app.config.get('PREFERRED_URL_SCHEME', 'http')
            if server_name:
                reviews_base_url = f"{preferred_scheme}://{server_name}"
            else:
                reviews_base_url = request.host_url.rstrip('/')
                if ':5001' in reviews_base_url:
                    reviews_base_url = reviews_base_url.replace(':5001', ':5002')
        else:
            reviews_base_url = reviews_base_url.rstrip('/')
        
        approval_path = url_for('reviews.approve', review_id=review_id)
        return_url = f"{reviews_base_url}{approval_path}"
        encoded_return_url = quote(return_url, safe='')
        
        return redirect(f"{connect_url}?return_url={encoded_return_url}")
    
    # Se há token válido e usuário está logado, verificar se corresponde
    if token and approver_email_from_token and current_user.is_authenticated:
        logged_user_email = current_user.email.lower()
        token_approver_email = approver_email_from_token.lower()
        
        # Se o usuário logado não corresponde ao aprovador do token, fazer logout e redirecionar para Connect
        if logged_user_email != token_approver_email:
            logger.info(f"Usuário logado ({logged_user_email}) não corresponde ao aprovador do token ({token_approver_email}). Fazendo logout e redirecionando para Connect.")
            
            # Fazer logout do usuário atual no sistema de revisões
            logout_user()
            session.clear()
            
            # Armazenar token na sessão para usar após autenticação correta
            session['approval_token'] = token
            session['approval_review_id'] = review_id
            
            # Redirecionar direto para Connect (sem tela intermediária)
            connect_url = current_app.config.get('CONNECT_URL', 'http://localhost:5001')
            
            # Construir URL de retorno após autenticação
            reviews_base_url = os.getenv('REVIEWS_BASE_URL')
            if not reviews_base_url:
                server_name = current_app.config.get('SERVER_NAME')
                preferred_scheme = current_app.config.get('PREFERRED_URL_SCHEME', 'http')
                if server_name:
                    reviews_base_url = f"{preferred_scheme}://{server_name}"
                else:
                    reviews_base_url = request.host_url.rstrip('/')
                    if ':5001' in reviews_base_url:
                        reviews_base_url = reviews_base_url.replace(':5001', ':5002')
            else:
                reviews_base_url = reviews_base_url.rstrip('/')
            
            approval_path = url_for('reviews.approve', review_id=review_id)
            return_url = f"{reviews_base_url}{approval_path}"
            encoded_return_url = quote(return_url, safe='')
            
            logger.info(f"Redirecionando para Connect para autenticação do usuário correto: {connect_url}?return_url={encoded_return_url}")
            
            return redirect(f"{connect_url}?return_url={encoded_return_url}")
    
    # Determinar qual email usar
    approver_email = None
    
    if approver_email_no_token:
        # Usuário acessou sem token mas está autenticado
        approver_email = approver_email_no_token
    elif current_user.is_authenticated:
        # Usuário logado - usar email dele
        approver_email = current_user.email
    elif approver_email_from_token:
        # Usar email do token
        approver_email = approver_email_from_token
    else:
        # Tentar obter do parâmetro
        approver_email = request.args.get('approver_email') or request.form.get('approver_email')
    
    if not approver_email:
        flash('Aprovador não identificado. Faça login ou use o link do email.', 'error')
        return redirect(url_for('reviews.pending_approvals'))
    
    # Obter revisão (sem verificar permissão de visualização para aprovadores)
    from app.db import fetchone
    review = fetchone("""
        SELECT r.*, d.title, d.summary, d.description
        FROM revisoes_juridicas.reviews r
        INNER JOIN revisoes_juridicas.documents d ON r.document_id = d.id
        WHERE r.id = %s
    """, (review_id,))
    
    if not review:
        flash('Revisão não encontrada', 'error')
        return redirect(url_for('reviews.pending_approvals'))
    
    # Verificar se há aprovação pendente (comparação case-insensitive)
    approval = review_approvals_repository.get_approval_by_token(review_id, approver_email)
    
    # Se não encontrou aprovação pendente, verificar se existe na lista de pendentes do usuário
    if not approval or approval.get('status') != 'pending':
        # Verificar se o usuário tem aprovações pendentes para esta revisão
        pending_approvals = review_approvals_repository.get_pending_approvals(review_id)
        approver_email_lower = approver_email.lower()
        user_has_pending = any(
            pa.get('approver_email', '').lower() == approver_email_lower 
            for pa in pending_approvals
        )
        
        if user_has_pending:
            # Aprovação existe na lista, mas pode ter problema na busca específica
            # Tentar buscar novamente com email normalizado ou redirecionar para lista
            # Buscar todas as aprovações pendentes do usuário para esta revisão
            from app.db import fetchall
            user_approvals = fetchall("""
                SELECT * FROM revisoes_juridicas.review_approvals
                WHERE review_id = %s 
                AND LOWER(approver_email) = LOWER(%s) 
                AND status = 'pending'
                ORDER BY created_at DESC
                LIMIT 1
            """, (review_id, approver_email))
            
            if user_approvals:
                approval = user_approvals[0]
            else:
                # Aprovação existe mas não foi encontrada, redirecionar para lista sem erro
                return redirect(url_for('reviews.pending_approvals'))
        else:
            # Realmente não existe aprovação pendente para este usuário
            flash('Aprovação não encontrada ou já processada', 'error')
            return redirect(url_for('reviews.pending_approvals'))
    
    # Carregar dados completos da revisão
    risks = reviews_repository.get_review_risks(review_id)
    observations = reviews_repository.get_review_observations(review_id)
    approvals = review_approvals_repository.get_review_approvals(review_id)
    
    review['risks'] = risks
    review['observations'] = observations.get('observations', '') if observations else ''
    review['approvals'] = approvals
    
    return render_template('reviews/approve.html', review=review, approval=approval, approver_email=approver_email)


@bp.route('/<int:review_id>/export')
@login_required
@require_action('view')
def export(review_id):
    """Exporta revisão em PDF ou DOCX"""
    review = reviews_repository.get_review_by_id(review_id, current_user.email)
    
    if not review:
        flash('Revisão não encontrada ou sem permissão', 'error')
        return redirect(url_for('reviews.manage'))
    
    format_type = request.args.get('format', 'pdf').lower()
    include_history = request.args.get('include_history', 'false').lower() == 'true'
    
    # Carregar dados completos
    risks = reviews_repository.get_review_risks(review_id)
    observations = reviews_repository.get_review_observations(review_id)
    approvals = review_approvals_repository.get_review_approvals(review_id)
    
    review['risks'] = risks
    review['observations'] = observations.get('observations', '') if observations else ''
    review['approvals'] = approvals
    
    try:
        if include_history:
            # Carregar históricos completos
            versions_with_comments = reviews_repository.get_all_versions_with_comments(
                review['document_id'], current_user.email
            )
            versions_with_risks = reviews_repository.get_all_versions_with_risks(
                review['document_id'], current_user.email
            )
            
            if format_type == 'pdf':
                pdf_data = export_service.export_to_pdf_with_history(
                    review, versions_with_comments, versions_with_risks
                )
                filename = f"revisao_{review_id}_v{review['version']}_historico_completo.pdf"
                return send_file(
                    BytesIO(pdf_data),
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=filename
                )
            elif format_type == 'docx':
                docx_data = export_service.export_to_docx_with_history(
                    review, versions_with_comments, versions_with_risks
                )
                filename = f"revisao_{review_id}_v{review['version']}_historico_completo.docx"
                return send_file(
                    BytesIO(docx_data),
                    mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    as_attachment=True,
                    download_name=filename
                )
        else:
            # Exportação normal (apenas versão atual)
            if format_type == 'pdf':
                pdf_data = export_service.export_to_pdf(review)
                filename = f"revisao_{review_id}_v{review['version']}.pdf"
                return send_file(
                    BytesIO(pdf_data),
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=filename
                )
            elif format_type == 'docx':
                docx_data = export_service.export_to_docx(review)
                filename = f"revisao_{review_id}_v{review['version']}.docx"
                return send_file(
                    BytesIO(docx_data),
                    mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    as_attachment=True,
                    download_name=filename
                )
        
        flash('Formato inválido. Use pdf ou docx', 'error')
        return redirect(get_return_url(review_id))
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Erro ao exportar revisão: {str(e)}', exc_info=True)
        flash(f'Erro ao exportar revisão: {str(e)}', 'error')
        return redirect(get_return_url(review_id))

