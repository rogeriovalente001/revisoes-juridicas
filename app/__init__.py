import os
from flask import Flask
from config import Config
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis do arquivo config.env
_env_path = Path(__file__).resolve().parents[1] / 'config.env'
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path, override=True)


def create_app(config_object: type[Config] | None = None) -> Flask:
    """Application factory to create and configure the Flask app."""
    base_templates = os.path.join(os.path.dirname(__file__), '..', 'templates')
    base_static = os.path.join(os.path.dirname(__file__), '..', 'static')

    app = Flask(__name__, template_folder=base_templates, static_folder=base_static)

    if config_object is None:
        config_object = Config
    app.config.from_object(config_object)
    
    # Validar SECRET_KEY após carregar configuração
    secret_key = app.config.get('SECRET_KEY')
    if not secret_key:
        _env_path = Path(__file__).resolve().parents[1] / 'config.env'
        raise ValueError(
            f"SECRET_KEY não encontrada. "
            f"Configure SECRET_KEY no arquivo config.env ({_env_path}) ou como variável de ambiente."
        )
    if len(secret_key) < 32:
        raise ValueError(
            f"SECRET_KEY deve ter pelo menos 32 caracteres. "
            f"Tamanho atual: {len(secret_key)} caracteres."
        )
    
    # Validar CONNECT_SECRET_KEY
    connect_secret_key = app.config.get('CONNECT_SECRET_KEY')
    if not connect_secret_key:
        raise ValueError("CONNECT_SECRET_KEY não encontrada. Configure no arquivo config.env.")
    if len(connect_secret_key) < 32:
        raise ValueError("CONNECT_SECRET_KEY deve ter pelo menos 32 caracteres.")
    
    # Configurações de Sessão
    from datetime import timedelta
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    app.config['SESSION_COOKIE_SAMESITE'] = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    app.config['SESSION_COOKIE_NAME'] = 'revisoes_juridicas_session'

    # Init extensions
    from .extensions import login_manager
    login_manager.init_app(app)
    login_manager.login_view = 'auth.connect_auth'
    # Desabilitar mensagem automática do Flask-Login para não interferir no fluxo do Connect
    login_manager.login_message = None
    login_manager.login_message_category = None
    
    # Configurar CSRF protection
    from flask_wtf.csrf import CSRFProtect
    csrf = CSRFProtect(app)
    
    # User loader registration
    from .models import load_user  # noqa: F401

    # Register blueprints
    from .blueprints.auth.routes import bp as auth_bp, connect_auth
    from .blueprints.reviews.routes import bp as reviews_bp
    from .blueprints.documents.routes import bp as documents_bp
    from .blueprints.settings.routes import bp as settings_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(reviews_bp, url_prefix='/reviews')
    app.register_blueprint(documents_bp, url_prefix='/documents')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    
    # Exempt rota de autenticação do Connect (recebe tokens de sistemas externos)
    # Esta rota precisa estar isenta de CSRF pois recebe requisições do Connect
    csrf.exempt(connect_auth)
    
    # Rota de health check para validação do Connect
    @app.route('/health')
    def health_check():
        """Health check endpoint para validação do Connect"""
        from flask import jsonify
        return jsonify({'status': 'ok', 'service': 'revisoes_juridicas'}), 200
    
    # Rota raiz - redirecionar para login
    @app.route('/')
    def root():
        from flask import redirect, url_for
        from flask_login import current_user
        if current_user and current_user.is_authenticated:
            return redirect(url_for('reviews.dashboard'))
        return redirect(url_for('auth.connect_auth'))
    
    # Security headers
    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Disable cache in development
        if app.config.get('DEBUG'):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        
        return response
    
    # Template helpers
    @app.context_processor
    def inject_user():
        from flask_login import current_user
        if current_user and current_user.is_authenticated:
            return {
                'current_user': current_user,
                'user_name': current_user.name,
                'user_email': current_user.email
            }
        return {'current_user': None, 'user_name': None, 'user_email': None}
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        from flask import render_template
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template
        return render_template('errors/500.html'), 500
    
    return app

