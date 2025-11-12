"""
Módulo de conexão com banco de dados
"""

import os
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from contextlib import contextmanager
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from pathlib import Path

# Carregar variáveis de ambiente
_env_path = Path(__file__).resolve().parents[1] / 'config.env'
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path, override=True)

# Connection pool
_connection_pool = None


def init_db_pool():
    """Inicializa o pool de conexões"""
    global _connection_pool
    
    if _connection_pool is None:
        try:
            # Tentar usar DATABASE_URL primeiro
            database_url = os.environ.get('DATABASE_URL')
            
            if database_url:
                # Parse da URL se necessário
                _connection_pool = psycopg2.pool.SimpleConnectionPool(
                    1, 20,
                    dsn=database_url
                )
            else:
                # Usar parâmetros individuais
                _connection_pool = psycopg2.pool.SimpleConnectionPool(
                    1, 20,
                    host=os.environ.get('DB_HOST', 'localhost'),
                    port=os.environ.get('DB_PORT', '5433'),
                    database=os.environ.get('DB_NAME', 'argo_connect_db'),
                    user=os.environ.get('DB_USER'),
                    password=os.environ.get('DB_PASSWORD')
                )
        except Exception as e:
            raise ConnectionError(f"Erro ao criar pool de conexões: {e}")
    
    return _connection_pool


def get_connection():
    """Obtém uma conexão do pool"""
    if _connection_pool is None:
        init_db_pool()
    
    if _connection_pool:
        return _connection_pool.getconn()
    else:
        raise ConnectionError("Pool de conexões não inicializado")


def return_connection(conn):
    """Retorna uma conexão ao pool"""
    if _connection_pool:
        _connection_pool.putconn(conn)


@contextmanager
def get_db_connection():
    """Context manager para conexões do banco"""
    conn = None
    try:
        conn = get_connection()
        # Definir schema
        with conn.cursor() as cur:
            cur.execute("SET search_path TO revisoes_juridicas, public")
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            return_connection(conn)


def fetchone(query: str, params: tuple = None) -> Optional[Dict]:
    """Executa query e retorna um único resultado"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Definir schema
            cur.execute("SET search_path TO revisoes_juridicas, public")
            cur.execute(query, params)
            result = cur.fetchone()
            return dict(result) if result else None


def fetchall(query: str, params: tuple = None) -> List[Dict]:
    """Executa query e retorna todos os resultados"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Definir schema
            cur.execute("SET search_path TO revisoes_juridicas, public")
            cur.execute(query, params)
            results = cur.fetchall()
            return [dict(row) for row in results]


def execute(query: str, params: tuple = None) -> None:
    """Executa query sem retorno"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Definir schema
            cur.execute("SET search_path TO revisoes_juridicas, public")
            cur.execute(query, params)


def execute_returning(query: str, params: tuple = None) -> Any:
    """Executa query e retorna o valor de RETURNING"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Definir schema
            cur.execute("SET search_path TO revisoes_juridicas, public")
            cur.execute(query, params)
            result = cur.fetchone()
            return result[0] if result else None

