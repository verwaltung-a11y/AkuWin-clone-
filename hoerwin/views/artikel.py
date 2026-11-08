from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import db
from ..helpers import Feld, hole_oder_404, seite_suche
from . import formular_seite

bp = Blueprint("artikel", __name__, url_prefix="/artikel")

KATEGORIEN = ["Hörgerät", "Otoplastik", "Batterie", "Zubehör", "Gehörschutz", "Pflegemittel", "Dienstleistung"]

FELDER = [
    Feld("kategorie", "Kategorie", "select", optionen=KATEGORIEN),
    Feld("artikelnummer", "Artikelnummer"),
    Feld("hersteller", "Hersteller"),
    Feld("bezeichnung", "Bezeichnung", pflicht=True, breit=True),
    Feld("bauform", "Bauform", "select", optionen=["", "HdO", "RIC/RITE", "IdO", "CIC/IIC", "Im-Ohr-Kanal", "sonstige"]),
    Feld("hilfsmittelnummer", "Hilfsmittelnummer", hilfe="10-stellige Positionsnummer des GKV-Hilfsmittelverzeichnisses"),
    Feld("preis", "Verkaufspreis brutto (€)", "money"),
    Feld("mwst", "MwSt.-Satz (%)", "select", optionen=[("19", "19 %"), ("7", "7 %"), ("0", "0 %")]),
    Feld("bestand", "Lagerbestand", "number"),
    Feld("mindestbestand", "Mindestbestand", "number", hilfe="Unterschreitung wird auf der Startseite gemeldet."),
    Feld("aktiv", "Aktiv (im Verkauf)", "check"),
]


@bp.route("/")
def liste():
    q, kat = seite_suche(), request.args.get("kategorie", "")
    sql = ("SELECT * FROM artikel WHERE (bezeichnung LIKE ? OR hersteller LIKE ? OR artikelnummer LIKE ?)")
    args = [f"%{q}%"] * 3
    if kat:
        sql += " AND kategorie = ?"
        args.append(kat)
    if request.args.get("knapp"):
        sql += " AND bestand <= mindestbestand AND mindestbestand > 0"
    rows = db.query(sql + " ORDER BY aktiv DESC, kategorie, hersteller, bezeichnung", args)
    return render_template("artikel/liste.html", rows=rows, q=q, kat=kat, kategorien=KATEGORIEN)


@bp.route("/neu", methods=["GET", "POST"])
def neu():
    return formular_seite(FELDER, "Neuer Artikel", "artikel", lambda _id: url_for("artikel.liste"),
                          vorbelegung={"kategorie": "Hörgerät", "mwst": 19, "aktiv": 1},
                          abbrechen=url_for("artikel.liste"))


@bp.route("/<int:aid>", methods=["GET", "POST"])
def bearbeiten(aid):
    row = hole_oder_404("artikel", aid)
    return formular_seite(FELDER, f"Artikel: {row['bezeichnung']}", "artikel", lambda _id: url_for("artikel.liste"),
                          row=row, abbrechen=url_for("artikel.liste"))


@bp.route("/<int:aid>/bestand", methods=["POST"])
def bestand(aid):
    hole_oder_404("artikel", aid)
    try:
        menge = int(request.form.get("menge", "0"))
    except ValueError:
        flash("Bitte eine ganze Zahl angeben.", "fehler")
    else:
        db.execute("UPDATE artikel SET bestand = bestand + ? WHERE id = ?", (menge, aid))
        flash(f"Bestand um {menge:+d} geändert.", "ok")
    return redirect(request.referrer or url_for("artikel.liste"))


@bp.route("/<int:aid>/loeschen", methods=["POST"])
def loeschen(aid):
    hole_oder_404("artikel", aid)
    db.execute("DELETE FROM artikel WHERE id = ?", (aid,))
    flash("Artikel gelöscht.", "ok")
    return redirect(url_for("artikel.liste"))
