"""Anmeldung, Ersteinrichtung und CSRF-Schutz."""
import hmac
import secrets

from flask import (Blueprint, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from . import db

bp = Blueprint("auth", __name__)

OFFENE_ENDPUNKTE = {"auth.login", "auth.einrichtung", "static"}


def register_guards(app):
    @app.before_request
    def pruefe_anmeldung():
        g.benutzer = None
        if session.get("benutzer_id"):
            g.benutzer = db.query("SELECT id, benutzername, name FROM benutzer WHERE id = ?",
                                  (session["benutzer_id"],), one=True)
        if request.method == "POST":
            token = request.form.get("csrf_token", "")
            erwartet = session.get("csrf_token", "")
            if not erwartet or not hmac.compare_digest(token, erwartet):
                abort(400, "Ungültiges Formular-Token – bitte Seite neu laden.")
        if request.endpoint in OFFENE_ENDPUNKTE:
            return None
        if db.query("SELECT 1 FROM benutzer LIMIT 1", one=True) is None:
            return redirect(url_for("auth.einrichtung"))
        if g.benutzer is None:
            return redirect(url_for("auth.login", weiter=request.path))
        return None

    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return session["csrf_token"]

    # als globale Funktion, damit sie auch in importierten Makros verfügbar ist
    app.jinja_env.globals["csrf_token"] = csrf_token


def _sicheres_ziel(ziel):
    return ziel if ziel and ziel.startswith("/") and not ziel.startswith("//") else url_for("dashboard.index")


@bp.route("/einrichtung", methods=["GET", "POST"])
def einrichtung():
    if db.query("SELECT 1 FROM benutzer LIMIT 1", one=True):
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        name = request.form.get("benutzername", "").strip()
        pw = request.form.get("passwort", "")
        if not name or len(pw) < 8:
            flash("Benutzername angeben und ein Passwort mit mindestens 8 Zeichen wählen.", "fehler")
        elif pw != request.form.get("passwort2"):
            flash("Die Passwörter stimmen nicht überein.", "fehler")
        else:
            db.insert("benutzer", {"benutzername": name, "name": request.form.get("anzeigename") or name,
                                   "passwort_hash": generate_password_hash(pw)})
            db.setze_einstellung("firma_name", request.form.get("firma_name", "").strip())
            flash("Einrichtung abgeschlossen. Bitte melden Sie sich an.", "ok")
            return redirect(url_for("auth.login"))
    return render_template("auth/einrichtung.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        row = db.query("SELECT * FROM benutzer WHERE benutzername = ?",
                       (request.form.get("benutzername", "").strip(),), one=True)
        if row and check_password_hash(row["passwort_hash"], request.form.get("passwort", "")):
            session.clear()
            session["benutzer_id"] = row["id"]
            session["csrf_token"] = secrets.token_urlsafe(32)
            return redirect(_sicheres_ziel(request.args.get("weiter")))
        flash("Benutzername oder Passwort falsch.", "fehler")
    return render_template("auth/login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/benutzer", methods=["GET", "POST"])
def benutzer():
    if request.method == "POST":
        aktion = request.form.get("aktion")
        if aktion == "neu":
            name, pw = request.form.get("benutzername", "").strip(), request.form.get("passwort", "")
            if not name or len(pw) < 8:
                flash("Benutzername und Passwort (mind. 8 Zeichen) erforderlich.", "fehler")
            elif db.query("SELECT 1 FROM benutzer WHERE benutzername = ?", (name,), one=True):
                flash("Diesen Benutzernamen gibt es bereits.", "fehler")
            else:
                db.insert("benutzer", {"benutzername": name, "name": request.form.get("anzeigename") or name,
                                       "passwort_hash": generate_password_hash(pw)})
                flash(f"Benutzer „{name}“ angelegt.", "ok")
        elif aktion == "passwort":
            alt, neu = request.form.get("alt", ""), request.form.get("neu", "")
            row = db.query("SELECT * FROM benutzer WHERE id = ?", (g.benutzer["id"],), one=True)
            if not check_password_hash(row["passwort_hash"], alt):
                flash("Das bisherige Passwort ist falsch.", "fehler")
            elif len(neu) < 8:
                flash("Das neue Passwort muss mindestens 8 Zeichen haben.", "fehler")
            else:
                db.update("benutzer", row["id"], {"passwort_hash": generate_password_hash(neu)})
                flash("Passwort geändert.", "ok")
        elif aktion == "loeschen":
            uid = int(request.form.get("id", 0))
            if uid == g.benutzer["id"]:
                flash("Sie können sich nicht selbst löschen.", "fehler")
            else:
                db.execute("DELETE FROM benutzer WHERE id = ?", (uid,))
                flash("Benutzer gelöscht.", "ok")
        return redirect(url_for("auth.benutzer"))
    liste = db.query("SELECT id, benutzername, name, erstellt FROM benutzer ORDER BY benutzername")
    return render_template("auth/benutzer.html", liste=liste)
