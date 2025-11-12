"""
Serviço para integração com API do Connect
"""

import os
import requests
import logging
from typing import List, Dict
from cachetools import TTLCache
from flask import current_app

logger = logging.getLogger(__name__)

# Cache de usuários com TTL de 5 minutos
_users_cache = TTLCache(maxsize=1, ttl=300)


class ConnectAPIService:
    """Serviço para comunicação com API do Connect"""
    
    def __init__(self):
        self.connect_url = os.getenv('CONNECT_URL', 'http://localhost:5001')
        self.api_token = os.getenv('CONNECT_API_TOKEN')  # Token de serviço se necessário
    
    def get_users(self) -> List[Dict]:
        """
        Obtém lista de usuários do Connect.
        Usa cache para evitar múltiplas requisições.
        """
        # Verificar cache primeiro
        if 'users' in _users_cache:
            logger.info("Retornando usuários do cache")
            return _users_cache['users']
        
        try:
            # Fazer requisição para API do Connect
            url = f"{self.connect_url}/api/users"
            headers = {}
            
            # Se tiver token de serviço, adicionar ao header
            if self.api_token:
                headers['Authorization'] = f'Bearer {self.api_token}'
            
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                users = response.json()
                # Armazenar no cache
                _users_cache['users'] = users
                logger.info(f"Usuários obtidos do Connect: {len(users)}")
                return users
            else:
                logger.error(f"Erro ao obter usuários do Connect: {response.status_code}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro na requisição ao Connect: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Erro inesperado ao obter usuários: {str(e)}")
            return []
    
    def clear_cache(self):
        """Limpa o cache de usuários"""
        _users_cache.clear()
        logger.info("Cache de usuários limpo")


# Instância global do serviço
connect_api_service = ConnectAPIService()

