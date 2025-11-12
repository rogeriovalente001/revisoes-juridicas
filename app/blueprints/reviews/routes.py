"""
Rotas de revisões
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
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
                'comments': request.form.get('comments', '').strip()
            }
            
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
            document_data = {
                'title': request.form.get('title', '').strip(),
                'summary': '',  # Campo removido - sempre vazio
                'description': request.form.get('description', '').strip()
            }
            
            review_data = {
                'comments': request.form.get('comments', '').strip()
            }
            
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
            
            reviews_repository.update_review(
                review_id, document_data, review_data, risks_data, observations,
                current_user.email, current_user.name
            )
            
            flash('Revisão atualizada com sucesso!', 'success')
            return redirect(url_for('reviews.manage'))
            
        except Exception as e:
            flash(f'Erro ao atualizar revisão: {str(e)}', 'error')
    
    # Carregar dados para edição
    risks = reviews_repository.get_review_risks(review_id)
    observations_obj = reviews_repository.get_review_observations(review_id)
    
    review['risks'] = risks
    review['observations'] = observations_obj.get('observations', '') if observations_obj else ''
    
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
    versions = reviews_repository.get_review_versions(review['document_id'], current_user.email)
    
    review['risks'] = risks
    review['observations'] = observations.get('observations', '') if observations else ''
    review['approvals'] = approvals
    review['versions'] = versions
    review['documents'] = review_documents_repository.get_review_documents(review_id)
    
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
    
    # Redirecionar para tela de escolha de aprovadores
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
            review_viewers_repository.add_viewers(review_id, viewer_emails)
            flash('Visualizadores atualizados com sucesso!', 'success')
            return redirect(url_for('reviews.detail', review_id=review_id))
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
    
    return render_template('reviews/manage_viewers.html', review=review, users=users, viewer_emails=viewer_emails)


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
        
        if action == 'yes':
            # Usuário escolheu enviar para aprovação
            return redirect(url_for('reviews.request_approval', review_id=review_id))
        elif action == 'no':
            # Usuário escolheu não enviar para aprovação agora
            flash('Revisão criada com sucesso! Você pode solicitar aprovação mais tarde.', 'success')
            return redirect(url_for('reviews.detail', review_id=review_id))
    
    return render_template('reviews/choose_approval.html', review=review)


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
                
                # Enviar emails
                from flask import url_for
                base_url = request.host_url.rstrip('/')
                
                for approver_email in approver_emails:
                    # Buscar nome do aprovador do Connect
                    users = connect_api_service.get_users(request_context=request)
                    approver_name = next((u.get('name', approver_email) for u in users if u.get('email') == approver_email), approver_email)
                    
                    # Gerar token de aprovação
                    from itsdangerous import URLSafeTimedSerializer
                    serializer = URLSafeTimedSerializer(os.getenv('SECRET_KEY'))
                    token = serializer.dumps({'review_id': review_id, 'approver_email': approver_email})
                    
                    approval_url = f"{base_url}{url_for('reviews.approve', review_id=review_id, token=token)}"
                    
                    email_service.send_approval_request_email(
                        approver_email, approver_name, review, approval_url
                    )
                
                flash('Solicitação de aprovação enviada com sucesso!', 'success')
                return redirect(url_for('reviews.detail', review_id=review_id))
                
            except Exception as e:
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
    
    return render_template('reviews/request_approval.html', review=review, users=users)


@bp.route('/<int:review_id>/approve', methods=['GET', 'POST'])
@login_required
def approve(review_id):
    """Aprova ou rejeita revisão"""
    # Se usuário está logado, usar email do usuário logado
    # Caso contrário, tentar obter do token
    approver_email = None
    
    if current_user.is_authenticated:
        # Usuário logado - usar email dele
        approver_email = current_user.email
    else:
        # Tentar obter do token (para links de email)
        token = request.args.get('token') or request.form.get('token')
        if token:
            try:
                from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
                serializer = URLSafeTimedSerializer(os.getenv('SECRET_KEY'))
                token_data = serializer.loads(token, max_age=86400)  # 24 horas
                approver_email = token_data.get('approver_email')
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Erro ao decodificar token: {str(e)}")
    
    # Se não conseguiu obter email, tentar do parâmetro
    if not approver_email:
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
    
    # Verificar se há aprovação pendente
    approval = review_approvals_repository.get_approval_by_token(review_id, approver_email)
    
    if not approval or approval['status'] != 'pending':
        flash('Aprovação não encontrada ou já processada', 'error')
        return redirect(url_for('reviews.pending_approvals'))
    
    # Carregar dados completos da revisão
    risks = reviews_repository.get_review_risks(review_id)
    observations = reviews_repository.get_review_observations(review_id)
    approvals = review_approvals_repository.get_review_approvals(review_id)
    
    review['risks'] = risks
    review['observations'] = observations.get('observations', '') if observations else ''
    review['approvals'] = approvals
    
    if request.method == 'POST':
        action = request.form.get('action')
        comments = request.form.get('comments', '').strip()
        
        if not comments:
            flash('Comentário é obrigatório', 'error')
            return render_template('reviews/approve.html', review=review, approval=approval, approver_email=approver_email)
        
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
            return render_template('reviews/approve.html', review=review, approval=approval, approver_email=approver_email)
        
        # Enviar email de confirmação ao responsável pela revisão
        reviewer_email = review.get('reviewer_email')
        reviewer_name = review.get('reviewer_name')
        
        if reviewer_email:
            email_service.send_approval_confirmation_email(
                reviewer_email, reviewer_name, approver_name, review, status, comments
            )
        
        flash(f'Revisão {status} com sucesso!', 'success')
        return redirect(url_for('reviews.pending_approvals'))
    
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
    
    # Carregar dados completos
    risks = reviews_repository.get_review_risks(review_id)
    observations = reviews_repository.get_review_observations(review_id)
    approvals = review_approvals_repository.get_review_approvals(review_id)
    
    review['risks'] = risks
    review['observations'] = observations.get('observations', '') if observations else ''
    review['approvals'] = approvals
    
    try:
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
        else:
            flash('Formato inválido. Use pdf ou docx', 'error')
            return redirect(url_for('reviews.detail', review_id=review_id))
    except Exception as e:
        flash(f'Erro ao exportar revisão: {str(e)}', 'error')
        return redirect(url_for('reviews.detail', review_id=review_id))

