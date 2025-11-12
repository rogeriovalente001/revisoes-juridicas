# Sistema de Revisões Jurídicas

Sistema para revisão jurídica de documentos estratégicos, integrado com o Argo Connect.

## Características

- CRUD completo de revisões jurídicas
- Sistema de versionamento automático
- Controle granular de visualização por usuário
- Sistema de aprovações com histórico completo
- Upload e download de documentos
- Exportação em PDF e DOCX
- Integração com Argo Connect via token

## Requisitos

- Python 3.8+
- PostgreSQL
- Argo Connect rodando (para autenticação)

## Instalação

1. Instalar dependências:
```bash
pip install -r requirements.txt
```

2. Configurar variáveis de ambiente:
```bash
cp env.example config.env
# Editar config.env com suas configurações
```

3. Criar schema e tabelas no banco de dados:
```bash
# Executar scripts SQL na ordem:
# database/01-create-schema.sql
# database/02-create-tables.sql
```

4. Executar aplicação:
```bash
python run.py
```

O sistema estará disponível em `http://localhost:5002`

## Configuração

### Variáveis de Ambiente Importantes

- `SECRET_KEY`: Chave secreta para sessões Flask
- `CONNECT_SECRET_KEY`: Chave compartilhada com Connect (deve ser a mesma)
- `CONNECT_URL`: URL do sistema Connect (padrão: http://localhost:5001)
- `DATABASE_URL`: URL de conexão com PostgreSQL
- `PORT`: Porta do servidor (padrão: 5002)

## Integração com Connect

O sistema recebe tokens do Connect via POST em `/auth/connect` e descriptografa usando a mesma `CONNECT_SECRET_KEY`.

O Connect deve estar configurado com:
- Sistema cadastrado na área "Jurídico"
- Flag `is_sistema_tokenizado = TRUE`
- URL: `http://localhost:5002`

## Estrutura do Projeto

```
projeto_revisoes_juridicas/
├── app/
│   ├── blueprints/      # Rotas da aplicação
│   ├── repositories/    # Acesso a dados
│   ├── services/        # Lógica de negócio
│   └── utils/          # Utilitários
├── database/           # Scripts SQL
├── static/             # Arquivos estáticos
├── templates/          # Templates HTML
└── config.py          # Configurações
```

## Funcionalidades

### Revisões
- Criar, editar, visualizar e excluir revisões
- Versionamento automático
- Histórico de versões

### Controle de Visualização
- Seleção de usuários que podem visualizar cada revisão
- Filtro automático na listagem (não mostra revisões sem permissão)

### Aprovações
- Solicitar aprovação de múltiplos usuários
- Comentário obrigatório na aprovação/rejeição
- Histórico completo de aprovações
- Emails de notificação

### Documentos
- Upload de documentos (PDF, DOC, DOCX, TXT, RTF)
- Validação de segurança (bloqueio de arquivos perigosos)
- Download protegido

### Exportação
- Exportar revisão completa em PDF
- Exportar revisão completa em DOCX

## Segurança

- Validação de tokens do Connect
- Controle de acesso baseado em ações (view, edit, delete)
- Sanitização de inputs
- Validação de arquivos uploadados
- Queries parametrizadas (prevenção SQL injection)

