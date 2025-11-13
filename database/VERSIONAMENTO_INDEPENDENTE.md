# Versionamento Independente - Explicação

## 📋 Conceito

Cada documento agora terá **3 versões independentes**:

### 1. **document_version** (Versão do Documento)
- Incrementa **sempre** que qualquer alteração for feita
- Exemplos: título, descrição, observações, comentários, riscos

### 2. **review_version** (Versão de Revisões/Comentários)
- Incrementa **apenas** quando novos comentários de revisão forem adicionados
- Fica parada se não houver novos comentários

### 3. **risk_version** (Versão de Riscos)
- Incrementa **apenas** quando novos riscos forem adicionados
- Fica parada se não houver novos riscos

---

## 🔄 Exemplos de Versionamento

### Situação Inicial
```
Documento V1, Revisão V1, Risco V1
```

### Cenário 1: Alterar apenas o título
```
ANTES: Documento V1, Revisão V1, Risco V1
DEPOIS: Documento V2, Revisão V1, Risco V1
```

### Cenário 2: Adicionar novo comentário
```
ANTES: Documento V2, Revisão V1, Risco V1
DEPOIS: Documento V3, Revisão V2, Risco V1
```

### Cenário 3: Adicionar novo risco
```
ANTES: Documento V3, Revisão V2, Risco V1
DEPOIS: Documento V4, Revisão V2, Risco V2
```

### Cenário 4: Adicionar comentário E risco
```
ANTES: Documento V4, Revisão V2, Risco V2
DEPOIS: Documento V5, Revisão V3, Risco V3
```

---

## 🗄️ Estrutura do Banco

### Tabela `documents` (NOVA ESTRUTURA)
```sql
- id
- title
- description
- document_version  ← NOVO (versão geral)
- review_version    ← NOVO (última versão com comentários)
- risk_version      ← NOVO (última versão com riscos)
- created_at
- updated_at
```

### Tabela `reviews` (MANTÉM)
```sql
- id
- document_id
- version           ← Versão geral do documento naquele momento
- reviewer_email
- reviewer_name
- review_date
- comments
```

### Tabela `review_comments` (MANTÉM)
```sql
- id
- review_id         ← Vinculado à versão do documento
- reviewer_email
- reviewer_name
- review_date
- comments
```

### Tabela `review_risks` (MANTÉM)
```sql
- id
- review_id         ← Vinculado à versão do documento
- risk_text
- legal_suggestion
- final_definition
```

---

## 🔧 Funções SQL Criadas

### 1. `increment_document_version(document_id)`
- Incrementa apenas a versão geral do documento
- Usado quando: título, descrição ou observações mudam

### 2. `increment_review_version(document_id)`
- Incrementa a versão de revisão E a versão do documento
- Usado quando: novos comentários são adicionados

### 3. `increment_risk_version(document_id)`
- Incrementa a versão de risco E a versão do documento
- Usado quando: novos riscos são adicionados

---

## 📊 Exibição nos Históricos

### Histórico de Revisões
Mostra todas as versões do documento, mas destaca apenas as que têm comentários:
```
V5 - Rogerio - 13/11/2025 - [2 comentários]  ← review_version = 3
V4 - Rogerio - 13/11/2025 - Nenhum comentário
V3 - Rogerio - 13/11/2025 - [1 comentário]   ← review_version = 2
V2 - Rogerio - 13/11/2025 - Nenhum comentário
V1 - Rogerio - 13/11/2025 - [1 comentário]   ← review_version = 1
```

### Histórico de Riscos
Mostra todas as versões do documento, mas destaca apenas as que têm riscos:
```
V5 - [1 risco]          ← risk_version = 2
V4 - Nenhum risco
V3 - Nenhum risco
V2 - [2 riscos]         ← risk_version = 1
V1 - Nenhum risco
```

---

## ⚙️ Próximos Passos

1. ✅ Executar o script SQL no pgAdmin
2. ⏳ Modificar o código Python para usar as novas funções
3. ⏳ Atualizar a interface para mostrar as 3 versões
4. ⏳ Testar todos os cenários

---

## 🧪 Como Testar

Após implementação completa:

1. Criar documento → V1, R0, K0
2. Adicionar comentário → V2, R1, K0
3. Alterar título → V3, R1, K0
4. Adicionar risco → V4, R1, K1
5. Adicionar comentário e risco → V5, R2, K2

Onde:
- V = document_version
- R = review_version
- K = risk_version

