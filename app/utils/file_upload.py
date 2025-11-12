"""
Utilitários para upload de arquivos
"""

import os
import uuid
import magic
from werkzeug.utils import secure_filename
from flask import current_app
import logging

logger = logging.getLogger(__name__)


def validate_file(file) -> bool:
    """
    Valida arquivo antes do upload.
    Verifica extensão, MIME type e lista negra.
    """
    if not file or not file.filename:
        return False
    
    filename = file.filename.lower()
    extension = filename.rsplit('.', 1)[1] if '.' in filename else ''
    
    # Verificar lista negra de extensões perigosas
    dangerous_extensions = current_app.config.get('DANGEROUS_EXTENSIONS', [])
    if extension in dangerous_extensions:
        logger.warning(f"Tentativa de upload de arquivo perigoso: {filename}")
        return False
    
    # Verificar extensões permitidas
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', set())
    if extension not in allowed_extensions:
        logger.warning(f"Extensão não permitida: {extension}")
        return False
    
    # Verificar tamanho
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    max_size = current_app.config.get('MAX_UPLOAD_SIZE', 10 * 1024 * 1024)
    if file_size > max_size:
        logger.warning(f"Arquivo muito grande: {file_size} bytes")
        return False
    
    # Verificar MIME type real do arquivo
    try:
        file_content = file.read(1024)
        file.seek(0)
        mime_type = magic.from_buffer(file_content, mime=True)
        
        # Mapear MIME types permitidos
        allowed_mimes = {
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain',
            'application/rtf'
        }
        
        if mime_type not in allowed_mimes:
            logger.warning(f"MIME type não permitido: {mime_type}")
            return False
    except Exception as e:
        logger.error(f"Erro ao verificar MIME type: {str(e)}")
        return False
    
    return True


def save_uploaded_file(file, review_id: int, uploaded_by: str) -> dict:
    """
    Salva arquivo no servidor e retorna informações.
    """
    # Criar diretório se não existir
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    review_folder = os.path.join(upload_folder, str(review_id))
    os.makedirs(review_folder, exist_ok=True)
    
    # Gerar nome único
    original_filename = secure_filename(file.filename)
    file_extension = original_filename.rsplit('.', 1)[1] if '.' in original_filename else ''
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join(review_folder, unique_filename)
    
    # Salvar arquivo
    file.save(file_path)
    
    # Obter tamanho
    file_size = os.path.getsize(file_path)
    
    # Salvar referência no banco
    from app.repositories.review_documents_repository import create_document_reference
    doc_id = create_document_reference(
        review_id, original_filename, file_path, file_size, uploaded_by
    )
    
    return {
        'id': doc_id,
        'file_name': original_filename,
        'file_path': file_path,
        'file_size': file_size
    }

