from datetime import date, datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import db
from ..helpers import Feld, hole_oder_404, kunden_optionen
from . import formular_seite

bp = Blueprint("termine", __name__, url_prefix="/termine")

ARTEN = ["Beratung", "Hörtest", "Anpassung", "Feinanpassung", "Abgabe", "Nachsorge", "Abdrucknahme",
         "Reparatur/Service", "Hausbesuch", "Sonstiges"]
TAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

FELDER = [
    Feld("kunde_id", "Kunde", "select", optionen=kunden_optionen, breit=True),
    Feld("beginn", "Beginn", "datetime-local", pflicht=True),
    Feld("dauer_min", "Dauer (Minuten)", "number"),
    Feld("art", "Terminart", "select", optionen=ARTEN),
    Feld("erledigt", "Erledigt", "check"),
    Feld("notiz", "Notiz", "textarea", breit=True),
]


def _pruefe(daten):
    try:
        datetime.fromisoformat(daten["beginn"])
    except (TypeError, ValueError):
        return ["Ungültiger Terminbeginn."]
    daten["kunde_id"] = daten.get("kunde_id") or None
    daten["dauer_min"] = daten.get("dauer_min") or 30
    return []


@bp.route("/")
def woche():
    try:
        start = date.fromisoformat(request.args.get("ab", ""))
    except ValueError:
        start = date.today()
    montag = start - timedelta(days=start.weekday())
    ende = montag + timedelta(days=7)
    rows = db.query("SELECT t.*, ku.vorname, ku.nachname FROM termine t LEFT JOIN kunden ku ON ku.id = t.kunde_id "
                    "WHERE t.beginn >= ? AND t.beginn < ? ORDER BY t.beginn",
                    (montag.isoformat(), ende.isoformat()))
    tage = []
    for i in range(7):
        tag = montag + timedelta(days=i)
        tage.append({"name": TAGE[i], "datum": tag,
                     "termine": [r for r in rows if r["beginn"][:10] == tag.isoformat()]})
    return render_template("termine/woche.html", tage=tage, montag=montag,
                           vor=(montag + timedelta(days=7)).isoformat(),
                           zurueck=(montag - timedelta(days=7)).isoformat())


@bp.route("/neu", methods=["GET", "POST"])
def neu():
    tag = request.args.get("tag") or date.today().isoformat()
    vorbelegung = {"beginn": f"{tag}T09:00", "dauer_min": 30, "art": "Beratung",
                   "kunde_id": request.args.get("kunde", "")}
    return formular_seite(FELDER, "Neuer Termin", "termine",
                          lambda _id: url_for("termine.woche", ab=request.form.get("beginn", "")[:10]),
                          vorbelegung=vorbelegung, vorher=_pruefe, abbrechen=url_for("termine.woche"))


@bp.route("/<int:tid>", methods=["GET", "POST"])
def bearbeiten(tid):
    row = hole_oder_404("termine", tid)
    return formular_seite(FELDER, "Termin bearbeiten", "termine",
                          lambda _id: url_for("termine.woche", ab=request.form.get("beginn", "")[:10]),
                          row=row, vorher=_pruefe, abbrechen=url_for("termine.woche", ab=row["beginn"][:10]))


@bp.route("/<int:tid>/erledigt", methods=["POST"])
def erledigt(tid):
    db.execute("UPDATE termine SET erledigt = 1 - erledigt WHERE id = ?", (tid,))
    return redirect(request.referrer or url_for("termine.woche"))


@bp.route("/<int:tid>/loeschen", methods=["POST"])
def loeschen(tid):
    row = hole_oder_404("termine", tid)
    db.execute("DELETE FROM termine WHERE id = ?", (tid,))
    flash("Termin gelöscht.", "ok")
    return redirect(url_for("termine.woche", ab=row["beginn"][:10]))
