from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import db
from ..helpers import Feld, hole_oder_404, kunden_optionen
from . import formular_seite

bp = Blueprint("reparaturen", __name__, url_prefix="/reparaturen")

STATUS = ["Eingegangen", "In Werkstatt", "Beim Hersteller", "Zurück – abholbereit", "Abgeholt", "Nicht reparabel"]
OFFEN = STATUS[:4]

FELDER = [
    Feld("kunde_id", "Kunde", "select", pflicht=True, optionen=kunden_optionen, breit=True),
    Feld("geraet", "Gerät", pflicht=True),
    Feld("seriennummer", "Seriennummer"),
    Feld("eingang", "Eingang", "date", pflicht=True),
    Feld("status", "Status", "select", optionen=STATUS),
    Feld("fehler", "Fehlerbeschreibung", "textarea", breit=True),
    Feld("versand_hersteller", "An Hersteller gesendet", "date"),
    Feld("rueckgabe", "Rückgabe an Kunden", "date"),
    Feld("garantie", "Garantie-/Gewährleistungsfall", "check"),
    Feld("kosten", "Kosten für Kunden (€)", "money"),
    Feld("notiz", "Notiz", "textarea", breit=True),
]


@bp.route("/")
def liste():
    alle = request.args.get("alle")
    sql = ("SELECT r.*, ku.vorname, ku.nachname, ku.telefon FROM reparaturen r "
           "JOIN kunden ku ON ku.id = r.kunde_id")
    if alle:
        rows = db.query(sql + " ORDER BY r.eingang DESC")
    else:
        rows = db.query(sql + f" WHERE r.status IN ({','.join('?' * len(OFFEN))}) ORDER BY r.eingang", OFFEN)
    return render_template("reparaturen/liste.html", rows=rows, alle=alle, offen=OFFEN)


@bp.route("/neu", methods=["GET", "POST"])
def neu():
    vorbelegung = {"eingang": date.today().isoformat(), "status": "Eingegangen",
                   "kunde_id": request.args.get("kunde", "")}
    return formular_seite(FELDER, "Neue Reparatur", "reparaturen", lambda _id: url_for("reparaturen.liste"),
                          vorbelegung=vorbelegung, abbrechen=url_for("reparaturen.liste"))


@bp.route("/<int:rid>", methods=["GET", "POST"])
def bearbeiten(rid):
    row = hole_oder_404("reparaturen", rid)
    return formular_seite(FELDER, f"Reparatur: {row['geraet']}", "reparaturen",
                          lambda _id: url_for("reparaturen.liste"), row=row, abbrechen=url_for("reparaturen.liste"))


@bp.route("/<int:rid>/loeschen", methods=["POST"])
def loeschen(rid):
    hole_oder_404("reparaturen", rid)
    db.execute("DELETE FROM reparaturen WHERE id = ?", (rid,))
    flash("Reparatur gelöscht.", "ok")
    return redirect(url_for("reparaturen.liste"))
