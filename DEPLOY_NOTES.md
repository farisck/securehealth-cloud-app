# Deploying the Patient Records App

This app has grown from the small connectivity test into the real
patient records system: patients, diagnoses, medications, and clinical notes.

## What's new since the last deploy

- `schema.sql` — creates the 4 database tables the app needs. **You need to run
  this once before the app will work**, because right now those tables don't
  exist yet in `sqldb-patientrecords`.
- `app.py` — now a full app with pages for viewing patients, adding patients,
  and adding/removing diagnoses, medications, and notes.
- `templates/` and `static/style.css` — the actual visual design (pages and styling).

## Step 1 — Create the database tables

Because the database only allows private, Entra ID–based connections (by design,
for security), the easiest way to run `schema.sql` is the same way we granted
the original permissions: a **temporary jumpbox VM**, connected to the database
with `sqlcmd`.

This is the same playbook as before, so it should go faster this time:

1. Create a small temporary VM (Ubuntu) in `snet-app`, no public IP, connect via
   Azure Bastion (Developer SKU — free).
2. Give the VM a system-assigned managed identity.
3. Temporarily add that identity to `sg-sql-admins` in Entra ID (or recreate
   that group if it was deleted — check first).
4. On the VM: `az login --identity`, then install `sqlcmd`:
   ```bash
   curl -sSL -o sqlcmd.tar.bz2 https://github.com/microsoft/go-sqlcmd/releases/latest/download/sqlcmd-linux-amd64.tar.bz2
   tar -xjf sqlcmd.tar.bz2
   sudo mv sqlcmd /usr/local/bin/sqlcmd
   ```
5. Upload `schema.sql` to the VM (via Bastion's file transfer, or paste its
   contents into a file using `nano schema.sql`).
6. Run it:
   ```bash
   sqlcmd -S sql-securehealth-faris.database.windows.net -d sqldb-patientrecords \
     --authentication-method ActiveDirectoryManagedIdentity -i schema.sql
   ```
7. Confirm the 4 tables were created:
   ```sql
   SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES;
   ```
8. **Clean up afterward** — remove the identity from `sg-sql-admins`, delete the
   VM, NAT Gateway, and Bastion, same as last time.

*(If this feels like a lot to redo, say so — we can talk through it step by
step live instead of all at once, the same way we did originally.)*

## Step 2 — Deploy the updated app

Same process as before:

1. Zip the contents of this folder (`app.py`, `requirements.txt`, `schema.sql`,
   `templates/`, `static/`) into `app.zip`.
2. Open Cloud Shell in the Portal, upload `app.zip`.
3. Deploy:
   ```bash
   az webapp deploy --resource-group rg-securehealth-dev \
     --name app-securehealth-faris \
     --src-path app.zip \
     --type zip
   ```
4. No new Application Settings are needed — `SQL_SERVER` and `SQL_DATABASE`
   are already configured from last time.

## Step 3 — Try it out

Visit your app's real URL (remember, Azure added a random suffix):

```
https://app-securehealth-faris-fud2h4fwdvbchef9.southafricanorth-01.azurewebsites.net/
```

You'll be asked to sign in (Entra ID auth is on) — sign in with
`broboogy@gmail.com`. You should land on an empty "Patients" page with an
"Add patient" button.

Try adding a patient, then click into their name to add a diagnosis,
medication, and note.

## What's still not included (on purpose, for now)

- Editing existing patient details or records (only add / remove for now)
- Search or filtering on the patient list
- Any patient-facing view (this is a clinician-facing tool only)

These are natural next steps once the core flow is confirmed working.
