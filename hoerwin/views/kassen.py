from flask import Blueprint, flash, redirect, render_template, url_for

from .. import db
from ..helpers import Feld, hole_oder_404, seite_suche
from . import formular_seite

bp = Blueprint("kassen", __name__, url_prefix="/kostentraeger")

FELDER = [
    Feld("name", "Name", pflicht=True, breit=True),
    Feld("ik_nummer", "IK-Nummer"),
    Feld("art", "Art", "select", optionen=["gesetzlich", "privat", "Berufsgenossenschaft", "Sozialamt", "sonstige"]),
    Feld("festbetrag", "Festbetrag je Hörsystem (€)", "money",
         hilfe="Vertragspreis/Festbetrag der Kasse pro Ohr. Bei privaten Kostenträgern 0."),
    Feld("strasse", "Straße"), Feld("plz", "PLZ"), Feld("ort", "Ort"),
    Feld("telefon", "Telefon", "tel"), Feld("email", "E-Mail", "email"),
    Feld("notiz", "Notiz", "textarea", breit=True),
]


@bp.route("/")
def liste():
    q = seite_suche()
    rows = db.query("SELECT k.*, (SELECT COUNT(*) FROM kunden WHERE krankenkasse_id = k.id) AS anzahl "
                    "FROM krankenkassen k WHERE name LIKE ? OR ik_nummer LIKE ? ORDER BY name",
                    (f"%{q}%", f"%{q}%"))
    return render_template("kassen/liste.html", rows=rows, q=q)


@bp.route("/neu", methods=["GET", "POST"])
def neu():
    return formular_seite(FELDER, "Neuer Kostenträger", "krankenkassen",
                          lambda _id: url_for("kassen.liste"), vorbelegung={"art": "gesetzlich"},
                          abbrechen=url_for("kassen.liste"))


@bp.route("/<int:kid>", methods=["GET", "POST"])
def bearbeiten(kid):
    row = hole_oder_404("krankenkassen", kid)
    return formular_seite(FELDER, f"Kostenträger: {row['name']}", "krankenkassen",
                          lambda _id: url_for("kassen.liste"), row=row, abbrechen=url_for("kassen.liste"))


@bp.route("/<int:kid>/loeschen", methods=["POST"])
def loeschen(kid):
    hole_oder_404("krankenkassen", kid)
    db.execute("DELETE FROM krankenkassen WHERE id = ?", (kid,))
    flash("Kostenträger gelöscht.", "ok")
    return redirect(url_for("kassen.liste"))
