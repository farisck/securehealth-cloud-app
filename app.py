"""
app.py — SecureHealth Cloud
============================
Flask application for managing patient records on Azure.
Connects to Azure SQL via managed identity (pyodbc + azure-identity).
Integrates RBAC via Entra ID app roles.
"""

import os
import struct
import logging
from datetime import datetime, date, timedelta
from math import ceil

import pyodbc
from flask import (
    Flask, render_template, request, redirect, url_for, flash, jsonify, g
)

# ── RBAC ─────────────────────────────────────────────────────────
from rbac import require_role, init_rbac

# ── Azure Identity (managed identity token for SQL) ──────────────
try:
    from azure.identity import DefaultAzureCredential
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

# ── Configuration ────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-production")

# Initialize RBAC (context processor + 403 handler)
init_rbac(app)

# Make `now()` available in templates (used for print timestamps)
app.jinja_env.globals["now"] = datetime.utcnow

# Database config
SQL_SERVER = os.environ.get("SQL_SERVER", "sql-securehealth-faris.database.windows.net")
SQL_DATABASE = os.environ.get("SQL_DATABASE", "sqldb-patientrecords")

# Pagination defaults
PER_PAGE = 20
AUDIT_PER_PAGE = 30

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Database Connection ──────────────────────────────────────────
def get_db():
    """Return a pyodbc connection (cached per-request on Flask `g`)."""
    if "db" not in g:
        if AZURE_AVAILABLE and not os.environ.get("LOCAL_DEV"):
            # Production: use managed identity token
            credential = DefaultAzureCredential()
            token = credential.get_token("https://database.windows.net/.default")
            token_bytes = token.token.encode("utf-16-le")
            token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

            conn_str = (
                f"Driver={{ODBC Driver 18 for SQL Server}};"
                f"Server=tcp:{SQL_SERVER},1433;"
                f"Database={SQL_DATABASE};"
                f"Encrypt=yes;TrustServerCertificate=no;"
                "Column Encryption Setting=Enabled;"
            )
            g.db = pyodbc.connect(conn_str, attrs_before={1256: token_struct})
        else:
            # Local development: direct connection string
            local_conn = os.environ.get(
                "LOCAL_DB_CONN",
                f"Driver={{ODBC Driver 18 for SQL Server}};"
                f"Server=tcp:{SQL_SERVER},1433;"
                f"Database={SQL_DATABASE};"
                f"Encrypt=yes;TrustServerCertificate=no;"
                "Column Encryption Setting=Enabled;"
            )
            g.db = pyodbc.connect(local_conn)

    return g.db


@app.teardown_appcontext
def close_db(exc):
    """Close the database connection at the end of each request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ── Helpers ──────────────────────────────────────────────────────
def get_current_actor():
    """Get the current user's name for audit logging."""
    return request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME", "anonymous")


def log_audit(action, entity_type, entity_id, details=""):
    """Write an entry to the audit_log table."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO audit_log (action, entity_type, entity_id, actor, details, timestamp)
           VALUES (?, ?, ?, ?, ?, GETDATE())""",
        (action, entity_type, entity_id, get_current_actor(), details),
    )
    conn.commit()


def row_to_dict(row, cursor):
    """Convert a pyodbc Row into a dict using cursor.description."""
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


class RowProxy:
    """Simple object that allows attribute-style access on a dict."""
    def __init__(self, d):
        self.__dict__.update(d)
    def __getattr__(self, name):
        return self.__dict__.get(name)


def rows_to_objects(rows, cursor):
    """Convert a list of pyodbc rows into RowProxy objects."""
    columns = [col[0] for col in cursor.description]
    return [RowProxy(dict(zip(columns, row))) for row in rows]


# ── Routes: Dashboard ───────────────────────────────────────────
@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    conn = get_db()
    cursor = conn.cursor()

    # Stats
    cursor.execute("SELECT COUNT(*) FROM patients")
    total_patients = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM patients WHERE created_at >= ?",
        (datetime.now() - timedelta(days=7),),
    )
    new_this_week = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM diagnoses WHERE status = 'Active' OR status IS NULL")
    active_diagnoses = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM medications WHERE end_date IS NULL OR end_date >= GETDATE()")
    total_medications = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM clinical_notes")
    total_notes = cursor.fetchone()[0]

    stats = RowProxy({
        "total_patients": total_patients,
        "new_this_week": new_this_week,
        "active_diagnoses": active_diagnoses,
        "total_medications": total_medications,
        "total_notes": total_notes,
    })

    # Recent activity (last 10)
    cursor.execute(
        "SELECT TOP 10 * FROM audit_log ORDER BY timestamp DESC"
    )
    recent_activity = rows_to_objects(cursor.fetchall(), cursor)

    today = date.today().strftime("%A, %B %d, %Y")

    return render_template(
        "dashboard.html",
        stats=stats,
        recent_activity=recent_activity,
        today=today,
    )


# ── Routes: Patients ────────────────────────────────────────────
@app.route("/patients")
def patients():
    conn = get_db()
    cursor = conn.cursor()

    search_query = request.args.get("q", "").strip()
    gender_filter = request.args.get("gender", "").strip()
    sort_by = request.args.get("sort", "name_asc").strip()
    page = max(1, request.args.get("page", 1, type=int))

    # Build WHERE clause
    conditions = []
    params = []

    if search_query:
        conditions.append("(first_name LIKE ? OR last_name LIKE ? OR id_number LIKE ?)")
        like = f"%{search_query}%"
        params.extend([like, like, like])

    if gender_filter:
        conditions.append("gender = ?")
        params.append(gender_filter)

    where = " WHERE " + " AND ".join(conditions) if conditions else ""

    # Sort
    sort_map = {
        "name_asc": "last_name ASC, first_name ASC",
        "name_desc": "last_name DESC, first_name DESC",
        "newest": "created_at DESC",
        "oldest": "created_at ASC",
    }
    order = sort_map.get(sort_by, "last_name ASC, first_name ASC")

    # Count
    cursor.execute(f"SELECT COUNT(*) FROM patients{where}", params)
    total_patients = cursor.fetchone()[0]
    total_pages = max(1, ceil(total_patients / PER_PAGE))

    # Fetch patients with diagnosis count
    offset = (page - 1) * PER_PAGE
    cursor.execute(
        f"""SELECT p.*,
                   (SELECT COUNT(*) FROM diagnoses d
                    WHERE d.patient_id = p.id AND (d.status = 'Active' OR d.status IS NULL)
                   ) AS diagnosis_count
            FROM patients p
            {where}
            ORDER BY {order}
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY""",
        params + [offset, PER_PAGE],
    )
    patient_list = rows_to_objects(cursor.fetchall(), cursor)

    return render_template(
        "patients.html",
        patients=patient_list,
        search_query=search_query,
        gender_filter=gender_filter,
        sort_by=sort_by,
        current_page=page,
        total_pages=total_pages,
        total_patients=total_patients,
    )


@app.route("/patients/<int:patient_id>")
def view_patient(patient_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
    row = cursor.fetchone()
    if not row:
        flash("Patient not found.", "error")
        return redirect(url_for("patients"))
    patient = RowProxy(row_to_dict(row, cursor))

    # Diagnoses
    cursor.execute(
        "SELECT * FROM diagnoses WHERE patient_id = ? ORDER BY diagnosed_date DESC",
        (patient_id,),
    )
    diagnoses = rows_to_objects(cursor.fetchall(), cursor)

    # Medications
    cursor.execute(
        "SELECT * FROM medications WHERE patient_id = ? ORDER BY start_date DESC",
        (patient_id,),
    )
    medications = rows_to_objects(cursor.fetchall(), cursor)

    # Clinical Notes
    cursor.execute(
        "SELECT * FROM clinical_notes WHERE patient_id = ? ORDER BY created_at DESC",
        (patient_id,),
    )
    notes = rows_to_objects(cursor.fetchall(), cursor)

    # Audit entries for this patient
    cursor.execute(
        """SELECT * FROM audit_log
           WHERE (entity_type = 'patient' AND entity_id = ?)
              OR (entity_type IN ('diagnosis', 'medication', 'note')
                  AND details LIKE ?)
           ORDER BY timestamp DESC""",
        (patient_id, f"%patient_id={patient_id}%"),
    )
    audit_entries = rows_to_objects(cursor.fetchall(), cursor)

    # Log view
    log_audit("VIEW", "patient", patient_id, f"{patient.first_name} {patient.last_name}")

    return render_template(
        "patient_detail.html",
        patient=patient,
        diagnoses=diagnoses,
        medications=medications,
        notes=notes,
        audit_entries=audit_entries,
    )


@app.route("/patients/add", methods=["GET", "POST"])
@require_role("clinician")
def add_patient():
    if request.method == "POST":
        conn = get_db()
        cursor = conn.cursor()

        dob = request.form.get("date_of_birth") or None

        cursor.execute(
            """INSERT INTO patients (first_name, last_name, id_number, date_of_birth,
                                     gender, email, phone, address, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, GETDATE(), GETDATE())""",
            (
                request.form["first_name"],
                request.form["last_name"],
                request.form.get("id_number"),
                dob,
                request.form.get("gender"),
                request.form.get("email"),
                request.form.get("phone"),
                request.form.get("address"),
            ),
        )
        conn.commit()

        cursor.execute("SELECT @@IDENTITY")
        new_id = int(cursor.fetchone()[0])

        log_audit("CREATE", "patient", new_id,
                  f"{request.form['first_name']} {request.form['last_name']}")

        flash("Patient added successfully.", "success")
        return redirect(url_for("view_patient", patient_id=new_id))

    return render_template("patient_form.html", patient=None)


@app.route("/patients/<int:patient_id>/edit", methods=["GET", "POST"])
@require_role("clinician")
def edit_patient(patient_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
    row = cursor.fetchone()
    if not row:
        flash("Patient not found.", "error")
        return redirect(url_for("patients"))
    patient = RowProxy(row_to_dict(row, cursor))

    if request.method == "POST":
        dob = request.form.get("date_of_birth") or None

        cursor.execute(
            """UPDATE patients
               SET first_name=?, last_name=?, id_number=?, date_of_birth=?,
                   gender=?, email=?, phone=?, address=?, updated_at=GETDATE()
               WHERE id=?""",
            (
                request.form["first_name"],
                request.form["last_name"],
                request.form.get("id_number"),
                dob,
                request.form.get("gender"),
                request.form.get("email"),
                request.form.get("phone"),
                request.form.get("address"),
                patient_id,
            ),
        )
        conn.commit()

        log_audit("UPDATE", "patient", patient_id,
                  f"{request.form['first_name']} {request.form['last_name']}")

        flash("Patient updated successfully.", "success")
        return redirect(url_for("view_patient", patient_id=patient_id))

    return render_template("patient_form.html", patient=patient)


@app.route("/patients/<int:patient_id>/delete", methods=["POST"])
@require_role("clinician")
def delete_patient(patient_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT first_name, last_name FROM patients WHERE id = ?", (patient_id,))
    row = cursor.fetchone()
    if row:
        log_audit("DELETE", "patient", patient_id, f"{row[0]} {row[1]}")
        cursor.execute("DELETE FROM clinical_notes WHERE patient_id = ?", (patient_id,))
        cursor.execute("DELETE FROM medications WHERE patient_id = ?", (patient_id,))
        cursor.execute("DELETE FROM diagnoses WHERE patient_id = ?", (patient_id,))
        cursor.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
        conn.commit()
        flash("Patient deleted.", "success")
    else:
        flash("Patient not found.", "error")

    return redirect(url_for("patients"))


# ── Routes: Diagnoses ───────────────────────────────────────────
@app.route("/patients/<int:patient_id>/diagnoses/add", methods=["GET", "POST"])
@require_role("clinician")
def add_diagnosis(patient_id):
    if request.method == "POST":
        conn = get_db()
        cursor = conn.cursor()

        cursor.setinputsizes([
            None,
            (pyodbc.SQL_WVARCHAR, 26, 0),
            None,
            None,
            None,
            None,
        ])
        app.logger.info(f"DIAGNOSIS INSERT PARAMS: {repr((patient_id, request.form['diagnosis'], request.form.get('diagnosed_date') or None, request.form.get('severity'), request.form.get('status', 'Active'), request.form.get('notes')))}")
        cursor.execute(
            """INSERT INTO diagnoses (patient_id, diagnosis, diagnosed_date, severity,
                                      status, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, GETDATE(), GETDATE())""",
            (
                patient_id,
                request.form["diagnosis"],
                request.form.get("diagnosed_date") or None,
                request.form.get("severity"),
                request.form.get("status", "Active"),
                request.form.get("notes"),
            ),
        )
        conn.commit()

        cursor.execute("SELECT @@IDENTITY")
        new_id = int(cursor.fetchone()[0])

        log_audit("CREATE", "diagnosis", new_id,
                  f"patient_id={patient_id}, {request.form['diagnosis']}")

        flash("Diagnosis added.", "success")
        return redirect(url_for("view_patient", patient_id=patient_id))

    return render_template("record_form.html", record_type="diagnosis",
                           patient_id=patient_id, record=None)


@app.route("/diagnoses/<int:diagnosis_id>/edit", methods=["GET", "POST"])
@require_role("clinician")
def edit_diagnosis(diagnosis_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM diagnoses WHERE id = ?", (diagnosis_id,))
    row = cursor.fetchone()
    if not row:
        flash("Diagnosis not found.", "error")
        return redirect(url_for("patients"))
    record = RowProxy(row_to_dict(row, cursor))

    if request.method == "POST":
        cursor.execute(
            """UPDATE diagnoses
               SET diagnosis=?, diagnosed_date=?, severity=?, status=?,
                   notes=?, updated_at=GETDATE()
               WHERE id=?""",
            (
                request.form["diagnosis"],
                request.form.get("diagnosed_date") or None,
                request.form.get("severity"),
                request.form.get("status"),
                request.form.get("notes"),
                diagnosis_id,
            ),
        )
        conn.commit()

        log_audit("UPDATE", "diagnosis", diagnosis_id,
                  f"patient_id={record.patient_id}, {request.form['diagnosis']}")

        flash("Diagnosis updated.", "success")
        return redirect(url_for("view_patient", patient_id=record.patient_id))

    return render_template("record_form.html", record_type="diagnosis",
                           patient_id=record.patient_id, record=record)


@app.route("/diagnoses/<int:diagnosis_id>/delete", methods=["POST"])
@require_role("clinician")
def delete_diagnosis(diagnosis_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT patient_id, diagnosis FROM diagnoses WHERE id = ?", (diagnosis_id,))
    row = cursor.fetchone()
    if row:
        patient_id, name = row
        log_audit("DELETE", "diagnosis", diagnosis_id,
                  f"patient_id={patient_id}, {name}")
        cursor.execute("DELETE FROM diagnoses WHERE id = ?", (diagnosis_id,))
        conn.commit()
        flash("Diagnosis deleted.", "success")
        return redirect(url_for("view_patient", patient_id=patient_id))

    flash("Diagnosis not found.", "error")
    return redirect(url_for("patients"))


# ── Routes: Medications ─────────────────────────────────────────
@app.route("/patients/<int:patient_id>/medications/add", methods=["GET", "POST"])
@require_role("clinician")
def add_medication(patient_id):
    if request.method == "POST":
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO medications (patient_id, medication_name, dosage, frequency,
                                        prescriber, start_date, end_date, notes,
                                        created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, GETDATE(), GETDATE())""",
            (
                patient_id,
                request.form["medication_name"],
                request.form.get("dosage"),
                request.form.get("frequency"),
                request.form.get("prescriber"),
                request.form.get("start_date") or None,
                request.form.get("end_date") or None,
                request.form.get("notes"),
            ),
        )
        conn.commit()

        cursor.execute("SELECT @@IDENTITY")
        new_id = int(cursor.fetchone()[0])

        log_audit("CREATE", "medication", new_id,
                  f"patient_id={patient_id}, {request.form['medication_name']}")

        flash("Medication added.", "success")
        return redirect(url_for("view_patient", patient_id=patient_id))

    return render_template("record_form.html", record_type="medication",
                           patient_id=patient_id, record=None)


@app.route("/medications/<int:medication_id>/edit", methods=["GET", "POST"])
@require_role("clinician")
def edit_medication(medication_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM medications WHERE id = ?", (medication_id,))
    row = cursor.fetchone()
    if not row:
        flash("Medication not found.", "error")
        return redirect(url_for("patients"))
    record = RowProxy(row_to_dict(row, cursor))

    if request.method == "POST":
        cursor.execute(
            """UPDATE medications
               SET medication_name=?, dosage=?, frequency=?, prescriber=?,
                   start_date=?, end_date=?, notes=?, updated_at=GETDATE()
               WHERE id=?""",
            (
                request.form["medication_name"],
                request.form.get("dosage"),
                request.form.get("frequency"),
                request.form.get("prescriber"),
                request.form.get("start_date") or None,
                request.form.get("end_date") or None,
                request.form.get("notes"),
                medication_id,
            ),
        )
        conn.commit()

        log_audit("UPDATE", "medication", medication_id,
                  f"patient_id={record.patient_id}, {request.form['medication_name']}")

        flash("Medication updated.", "success")
        return redirect(url_for("view_patient", patient_id=record.patient_id))

    return render_template("record_form.html", record_type="medication",
                           patient_id=record.patient_id, record=record)


@app.route("/medications/<int:medication_id>/delete", methods=["POST"])
@require_role("clinician")
def delete_medication(medication_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT patient_id, medication_name FROM medications WHERE id = ?",
                   (medication_id,))
    row = cursor.fetchone()
    if row:
        patient_id, name = row
        log_audit("DELETE", "medication", medication_id,
                  f"patient_id={patient_id}, {name}")
        cursor.execute("DELETE FROM medications WHERE id = ?", (medication_id,))
        conn.commit()
        flash("Medication deleted.", "success")
        return redirect(url_for("view_patient", patient_id=patient_id))

    flash("Medication not found.", "error")
    return redirect(url_for("patients"))


# ── Routes: Clinical Notes ──────────────────────────────────────
@app.route("/patients/<int:patient_id>/notes/add", methods=["GET", "POST"])
@require_role("clinician")
def add_note(patient_id):
    if request.method == "POST":
        conn = get_db()
        cursor = conn.cursor()

        cursor.setinputsizes([
            None,
            None,
            (pyodbc.SQL_WVARCHAR, 0, 0),
            None,
        ])
        cursor.execute(
            """INSERT INTO clinical_notes (patient_id, note_type, content, author,
                                           created_at, updated_at)
               VALUES (?, ?, ?, ?, GETDATE(), GETDATE())""",
            (
                patient_id,
                request.form.get("note_type"),
                request.form["content"],
                get_current_actor(),
            ),
        )
        conn.commit()

        cursor.execute("SELECT @@IDENTITY")
        new_id = int(cursor.fetchone()[0])

        log_audit("CREATE", "note", new_id,
                  f"patient_id={patient_id}, {request.form.get('note_type', 'note')}")

        flash("Note added.", "success")
        return redirect(url_for("view_patient", patient_id=patient_id))

    return render_template("record_form.html", record_type="note",
                           patient_id=patient_id, record=None)


@app.route("/notes/<int:note_id>/edit", methods=["GET", "POST"])
@require_role("clinician")
def edit_note(note_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM clinical_notes WHERE id = ?", (note_id,))
    row = cursor.fetchone()
    if not row:
        flash("Note not found.", "error")
        return redirect(url_for("patients"))
    record = RowProxy(row_to_dict(row, cursor))

    if request.method == "POST":
        cursor.execute(
            """UPDATE clinical_notes
               SET note_type=?, content=?, updated_at=GETDATE()
               WHERE id=?""",
            (
                request.form.get("note_type"),
                request.form["content"],
                note_id,
            ),
        )
        conn.commit()

        log_audit("UPDATE", "note", note_id,
                  f"patient_id={record.patient_id}, {request.form.get('note_type', 'note')}")

        flash("Note updated.", "success")
        return redirect(url_for("view_patient", patient_id=record.patient_id))

    return render_template("record_form.html", record_type="note",
                           patient_id=record.patient_id, record=record)


@app.route("/notes/<int:note_id>/delete", methods=["POST"])
@require_role("clinician")
def delete_note(note_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT patient_id, note_type FROM clinical_notes WHERE id = ?", (note_id,))
    row = cursor.fetchone()
    if row:
        patient_id, note_type = row
        log_audit("DELETE", "note", note_id,
                  f"patient_id={patient_id}, {note_type}")
        cursor.execute("DELETE FROM clinical_notes WHERE id = ?", (note_id,))
        conn.commit()
        flash("Note deleted.", "success")
        return redirect(url_for("view_patient", patient_id=patient_id))

    flash("Note not found.", "error")
    return redirect(url_for("patients"))


# ── Routes: Audit Log ───────────────────────────────────────────
@app.route("/audit")
def audit_log():
    conn = get_db()
    cursor = conn.cursor()

    search_query = request.args.get("q", "").strip()
    action_filter = request.args.get("action", "").strip()
    entity_filter = request.args.get("entity", "").strip()
    page = max(1, request.args.get("page", 1, type=int))

    conditions = []
    params = []

    if search_query:
        conditions.append("(actor LIKE ? OR details LIKE ?)")
        like = f"%{search_query}%"
        params.extend([like, like])

    if action_filter:
        conditions.append("action = ?")
        params.append(action_filter)

    if entity_filter:
        conditions.append("entity_type = ?")
        params.append(entity_filter)

    where = " WHERE " + " AND ".join(conditions) if conditions else ""

    cursor.execute(f"SELECT COUNT(*) FROM audit_log{where}", params)
    total_entries = cursor.fetchone()[0]
    total_pages = max(1, ceil(total_entries / AUDIT_PER_PAGE))

    offset = (page - 1) * AUDIT_PER_PAGE
    cursor.execute(
        f"""SELECT * FROM audit_log{where}
            ORDER BY timestamp DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY""",
        params + [offset, AUDIT_PER_PAGE],
    )
    entries = rows_to_objects(cursor.fetchall(), cursor)

    return render_template(
        "audit_log.html",
        entries=entries,
        search_query=search_query,
        action_filter=action_filter,
        entity_filter=entity_filter,
        current_page=page,
        total_pages=total_pages,
        total_entries=total_entries,
    )


# ── API: Quick Search ────────────────────────────────────────────
@app.route("/api/search")
def api_search():
    """JSON endpoint for the Ctrl+K quick search overlay."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify(results=[])

    conn = get_db()
    cursor = conn.cursor()

    like = f"%{q}%"
    cursor.execute(
        """SELECT TOP 10 id, first_name, last_name, id_number, gender
           FROM patients
           WHERE first_name LIKE ? OR last_name LIKE ? OR id_number LIKE ?
           ORDER BY last_name, first_name""",
        (like, like, like),
    )

    results = []
    for row in cursor.fetchall():
        results.append({
            "id": row[0],
            "name": f"{row[1]} {row[2]}",
            "initials": f"{row[1][0]}{row[2][0]}".upper() if row[1] and row[2] else "??",
            "id_number": row[3] or "",
            "gender": row[4] or "",
        })

    return jsonify(results=results)


# ── Run ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
