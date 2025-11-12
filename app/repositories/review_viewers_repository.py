"""
Repositório para controle de visualização de revisões
"""

from typing import List
from app.db import fetchall, execute, get_db_connection


def add_viewers(review_id: int, user_emails: List[str]) -> None:
    """Adiciona visualizadores a uma revisão"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for email in user_emails:
                cur.execute("""
                    INSERT INTO revisoes_juridicas.review_viewers (review_id, user_email, can_view)
                    VALUES (%s, %s, TRUE)
                    ON CONFLICT (review_id, user_email) DO UPDATE SET can_view = TRUE
                """, (review_id, email))
        conn.commit()


def get_viewers(review_id: int) -> List[dict]:
    """Obtém lista de visualizadores de uma revisão"""
    return fetchall("""
        SELECT user_email, granted_at
        FROM revisoes_juridicas.review_viewers
        WHERE review_id = %s AND can_view = TRUE
        ORDER BY granted_at
    """, (review_id,))


def can_user_view(review_id: int, user_email: str) -> bool:
    """Verifica se usuário pode visualizar uma revisão"""
    result = fetchone("""
        SELECT 1 FROM revisoes_juridicas.review_viewers
        WHERE review_id = %s AND user_email = %s AND can_view = TRUE
    """, (review_id, user_email))
    return result is not None


def remove_viewer(review_id: int, user_email: str) -> None:
    """Remove permissão de visualização de um usuário"""
    execute("""
        DELETE FROM revisoes_juridicas.review_viewers
        WHERE review_id = %s AND user_email = %s
    """, (review_id, user_email))

