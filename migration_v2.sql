-- SecureHealth Cloud — Migration v2
-- Run this on the JUMPBOX against the EXISTING database.
--
-- This reconciles the schema with the upgraded app.py (which was built
-- against slightly different column names). It renames a few existing
-- columns and adds new ones — no data is deleted, your existing test
-- patient is preserved.

-- ── Rename primary keys to `id` (what the new app.py expects) ──────────
EXEC sp_rename 'patients.patient_id', 'id', 'COLUMN';
EXEC sp_rename 'diagnoses.diagnosis_id', 'id', 'COLUMN';
EXEC sp_rename 'medications.medication_id', 'id', 'COLUMN';
EXEC sp_rename 'clinical_notes.note_id', 'id', 'COLUMN';

-- ── Rename business columns to match the new app.py ─────────────────────
EXEC sp_rename 'diagnoses.condition_name', 'diagnosis', 'COLUMN';
EXEC sp_rename 'medications.prescribing_clinician', 'prescriber', 'COLUMN';
EXEC sp_rename 'clinical_notes.note_text', 'content', 'COLUMN';
EXEC sp_rename 'clinical_notes.created_by', 'author', 'COLUMN';

-- ── New patient fields ───────────────────────────────────────────────────
ALTER TABLE patients ADD id_number NVARCHAR(50);
ALTER TABLE patients ADD gender NVARCHAR(30);
ALTER TABLE patients ADD blood_type NVARCHAR(5);
ALTER TABLE patients ADD emergency_contact_name NVARCHAR(150);
ALTER TABLE patients ADD emergency_contact_phone NVARCHAR(30);
ALTER TABLE patients ADD allergies NVARCHAR(500);
ALTER TABLE patients ADD insurance_provider NVARCHAR(150);
ALTER TABLE patients ADD insurance_id NVARCHAR(100);
ALTER TABLE patients ADD updated_at DATETIME2;

-- ── New fields the upgraded app.py needs on other tables ────────────────
ALTER TABLE diagnoses ADD severity NVARCHAR(20);
ALTER TABLE diagnoses ADD updated_at DATETIME2;

ALTER TABLE medications ADD updated_at DATETIME2;

ALTER TABLE clinical_notes ADD note_type NVARCHAR(30);
ALTER TABLE clinical_notes ADD updated_at DATETIME2;

-- ── Audit trail table (column names matched to the new app.py) ─────────
CREATE TABLE audit_log (
    id           INT IDENTITY(1,1) PRIMARY KEY,
    action       NVARCHAR(20) NOT NULL,        -- 'CREATE', 'UPDATE', or 'DELETE'
    entity_type  NVARCHAR(50) NOT NULL,        -- 'patient', 'diagnosis', 'medication', 'note'
    entity_id    INT,
    actor        NVARCHAR(200) NOT NULL,       -- signed-in user who performed the action
    details      NVARCHAR(500),
    timestamp    DATETIME2 DEFAULT SYSUTCDATETIME()
);
