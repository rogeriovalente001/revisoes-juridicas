-- ========================================
-- REVISÕES JURÍDICAS - Criação das Tabelas
-- ========================================
-- Este script cria todas as tabelas necessárias para o sistema

SET search_path TO revisoes_juridicas;

-- ========================================
-- 1. Tabela de Documentos Estratégicos
-- ========================================
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    summary TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255) NOT NULL
);

COMMENT ON TABLE documents IS 'Documentos estratégicos que serão revisados';
COMMENT ON COLUMN documents.title IS 'Título do documento';
COMMENT ON COLUMN documents.summary IS 'Resumo do documento';
COMMENT ON COLUMN documents.description IS 'Breve descrição do objeto do documento';
COMMENT ON COLUMN documents.created_by IS 'Email do usuário que criou o documento';

-- ========================================
-- 2. Tabela de Revisões
-- ========================================
CREATE TABLE IF NOT EXISTS reviews (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    reviewer_email VARCHAR(255) NOT NULL,
    reviewer_name VARCHAR(255) NOT NULL,
    review_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    comments TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, version)
);

COMMENT ON TABLE reviews IS 'Revisões dos documentos estratégicos';
COMMENT ON COLUMN reviews.version IS 'Versão da revisão (incrementa automaticamente)';
COMMENT ON COLUMN reviews.reviewer_email IS 'Email do revisor';
COMMENT ON COLUMN reviews.reviewer_name IS 'Nome do revisor';
COMMENT ON COLUMN reviews.comments IS 'Comentários da revisão';

-- ========================================
-- 3. Tabela de Riscos Identificados
-- ========================================
CREATE TABLE IF NOT EXISTS review_risks (
    id SERIAL PRIMARY KEY,
    review_id INTEGER NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    risk_text TEXT NOT NULL,
    legal_suggestion TEXT,
    final_definition TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE review_risks IS 'Riscos identificados e tratamento';
COMMENT ON COLUMN review_risks.risk_text IS 'Risco identificado';
COMMENT ON COLUMN review_risks.legal_suggestion IS 'Sugestão do jurídico';
COMMENT ON COLUMN review_risks.final_definition IS 'Definição final';

-- ========================================
-- 4. Tabela de Observações Gerais
-- ========================================
CREATE TABLE IF NOT EXISTS review_observations (
    id SERIAL PRIMARY KEY,
    review_id INTEGER NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    observations TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(review_id)
);

COMMENT ON TABLE review_observations IS 'Observações gerais do jurídico';
COMMENT ON COLUMN review_observations.observations IS 'Comentários adicionais sobre riscos futuros, compliance, ajustes recomendados, etc.';

-- ========================================
-- 5. Tabela de Documentos Anexos
-- ========================================
CREATE TABLE IF NOT EXISTS review_documents (
    id SERIAL PRIMARY KEY,
    review_id INTEGER NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    file_name VARCHAR(500) NOT NULL,
    file_path VARCHAR(1000) NOT NULL,
    file_size BIGINT NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_by VARCHAR(255) NOT NULL
);

COMMENT ON TABLE review_documents IS 'Referências a documentos anexos (armazenados no file server)';
COMMENT ON COLUMN review_documents.file_name IS 'Nome original do arquivo';
COMMENT ON COLUMN review_documents.file_path IS 'Caminho do arquivo no servidor';
COMMENT ON COLUMN review_documents.file_size IS 'Tamanho do arquivo em bytes';
COMMENT ON COLUMN review_documents.uploaded_by IS 'Email do usuário que fez upload';

-- ========================================
-- 6. Tabela de Controle de Visualização
-- ========================================
CREATE TABLE IF NOT EXISTS review_viewers (
    id SERIAL PRIMARY KEY,
    review_id INTEGER NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    user_email VARCHAR(255) NOT NULL,
    can_view BOOLEAN DEFAULT TRUE,
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(review_id, user_email)
);

COMMENT ON TABLE review_viewers IS 'Controle de quais usuários podem visualizar cada revisão';
COMMENT ON COLUMN review_viewers.user_email IS 'Email do usuário que pode visualizar';
COMMENT ON COLUMN review_viewers.can_view IS 'Se o usuário pode visualizar (sempre TRUE quando existe registro)';

-- ========================================
-- 7. Tabela de Aprovações
-- ========================================
CREATE TABLE IF NOT EXISTS review_approvals (
    id SERIAL PRIMARY KEY,
    review_id INTEGER NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    approver_email VARCHAR(255) NOT NULL,
    approver_name VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    approved_at TIMESTAMP,
    comments TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (status IN ('pending', 'approved', 'rejected'))
);

COMMENT ON TABLE review_approvals IS 'Histórico completo de aprovações de cada revisão';
COMMENT ON COLUMN review_approvals.status IS 'Status da aprovação: pending, approved, rejected';
COMMENT ON COLUMN review_approvals.comments IS 'Comentário obrigatório da aprovação';
COMMENT ON COLUMN review_approvals.approved_at IS 'Data/hora da aprovação/rejeição';

-- ========================================
-- 8. Tabela de Solicitações de Aprovação
-- ========================================
CREATE TABLE IF NOT EXISTS review_approval_requests (
    id SERIAL PRIMARY KEY,
    review_id INTEGER NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    requested_by VARCHAR(255) NOT NULL,
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    CHECK (status IN ('pending', 'completed', 'cancelled'))
);

COMMENT ON TABLE review_approval_requests IS 'Solicitações de aprovação de revisões';
COMMENT ON COLUMN review_approval_requests.requested_by IS 'Email do usuário que solicitou aprovação';
COMMENT ON COLUMN review_approval_requests.status IS 'Status da solicitação';

-- ========================================
-- Índices para Performance
-- ========================================

-- Índices para documentos
CREATE INDEX IF NOT EXISTS idx_documents_title ON documents(title);
CREATE INDEX IF NOT EXISTS idx_documents_created_by ON documents(created_by);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);

-- Índices para revisões
CREATE INDEX IF NOT EXISTS idx_reviews_document_id ON reviews(document_id);
CREATE INDEX IF NOT EXISTS idx_reviews_reviewer_email ON reviews(reviewer_email);
CREATE INDEX IF NOT EXISTS idx_reviews_review_date ON reviews(review_date);
CREATE INDEX IF NOT EXISTS idx_reviews_version ON reviews(version);

-- Índices para riscos
CREATE INDEX IF NOT EXISTS idx_review_risks_review_id ON review_risks(review_id);

-- Índices para documentos anexos
CREATE INDEX IF NOT EXISTS idx_review_documents_review_id ON review_documents(review_id);

-- Índices para visualizadores
CREATE INDEX IF NOT EXISTS idx_review_viewers_review_id ON review_viewers(review_id);
CREATE INDEX IF NOT EXISTS idx_review_viewers_user_email ON review_viewers(user_email);

-- Índices para aprovações
CREATE INDEX IF NOT EXISTS idx_review_approvals_review_id ON review_approvals(review_id);
CREATE INDEX IF NOT EXISTS idx_review_approvals_approver_email ON review_approvals(approver_email);
CREATE INDEX IF NOT EXISTS idx_review_approvals_status ON review_approvals(status);
CREATE INDEX IF NOT EXISTS idx_review_approvals_approved_at ON review_approvals(approved_at);

-- Índices para solicitações de aprovação
CREATE INDEX IF NOT EXISTS idx_review_approval_requests_review_id ON review_approval_requests(review_id);
CREATE INDEX IF NOT EXISTS idx_review_approval_requests_status ON review_approval_requests(status);

-- ========================================
-- Função para atualizar updated_at automaticamente
-- ========================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers para updated_at
CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_reviews_updated_at BEFORE UPDATE ON reviews
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_review_risks_updated_at BEFORE UPDATE ON review_risks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_review_observations_updated_at BEFORE UPDATE ON review_observations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- Função para incrementar versão automaticamente
-- ========================================
CREATE OR REPLACE FUNCTION get_next_review_version(p_document_id INTEGER)
RETURNS INTEGER AS $$
DECLARE
    v_max_version INTEGER;
BEGIN
    SELECT COALESCE(MAX(version), 0) INTO v_max_version
    FROM reviews
    WHERE document_id = p_document_id;
    
    RETURN v_max_version + 1;
END;
$$ language 'plpgsql';

COMMENT ON FUNCTION get_next_review_version IS 'Retorna a próxima versão para um documento';

-- Resetar search_path
RESET search_path;

