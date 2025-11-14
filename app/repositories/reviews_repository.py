"""
Repositório para acesso a dados de revisões
"""

from typing import List, Dict, Optional
from app.db import fetchone, fetchall, execute, execute_returning


def list_reviews(user_email: str, filters: Dict = None, page: int = 1, per_page: int = 10) -> List[Dict]:
    """
    Lista revisões que o usuário tem permissão de visualizar.
    Filtra na query SQL para não mostrar revisões sem permissão.
    """
    filters = filters or {}
    
    # Construir query com filtros
    where_clauses = []
    params = [user_email]  # Primeiro parâmetro para o EXISTS
    
    # Filtro por status
    if filters.get('status'):
        status = filters['status']
        if status == 'pending':
            where_clauses.append("EXISTS (SELECT 1 FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id AND ra.status = 'pending')")
        elif status == 'approved':
            where_clauses.append("EXISTS (SELECT 1 FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id AND ra.status = 'approved')")
        elif status == 'rejected':
            where_clauses.append("EXISTS (SELECT 1 FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id AND ra.status = 'rejected')")
        elif status == 'in_review':
            where_clauses.append("NOT EXISTS (SELECT 1 FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id)")
    
    # Filtro por título/descrição
    if filters.get('search'):
        search_term = f"%{filters['search']}%"
        where_clauses.append("(d.title ILIKE %s OR d.description ILIKE %s)")
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
    
    # Montar WHERE clause adicional (além do filtro de permissão)
    additional_where = ""
    if where_clauses:
        additional_where = " AND " + " AND ".join(where_clauses)
    
    # Calcular offset para paginação
    offset = (page - 1) * per_page
    
    query = f"""
        WITH latest_reviews AS (
            SELECT 
                r.document_id,
                MAX(r.id) as latest_review_id
            FROM revisoes_juridicas.reviews r
            WHERE EXISTS (
                SELECT 1 FROM revisoes_juridicas.review_viewers rv 
                WHERE rv.review_id = r.id 
                AND rv.user_email = %s 
                AND rv.can_view = TRUE
            )
            GROUP BY r.document_id
        )
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
            d.document_version,
            d.review_version,
            d.risk_version,
            (SELECT COUNT(*) FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id AND ra.status = 'pending') as pending_approvals,
            (SELECT COUNT(*) FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id AND ra.status = 'approved') as approved_count,
            (SELECT COUNT(*) FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id AND ra.status = 'rejected') as rejected_count
        FROM revisoes_juridicas.reviews r
        INNER JOIN revisoes_juridicas.documents d ON r.document_id = d.id
        INNER JOIN latest_reviews lr ON r.id = lr.latest_review_id
        WHERE 1=1{additional_where}
        ORDER BY r.review_date DESC, d.updated_at DESC
        LIMIT %s OFFSET %s
    """
    
    params.extend([per_page, offset])
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
            d.created_at as document_created_at,
            d.document_version,
            d.review_version,
            d.risk_version
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
            
            # Criar revisão (comments deixado vazio - usar review_comments)
            cur.execute("""
                INSERT INTO revisoes_juridicas.reviews 
                (document_id, version, reviewer_email, reviewer_name, review_date, comments)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
                RETURNING id
            """, (document_id, version, user_email, user_name, ''))
            review_id = cur.fetchone()[0]
            
            # Criar riscos
            for risk in risks_data:
                category_id = risk.get('category_id')
                # Convert empty string to None
                if category_id == '' or category_id == 'None':
                    category_id = None
                cur.execute("""
                    INSERT INTO revisoes_juridicas.review_risks 
                    (review_id, risk_text, legal_suggestion, final_definition, category_id)
                    VALUES (%s, %s, %s, %s, %s)
                """, (review_id, risk.get('risk_text'), risk.get('legal_suggestion'), 
                      risk.get('final_definition'), category_id))
            
            # Criar observações
            if observations:
                cur.execute("""
                    INSERT INTO revisoes_juridicas.review_observations (review_id, observations)
                    VALUES (%s, %s)
                """, (review_id, observations))
            
            conn.commit()
            return review_id


def update_review(review_id: int, document_data: Dict, review_data: Dict, 
                  risks_data: List[Dict], observations: str, user_email: str, user_name: str,
                  has_new_comments: bool = False, has_new_risks: bool = False) -> int:
    """
    Atualiza documento com versionamento independente.
    Retorna o ID da review (pode ser nova ou a mesma se nada mudou).
    """
    from app.db import get_db_connection
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Obter document_id e review atual
            cur.execute("""
                SELECT r.document_id, d.document_version 
                FROM revisoes_juridicas.reviews r
                INNER JOIN revisoes_juridicas.documents d ON r.document_id = d.id
                WHERE r.id = %s
            """, (review_id,))
            result = cur.fetchone()
            if not result:
                return 0
            document_id = result[0]
            current_doc_version = result[1]
            
            # Verificar se houve mudança no documento (título, descrição, observações)
            cur.execute("""
                SELECT title, description FROM revisoes_juridicas.documents WHERE id = %s
            """, (document_id,))
            old_doc = cur.fetchone()
            
            document_changed = (
                old_doc[0] != document_data['title'] or 
                old_doc[1] != document_data['description']
            )
            
            # Verificar se observações mudaram
            cur.execute("""
                SELECT observations FROM revisoes_juridicas.review_observations 
                WHERE review_id = %s
            """, (review_id,))
            old_obs = cur.fetchone()
            old_observations = old_obs[0] if old_obs else ''
            observations_changed = (old_observations != observations)
            
            # Determinar qual versão incrementar
            new_review_id = review_id  # Por padrão, mantém o mesmo
            new_version = current_doc_version
            
            # Se QUALQUER coisa mudou
            if document_changed or observations_changed or has_new_comments or has_new_risks:
                # Atualizar documento
                cur.execute("""
                    UPDATE revisoes_juridicas.documents
                    SET title = %s, summary = %s, description = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (document_data['title'], document_data['summary'], 
                      document_data['description'], document_id))
                
                # Incrementar versão apropriada
                if has_new_comments and has_new_risks:
                    # Ambos mudaram - incrementar review e risk
                    cur.execute("SELECT revisoes_juridicas.increment_review_version(%s)", (document_id,))
                    cur.execute("SELECT revisoes_juridicas.increment_risk_version(%s)", (document_id,))
                elif has_new_comments:
                    # Só comentários mudaram
                    cur.execute("SELECT revisoes_juridicas.increment_review_version(%s)", (document_id,))
                elif has_new_risks:
                    # Só riscos mudaram
                    cur.execute("SELECT revisoes_juridicas.increment_risk_version(%s)", (document_id,))
                else:
                    # Só documento mudou (título, descrição, observações)
                    cur.execute("SELECT revisoes_juridicas.increment_document_version(%s)", (document_id,))
                
                # Obter nova versão do documento
                cur.execute("SELECT document_version FROM revisoes_juridicas.documents WHERE id = %s", (document_id,))
                new_version = cur.fetchone()[0]
                
                # SEMPRE criar nova entrada de review para manter histórico completo
                cur.execute("""
                    INSERT INTO revisoes_juridicas.reviews 
                    (document_id, version, reviewer_email, reviewer_name, review_date, comments)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
                    RETURNING id
                """, (document_id, new_version, user_email, user_name, ''))
                new_review_id = cur.fetchone()[0]
                
                # Copiar visualizadores para nova versão
                cur.execute("""
                    INSERT INTO revisoes_juridicas.review_viewers (review_id, user_email, can_view)
                    SELECT %s, user_email, can_view
                    FROM revisoes_juridicas.review_viewers
                    WHERE review_id = %s
                """, (new_review_id, review_id))
                
                # Copiar documentos anexos para nova versão
                cur.execute("""
                    INSERT INTO revisoes_juridicas.review_documents 
                    (review_id, file_name, file_path, file_size, uploaded_by, uploaded_at)
                    SELECT %s, file_name, file_path, file_size, uploaded_by, uploaded_at
                    FROM revisoes_juridicas.review_documents
                    WHERE review_id = %s
                """, (new_review_id, review_id))
                
                # Adicionar comentários novos (se houver)
                # Isso será feito na rota após retornar o new_review_id
                
                # Adicionar riscos novos (se houver)
                if has_new_risks and risks_data:
                    for risk in risks_data:
                        category_id = risk.get('category_id')
                        # Convert empty string to None
                        if category_id == '' or category_id == 'None':
                            category_id = None
                        cur.execute("""
                            INSERT INTO revisoes_juridicas.review_risks 
                            (review_id, risk_text, legal_suggestion, final_definition, category_id)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (new_review_id, risk.get('risk_text'), risk.get('legal_suggestion'), 
                              risk.get('final_definition'), category_id))
                
                # Atualizar observações na nova versão
                cur.execute("""
                    INSERT INTO revisoes_juridicas.review_observations (review_id, observations)
                    VALUES (%s, %s)
                    ON CONFLICT (review_id) DO UPDATE SET observations = EXCLUDED.observations
                """, (new_review_id, observations))
            
            conn.commit()
            return new_review_id


def delete_review(review_id: int) -> bool:
    """
    Exclui TODAS as revisões de um documento (hard delete).
    Quando o usuário exclui uma revisão, todas as versões do documento são excluídas.
    """
    from app.db import get_db_connection
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Obter document_id da revisão
            cur.execute("""
                SELECT document_id FROM revisoes_juridicas.reviews WHERE id = %s
            """, (review_id,))
            result = cur.fetchone()
            
            if not result:
                return False
            
            document_id = result[0]
            
            # Excluir TODAS as revisões do documento
            # CASCADE excluirá automaticamente:
            # - review_risks
            # - review_observations
            # - review_documents
            # - review_viewers
            # - review_approvals
            # - review_comments
            cur.execute("""
                DELETE FROM revisoes_juridicas.reviews WHERE document_id = %s
            """, (document_id,))
            
            # Excluir o documento também
            cur.execute("""
                DELETE FROM revisoes_juridicas.documents WHERE id = %s
            """, (document_id,))
            
            conn.commit()
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
    """Obtém riscos de uma revisão com categoria"""
    return fetchall("""
        SELECT 
            rr.*,
            rc.name as category_name
        FROM revisoes_juridicas.review_risks rr
        LEFT JOIN revisoes_juridicas.risk_categories rc ON rr.category_id = rc.id
        WHERE rr.review_id = %s
        ORDER BY rr.id
    """, (review_id,))


def get_review_observations(review_id: int) -> Optional[Dict]:
    """Obtém observações de uma revisão"""
    return fetchone("""
        SELECT * FROM revisoes_juridicas.review_observations
        WHERE review_id = %s
    """, (review_id,))


def get_dashboard_stats(user_email: str) -> Dict:
    """Obtém estatísticas para o dashboard - alinhado com a lógica de status da lista"""
    stats = {}
    
    # Total de revisões que o usuário pode visualizar
    result = fetchone("""
        SELECT COUNT(DISTINCT r.id) as total
        FROM revisoes_juridicas.reviews r
        INNER JOIN revisoes_juridicas.documents d ON r.document_id = d.id
        INNER JOIN revisoes_juridicas.review_viewers rv ON r.id = rv.review_id
        WHERE rv.user_email = %s AND rv.can_view = TRUE
    """, (user_email,))
    stats['total_reviews'] = result['total'] if result else 0
    
    # Revisões pendentes de aprovação (tem aprovação pendente)
    result = fetchone("""
        SELECT COUNT(DISTINCT r.id) as total
        FROM revisoes_juridicas.reviews r
        INNER JOIN revisoes_juridicas.documents d ON r.document_id = d.id
        INNER JOIN revisoes_juridicas.review_viewers rv ON r.id = rv.review_id
        WHERE rv.user_email = %s AND rv.can_view = TRUE
        AND EXISTS (
            SELECT 1 FROM revisoes_juridicas.review_approvals ra 
            WHERE ra.review_id = r.id AND ra.status = 'pending'
        )
    """, (user_email,))
    stats['pending_approvals'] = result['total'] if result else 0
    
    # Revisões aprovadas (tem aprovação aprovada E não tem pendente)
    result = fetchone("""
        SELECT COUNT(DISTINCT r.id) as total
        FROM revisoes_juridicas.reviews r
        INNER JOIN revisoes_juridicas.documents d ON r.document_id = d.id
        INNER JOIN revisoes_juridicas.review_viewers rv ON r.id = rv.review_id
        WHERE rv.user_email = %s AND rv.can_view = TRUE
        AND EXISTS (
            SELECT 1 FROM revisoes_juridicas.review_approvals ra 
            WHERE ra.review_id = r.id AND ra.status = 'approved'
        )
        AND NOT EXISTS (
            SELECT 1 FROM revisoes_juridicas.review_approvals ra2 
            WHERE ra2.review_id = r.id AND ra2.status = 'pending'
        )
    """, (user_email,))
    stats['approved_reviews'] = result['total'] if result else 0
    
    # Revisões rejeitadas (tem aprovação rejeitada)
    result = fetchone("""
        SELECT COUNT(DISTINCT r.id) as total
        FROM revisoes_juridicas.reviews r
        INNER JOIN revisoes_juridicas.documents d ON r.document_id = d.id
        INNER JOIN revisoes_juridicas.review_viewers rv ON r.id = rv.review_id
        WHERE rv.user_email = %s AND rv.can_view = TRUE
        AND EXISTS (
            SELECT 1 FROM revisoes_juridicas.review_approvals ra 
            WHERE ra.review_id = r.id AND ra.status = 'rejected'
        )
    """, (user_email,))
    stats['rejected_reviews'] = result['total'] if result else 0
    
    # Revisões em revisão (sem aprovações - nem pendente nem aprovada)
    result = fetchone("""
        SELECT COUNT(DISTINCT r.id) as total
        FROM revisoes_juridicas.reviews r
        INNER JOIN revisoes_juridicas.documents d ON r.document_id = d.id
        INNER JOIN revisoes_juridicas.review_viewers rv ON r.id = rv.review_id
        WHERE rv.user_email = %s AND rv.can_view = TRUE
        AND NOT EXISTS (
            SELECT 1 FROM revisoes_juridicas.review_approvals ra 
            WHERE ra.review_id = r.id
        )
    """, (user_email,))
    stats['in_review'] = result['total'] if result else 0
    
    # Revisões criadas nos últimos 30 dias
    result = fetchone("""
        SELECT COUNT(DISTINCT r.id) as total
        FROM revisoes_juridicas.reviews r
        INNER JOIN revisoes_juridicas.documents d ON r.document_id = d.id
        INNER JOIN revisoes_juridicas.review_viewers rv ON r.id = rv.review_id
        WHERE rv.user_email = %s AND rv.can_view = TRUE
        AND r.review_date >= CURRENT_DATE - INTERVAL '30 days'
    """, (user_email,))
    stats['recent_reviews'] = result['total'] if result else 0
    
    # Total de documentos únicos
    result = fetchone("""
        SELECT COUNT(DISTINCT r.document_id) as total
        FROM revisoes_juridicas.reviews r
        INNER JOIN revisoes_juridicas.documents d ON r.document_id = d.id
        INNER JOIN revisoes_juridicas.review_viewers rv ON r.id = rv.review_id
        WHERE rv.user_email = %s AND rv.can_view = TRUE
    """, (user_email,))
    stats['total_documents'] = result['total'] if result else 0
    
    return stats


def get_recent_reviews_list(user_email: str, page: int = 1, per_page: int = 10) -> List[Dict]:
    """Obtém lista de revisões recentes para o dashboard (apenas última versão de cada documento)"""
    offset = (page - 1) * per_page
    
    return fetchall("""
        WITH latest_reviews AS (
            SELECT 
                r.document_id,
                MAX(r.id) as latest_review_id
            FROM revisoes_juridicas.reviews r
            WHERE EXISTS (
                SELECT 1 FROM revisoes_juridicas.review_viewers rv 
                WHERE rv.review_id = r.id 
                AND rv.user_email = %s 
                AND rv.can_view = TRUE
            )
            GROUP BY r.document_id
        )
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
            d.document_version,
            d.review_version,
            d.risk_version,
            (SELECT COUNT(*) FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id AND ra.status = 'pending') as pending_approvals,
            (SELECT COUNT(*) FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id AND ra.status = 'approved') as approved_count,
            (SELECT COUNT(*) FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id AND ra.status = 'rejected') as rejected_count
        FROM revisoes_juridicas.reviews r
        INNER JOIN revisoes_juridicas.documents d ON r.document_id = d.id
        INNER JOIN latest_reviews lr ON r.id = lr.latest_review_id
        ORDER BY r.review_date DESC, d.updated_at DESC
        LIMIT %s OFFSET %s
    """, (user_email, per_page, offset))


def count_recent_reviews(user_email: str) -> int:
    """Conta o total de revisões recentes (apenas última versão de cada documento)"""
    result = fetchone("""
        WITH latest_reviews AS (
            SELECT 
                r.document_id,
                MAX(r.id) as latest_review_id
            FROM revisoes_juridicas.reviews r
            WHERE EXISTS (
                SELECT 1 FROM revisoes_juridicas.review_viewers rv 
                WHERE rv.review_id = r.id 
                AND rv.user_email = %s 
                AND rv.can_view = TRUE
            )
            GROUP BY r.document_id
        )
        SELECT COUNT(*) as total
        FROM latest_reviews
    """, (user_email,))
    
    return result['total'] if result else 0


def count_reviews(user_email: str, filters: Dict = None) -> int:
    """Conta o total de revisões com filtros aplicados (apenas última versão de cada documento)"""
    filters = filters or {}
    
    # Construir query com filtros (mesma lógica de list_reviews)
    where_clauses = []
    params = [user_email]
    
    # Filtro por status
    if filters.get('status'):
        status = filters['status']
        if status == 'pending':
            where_clauses.append("EXISTS (SELECT 1 FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id AND ra.status = 'pending')")
        elif status == 'approved':
            where_clauses.append("EXISTS (SELECT 1 FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id AND ra.status = 'approved')")
        elif status == 'rejected':
            where_clauses.append("EXISTS (SELECT 1 FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id AND ra.status = 'rejected')")
        elif status == 'in_review':
            where_clauses.append("NOT EXISTS (SELECT 1 FROM revisoes_juridicas.review_approvals ra WHERE ra.review_id = r.id)")
    
    # Filtro por título/descrição
    if filters.get('search'):
        search_term = f"%{filters['search']}%"
        where_clauses.append("(d.title ILIKE %s OR d.description ILIKE %s)")
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
    
    # Montar WHERE clause adicional
    additional_where = ""
    if where_clauses:
        additional_where = " AND " + " AND ".join(where_clauses)
    
    query = f"""
        WITH latest_reviews AS (
            SELECT 
                r.document_id,
                MAX(r.id) as latest_review_id
            FROM revisoes_juridicas.reviews r
            WHERE EXISTS (
                SELECT 1 FROM revisoes_juridicas.review_viewers rv 
                WHERE rv.review_id = r.id 
                AND rv.user_email = %s 
                AND rv.can_view = TRUE
            )
            GROUP BY r.document_id
        )
        SELECT COUNT(*) as total
        FROM revisoes_juridicas.reviews r
        INNER JOIN revisoes_juridicas.documents d ON r.document_id = d.id
        INNER JOIN latest_reviews lr ON r.id = lr.latest_review_id
        WHERE 1=1{additional_where}
    """
    
    result = fetchone(query, tuple(params))
    return result['total'] if result else 0


def get_approvers_with_reviews(user_email: str) -> List[Dict]:
    """Obtém lista de aprovadores que têm revisões enviadas ou aprovadas por eles"""
    return fetchall("""
        SELECT DISTINCT
            ra.approver_email as email,
            ra.approver_name as name
        FROM revisoes_juridicas.review_approvals ra
        INNER JOIN revisoes_juridicas.reviews r ON ra.review_id = r.id
        INNER JOIN revisoes_juridicas.review_viewers rv ON r.id = rv.review_id
        WHERE rv.user_email = %s 
        AND rv.can_view = TRUE
        AND ra.status IN ('pending', 'approved')
        ORDER BY ra.approver_name ASC
    """, (user_email,))


def get_reviewers_with_reviews(user_email: str) -> List[Dict]:
    """Obtém lista de responsáveis (revisores) que criaram revisões"""
    return fetchall("""
        SELECT DISTINCT
            r.reviewer_email as email,
            r.reviewer_name as name
        FROM revisoes_juridicas.reviews r
        INNER JOIN revisoes_juridicas.review_viewers rv ON r.id = rv.review_id
        WHERE rv.user_email = %s 
        AND rv.can_view = TRUE
        ORDER BY r.reviewer_name ASC
    """, (user_email,))


def get_pending_approvals_for_user(approver_email: str) -> List[Dict]:
    """Obtém revisões pendentes de aprovação para um aprovador específico"""
    return fetchall("""
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
            ra.approver_email,
            ra.approver_name,
            ra.created_at as approval_requested_at,
            ra.comments as approval_comments
        FROM revisoes_juridicas.reviews r
        INNER JOIN revisoes_juridicas.documents d ON r.document_id = d.id
        INNER JOIN revisoes_juridicas.review_approvals ra ON r.id = ra.review_id
        WHERE ra.approver_email = %s
        AND ra.status = 'pending'
        ORDER BY ra.created_at DESC
    """, (approver_email,))


# ========================================
# Funções para Review Comments (Múltiplas Revisões)
# ========================================

def add_review_comments(review_id: int, comments_list: List[Dict]) -> bool:
    """
    Adiciona múltiplos comentários de revisão para uma versão.
    
    Args:
        review_id: ID da versão (review)
        comments_list: Lista de dicionários com:
            - reviewer_email: Email do revisor
            - reviewer_name: Nome do revisor
            - comments: Texto do comentário
            - review_date: Data/hora do comentário (datetime)
    
    Returns:
        True se sucesso, False caso contrário
    """
    from app.db import get_db_connection
    
    if not comments_list:
        return True
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for comment_data in comments_list:
                    cur.execute("""
                        INSERT INTO revisoes_juridicas.review_comments 
                        (review_id, reviewer_email, reviewer_name, review_date, comments)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        review_id,
                        comment_data.get('reviewer_email'),
                        comment_data.get('reviewer_name'),
                        comment_data.get('review_date'),
                        comment_data.get('comments')
                    ))
                conn.commit()
                return True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erro ao adicionar comentários de revisão: {str(e)}", exc_info=True)
        return False


def get_review_comments(review_id: int) -> List[Dict]:
    """
    Busca todos os comentários de uma versão específica.
    
    Args:
        review_id: ID da versão (review)
    
    Returns:
        Lista de comentários ordenados por data
    """
    return fetchall("""
        SELECT 
            id,
            review_id,
            reviewer_email,
            reviewer_name,
            review_date,
            comments,
            created_at
        FROM revisoes_juridicas.review_comments
        WHERE review_id = %s
        ORDER BY review_date ASC
    """, (review_id,))


def get_all_document_versions(document_id: int, user_email: str) -> List[Dict]:
    """
    Busca TODAS as versões de um documento (independente de ter comentários ou riscos).
    Mostra qualquer alteração feita no documento.
    
    Args:
        document_id: ID do documento
        user_email: Email do usuário (para verificar permissão)
    
    Returns:
        Lista de todas as versões do documento:
        [{
            'review_id': int,
            'version': int,
            'reviewer_name': str,
            'review_date': datetime
        }, ...]
    """
    query = """
        SELECT 
            r.id as review_id,
            r.version,
            r.reviewer_name,
            r.review_date
        FROM revisoes_juridicas.reviews r
        INNER JOIN revisoes_juridicas.review_viewers rv ON r.id = rv.review_id
        WHERE r.document_id = %s 
        AND rv.user_email = %s 
        AND rv.can_view = TRUE
        GROUP BY r.id, r.version, r.reviewer_name, r.review_date
        ORDER BY r.version DESC
    """
    
    return fetchall(query, (document_id, user_email))


def get_all_versions_with_comments(document_id: int, user_email: str) -> List[Dict]:
    """
    Busca todas as versões de um documento com seus comentários agrupados.
    Apenas versões que o usuário tem permissão de visualizar e que possuem comentários.
    
    Args:
        document_id: ID do documento
        user_email: Email do usuário (para verificar permissão)
    
    Returns:
        Lista de versões com comentários agrupados:
        [{
            'review_id': int,
            'version': int,
            'reviewer_name': str,
            'review_date': datetime,
            'comments_list': [{'comment': str, 'review_date': datetime, 'reviewer_name': str}, ...]
        }, ...]
    """
    query = """
        SELECT 
            r.id as review_id,
            r.version,
            r.reviewer_name,
            r.review_date,
            json_agg(
                json_build_object(
                    'comment', rc.comments,
                    'review_date', rc.review_date,
                    'reviewer_name', rc.reviewer_name,
                    'reviewer_email', rc.reviewer_email
                ) ORDER BY rc.review_date
            ) as comments_list
        FROM revisoes_juridicas.reviews r
        INNER JOIN revisoes_juridicas.review_viewers rv ON r.id = rv.review_id
        INNER JOIN revisoes_juridicas.review_comments rc ON rc.review_id = r.id
        WHERE r.document_id = %s 
        AND rv.user_email = %s 
        AND rv.can_view = TRUE
        GROUP BY r.id, r.version, r.reviewer_name, r.review_date
        ORDER BY r.version DESC
    """
    
    results = fetchall(query, (document_id, user_email))
    
    # Converter JSON string para lista Python
    import json
    for result in results:
        if isinstance(result.get('comments_list'), str):
            result['comments_list'] = json.loads(result['comments_list'])
    
    return results


def get_all_versions_with_risks(document_id: int, user_email: str) -> List[Dict]:
    """
    Busca todas as versões de um documento com seus riscos agrupados.
    Apenas versões que o usuário tem permissão de visualizar e que possuem riscos.
    
    Args:
        document_id: ID do documento
        user_email: Email do usuário (para verificar permissão)
    
    Returns:
        Lista de versões com riscos agrupados:
        [{
            'review_id': int,
            'version': int,
            'reviewer_name': str,
            'review_date': datetime,
            'risks_list': [{'risk_text': str, 'legal_suggestion': str, 'final_definition': str}, ...]
        }, ...]
    """
    query = """
        SELECT 
            r.id as review_id,
            r.version,
            r.reviewer_name,
            r.review_date,
            json_agg(
                json_build_object(
                    'risk_text', rr.risk_text,
                    'legal_suggestion', rr.legal_suggestion,
                    'final_definition', rr.final_definition,
                    'category_name', rc.name
                ) ORDER BY rr.id
            ) as risks_list
        FROM revisoes_juridicas.reviews r
        INNER JOIN revisoes_juridicas.review_viewers rv ON r.id = rv.review_id
        INNER JOIN revisoes_juridicas.review_risks rr ON rr.review_id = r.id
        LEFT JOIN revisoes_juridicas.risk_categories rc ON rr.category_id = rc.id
        WHERE r.document_id = %s 
        AND rv.user_email = %s 
        AND rv.can_view = TRUE
        GROUP BY r.id, r.version, r.reviewer_name, r.review_date
        ORDER BY r.version DESC
    """
    
    results = fetchall(query, (document_id, user_email))
    
    # Converter JSON string para lista Python
    import json
    for result in results:
        if isinstance(result.get('risks_list'), str):
            result['risks_list'] = json.loads(result['risks_list'])
    
    return results


def has_new_or_modified_risks(current_risks: List[Dict], previous_review_id: int) -> bool:
    """
    Detecta se há riscos novos ou modificados comparando com a versão anterior.
    Compara os textos dos riscos (risk_text) de forma case-insensitive.
    
    Args:
        current_risks: Lista de riscos atuais (dicionários com 'risk_text')
        previous_review_id: ID da versão anterior para comparação
    
    Returns:
        True se há riscos novos ou modificados, False caso contrário
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Buscar riscos da versão anterior
        previous_risks = get_review_risks(previous_review_id)
        
        # Extrair textos dos riscos (normalizar: strip e lowercase)
        previous_risk_texts = {
            r.get('risk_text', '').strip().lower() 
            for r in previous_risks 
            if r.get('risk_text', '').strip()
        }
        
        current_risk_texts = {
            r.get('risk_text', '').strip().lower() 
            for r in current_risks 
            if r.get('risk_text', '').strip()
        }
        
        # Verificar se há textos novos (não existiam antes)
        new_risks = current_risk_texts - previous_risk_texts
        
        has_new = len(new_risks) > 0
        
        if has_new:
            logger.info(f"Detectados {len(new_risks)} risco(s) novo(s) ou modificado(s)")
        else:
            logger.info("Nenhum risco novo ou modificado detectado")
        
        return has_new
        
    except Exception as e:
        logger.error(f"Erro ao detectar novos riscos: {str(e)}", exc_info=True)
        # Em caso de erro, assumir que não há novos riscos (comportamento seguro)
        return False