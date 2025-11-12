"""
Repositório para documentos anexos
"""

from typing import List, Optional
from app.db import fetchall, fetchone, execute, execute_returning


def create_document_reference(review_id: int, file_name: str, file_path: str, 
                              file_size: int, uploaded_by: str) -> int:
    """Cria referência a documento anexo"""
    return execute_returning("""
        INSERT INTO revisoes_juridicas.review_documents 
        (review_id, file_name, file_path, file_size, uploaded_by)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """, (review_id, file_name, file_path, file_size, uploaded_by))


def get_review_documents(review_id: int) -> List[dict]:
    """Obtém documentos anexos de uma revisão"""
    return fetchall("""
        SELECT * FROM revisoes_juridicas.review_documents
        WHERE review_id = %s
        ORDER BY uploaded_at DESC
    """, (review_id,))


def get_document_by_id(doc_id: int) -> Optional[dict]:
    """Obtém documento por ID"""
    return fetchone("""
        SELECT * FROM revisoes_juridicas.review_documents
        WHERE id = %s
    """, (doc_id,))


def delete_document_file(doc_id: int) -> bool:
    """Exclui arquivo do servidor e referência do banco"""
    doc = get_document_by_id(doc_id)
    
    if doc:
        # Excluir arquivo do servidor
        import os
        if os.path.exists(doc['file_path']):
            try:
                os.remove(doc['file_path'])
            except Exception:
                pass  # Continuar mesmo se não conseguir excluir
        
        # Excluir referência do banco
        execute("DELETE FROM revisoes_juridicas.review_documents WHERE id = %s", (doc_id,))
        return True
    
    return False

