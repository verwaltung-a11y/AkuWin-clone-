import csv
import io
import json

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

from .. import db, fachlogik
from ..helpers import Feld, hole_oder_404, kassen_optionen, seite_suche
from . import formular_seite

bp = Blueprint("kunden", __name__, url_prefix="/kunden")

FELDER = [
    Feld("anrede", "Anrede", "select", optionen=["", "Frau", "Herr", "Divers"]),
    Feld("vorname", "Vorname"),
    Feld("nachname", "Nachname", pflicht=True),
    Feld("geburtsdatum", "Geburtsdatum", "date"),
    Feld("strasse", "Straße", breit=True), Feld("plz", "PLZ"), Feld("ort", "Ort"),
    Feld("telefon", "Telefon", "tel"), Feld("mobil", "Mobil", "tel"), Feld("email", "E-Mail", "email"),
    Feld("krankenkasse_id", "Krankenkasse / Kostenträger", "select", optionen=kassen_optionen),
    Feld("versichertennummer", "Versichertennummer"),
    Feld("zuzahlungsbefreit", "Von der Zuzahlung befreit", "check"),
    Feld("hno_arzt", "HNO-Arzt", breit=True),
    Feld("einwilligung_dsgvo", "Einwilligung Datenverarbeitung (DSGVO) liegt vor", "check", breit=True),
    Feld("notiz", "Notiz", "textarea", breit=True),
]


def _naechste_kundennummer():
    row = db.query("SELECT MAX(CAST(kundennummer AS INTEGER)) AS m FROM kunden", one=True)
    return str((row["m"] or 10000) + 1)


@bp.route("/")
def liste():
    q = seite_suche()
    muster = f"%{q}%"
    rows = db.query(
        "SELECT ku.*, ka.name AS kasse FROM kunden ku LEFT JOIN krankenkassen ka ON ka.id = ku.krankenkasse_id "
        "WHERE ku.nachname LIKE ? OR ku.vorname LIKE ? OR ku.kundennummer LIKE ? OR ku.ort LIKE ? "
        "OR ku.telefon LIKE ? OR ku.mobil LIKE ? OR (ku.vorname || ' ' || ku.nachname) LIKE ? "
        "ORDER BY ku.nachname, ku.vorname LIMIT 500",
        (muster,) * 7)
    return render_template("kunden/liste.html", rows=rows, q=q)


@bp.route("/neu", methods=["GET", "POST"])
def neu():
    def vorher(daten):
        daten["kundennummer"] = _naechste_kundennummer()

    return formular_seite(FELDER, "Neuer Kunde", "kunden", lambda kid: url_for("kunden.detail", kid=kid),
                          vorher=vorher, abbrechen=url_for("kunden.liste"))


@bp.route("/<int:kid>")
def detail(kid):
    kunde = db.query("SELECT ku.*, ka.name AS kasse, ka.art AS kasse_art FROM kunden ku "
                     "LEFT JOIN krankenkassen ka ON ka.id = ku.krankenkasse_id WHERE ku.id = ?", (kid,), one=True)
    if kunde is None:
        return render_template("fehler.html", meldung="Kunde nicht gefunden."), 404
    audiogramme = []
    for a in db.query("SELECT * FROM audiogramme WHERE kunde_id = ? ORDER BY datum DESC", (kid,)):
        werte = fachlogik.parse_werte(a["werte"])
        audiogramme.append({"row": a, "auswertung": fachlogik.audiogramm_auswertung(werte)})
    letztes_svg = None
    if audiogramme:
        letztes_svg = fachlogik.audiogramm_svg(fachlogik.parse_werte(audiogramme[0]["row"]["werte"]))
    return render_template(
        "kunden/detail.html", k=kunde, alter=fachlogik.alter(kunde["geburtsdatum"]),
        audiogramme=audiogramme, letztes_svg=letztes_svg,
        versorgungen=db.query("SELECT v.*, (SELECT COUNT(*) FROM versorgung_geraete WHERE versorgung_id = v.id) "
                              "AS geraete FROM versorgungen v WHERE kunde_id = ? ORDER BY beginn DESC", (kid,)),
        termine=db.query("SELECT * FROM termine WHERE kunde_id = ? ORDER BY beginn DESC LIMIT 20", (kid,)),
        rechnungen=db.query("SELECT r.*, (SELECT SUM(menge * einzelpreis) FROM rechnung_positionen "
                            "WHERE rechnung_id = r.id) AS summe FROM rechnungen r WHERE kunde_id = ? "
                            "ORDER BY datum DESC", (kid,)),
        reparaturen=db.query("SELECT * FROM reparaturen WHERE kunde_id = ? ORDER BY eingang DESC", (kid,)),
    )


@bp.route("/<int:kid>/bearbeiten", methods=["GET", "POST"])
def bearbeiten(kid):
    row = hole_oder_404("kunden", kid)
    return formular_seite(FELDER, f"Kunde bearbeiten: {row['vorname'] or ''} {row['nachname']}", "kunden",
                          lambda _id: url_for("kunden.detail", kid=kid), row=row,
                          abbrechen=url_for("kunden.detail", kid=kid))


@bp.route("/<int:kid>/loeschen", methods=["POST"])
def loeschen(kid):
    row = hole_oder_404("kunden", kid)
    if request.form.get("bestaetigung") != row["nachname"]:
        flash("Zum Löschen bitte den Nachnamen exakt eingeben.", "fehler")
        return redirect(url_for("kunden.detail", kid=kid))
    db.execute("DELETE FROM kunden WHERE id = ?", (kid,))
    flash("Kunde und alle zugehörigen Daten wurden gelöscht.", "ok")
    return redirect(url_for("kunden.liste"))


# -------------------------------------------------------------- Audiogramme

@bp.route("/<int:kid>/audiogramm/neu", methods=["GET", "POST"])
@bp.route("/<int:kid>/audiogramm/<int:aid>", methods=["GET", "POST"])
def audiogramm(kid, aid=None):
    kunde = hole_oder_404("kunden", kid)
    row = None
    if aid:
        row = db.query("SELECT * FROM audiogramme WHERE id = ? AND kunde_id = ?", (aid, kid), one=True)
        if row is None:
            return render_template("fehler.html", meldung="Audiogramm nicht gefunden."), 404
    werte = fachlogik.parse_werte(row["werte"]) if row else fachlogik.parse_werte("{}")
    if request.method == "POST":
        try:
            daten = fachlogik.werte_aus_formular(request.form)
            sv = {}
            for s in ("r", "l"):
                roh = request.form.get(f"sprachverstehen_{s}", "").strip()
                sv[s] = int(roh) if roh else None
                if sv[s] is not None and not 0 <= sv[s] <= 100:
                    raise ValueError("Sprachverstehen muss zwischen 0 und 100 % liegen.")
        except ValueError as e:
            flash(str(e) if "dB" in str(e) or "%" in str(e) else "Bitte nur Zahlen eintragen.", "fehler")
        else:
            eintrag = {"kunde_id": kid, "datum": request.form.get("datum") or None, "werte": json.dumps(daten),
                       "sprachverstehen_r": sv["r"], "sprachverstehen_l": sv["l"],
                       "bemerkung": request.form.get("bemerkung", "").strip() or None}
            if not eintrag["datum"]:
                flash("Bitte ein Messdatum angeben.", "fehler")
            else:
                if row:
                    db.update("audiogramme", row["id"], eintrag)
                else:
                    db.insert("audiogramme", eintrag)
                flash("Audiogramm gespeichert.", "ok")
                return redirect(url_for("kunden.detail", kid=kid))
    return render_template("kunden/audiogramm.html", k=kunde, row=row, werte=werte,
                           frequenzen=fachlogik.FREQUENZEN, kurven=fachlogik.KURVEN,
                           svg=fachlogik.audiogramm_svg(werte) if row else None,
                           auswertung=fachlogik.audiogramm_auswertung(werte) if row else None,
                           form=request.form if request.method == "POST" else None)


@bp.route("/<int:kid>/audiogramm/<int:aid>/loeschen", methods=["POST"])
def audiogramm_loeschen(kid, aid):
    db.execute("DELETE FROM audiogramme WHERE id = ? AND kunde_id = ?", (aid, kid))
    flash("Audiogramm gelöscht.", "ok")
    return redirect(url_for("kunden.detail", kid=kid))


# ------------------------------------------------------------------- Export

@bp.route("/export.csv")
def export():
    rows = db.query("SELECT ku.kundennummer, ku.anrede, ku.vorname, ku.nachname, ku.geburtsdatum, ku.strasse, "
                    "ku.plz, ku.ort, ku.telefon, ku.mobil, ku.email, ka.name AS krankenkasse, "
                    "ku.versichertennummer FROM kunden ku LEFT JOIN krankenkassen ka ON ka.id = ku.krankenkasse_id "
                    "ORDER BY ku.nachname")
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";")
    w.writerow(["Kundennr.", "Anrede", "Vorname", "Nachname", "Geburtsdatum", "Straße", "PLZ", "Ort",
                "Telefon", "Mobil", "E-Mail", "Krankenkasse", "Versichertennr."])
    for r in rows:
        w.writerow([("'" + str(v)) if isinstance(v, str) and v[:1] in "=+-@" else ("" if v is None else v)
                    for v in r])
    return Response("﻿" + puffer.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=kunden.csv"})
