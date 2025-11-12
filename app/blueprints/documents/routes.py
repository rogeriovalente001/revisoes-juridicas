"""
Rotas para download de documentos
"""

from flask import Blueprint, send_file, abort
from flask_login import login_required, current_user
from app.repositories import review_documents_repository, review_viewers_repository
import os

bp = Blueprint('documents', __name__)


@bp.route('/download/<int:doc_id>')
@login_required
def download(doc_id):
    """Download de documento anexo"""
    doc = review_documents_repository.get_document_by_id(doc_id)
    
    if not doc:
        abort(404)
    
    # Verificar se usuário pode visualizar a revisão
    review_id = doc['review_id']
    can_view = review_viewers_repository.can_user_view(review_id, current_user.email)
    
    if not can_view:
        abort(403)
    
    # Verificar se arquivo existe
    if not os.path.exists(doc['file_path']):
        abort(404)
    
    return send_file(
        doc['file_path'],
        as_attachment=True,
        download_name=doc['file_name']
    )

