"""
Repository for risk categories management
"""

from typing import List, Dict, Optional
from app.db import fetchone, fetchall, execute, execute_returning


def list_all_categories() -> List[Dict]:
    """List all risk categories ordered by name"""
    query = """
        SELECT 
            id,
            name,
            description,
            created_at,
            updated_at,
            created_by
        FROM revisoes_juridicas.risk_categories
        ORDER BY name ASC
    """
    return fetchall(query)


def get_category_by_id(category_id: int) -> Optional[Dict]:
    """Get a specific risk category by ID"""
    query = """
        SELECT 
            id,
            name,
            description,
            created_at,
            updated_at,
            created_by
        FROM revisoes_juridicas.risk_categories
        WHERE id = %s
    """
    return fetchone(query, (category_id,))


def create_category(name: str, description: str, user_email: str) -> int:
    """Create a new risk category"""
    query = """
        INSERT INTO revisoes_juridicas.risk_categories (name, description, created_by)
        VALUES (%s, %s, %s)
        RETURNING id
    """
    return execute_returning(query, (name, description, user_email))


def update_category(category_id: int, name: str, description: str) -> bool:
    """Update an existing risk category"""
    query = """
        UPDATE revisoes_juridicas.risk_categories
        SET name = %s, description = %s
        WHERE id = %s
    """
    rows_affected = execute(query, (name, description, category_id))
    return rows_affected > 0


def delete_category(category_id: int) -> bool:
    """
    Delete a risk category permanently (hard delete).
    Associated risks will have category_id set to NULL due to ON DELETE SET NULL.
    """
    query = """
        DELETE FROM revisoes_juridicas.risk_categories
        WHERE id = %s
    """
    rows_affected = execute(query, (category_id,))
    return rows_affected > 0


def check_category_in_use(category_id: int) -> Dict:
    """
    Check if a category is being used by any risks.
    Returns dict with count and example risks.
    """
    query = """
        SELECT 
            COUNT(*) as total_risks,
            ARRAY_AGG(r.id ORDER BY r.created_at DESC) FILTER (WHERE r.id IS NOT NULL) as risk_ids
        FROM revisoes_juridicas.review_risks r
        WHERE r.category_id = %s
        LIMIT 5
    """
    result = fetchone(query, (category_id,))
    return {
        'total_risks': result.get('total_risks', 0) if result else 0,
        'risk_ids': result.get('risk_ids', []) if result else []
    }

