# Configuração de Autenticação JWT

## Implementação

A autenticação JWT foi implementada para comunicação segura entre o sistema de Revisões Jurídicas e o Connect.

## Arquivos Modificados

### Connect (`projeto_connect`)
1. **`app/utils/jwt_auth.py`** (NOVO)
   - Funções para gerar e validar tokens JWT
   - Decorators: `require_jwt_token`, `require_api_auth`

2. **`app/blueprints/main/api_routes.py`**
   - Endpoint `/api/users` agora aceita JWT token OU sessão
   - Novo endpoint `/api/generate-token` para gerar tokens

3. **`requirements.txt`**
   - Adicionado `PyJWT==2.8.0`

### Sistema Jurídico (`projeto_revisoes_juridicas`)
1. **`app/services/connect_api_service.py`**
   - Método `_generate_jwt_token()` para gerar tokens
   - Uso automático de JWT nas requisições à API

2. **`requirements.txt`**
   - Adicionado `PyJWT==2.8.0`

## Configuração

### 1. Instalar dependências

**No Connect:**
```bash
pip install PyJWT==2.8.0
```

**No Sistema Jurídico:**
```bash
pip install PyJWT==2.8.0
```

### 2. Configurar variáveis de ambiente

**No Connect (`config.env`):**
```env
# Secret para assinar tokens JWT (use o mesmo SECRET_KEY ou um específico)
JWT_SECRET=sua_chave_secreta_aqui
# OU usar SECRET_KEY existente (será usado como fallback)
```

**No Sistema Jurídico (`config.env`):**
```env
# Secret para gerar tokens (deve ser o MESMO do Connect)
JWT_SECRET=sua_chave_secreta_aqui
# OU usar SECRET_KEY existente (será usado como fallback)

# Opcional: Token JWT fixo pré-gerado (se não quiser gerar automaticamente)
# CONNECT_API_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGc...
```

### 3. Gerar token (Opcional)

Se quiser usar um token fixo pré-gerado:

1. Acesse o Connect autenticado
2. Faça POST para `/api/generate-token`:
```bash
curl -X POST http://localhost:5001/api/generate-token \
  -H "Content-Type: application/json" \
  -d '{"service": "revisoes_juridicas", "expires_days": 365}' \
  --cookie "session=..."
```

3. Copie o token retornado e configure em `CONNECT_API_TOKEN` no sistema jurídico

## Como Funciona

### Fluxo Automático (Recomendado)

1. Sistema jurídico gera token JWT automaticamente usando `JWT_SECRET`
2. Token é enviado no header: `Authorization: Bearer <token>`
3. Connect valida o token usando o mesmo `JWT_SECRET`
4. Se válido, permite acesso à API

### Fluxo com Token Fixo

1. Configure `CONNECT_API_TOKEN` no sistema jurídico
2. Sistema usa esse token diretamente (não gera novo)
3. Útil para tokens pré-gerados ou renovação manual

## Segurança

- ✅ Tokens assinados com algoritmo HS256
- ✅ Validação de expiração automática
- ✅ Validação de issuer (`argo_connect`)
- ✅ Validação de tipo (`service_token`)
- ✅ Cache de tokens (evita regeneração desnecessária)
- ✅ Fallback para sessão Flask-Login (compatibilidade)

## Troubleshooting

### Erro: "Invalid token"
- Verifique se `JWT_SECRET` é o mesmo em ambos os sistemas
- Verifique se o token não expirou
- Verifique logs para detalhes

### Erro: "Token not provided"
- Verifique se o header `Authorization: Bearer <token>` está sendo enviado
- Verifique logs do sistema jurídico para ver se o token está sendo gerado

### Lista de usuários vazia
- Verifique se o Connect está acessível
- Verifique logs de autenticação
- O sistema tenta primeiro banco de dados, depois API HTTP

## Logs

Os logs mostram:
- Geração de tokens
- Validação de tokens
- Erros de autenticação
- Método de autenticação usado (JWT ou sessão)

