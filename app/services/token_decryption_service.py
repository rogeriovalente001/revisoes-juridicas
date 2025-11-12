"""
Serviço para descriptografar tokens do Connect
"""

import os
import json
import base64
import logging
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
_env_path = Path(__file__).resolve().parents[2] / 'config.env'
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path, override=True)


class TokenDecryptionService:
    """
    Serviço para descriptografar tokens criptografados recebidos do Connect.
    """
    
    def __init__(self):
        """Inicializa o serviço com a chave secreta do ambiente"""
        self.secret_key = os.getenv('CONNECT_SECRET_KEY')
        if not self.secret_key:
            raise ValueError("CONNECT_SECRET_KEY não encontrada nas variáveis de ambiente")
        
        if len(self.secret_key) < 32:
            raise ValueError("CONNECT_SECRET_KEY deve ter pelo menos 32 caracteres")
        
        # Gerar chave de criptografia a partir da secret key
        self._fernet = self._create_fernet()
    
    def _create_fernet(self):
        """Cria instância Fernet para descriptografia"""
        # Usar a secret key como salt para gerar chave de descriptografia
        salt = self.secret_key.encode()[:16]  # Primeiros 16 bytes como salt
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.secret_key.encode()))
        return Fernet(key)
    
    def decrypt_token(self, token: str) -> dict:
        """
        Descriptografa token recebido do Connect.
        
        Args:
            token (str): Token criptografado em base64
            
        Returns:
            dict: Dados do usuário se válido
            
        Raises:
            ValueError: Se token for inválido ou expirado
        """
        try:
            # Corrigir padding do base64 se necessário
            missing_padding = len(token) % 4
            if missing_padding:
                token = token + '=' * (4 - missing_padding)
            
            # Decodificar base64
            encrypted_data = base64.urlsafe_b64decode(token.encode())
            
            # Descriptografar
            decrypted_data = self._fernet.decrypt(encrypted_data)
            json_data = decrypted_data.decode()
            
            # Converter JSON para dict
            token_data = json.loads(json_data)
            
            # Verificar se token não expirou
            expires_at = datetime.fromisoformat(token_data['expires_at'])
            current_time = datetime.utcnow()
            
            if current_time > expires_at:
                raise ValueError("Token expirado")
            
            return token_data
            
        except Exception as e:
            logger.error(f"Erro ao descriptografar token: {str(e)}", exc_info=True)
            raise ValueError(f"Token inválido: {str(e)}")


# Instância global do serviço
token_decryption_service = TokenDecryptionService()

