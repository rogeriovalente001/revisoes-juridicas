"""
Configurações da aplicação Revisões Jurídicas
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Carregar config.env antes de definir a classe Config
_env_path = Path(__file__).resolve().parent / 'config.env'
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path, override=True)

class Config:
    """Configuração base"""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    TESTING = False
    
    # CSRF Configuration
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_SSL_STRICT = False
    
    # Configurações de Sessão
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = os.environ.get('SESSION_COOKIE_HTTPONLY', 'True').lower() == 'true'
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    PERMANENT_SESSION_LIFETIME = 86400  # 24 horas em segundos
    SESSION_REFRESH_EACH_REQUEST = True
    
    # Configurações do Banco de Dados
    DATABASE_URL = os.environ.get('DATABASE_URL')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '5433')
    DB_NAME = os.environ.get('DB_NAME', 'revisoes_juridicas_db')
    DB_USER = os.environ.get('DB_USER')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    DB_SCHEMA = 'revisoes_juridicas'
    
    # Chave compartilhada para descriptografia de tokens (integração com Connect)
    CONNECT_SECRET_KEY = os.environ.get('CONNECT_SECRET_KEY')
    
    # Configurações de Email
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    # URL do Connect para API
    CONNECT_URL = os.environ.get('CONNECT_URL', 'http://localhost:5001')
    
    # Configurações para URLs externas
    SERVER_NAME = os.environ.get('SERVER_NAME')
    APPLICATION_ROOT = os.environ.get('APPLICATION_ROOT', '/')
    PREFERRED_URL_SCHEME = os.environ.get('PREFERRED_URL_SCHEME', 'http')
    
    # Upload de arquivos
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'reviews')
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'rtf'}
    DANGEROUS_EXTENSIONS = {'exe', 'bat', 'cmd', 'com', 'scr', 'vbs', 'js', 'jar', 'dll', 'msi', 'ps1', 'sh'}

class DevelopmentConfig(Config):
    """Configuração de desenvolvimento"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Configuração de produção"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True

class TestingConfig(Config):
    """Configuração de teste"""
    DEBUG = True
    TESTING = True

# Configuração por ambiente
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

