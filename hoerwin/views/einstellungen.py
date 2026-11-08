import os
import sqlite3
import tempfile
from datetime import datetime

from flask import Blueprint, after_this_request, current_app, flash, redirect, render_template, request, send_file, url_for

from .. import db

bp = Blueprint("einstellungen", __name__, url_prefix="/einstellungen")

FIRMA = [
    ("firma_name", "Firmenname"), ("firma_inhaber", "Inhaber/in"), ("firma_strasse", "Straße"),
    ("firma_plz_ort", "PLZ und Ort"), ("firma_telefon", "Telefon"), ("firma_email", "E-Mail"),
    ("firma_ik", "IK-Nummer (Leistungserbringer)"), ("firma_steuernr", "Steuernummer / USt-IdNr."),
    ("firma_bank", "Bankverbindung (IBAN, BIC, Bank)"),
    ("rechnung_fusstext", "Fußtext auf Rechnungen"),
]


@bp.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        for schluessel, _ in FIRMA:
            db.setze_einstellung(schluessel, request.form.get(schluessel, "").strip())
        flash("Einstellungen gespeichert.", "ok")
        return redirect(url_for("einstellungen.index"))
    werte = {k: db.einstellung(k) for k, _ in FIRMA}
    return render_template("einstellungen.html", felder=FIRMA, werte=werte)


@bp.route("/sicherung")
def sicherung():
    """Konsistente Kopie der Datenbank per SQLite-Backup-API zum Herunterladen."""
    fd, pfad = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    ziel = sqlite3.connect(pfad)
    quelle = sqlite3.connect(current_app.config["DATABASE"])
    with ziel:
        quelle.backup(ziel)
    quelle.close()
    ziel.close()

    @after_this_request
    def aufraeumen(antwort):
        try:
            os.remove(pfad)
        except OSError:
            pass
        return antwort

    name = f"hoerwin-sicherung-{datetime.now():%Y-%m-%d-%H%M}.sqlite"
    return send_file(pfad, as_attachment=True, download_name=name)
