#!/usr/bin/env python3
"""
REVISÕES JURÍDICAS - Script de Execução
Executa a aplicação Flask do Sistema de Revisões Jurídicas
"""

import os
import sys
from app import create_app

if __name__ == '__main__':
    # Configurações parametrizadas via variáveis de ambiente
    port = int(os.environ.get('PORT', 5002))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    print("Iniciando Sistema de Revisões Jurídicas...")
    print("Sistema de Revisão de Documentos Estratégicos")
    print(f"Acesse: http://localhost:{port}")
    print("=" * 50)
    
    try:
        app = create_app()
        app.run(debug=debug, host=host, port=port)
    except KeyboardInterrupt:
        print("\nSistema de Revisões Jurídicas encerrado pelo usuario.")
    except Exception as e:
        print(f"Erro ao iniciar Sistema de Revisões Jurídicas: {e}")
        sys.exit(1)

