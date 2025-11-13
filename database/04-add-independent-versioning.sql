-- Script para adicionar versionamento independente
-- Adiciona campos para controlar versões de documento, revisões e riscos separadamente

-- 1. Adicionar novos campos de versão na tabela documents
ALTER TABLE revisoes_juridicas.documents 
ADD COLUMN IF NOT EXISTS document_version INTEGER DEFAULT 1,
ADD COLUMN IF NOT EXISTS review_version INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS risk_version INTEGER DEFAULT 0;

-- 2. Criar índices para melhor performance
CREATE INDEX IF NOT EXISTS idx_documents_versions 
ON revisoes_juridicas.documents(document_version, review_version, risk_version);

-- 3. Inicializar versões baseado nos dados existentes
-- Para cada documento, pegar a versão máxima atual da tabela reviews
UPDATE revisoes_juridicas.documents d
SET 
    document_version = COALESCE((
        SELECT MAX(r.version) 
        FROM revisoes_juridicas.reviews r 
        WHERE r.document_id = d.id
    ), 1),
    review_version = COALESCE((
        SELECT MAX(r.version) 
        FROM revisoes_juridicas.reviews r 
        WHERE r.document_id = d.id
        AND EXISTS (
            SELECT 1 FROM revisoes_juridicas.review_comments rc 
            WHERE rc.review_id = r.id
        )
    ), 0),
    risk_version = COALESCE((
        SELECT MAX(r.version) 
        FROM revisoes_juridicas.reviews r 
        WHERE r.document_id = d.id
        AND EXISTS (
            SELECT 1 FROM revisoes_juridicas.review_risks rr 
            WHERE rr.review_id = r.id
        )
    ), 0);

-- 4. Adicionar comentário explicativo
COMMENT ON COLUMN revisoes_juridicas.documents.document_version IS 'Versão geral do documento - incrementa a cada alteração';
COMMENT ON COLUMN revisoes_juridicas.documents.review_version IS 'Última versão onde comentários de revisão foram adicionados';
COMMENT ON COLUMN revisoes_juridicas.documents.risk_version IS 'Última versão onde riscos foram adicionados';

-- 5. Criar função para incrementar versão do documento
CREATE OR REPLACE FUNCTION revisoes_juridicas.increment_document_version(p_document_id INTEGER)
RETURNS INTEGER AS $$
DECLARE
    v_new_version INTEGER;
BEGIN
    UPDATE revisoes_juridicas.documents
    SET document_version = document_version + 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_document_id
    RETURNING document_version INTO v_new_version;
    
    RETURN v_new_version;
END;
$$ LANGUAGE plpgsql;

-- 6. Criar função para incrementar versão de revisão
CREATE OR REPLACE FUNCTION revisoes_juridicas.increment_review_version(p_document_id INTEGER)
RETURNS INTEGER AS $$
DECLARE
    v_new_version INTEGER;
BEGIN
    UPDATE revisoes_juridicas.documents
    SET review_version = review_version + 1,
        document_version = document_version + 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_document_id
    RETURNING review_version INTO v_new_version;
    
    RETURN v_new_version;
END;
$$ LANGUAGE plpgsql;

-- 7. Criar função para incrementar versão de risco
CREATE OR REPLACE FUNCTION revisoes_juridicas.increment_risk_version(p_document_id INTEGER)
RETURNS INTEGER AS $$
DECLARE
    v_new_version INTEGER;
BEGIN
    UPDATE revisoes_juridicas.documents
    SET risk_version = risk_version + 1,
        document_version = document_version + 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_document_id
    RETURNING risk_version INTO v_new_version;
    
    RETURN v_new_version;
END;
$$ LANGUAGE plpgsql;

-- 8. Verificação final
SELECT 
    d.id,
    d.title,
    d.document_version,
    d.review_version,
    d.risk_version,
    (SELECT COUNT(*) FROM revisoes_juridicas.reviews r WHERE r.document_id = d.id) as total_reviews
FROM revisoes_juridicas.documents d
ORDER BY d.id;

