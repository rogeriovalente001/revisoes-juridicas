"""
Serviço para integração com API do Connect
"""

import os
import requests
import logging
import jwt
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from cachetools import TTLCache
from flask import current_app, request, session

logger = logging.getLogger(__name__)

# Cache de usuários com TTL de 5 minutos
_users_cache = TTLCache(maxsize=1, ttl=300)

# Cache de token JWT com TTL de 1 hora
_jwt_token_cache = TTLCache(maxsize=1, ttl=3600)


class ConnectAPIService:
    """Serviço para comunicação com API do Connect"""
    
    def __init__(self):
        self.connect_url = os.getenv('CONNECT_URL', 'http://localhost:5001')
        self.api_token = os.getenv('CONNECT_API_TOKEN')  # Token JWT fixo (opcional)
        self.jwt_secret = os.getenv('JWT_SECRET', os.getenv('SECRET_KEY'))
    
    def _generate_jwt_token(self) -> str:
        """
        Gera token JWT para autenticação na API do Connect.
        Usa cache para evitar gerar tokens desnecessariamente.
        """
        # Verificar cache primeiro
        if 'token' in _jwt_token_cache:
            logger.debug("Retornando token JWT do cache")
            return _jwt_token_cache['token']
        
        # Se tiver token fixo configurado, usar ele
        if self.api_token:
            logger.info("Usando token JWT fixo configurado")
            _jwt_token_cache['token'] = self.api_token
            return self.api_token
        
        # Gerar novo token JWT
        if not self.jwt_secret:
            logger.error("JWT_SECRET ou SECRET_KEY não configurado - não é possível gerar token")
            return None
        
        try:
            payload = {
                'service': 'revisoes_juridicas',
                'type': 'service_token',
                'exp': datetime.utcnow() + timedelta(days=365),
                'iat': datetime.utcnow(),
                'iss': 'argo_connect'  # Issuer deve corresponder ao esperado pelo Connect
            }
            
            token = jwt.encode(payload, self.jwt_secret, algorithm='HS256')
            _jwt_token_cache['token'] = token
            logger.info("Token JWT gerado com sucesso")
            return token
        except Exception as e:
            logger.error(f"Erro ao gerar token JWT: {str(e)}", exc_info=True)
            return None
    
    def get_users(self, request_context=None) -> List[Dict]:
        """
        Obtém lista de usuários do Connect.
        Tenta primeiro consultar diretamente o banco de dados do Connect.
        Se falhar, tenta via API HTTP.
        Usa cache para evitar múltiplas requisições.
        
        Args:
            request_context: Contexto da requisição Flask (opcional) para passar cookies de sessão
        """
        # Verificar cache primeiro
        if 'users' in _users_cache:
            logger.info("Retornando usuários do cache")
            return _users_cache['users']
        
        # Tentar obter do banco de dados do Connect primeiro
        users = self._get_users_from_db()
        if users:
            _users_cache['users'] = users
            logger.info(f"Usuários obtidos do banco de dados do Connect: {len(users)}")
            return users
        
        # Se falhar, tentar via API HTTP
        logger.info("Tentando obter usuários via API HTTP do Connect")
        users = self._get_users_from_api(request_context)
        if users:
            _users_cache['users'] = users
            logger.info(f"Usuários obtidos via API do Connect: {len(users)}")
            return users
        
        logger.error("Não foi possível obter usuários nem do banco nem da API")
        return []
    
    def _get_users_from_db(self) -> List[Dict]:
        """Obtém usuários consultando diretamente o banco de dados do Connect"""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            # Tentar usar as mesmas credenciais do banco atual, mas mudar o database
            # Se tiver DATABASE_URL, tentar extrair e modificar
            database_url = os.getenv('DATABASE_URL')
            
            if database_url:
                # Modificar a URL para apontar para o banco do Connect
                # Assumindo que o banco do Connect está no mesmo servidor
                connect_db_url = database_url.replace(
                    '/revisoes_juridicas_db', '/argo_connect_db'
                ).replace(
                    '/revisoes_juridicas', '/argo_connect_db'
                )
            else:
                # Usar parâmetros individuais
                connect_db_url = None
                # Tentar porta do Connect (pode ser diferente)
                connect_port = os.getenv('CONNECT_DB_PORT') or os.getenv('DB_PORT', '5432')
                db_config = {
                    'host': os.getenv('DB_HOST', 'localhost'),
                    'port': connect_port,
                    'database': os.getenv('CONNECT_DB_NAME', 'argo_connect_db'),
                    'user': os.getenv('DB_USER'),
                    'password': os.getenv('DB_PASSWORD')
                }
            
            # Conectar ao banco do Connect
            if connect_db_url:
                conn = psycopg2.connect(connect_db_url)
            else:
                conn = psycopg2.connect(**db_config)
            
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Consultar tabela users do Connect
                    cur.execute("""
                        SELECT 
                            u.id,
                            u.email,
                            u.name
                        FROM users u
                        WHERE u.is_active = TRUE
                        ORDER BY u.name ASC
                    """)
                    results = cur.fetchall()
                    users = [
                        {
                            'id': row['id'],
                            'email': row['email'],
                            'name': row['name']
                        }
                        for row in results
                    ]
                    return users
            finally:
                conn.close()
                
        except Exception as e:
            logger.warning(f"Erro ao obter usuários do banco de dados do Connect: {str(e)}")
            return []
    
    def _get_users_from_api(self, request_context=None) -> List[Dict]:
        """Obtém usuários via API HTTP do Connect usando JWT token"""
        try:
            # Fazer requisição para API do Connect
            url = f"{self.connect_url}/api/users"
            headers = {}
            cookies = {}
            
            # Gerar/obter token JWT
            jwt_token = self._generate_jwt_token()
            if jwt_token:
                headers['Authorization'] = f'Bearer {jwt_token}'
                logger.debug("Usando token JWT para autenticação")
            else:
                # Fallback: tentar cookies de sessão se disponível
                if request_context or hasattr(request, 'cookies'):
                    try:
                        flask_request = request_context if request_context else request
                        if hasattr(flask_request, 'cookies'):
                            cookies = dict(flask_request.cookies)
                            logger.info(f"Usando cookies de sessão como fallback: {list(cookies.keys())}")
                    except Exception as e:
                        logger.warning(f"Não foi possível obter cookies: {str(e)}")
            
            response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
            
            if response.status_code == 200:
                users = response.json()
                if isinstance(users, list) and len(users) > 0:
                    if all('email' in user and 'name' in user for user in users):
                        return users
                    else:
                        logger.error("Formato de dados inválido: usuários não têm campos 'email' ou 'name'")
                        return []
                else:
                    logger.warning(f"Lista de usuários vazia ou formato inválido: {type(users)}")
                    return []
            elif response.status_code == 401:
                logger.error("Erro de autenticação ao obter usuários do Connect (401 Unauthorized)")
                return []
            else:
                logger.error(f"Erro ao obter usuários do Connect: {response.status_code} - {response.text}")
                return []
                
        except requests.exceptions.Timeout:
            logger.error("Timeout ao obter usuários do Connect")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro na requisição ao Connect: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Erro inesperado ao obter usuários via API: {str(e)}", exc_info=True)
            return []
    
    def clear_cache(self):
        """Limpa o cache de usuários"""
        _users_cache.clear()
        logger.info("Cache de usuários limpo")


# Instância global do serviço
connect_api_service = ConnectAPIService()

