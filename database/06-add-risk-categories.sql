-- ========================================
-- REVISÕES JURÍDICAS - Categorização de Riscos
-- ========================================
-- Este script adiciona o sistema de categorização de riscos
-- 
-- INSTRUÇÕES DE EXECUÇÃO NO PGADMIN:
-- ========================================
-- 1. No pgAdmin, conecte-se ao banco 'revisoes_juridicas_db'
-- 2. Abra Query Tool
-- 3. Execute este script completo
-- ========================================

BEGIN;

SET search_path TO revisoes_juridicas;

-- ========================================
-- 1. Criar Tabela de Categorias de Risco
-- ========================================
CREATE TABLE IF NOT EXISTS risk_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255) NOT NULL
);

COMMENT ON TABLE risk_categories IS 'Categorias de riscos jurídicos para classificação';
COMMENT ON COLUMN risk_categories.name IS 'Nome da categoria de risco';
COMMENT ON COLUMN risk_categories.description IS 'Descrição detalhada da categoria';
COMMENT ON COLUMN risk_categories.created_by IS 'Email do usuário que criou a categoria';

-- ========================================
-- 2. Criar Índices
-- ========================================
CREATE INDEX IF NOT EXISTS idx_risk_categories_name ON risk_categories(name);

-- ========================================
-- 3. Criar Trigger para updated_at
-- ========================================
CREATE TRIGGER update_risk_categories_updated_at BEFORE UPDATE ON risk_categories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- 4. Adicionar coluna category_id na tabela review_risks
-- ========================================
-- Verificar se a coluna já existe antes de adicionar
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'revisoes_juridicas' 
        AND table_name = 'review_risks' 
        AND column_name = 'category_id'
    ) THEN
        ALTER TABLE review_risks 
        ADD COLUMN category_id INTEGER REFERENCES risk_categories(id) ON DELETE SET NULL;
    END IF;
END $$;

COMMENT ON COLUMN review_risks.category_id IS 'Categoria do risco (opcional, NULL = não categorizado)';

-- ========================================
-- 5. Criar Índice para category_id
-- ========================================
CREATE INDEX IF NOT EXISTS idx_review_risks_category_id ON review_risks(category_id);

-- ========================================
-- 6. Inserir Categorias Padrão
-- ========================================
INSERT INTO risk_categories (name, description, created_by) VALUES
('Contratual', 'Riscos relacionados a contratos e obrigações contratuais', 'system'),
('Compliance', 'Riscos de conformidade regulatória e legal', 'system'),
('Trabalhista', 'Riscos relacionados a questões trabalhistas', 'system'),
('Tributário', 'Riscos fiscais e tributários', 'system'),
('Societário', 'Riscos relacionados a estrutura societária', 'system'),
('Propriedade Intelectual', 'Riscos relacionados a PI, marcas e patentes', 'system'),
('Litígio', 'Riscos de processos judiciais', 'system'),
('Outros', 'Outros riscos não categorizados', 'system')
ON CONFLICT (name) DO NOTHING;

-- ========================================
-- 7. Verificação
-- ========================================
SELECT 
    'Tabela risk_categories criada com sucesso' as status,
    COUNT(*) as total_categorias
FROM risk_categories;

SELECT 
    'Coluna category_id adicionada em review_risks' as status,
    COUNT(*) as total_riscos
FROM review_risks;

RESET search_path;

COMMIT;

-- ========================================
-- FIM DO SCRIPT
-- ========================================

