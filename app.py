import os
import struct
from datetime import date

import pyodbc
from flask import Flask, render_template, request, redirect, url_for, flash
from azure.identity import DefaultAzureCredential

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

SQL_SERVER = os.environ.get("SQL_SERVER", "sql-securehealth-faris.database.windows.net")
SQL_DATABASE = os.environ.get("SQL_DATABASE", "sqldb-patientrecords")

SQL_COPT_SS_ACCESS_TOKEN = 1256


def get_db_connection():
    """Connects to Azure SQL using the App Service's managed identity."""
    credential = DefaultAzureCredential()
    token = credential.get_token("https://database.windows.net/.default")
    token_bytes = token.token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"Encrypt=yes;TrustServerCertificate=no;"
    )
    return pyodbc.connect(conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})


def calculate_age(dob):
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


# ---------- Health check (kept from the diagnostic app) ----------

@app.route("/health")
def health():
    return {"status": "healthy"}


# ---------- Patients ----------

@app.route("/")
def patients_list():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT patient_id, first_name, last_name, date_of_birth, created_at
        FROM patients
        ORDER BY last_name, first_name
    """)
    patients = cursor.fetchall()
    conn.close()
    return render_template("patients.html", patients=patients)


@app.route("/patients/new", methods=["GET", "POST"])
def add_patient():
    if request.method == "POST":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO patients (first_name, last_name, date_of_birth, phone, email, address)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            request.form["first_name"],
            request.form["last_name"],
            request.form["date_of_birth"],
            request.form.get("phone"),
            request.form.get("email"),
            request.form.get("address"),
        ))
        conn.commit()
        conn.close()
        flash("Patient added.")
        return redirect(url_for("patients_list"))
    return render_template("patient_form.html")


@app.route("/patients/<int:patient_id>")
def patient_detail(patient_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM patients WHERE patient_id = ?", patient_id)
    patient = cursor.fetchone()
    if not patient:
        conn.close()
        return "Patient not found", 404

    cursor.execute("""
        SELECT diagnosis_id, condition_name, diagnosed_date, status, notes
        FROM diagnoses WHERE patient_id = ? ORDER BY diagnosed_date DESC
    """, patient_id)
    diagnoses = cursor.fetchall()

    cursor.execute("""
        SELECT medication_id, medication_name, dosage, frequency, start_date, end_date, prescribing_clinician
        FROM medications WHERE patient_id = ? ORDER BY start_date DESC
    """, patient_id)
    medications = cursor.fetchall()

    cursor.execute("""
        SELECT note_id, note_text, created_by, created_at
        FROM clinical_notes WHERE patient_id = ? ORDER BY created_at DESC
    """, patient_id)
    notes = cursor.fetchall()

    conn.close()

    age = calculate_age(patient.date_of_birth)
    return render_template(
        "patient_detail.html",
        patient=patient, age=age,
        diagnoses=diagnoses, medications=medications, notes=notes,
    )


@app.route("/patients/<int:patient_id>/delete", methods=["POST"])
def delete_patient(patient_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM patients WHERE patient_id = ?", patient_id)
    conn.commit()
    conn.close()
    flash("Patient record deleted.")
    return redirect(url_for("patients_list"))


# ---------- Diagnoses ----------

@app.route("/patients/<int:patient_id>/diagnoses/new", methods=["GET", "POST"])
def add_diagnosis(patient_id):
    if request.method == "POST":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO diagnoses (patient_id, condition_name, diagnosed_date, status, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (
            patient_id,
            request.form["condition_name"],
            request.form["diagnosed_date"],
            request.form.get("status", "active"),
            request.form.get("notes"),
        ))
        conn.commit()
        conn.close()
        flash("Diagnosis added.")
        return redirect(url_for("patient_detail", patient_id=patient_id))
    return render_template("record_form.html", record_type="diagnosis", patient_id=patient_id)


@app.route("/diagnoses/<int:diagnosis_id>/delete", methods=["POST"])
def delete_diagnosis(diagnosis_id):
    patient_id = request.form["patient_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM diagnoses WHERE diagnosis_id = ?", diagnosis_id)
    conn.commit()
    conn.close()
    return redirect(url_for("patient_detail", patient_id=patient_id))


# ---------- Medications ----------

@app.route("/patients/<int:patient_id>/medications/new", methods=["GET", "POST"])
def add_medication(patient_id):
    if request.method == "POST":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO medications
                (patient_id, medication_name, dosage, frequency, start_date, end_date, prescribing_clinician)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            patient_id,
            request.form["medication_name"],
            request.form.get("dosage"),
            request.form.get("frequency"),
            request.form.get("start_date") or None,
            request.form.get("end_date") or None,
            request.form.get("prescribing_clinician"),
        ))
        conn.commit()
        conn.close()
        flash("Medication added.")
        return redirect(url_for("patient_detail", patient_id=patient_id))
    return render_template("record_form.html", record_type="medication", patient_id=patient_id)


@app.route("/medications/<int:medication_id>/delete", methods=["POST"])
def delete_medication(medication_id):
    patient_id = request.form["patient_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM medications WHERE medication_id = ?", medication_id)
    conn.commit()
    conn.close()
    return redirect(url_for("patient_detail", patient_id=patient_id))


# ---------- Clinical Notes ----------

@app.route("/patients/<int:patient_id>/notes/new", methods=["GET", "POST"])
def add_note(patient_id):
    if request.method == "POST":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO clinical_notes (patient_id, note_text, created_by)
            VALUES (?, ?, ?)
        """, (
            patient_id,
            request.form["note_text"],
            request.form.get("created_by", "Unknown"),
        ))
        conn.commit()
        conn.close()
        flash("Note added.")
        return redirect(url_for("patient_detail", patient_id=patient_id))
    return render_template("record_form.html", record_type="note", patient_id=patient_id)


@app.route("/notes/<int:note_id>/delete", methods=["POST"])
def delete_note(note_id):
    patient_id = request.form["patient_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clinical_notes WHERE note_id = ?", note_id)
    conn.commit()
    conn.close()
    return redirect(url_for("patient_detail", patient_id=patient_id))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
