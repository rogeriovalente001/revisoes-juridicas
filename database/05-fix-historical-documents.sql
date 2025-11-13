-- Script para copiar documentos anexos para todas as versões de cada documento
-- Este script corrige dados históricos onde documentos anexos não foram copiados para novas versões

-- Para cada documento, copiar os anexos da primeira versão para todas as outras versões
INSERT INTO revisoes_juridicas.review_documents 
    (review_id, file_name, file_path, file_size, uploaded_by, uploaded_at)
WITH document_versions AS (
    SELECT 
        r.document_id,
        r.id as review_id,
        r.version,
        MIN(r.id) OVER (PARTITION BY r.document_id) as first_review_id
    FROM revisoes_juridicas.reviews r
),
documents_to_copy AS (
    SELECT DISTINCT
        dv.review_id as target_review_id,
        rd.file_name,
        rd.file_path,
        rd.file_size,
        rd.uploaded_by,
        rd.uploaded_at
    FROM document_versions dv
    INNER JOIN revisoes_juridicas.review_documents rd ON rd.review_id = dv.first_review_id
    WHERE dv.review_id != dv.first_review_id  -- Não copiar para a primeira versão (já tem)
    AND NOT EXISTS (
        -- Só copiar se ainda não existe
        SELECT 1 
        FROM revisoes_juridicas.review_documents rd2 
        WHERE rd2.review_id = dv.review_id 
        AND rd2.file_name = rd.file_name
    )
)
SELECT 
    target_review_id,
    file_name,
    file_path,
    file_size,
    uploaded_by,
    uploaded_at
FROM documents_to_copy;

