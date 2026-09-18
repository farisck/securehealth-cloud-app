-- SecureHealth Cloud — Database Schema
-- Run this once to create the tables the app needs.
-- (See DEPLOY_NOTES.md for how to run this against sqldb-patientrecords.)
-- Includes: column renames from migration_v2.sql, all new columns added
-- since, and the live Always Encrypted setup on diagnoses.diagnosis and
-- clinical_notes.content.

CREATE COLUMN MASTER KEY [CMK_SecureHealth]
WITH (
    KEY_STORE_PROVIDER_NAME = 'AZURE_KEY_VAULT',
    KEY_PATH = 'https://kv-securehealth-faris.vault.azure.net/keys/cmk-securehealth'
);

CREATE COLUMN ENCRYPTION KEY [CEK_SecureHealth]
WITH VALUES (
    COLUMN_MASTER_KEY = [CMK_SecureHealth],
    ALGORITHM = 'RSA_OAEP',
    ENCRYPTED_VALUE = 0x0186000001680074007400700073003a002f002f006b0076002d007300650063007500720065006800650061006c00740068002d00660061007200690073002e007600610075006c0074002e0061007a007500720065002e006e00650074002f006b006500790073002f0063006d006b002d007300650063007500720065006800650061006c007400680055168c544ba85b34369e851c3b60ad26b12dad2bccc19b0ef866cd4e0a15765b64b5152137cda23cfeee529b00fdd0be0bd0069ed2391fdcd16b1a6036c5ccd52baa185743a267847142bcf87e6db74bb0c9fc84e7f25c20e1c10f254a36327e267c9c6ad3b3eb9a39245bd31810b03f950ff0d0aaae6c2924d8ad47ede621cff35b561bd615c51e3b3d4563a307ea941f2432e9f8afb08155efe04bea21f787336c27419894ebcab0c9049e8607c8919090ceff92b2eff435a4eb21d48032296d7407cb8c8ac358c91fb25006c7335b89854015d06c09999a214826e189b0ef989e388dbb6e16599640351bac899f9025b10369a4734e68df1af5b210d19b678483db8c2ece0e7b28767daa5f13f5b75d480672a53f1e13767499d73929cffa773566fa10dbc21daea24b0e53ee4611abb2da942ee012f273fcbb700bb050e9ca4ac22c623dd4ac212d44264c8b0e01db26f03f14000e849db0f352a7de4cb25d7fd617623c71515523fb7355caebf97ddf4cc74007d2b632050feca7096032c2cebbcc6004e13a233e60b8a1f3f361491ca6466f1ebafaa743356cdc7eb0156b4771b14c08ecbc49a3af87c053900fc9df22ee08323fc477043e749c63a849d36695c3a743d7fc4c209378ddf341e0bae73f978bbec7edbe09d40921c4a060340e05ae776b425e71fff2c5d532db2c26a69666d66c94f905c8e6455f9ea603
);

CREATE TABLE patients (
    id                          INT IDENTITY(1,1) PRIMARY KEY,
    first_name                  NVARCHAR(100) NOT NULL,
    last_name                   NVARCHAR(100) NOT NULL,
    date_of_birth               DATE NOT NULL,
    phone                       NVARCHAR(30),
    email                       NVARCHAR(200),
    address                     NVARCHAR(300),
    id_number                   NVARCHAR(50),
    gender                      NVARCHAR(30),
    blood_type                  NVARCHAR(5),
    emergency_contact_name      NVARCHAR(150),
    emergency_contact_phone     NVARCHAR(30),
    allergies                   NVARCHAR(500),
    insurance_provider          NVARCHAR(150),
    insurance_id                NVARCHAR(100),
    created_at                  DATETIME2 DEFAULT SYSUTCDATETIME(),
    updated_at                  DATETIME2
);

CREATE TABLE diagnoses (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    patient_id      INT NOT NULL FOREIGN KEY REFERENCES patients(id) ON DELETE CASCADE,
    diagnosis       NVARCHAR(400) COLLATE Latin1_General_BIN2 NOT NULL
                        ENCRYPTED WITH (
                            COLUMN_ENCRYPTION_KEY = [CEK_SecureHealth],
                            ENCRYPTION_TYPE = DETERMINISTIC,
                            ALGORITHM = 'AEAD_AES_256_CBC_HMAC_SHA_256'
                        ),
    diagnosed_date  DATE NOT NULL,
    status          NVARCHAR(20) NOT NULL DEFAULT 'active', -- 'active' or 'resolved'
    severity        NVARCHAR(20),
    notes           NVARCHAR(1000),
    created_at      DATETIME2 DEFAULT SYSUTCDATETIME(),
    updated_at      DATETIME2
);

CREATE TABLE medications (
    id                      INT IDENTITY(1,1) PRIMARY KEY,
    patient_id              INT NOT NULL FOREIGN KEY REFERENCES patients(id) ON DELETE CASCADE,
    medication_name         NVARCHAR(200) NOT NULL,
    dosage                  NVARCHAR(100),
    frequency               NVARCHAR(100),
    start_date              DATE,
    end_date                DATE,
    prescriber              NVARCHAR(200),
    created_at              DATETIME2 DEFAULT SYSUTCDATETIME(),
    updated_at              DATETIME2
);

CREATE TABLE clinical_notes (
    id            INT IDENTITY(1,1) PRIMARY KEY,
    patient_id    INT NOT NULL FOREIGN KEY REFERENCES patients(id) ON DELETE CASCADE,
    content       NVARCHAR(MAX) COLLATE Latin1_General_BIN2 NOT NULL
                        ENCRYPTED WITH (
                            COLUMN_ENCRYPTION_KEY = [CEK_SecureHealth],
                            ENCRYPTION_TYPE = RANDOMIZED,
                            ALGORITHM = 'AEAD_AES_256_CBC_HMAC_SHA_256'
                        ),
    author        NVARCHAR(200),
    note_type     NVARCHAR(30),
    created_at    DATETIME2 DEFAULT SYSUTCDATETIME(),
    updated_at    DATETIME2
);

CREATE TABLE audit_log (
    id           INT IDENTITY(1,1) PRIMARY KEY,
    action       NVARCHAR(20) NOT NULL,        -- 'CREATE', 'UPDATE', or 'DELETE'
    entity_type  NVARCHAR(50) NOT NULL,        -- 'patient', 'diagnosis', 'medication', 'note'
    entity_id    INT,
    actor        NVARCHAR(200) NOT NULL,       -- signed-in user who performed the action
    details      NVARCHAR(500),
    timestamp    DATETIME2 DEFAULT SYSUTCDATETIME()
);
