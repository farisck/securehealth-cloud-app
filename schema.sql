-- SecureHealth Cloud — Database Schema
-- Run this once to create the tables the app needs.
-- (See DEPLOY_NOTES.md for how to run this against sqldb-patientrecords.)

CREATE TABLE patients (
    patient_id      INT IDENTITY(1,1) PRIMARY KEY,
    first_name      NVARCHAR(100) NOT NULL,
    last_name       NVARCHAR(100) NOT NULL,
    date_of_birth   DATE NOT NULL,
    phone           NVARCHAR(30),
    email           NVARCHAR(200),
    address         NVARCHAR(300),
    created_at      DATETIME2 DEFAULT SYSUTCDATETIME()
);

CREATE TABLE diagnoses (
    diagnosis_id    INT IDENTITY(1,1) PRIMARY KEY,
    patient_id      INT NOT NULL FOREIGN KEY REFERENCES patients(patient_id) ON DELETE CASCADE,
    condition_name  NVARCHAR(200) NOT NULL,
    diagnosed_date  DATE NOT NULL,
    status          NVARCHAR(20) NOT NULL DEFAULT 'active', -- 'active' or 'resolved'
    notes           NVARCHAR(1000),
    created_at      DATETIME2 DEFAULT SYSUTCDATETIME()
);

CREATE TABLE medications (
    medication_id           INT IDENTITY(1,1) PRIMARY KEY,
    patient_id              INT NOT NULL FOREIGN KEY REFERENCES patients(patient_id) ON DELETE CASCADE,
    medication_name         NVARCHAR(200) NOT NULL,
    dosage                  NVARCHAR(100),
    frequency               NVARCHAR(100),
    start_date              DATE,
    end_date                DATE,
    prescribing_clinician   NVARCHAR(200),
    created_at              DATETIME2 DEFAULT SYSUTCDATETIME()
);

CREATE TABLE clinical_notes (
    note_id       INT IDENTITY(1,1) PRIMARY KEY,
    patient_id    INT NOT NULL FOREIGN KEY REFERENCES patients(patient_id) ON DELETE CASCADE,
    note_text     NVARCHAR(MAX) NOT NULL,
    created_by    NVARCHAR(200),
    created_at    DATETIME2 DEFAULT SYSUTCDATETIME()
);
