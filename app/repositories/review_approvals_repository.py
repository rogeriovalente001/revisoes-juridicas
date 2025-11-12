"""
Repositório para sistema de aprovações
"""

from typing import List, Optional
from app.db import fetchall, fetchone, execute, get_db_connection


def create_approval_request(review_id: int, requested_by: str, approver_emails: List[str]) -> int:
    """Cria solicitação de aprovação e registros de aprovação pendentes"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Criar solicitação
            cur.execute("""
                INSERT INTO revisoes_juridicas.review_approval_requests 
                (review_id, requested_by, status)
                VALUES (%s, %s, 'pending')
                RETURNING id
            """, (review_id, requested_by))
            request_id = cur.fetchone()[0]
            
            # Criar registros de aprovação pendentes
            for approver_email in approver_emails:
                # Buscar nome do aprovador (assumindo que temos acesso ao Connect)
                # Por enquanto, usar email como nome
                cur.execute("""
                    INSERT INTO revisoes_juridicas.review_approvals 
                    (review_id, approver_email, approver_name, status, comments)
                    VALUES (%s, %s, %s, 'pending', '')
                """, (review_id, approver_email, approver_email))
            
            conn.commit()
            return request_id


def get_pending_approvals(review_id: int) -> List[dict]:
    """Obtém aprovações pendentes de uma revisão"""
    return fetchall("""
        SELECT * FROM revisoes_juridicas.review_approvals
        WHERE review_id = %s AND status = 'pending'
        ORDER BY created_at
    """, (review_id,))


def approve_review(review_id: int, approver_email: str, approver_name: str, comments: str) -> bool:
    """Aprova uma revisão"""
    execute("""
        UPDATE revisoes_juridicas.review_approvals
        SET status = 'approved',
            approved_at = CURRENT_TIMESTAMP,
            comments = %s
        WHERE review_id = %s AND approver_email = %s AND status = 'pending'
    """, (comments, review_id, approver_email))
    return True


def reject_review(review_id: int, approver_email: str, approver_name: str, comments: str) -> bool:
    """Rejeita uma revisão"""
    execute("""
        UPDATE revisoes_juridicas.review_approvals
        SET status = 'rejected',
            approved_at = CURRENT_TIMESTAMP,
            comments = %s
        WHERE review_id = %s AND approver_email = %s AND status = 'pending'
    """, (comments, review_id, approver_email))
    return True


def get_review_approvals(review_id: int) -> List[dict]:
    """Obtém histórico completo de aprovações de uma revisão"""
    return fetchall("""
        SELECT * FROM revisoes_juridicas.review_approvals
        WHERE review_id = %s
        ORDER BY approved_at DESC NULLS LAST, created_at DESC
    """, (review_id,))


def get_approval_by_token(review_id: int, approver_email: str) -> Optional[dict]:
    """Obtém aprovação pendente por email do aprovador"""
    return fetchone("""
        SELECT * FROM revisoes_juridicas.review_approvals
        WHERE review_id = %s AND approver_email = %s AND status = 'pending'
        ORDER BY created_at DESC
        LIMIT 1
    """, (review_id, approver_email))


def update_approval_request_status(review_id: int, status: str) -> None:
    """Atualiza status da solicitação de aprovação"""
    execute("""
        UPDATE revisoes_juridicas.review_approval_requests
        SET status = %s
        WHERE review_id = %s
    """, (status, review_id))

