# SecureHealth Cloud

## A Privacy-Focused Patient Records Platform on Microsoft Azure

SecureHealth Cloud is a privacy-focused healthcare records web application developed as a Cloud Computing Capstone Project on Microsoft Azure.

The application allows authorized hospital staff to authenticate, look up patients, and view patient records. The main focus of the project is not only the application itself, but also the security controls surrounding identity, networking, secrets, data protection, monitoring, compliance, and recovery.

> **Note:** This project uses synthetic test records only and does not contain real patient/PHI data.

---

## Project Overview

SecureHealth Cloud was designed around a layered security approach.

The application uses Microsoft Entra ID for identity and Security Defaults for multi-factor authentication. The application is hosted on Azure App Service and connects to an Azure SQL Database through a private Azure networking architecture.

The database has public network access disabled and is accessed through a Private Endpoint. Network Security Groups are used to control network traffic between the application and data components.

Sensitive information is protected using encryption, with Azure Key Vault used for key and secret management. Application access to Azure resources uses Managed Identity rather than relying on hard-coded credentials.

Monitoring and security operations use Azure Monitor, Log Analytics, Microsoft Defender, KQL-based detection, and Azure Policy. Azure SQL automated backups and Point-in-Time Restore provide database recovery capabilities.

---

## Architecture

```text
                    Hospital Staff
                          |
                          v
                 Microsoft Entra ID
                          |
                          v
               Security Defaults / MFA
                          |
                          v
                 Azure App Service
              Python + Flask + Gunicorn
                          |
                    VNet Integration
                          |
                          v
              +-----------------------+
              |   Azure Virtual       |
              |      Network          |
              |                       |
              |  +----------------+   |
              |  | App Subnet     |   |
              |  +----------------+   |
              |          |            |
              |       NSGs            |
              |          |            |
              |  +----------------+   |
              |  | Private        |   |
              |  | Endpoint       |   |
              |  +----------------+   |
              |          |            |
              |  +----------------+   |
              |  | Data Subnet    |   |
              |  +----------------+   |
              +----------|------------+
                         |
                         v
                  Azure SQL Database
                         |
              +----------+----------+
              |                     |
             TDE            Always Encrypted
                                   |
                                   v
                             Azure Key Vault

     Monitoring / Security
     ---------------------
     Azure Monitor
          |
     Log Analytics
          |
         KQL
          |
     Microsoft Defender

     Governance
     -----------
     Azure Policy

     Recovery
     --------
     Azure SQL Automated Backup
          |
     Point-in-Time Restore
````

---

## Azure Services Used

| Azure Service / Technology            | Purpose                                                      |
| ------------------------------------- | ------------------------------------------------------------ |
| **Microsoft Entra ID**                | User identity and authentication                             |
| **Security Defaults**                 | Baseline identity protection and MFA                         |
| **Azure App Service**                 | Hosts the Flask web application                              |
| **Azure Virtual Network**             | Provides the private network boundary                        |
| **Subnets**                           | Separates application, data, and integration networking      |
| **Network Security Groups**           | Controls network traffic                                     |
| **VNet Integration**                  | Connects App Service to the VNet                             |
| **Private Endpoint**                  | Provides private connectivity to Azure SQL                   |
| **Private DNS**                       | Resolves the SQL hostname to private connectivity            |
| **Azure SQL Database**                | Stores patient records                                       |
| **Azure Key Vault**                   | Stores and manages secrets and encryption keys               |
| **Managed Identity**                  | Provides application identity without hard-coded credentials |
| **Transparent Data Encryption (TDE)** | Protects SQL data at rest                                    |
| **Always Encrypted**                  | Protects highly sensitive database columns                   |
| **Azure Monitor**                     | Monitoring and telemetry                                     |
| **Log Analytics**                     | Centralized log and telemetry analysis                       |
| **KQL**                               | Query and detection analysis                                 |
| **Microsoft Defender**                | Security monitoring and incident management                  |
| **Azure Policy**                      | Configuration and compliance monitoring                      |
| **Azure SQL Automated Backups**       | Database backup and recovery                                 |
| **Point-in-Time Restore**             | Recovery to an earlier database state                        |
| **Bicep / Azure CLI**                 | Infrastructure-as-code and deployment validation             |

---

## Application Stack

The web application uses:

* **Python 3.12**
* **Flask**
* **Gunicorn**
* **Azure App Service**
* **Azure SQL Database**
* **pyodbc**

### Python

Python is the programming language used to implement the application backend.

### Flask

Flask is the lightweight Python web framework used to build the web application and handle application routes and backend logic.

### Gunicorn

Gunicorn is the production WSGI web server used to run and serve the Flask application on Azure App Service.

---

## Network Architecture

The project uses the following VNet:

```text
VNet: vnet-securehealth
Address Space: 10.0.0.0/16
```

### Subnets

```text
Application Subnet
10.0.1.0/24

Data Subnet
10.0.2.0/24

Integration Subnet
10.0.3.0/24
```

The integration subnet is delegated for App Service VNet Integration.

The data subnet contains the SQL Private Endpoint.

### Private Database Access

The Azure SQL Database has public network access disabled.

The application accesses the database through:

```text
App Service
    |
VNet Integration
    |
VNet
    |
Private Endpoint
    |
Azure SQL Database
```

This prevents the database from being directly accessible through a public network endpoint.

---

## Identity and Access Security

### Microsoft Entra ID

Microsoft Entra ID provides authentication for application users.

### Security Defaults

Security Defaults are used to enforce baseline identity protections, including multi-factor authentication.

### Managed Identity

The App Service uses a system-assigned Managed Identity.

This allows the application to authenticate to Azure resources without storing credentials directly in application code.

### Azure RBAC

Role-based access control is used to provide the required permissions to identities and Azure resources.

### SQL Authentication

The SQL server is configured for Microsoft Entra-only authentication, with SQL username/password authentication disabled.

---

## Data Protection

The project uses multiple layers of database protection.

### Transparent Data Encryption

TDE protects the Azure SQL Database and underlying storage at rest.

### Always Encrypted

Always Encrypted provides additional protection for particularly sensitive patient columns, including:

* Diagnoses
* Clinical notes

The encryption key is managed through Azure Key Vault.

### Why Both?

TDE and Always Encrypted protect different layers:

```text
TDE
 |
 +-- Protects database/storage at rest


Always Encrypted
 |
 +-- Protects selected sensitive columns
```

Using both provides layered data protection.

---

## Azure Key Vault

Azure Key Vault is used for secure management of sensitive secrets and encryption keys.

The project avoids placing sensitive credentials or encryption material directly inside the application source code.

The App Service Managed Identity is used for controlled access to Azure resources.

---

## Monitoring and Security Operations

The project uses Azure Monitor and Log Analytics for collecting and analyzing telemetry.

```text
Azure Resources
       |
       v
Azure Monitor
       |
       v
Log Analytics
       |
       v
KQL Analysis
       |
       v
Security Detection
       |
       v
Microsoft Defender
```

### Failed Login Detection

A KQL-based analytics rule named:

```text
Repeated-Failed-Login-Attempt
```

was configured to detect repeated failed login activity from application telemetry.

The testing flow was:

```text
Multiple Invalid Login Attempts
            |
            v
Application Telemetry
            |
            v
Log Analytics
            |
            v
KQL Analytics Rule
            |
            v
Microsoft Defender
            |
            v
Security Incident
```

The test generated a medium-severity security incident for investigation.

---

## Azure Policy

A custom Azure Policy was used to monitor SQL network configuration.

Policy:

```text
Audit SQL public network access disabled
```

The policy uses **Audit** mode.

It detects and reports a non-compliant configuration rather than automatically blocking the change.

### Policy Test

The database public network access was temporarily enabled during testing.

Azure Policy detected the configuration as non-compliant.

Public network access was then disabled again, returning the configuration to compliance.

---

## Backup and Recovery

Azure SQL automated backups provide database recovery capabilities.

The project uses:

**Point-in-Time Restore (PITR)**

This allows the database to be restored to an appropriate point within the available restore window.

The project verified the active restore window and tested the restore workflow by configuring restoration to a target database.

---

## Application Features

The application provides a healthcare staff portal with functionality including:

* User authentication
* Role-based access control
* Patient lookup
* Patient record viewing
* Patient record management
* Audit logging
* Role-restricted dashboard information
* Security-focused application access controls

The application records audit activity for actions involving patient records.

---

## Security Controls

The main security controls implemented in the project include:

* Microsoft Entra ID authentication
* Security Defaults and MFA
* Role-based access control
* Managed Identity
* Azure RBAC
* Azure Key Vault
* Azure Virtual Network
* Network segmentation
* Network Security Groups
* Private Endpoint
* Private DNS
* SQL public network access disabled
* Microsoft Entra-only SQL authentication
* TLS for data in transit
* Transparent Data Encryption
* Always Encrypted
* Azure Monitor
* Log Analytics
* KQL-based detection
* Microsoft Defender
* Azure Policy
* Azure SQL automated backups
* Point-in-Time Restore
* Audit logging

---

## Testing and Validation

Several security and operational controls were tested.

### 1. Normal Application Access

Verified that an authorized user could authenticate and retrieve a patient record through the application.

### 2. Database Network Isolation

An external SQL connection attempt was tested.

The connection was refused because public SQL access was disabled and the database required private connectivity.

### 3. Failed Login Detection

Repeated invalid login attempts were generated.

The activity was ingested into Log Analytics and detected using the KQL analytics rule, resulting in a security incident in Microsoft Defender.

### 4. Azure Policy Compliance

SQL public network access was temporarily enabled.

Azure Policy detected the configuration as non-compliant.

The configuration was restored and compliance returned to 100%.

### 5. Database Recovery

The Azure SQL restore window and Point-in-Time Restore workflow were tested successfully.

### 6. Infrastructure-as-Code Validation

A Bicep representation of the infrastructure was created and validated using Azure CLI.

The Bicep template provides a documented infrastructure-as-code approach for future deployment.

---

## Infrastructure as Code

The infrastructure was initially created through Azure Portal and CLI workflows.

A Bicep template was subsequently created to document the infrastructure as code.

Azure CLI validation was used to verify the template.

The Bicep approach is intended to make future deployments more repeatable.

> **Current limitation:** The project did not perform a complete independent end-to-end rebuild of the environment from the Bicep template in a separate environment.

---

## Cost Optimization

The project was designed as a development/capstone environment with cost-conscious service selections.

Examples include:

* Azure App Service B1
* Azure SQL General Purpose Serverless
* 1 vCore
* Standard Azure Key Vault usage
* Controlled Log Analytics usage

### Budget

```text
Monthly Budget: $200
Evaluated Spend: $96.29
Forecast: $106.72
```

Budget alerts were configured at:

```text
50%  → $100
80%  → $160
100% → $200
```

The project was kept within the planned development budget during evaluation.

---

## Limitations

The project was developed as a cloud computing capstone and development environment rather than a production healthcare platform.

Current limitations include:

* No formal HIPAA audit or certification
* No tested high-availability/failover architecture
* No production CI/CD pipeline
* No WAF or Azure Front Door
* Some infrastructure setup remains outside the Bicep template
* Bicep was validated but not independently used for a complete end-to-end environment rebuild
* Cost-driven Azure service tiers
* Synthetic patient data only
* Some subscription-level administrative access remains broader than ideal for a real enterprise environment

---

## Future Improvements

Possible future improvements include:

* Azure Front Door with Web Application Firewall
* Additional Private Endpoints
* Just-in-Time RBAC
* Automated Microsoft Defender response playbooks
* CI/CD integration for Bicep
* More advanced database auditing
* Data masking
* Stronger production-grade high availability
* More granular enterprise role separation

---

## Project Structure

```text
securehealth-cloud-app/
│
├── app.py
├── rbac.py
├── requirements.txt
├── schema.sql
├── migration_v2.sql
├── DEPLOY_NOTES.md
├── README.md
│
├── static/
│   ├── app.js
│   └── style.css
│
└── templates/
    ├── 403.html
    ├── audit_log.html
    ├── base.html
    ├── dashboard.html
    ├── patients.html
    ├── patient_detail.html
    ├── patient_form.html
    └── record_form.html
```

---

## Deployment Environment

```text
Cloud Platform: Microsoft Azure
Environment: Development
Resource Group: rg-securehealth-dev
Region: South Africa North
```

### Main Azure Resources

```text
App Service:
app-securehealth-faris

Azure SQL Server:
sql-securehealth-faris

Azure SQL Database:
sqldb-patientrecords

Virtual Network:
vnet-securehealth

Log Analytics Workspace:
law-securehealth

Private Endpoint:
pe-sqldb-patientrecords
```

---

## Security Design Summary

The project follows a layered security approach:

```text
Identity
   ↓
Microsoft Entra ID + MFA
   ↓
Application
   ↓
App Service + Flask + Gunicorn
   ↓
Network
   ↓
VNet + Subnets + NSGs
   ↓
Private Connectivity
   ↓
Private Endpoint + Private DNS
   ↓
Database
   ↓
Azure SQL
   ↓
Data Protection
   ↓
TDE + Always Encrypted + Key Vault
   ↓
Monitoring
   ↓
Azure Monitor + Log Analytics + Microsoft Defender
   ↓
Governance
   ↓
Azure Policy
   ↓
Recovery
   ↓
Automated Backup + Point-in-Time Restore
```

The goal is to ensure that a failure or mistake in one security layer does not automatically expose the patient records.

---

## Project Goals

The project demonstrates practical implementation of:

* Cloud application deployment
* Azure networking
* Identity and access management
* Database security
* Encryption
* Secret and key management
* Security monitoring
* Compliance monitoring
* Backup and recovery
* Infrastructure as code
* Cloud cost management

---

## Author

**Faris K**

Cloud Computing Capstone Project

**Cloud Platform:** Microsoft Azure

**Project:** SecureHealth Cloud

**Date:** September 2026

---

## Disclaimer

SecureHealth Cloud is an educational cloud computing capstone project.

It is designed to demonstrate secure cloud architecture and implementation concepts using Microsoft Azure.

The application uses synthetic test data and is **not intended to be used as a production healthcare or clinical system**.

```
