-- Simplify doc_type to 3 canonical values: document, architecture, code
-- Migrate existing rows before dropping the old constraint

-- Migrate old types: design_doc, api_spec, deployment, config → code
UPDATE design_documents
SET doc_type = 'code'
WHERE doc_type IN ('design_doc', 'api_spec', 'deployment', 'config')
  AND doc_type != 'code';

-- Migrate old types: sop, runbook, troubleshooting, postmortem, onboarding → document
UPDATE design_documents
SET doc_type = 'document'
WHERE doc_type IN ('sop', 'runbook', 'troubleshooting', 'postmortem', 'onboarding')
  AND doc_type != 'document';

-- Drop old broad constraint
ALTER TABLE design_documents DROP CONSTRAINT IF EXISTS ck_design_documents_doc_type;

-- Add new 3-type constraint
ALTER TABLE design_documents
    ADD CONSTRAINT ck_design_documents_doc_type
    CHECK (doc_type = ANY (ARRAY['document'::character varying, 'architecture'::character varying, 'code'::character varying]));
