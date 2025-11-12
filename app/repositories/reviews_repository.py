"""
Repositório para acesso a dados de revisões
"""

from typing import List, Dict, Optional
from app.db import fetchone, fetchall, execute, execute_returning


def list_reviews(user_email: str, filters: Dict = None) -> List[Dict]:
    """
    Lista revisões que o usuário tem permissão de visualizar.
    Filtra na query SQL para não mostrar revisões sem permissão.
    """
    filters = filters or {}
    
    # Construir query com filtros
    where_clauses = [
        "rv.user_email = %s",  # Apenas revisões que o usuário pode visualizar
        "rv.can_view = TRUE"
    ]
    params = [user_email]
    
    # Filtro por status
    if filters.get('status'):
        status = filters['status']
        if status == 'pending':
            where_clauses.append("EXISTS (SELECT 1 FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id AND ra.status = 'pending')")
        elif status == 'approved':
            where_clauses.append("EXISTS (SELECT 1 FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id AND ra.status = 'approved')")
        elif status == 'in_review':
            where_clauses.append("NOT EXISTS (SELECT 1 FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id)")
    
    # Filtro por título/resumo
    if filters.get('search'):
        search_term = f"%{filters['search']}%"
        where_clauses.append("(d.title ILIKE %s OR d.summary ILIKE %s)")
        params.extend([search_term, search_term])
    
    # Filtro por aprovadores
    if filters.get('approvers'):
        approver_emails = filters['approvers']
        placeholders = ','.join(['%s'] * len(approver_emails))
        where_clauses.append(f"EXISTS (SELECT 1 FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id AND ra.approver_email IN ({placeholders}))")
        params.extend(approver_emails)
    
    # Filtro por responsável/revisor
    if filters.get('reviewers'):
        reviewer_emails = filters['reviewers']
        placeholders = ','.join(['%s'] * len(reviewer_emails))
        where_clauses.append(f"r.reviewer_email IN ({placeholders})")
        params.extend(reviewer_emails)
    
    where_sql = " AND ".join(where_clauses)
    
    query = f"""
        SELECT 
            r.id,
            r.document_id,
            r.version,
            r.reviewer_email,
            r.reviewer_name,
            r.review_date,
            r.comments,
            r.created_at,
            d.title,
            d.summary,
            d.description,
            (SELECT COUNT(*) FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id AND ra.status = 'pending') as pending_approvals,
            (SELECT COUNT(*) FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id AND ra.status = 'approved') as approved_count
        FROM revisoes_juridicas.reviews r
        INNER JOIN revisoes_juridicas.documents d ON r.document_id = d.id
        INNER JOIN revisoes_juridicas.review_viewers rv ON r.id = rv.review_id
        WHERE {where_sql}
        ORDER BY r.review_date DESC, r.version DESC
    """
    
    return fetchall(query, tuple(params))


def get_review_by_id(review_id: int, user_email: str) -> Optional[Dict]:
    """Obtém uma revisão específica se o usuário tiver permissão"""
    query = """
        SELECT 
            r.*,
            d.title,
            d.summary,
            d.description,
            d.created_by as document_created_by,
            d.created_at as document_created_at
        FROM revisoes_juridicas.reviews r
        INNER JOIN revisoes_juridicas.documents d ON r.document_id = d.id
        INNER JOIN revisoes_juridicas.review_viewers rv ON r.id = rv.review_id
        WHERE r.id = %s AND rv.user_email = %s AND rv.can_view = TRUE
    """
    return fetchone(query, (review_id, user_email))


def create_review(document_data: Dict, review_data: Dict, risks_data: List[Dict], 
                  observations: str, user_email: str, user_name: str) -> int:
    """Cria uma nova revisão"""
    from app.db import get_db_connection
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Criar documento se não existir
            if document_data.get('document_id'):
                document_id = document_data['document_id']
            else:
                cur.execute("""
                    INSERT INTO revisoes_juridicas.documents (title, summary, description, created_by)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (document_data['title'], document_data['summary'], 
                      document_data['description'], user_email))
                document_id = cur.fetchone()[0]
            
            # Obter próxima versão
            cur.execute("""
                SELECT revisoes_juridicas.get_next_review_version(%s)
            """, (document_id,))
            version = cur.fetchone()[0]
            
            # Criar revisão
            cur.execute("""
                INSERT INTO revisoes_juridicas.reviews 
                (document_id, version, reviewer_email, reviewer_name, review_date, comments)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
                RETURNING id
            """, (document_id, version, user_email, user_name, review_data.get('comments')))
            review_id = cur.fetchone()[0]
            
            # Criar riscos
            for risk in risks_data:
                cur.execute("""
                    INSERT INTO revisoes_juridicas.review_risks 
                    (review_id, risk_text, legal_suggestion, final_definition)
                    VALUES (%s, %s, %s, %s)
                """, (review_id, risk.get('risk_text'), risk.get('legal_suggestion'), 
                      risk.get('final_definition')))
            
            # Criar observações
            if observations:
                cur.execute("""
                    INSERT INTO revisoes_juridicas.review_observations (review_id, observations)
                    VALUES (%s, %s)
                """, (review_id, observations))
            
            conn.commit()
            return review_id


def update_review(review_id: int, document_data: Dict, review_data: Dict, 
                  risks_data: List[Dict], observations: str, user_email: str, user_name: str) -> bool:
    """Atualiza uma revisão (cria nova versão)"""
    from app.db import get_db_connection
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Obter document_id atual
            cur.execute("SELECT document_id FROM revisoes_juridicas.reviews WHERE id = %s", (review_id,))
            result = cur.fetchone()
            if not result:
                return False
            document_id = result[0]
            
            # Atualizar documento
            cur.execute("""
                UPDATE revisoes_juridicas.documents
                SET title = %s, summary = %s, description = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (document_data['title'], document_data['summary'], 
                  document_data['description'], document_id))
            
            # Obter próxima versão
            cur.execute("SELECT revisoes_juridicas.get_next_review_version(%s)", (document_id,))
            version = cur.fetchone()[0]
            
            # Criar nova versão da revisão
            cur.execute("""
                INSERT INTO revisoes_juridicas.reviews 
                (document_id, version, reviewer_email, reviewer_name, review_date, comments)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
                RETURNING id
            """, (document_id, version, user_email, user_name, review_data.get('comments')))
            new_review_id = cur.fetchone()[0]
            
            # Criar riscos para nova versão
            for risk in risks_data:
                cur.execute("""
                    INSERT INTO revisoes_juridicas.review_risks 
                    (review_id, risk_text, legal_suggestion, final_definition)
                    VALUES (%s, %s, %s, %s)
                """, (new_review_id, risk.get('risk_text'), risk.get('legal_suggestion'), 
                      risk.get('final_definition')))
            
            # Atualizar observações
            cur.execute("""
                INSERT INTO revisoes_juridicas.review_observations (review_id, observations)
                VALUES (%s, %s)
                ON CONFLICT (review_id) DO UPDATE SET observations = EXCLUDED.observations
            """, (new_review_id, observations))
            
            conn.commit()
            return True


def delete_review(review_id: int) -> bool:
    """Exclui uma revisão (hard delete)"""
    # Como há CASCADE, excluir a revisão excluirá todos os registros relacionados
    execute("DELETE FROM revisoes_juridicas.reviews WHERE id = %s", (review_id,))
    return True


def get_review_versions(document_id: int, user_email: str) -> List[Dict]:
    """Obtém todas as versões de um documento que o usuário pode visualizar"""
    query = """
        SELECT 
            r.*,
            d.title,
            d.summary,
            d.description
        FROM revisoes_juridicas.reviews r
        INNER JOIN revisoes_juridicas.documents d ON r.document_id = d.id
        INNER JOIN revisoes_juridicas.review_viewers rv ON r.id = rv.review_id
        WHERE r.document_id = %s AND rv.user_email = %s AND rv.can_view = TRUE
        ORDER BY r.version DESC
    """
    return fetchall(query, (document_id, user_email))


def get_review_risks(review_id: int) -> List[Dict]:
    """Obtém riscos de uma revisão"""
    return fetchall("""
        SELECT * FROM revisoes_juridicas.review_risks
        WHERE review_id = %s
        ORDER BY id
    """, (review_id,))


def get_review_observations(review_id: int) -> Optional[Dict]:
    """Obtém observações de uma revisão"""
    return fetchone("""
        SELECT * FROM revisoes_juridicas.review_observations
        WHERE review_id = %s
    """, (review_id,))

