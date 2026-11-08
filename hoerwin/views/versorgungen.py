from datetime import date, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import db, fachlogik
from ..helpers import Feld, hole_oder_404, kunden_optionen, naechste_nummer
from . import formular_seite

bp = Blueprint("versorgungen", __name__, url_prefix="/versorgungen")

STATUS = ["Beratung", "Vergleichsanpassung", "Kostenvoranschlag eingereicht", "Genehmigt",
          "Abgegeben", "Nachsorge", "Abgeschlossen", "Abgebrochen"]
OFFEN = STATUS[:6]
SEITEN = ["beidseitig", "rechts", "links"]


def felder(mit_kunde=True):
    f = [
        Feld("beginn", "Beginn", "date", pflicht=True),
        Feld("seite", "Versorgung", "select", optionen=SEITEN),
        Feld("status", "Status", "select", optionen=STATUS),
        Feld("verordnung_datum", "Datum ohrenärztl. Verordnung", "date"),
        Feld("verordnender_arzt", "Verordnender Arzt"),
        Feld("genehmigt_datum", "Genehmigt am", "date"),
        Feld("abgabe_datum", "Abgabe am", "date"),
        Feld("notiz", "Notiz", "textarea", breit=True),
    ]
    if mit_kunde:
        f.insert(0, Feld("kunde_id", "Kunde", "select", pflicht=True, optionen=kunden_optionen, breit=True))
    return f


def _lade(vid):
    v = db.query("SELECT v.*, ku.vorname, ku.nachname, ku.kundennummer, ku.zuzahlungsbefreit, "
                 "ku.krankenkasse_id, ku.versichertennummer, ku.geburtsdatum, ku.strasse, ku.plz, ku.ort, "
                 "ku.anrede FROM versorgungen v JOIN kunden ku ON ku.id = v.kunde_id WHERE v.id = ?",
                 (vid,), one=True)
    if v is None:
        return None, None, None, None
    kasse = db.query("SELECT * FROM krankenkassen WHERE id = ?", (v["krankenkasse_id"],), one=True) \
        if v["krankenkasse_id"] else None
    geraete = db.query("SELECT g.*, a.hilfsmittelnummer, a.hersteller FROM versorgung_geraete g "
                       "LEFT JOIN artikel a ON a.id = g.artikel_id WHERE versorgung_id = ? ORDER BY g.id", (vid,))
    return v, kasse, geraete, fachlogik.versorgung_berechnung(geraete, kasse, bool(v["zuzahlungsbefreit"]))


@bp.route("/")
def liste():
    status = request.args.get("status", "offen")
    sql = ("SELECT v.*, ku.vorname, ku.nachname, (SELECT COUNT(*) FROM versorgung_geraete WHERE "
           "versorgung_id = v.id) AS geraete FROM versorgungen v JOIN kunden ku ON ku.id = v.kunde_id")
    if status == "offen":
        rows = db.query(sql + f" WHERE v.status IN ({','.join('?' * len(OFFEN))}) ORDER BY v.beginn", OFFEN)
    elif status in STATUS:
        rows = db.query(sql + " WHERE v.status = ? ORDER BY v.beginn DESC", (status,))
    else:
        rows = db.query(sql + " ORDER BY v.beginn DESC")
    return render_template("versorgungen/liste.html", rows=rows, status=status, alle_status=STATUS)


@bp.route("/neu", methods=["GET", "POST"])
def neu():
    vorbelegung = {"beginn": date.today().isoformat(), "seite": "beidseitig", "status": "Beratung",
                   "kunde_id": request.args.get("kunde", "")}
    return formular_seite(felder(), "Neue Versorgung", "versorgungen",
                          lambda vid: url_for("versorgungen.detail", vid=vid), vorbelegung=vorbelegung,
                          abbrechen=request.referrer or url_for("versorgungen.liste"))


@bp.route("/<int:vid>")
def detail(vid):
    v, kasse, geraete, rechnung = _lade(vid)
    if v is None:
        return render_template("fehler.html", meldung="Versorgung nicht gefunden."), 404
    hoergeraete = db.query("SELECT * FROM artikel WHERE aktiv = 1 AND kategorie IN ('Hörgerät', 'Otoplastik') "
                           "ORDER BY hersteller, bezeichnung")
    rechnungen = db.query("SELECT * FROM rechnungen WHERE versorgung_id = ? ORDER BY id", (vid,))
    return render_template("versorgungen/detail.html", v=v, kasse=kasse, geraete=geraete, b=rechnung,
                           hoergeraete=hoergeraete, rechnungen=rechnungen, alle_status=STATUS, seiten=SEITEN)


@bp.route("/<int:vid>/bearbeiten", methods=["GET", "POST"])
def bearbeiten(vid):
    row = hole_oder_404("versorgungen", vid)
    return formular_seite(felder(mit_kunde=False), "Versorgung bearbeiten", "versorgungen",
                          lambda _id: url_for("versorgungen.detail", vid=vid), row=row,
                          abbrechen=url_for("versorgungen.detail", vid=vid))


@bp.route("/<int:vid>/status", methods=["POST"])
def status(vid):
    v = hole_oder_404("versorgungen", vid)
    neu = request.form.get("status")
    if neu not in STATUS:
        flash("Unbekannter Status.", "fehler")
        return redirect(url_for("versorgungen.detail", vid=vid))
    daten = {"status": neu}
    heute = date.today().isoformat()
    if neu == "Genehmigt" and not v["genehmigt_datum"]:
        daten["genehmigt_datum"] = heute
    if neu == "Abgegeben":
        if not v["abgabe_datum"]:
            daten["abgabe_datum"] = heute
        if not v["lager_gebucht"]:
            for g in db.query("SELECT artikel_id FROM versorgung_geraete WHERE versorgung_id = ? "
                              "AND artikel_id IS NOT NULL", (vid,)):
                db.execute("UPDATE artikel SET bestand = bestand - 1 WHERE id = ?", (g["artikel_id"],))
            daten["lager_gebucht"] = 1
            # Nachsorgetermin in sechs Wochen vorschlagen
            db.insert("termine", {"kunde_id": v["kunde_id"], "dauer_min": 30, "art": "Nachsorge",
                                  "beginn": f"{(date.today() + timedelta(weeks=6)).isoformat()}T10:00",
                                  "notiz": "Automatisch angelegt bei Abgabe – bitte mit Kunde abstimmen."})
            flash("Lagerbestand gebucht und Nachsorgetermin in 6 Wochen vorgemerkt.", "ok")
    db.update("versorgungen", vid, daten)
    flash(f"Status: {neu}", "ok")
    return redirect(url_for("versorgungen.detail", vid=vid))


@bp.route("/<int:vid>/geraet", methods=["POST"])
def geraet_hinzufuegen(vid):
    hole_oder_404("versorgungen", vid)
    artikel_id = request.form.get("artikel_id")
    artikel = db.query("SELECT * FROM artikel WHERE id = ?", (artikel_id,), one=True) if artikel_id else None
    bezeichnung = request.form.get("bezeichnung", "").strip() or (
        f"{artikel['hersteller'] or ''} {artikel['bezeichnung']}".strip() if artikel else "")
    if not bezeichnung:
        flash("Bitte einen Artikel wählen oder eine Bezeichnung eingeben.", "fehler")
        return redirect(url_for("versorgungen.detail", vid=vid))
    roh_preis = request.form.get("preis", "").strip().replace(",", ".")
    try:
        preis = float(roh_preis) if roh_preis else float(artikel["preis"] if artikel else 0)
    except ValueError:
        flash("Ungültiger Preis.", "fehler")
        return redirect(url_for("versorgungen.detail", vid=vid))
    seite = request.form.get("seite") if request.form.get("seite") in ("rechts", "links") else None
    db.insert("versorgung_geraete", {"versorgung_id": vid, "artikel_id": artikel["id"] if artikel else None,
                                     "bezeichnung": bezeichnung, "seite": seite, "preis": preis,
                                     "seriennummer": request.form.get("seriennummer", "").strip() or None})
    return redirect(url_for("versorgungen.detail", vid=vid))


@bp.route("/<int:vid>/geraet/<int:gid>", methods=["POST"])
def geraet_aendern(vid, gid):
    if request.form.get("aktion") == "loeschen":
        db.execute("DELETE FROM versorgung_geraete WHERE id = ? AND versorgung_id = ?", (gid, vid))
    else:
        db.execute("UPDATE versorgung_geraete SET seriennummer = ? WHERE id = ? AND versorgung_id = ?",
                   (request.form.get("seriennummer", "").strip() or None, gid, vid))
    return redirect(url_for("versorgungen.detail", vid=vid))


@bp.route("/<int:vid>/kostenvoranschlag")
def kostenvoranschlag(vid):
    v, kasse, geraete, b = _lade(vid)
    if v is None:
        return render_template("fehler.html", meldung="Versorgung nicht gefunden."), 404
    audiogramm = db.query("SELECT * FROM audiogramme WHERE kunde_id = ? ORDER BY datum DESC LIMIT 1",
                          (v["kunde_id"],), one=True)
    auswertung = fachlogik.audiogramm_auswertung(fachlogik.parse_werte(audiogramm["werte"])) if audiogramm else None
    return render_template("druck/kostenvoranschlag.html", v=v, kasse=kasse, b=b, audiogramm=audiogramm,
                           auswertung=auswertung)


@bp.route("/<int:vid>/rechnungen", methods=["POST"])
def rechnungen_erzeugen(vid):
    v, kasse, geraete, b = _lade(vid)
    if v is None:
        return render_template("fehler.html", meldung="Versorgung nicht gefunden."), 404
    if not geraete:
        flash("Die Versorgung enthält noch keine Geräte.", "fehler")
        return redirect(url_for("versorgungen.detail", vid=vid))
    if db.query("SELECT 1 FROM rechnungen WHERE versorgung_id = ? AND status != 'storniert'", (vid,), one=True):
        flash("Für diese Versorgung existieren bereits Rechnungen. Bitte zuerst stornieren.", "fehler")
        return redirect(url_for("versorgungen.detail", vid=vid))
    heute = date.today()
    erzeugt = []

    def anlegen(empfaenger, positionen, kasse_id=None):
        rid = db.insert("rechnungen", {
            "nummer": naechste_nummer(), "datum": heute.isoformat(),
            "faellig_am": (heute + timedelta(days=14 if empfaenger == "kunde" else 30)).isoformat(),
            "kunde_id": v["kunde_id"], "krankenkasse_id": kasse_id, "empfaenger": empfaenger,
            "versorgung_id": vid})
        for p in positionen:
            db.insert("rechnung_positionen", {"rechnung_id": rid, "menge": 1, "mwst": 19, **p})
        erzeugt.append(rid)

    kunden_pos, kassen_pos = [], []
    for z in b["zeilen"]:
        g = z["geraet"]
        name = f"{g['bezeichnung']}{' (' + g['seite'] + ')' if g['seite'] else ''}" \
               f"{', SN ' + g['seriennummer'] if g['seriennummer'] else ''}"
        if z["kasse"] > 0:
            kassen_pos.append({"artikel_id": g["artikel_id"], "einzelpreis": z["kasse"],
                               "bezeichnung": f"{name}{' – HMV ' + g['hilfsmittelnummer'] if g['hilfsmittelnummer'] else ''}"
                                              f" (Vertragspreis abzgl. Zuzahlung)"})
        if z["eigenanteil"] > 0:
            kunden_pos.append({"artikel_id": g["artikel_id"], "einzelpreis": z["eigenanteil"],
                               "bezeichnung": f"Wirtschaftliche Aufzahlung (Eigenanteil): {name}"})
        if z["zuzahlung"] > 0:
            kunden_pos.append({"einzelpreis": z["zuzahlung"],
                               "bezeichnung": f"Gesetzliche Zuzahlung gem. § 33 Abs. 8 SGB V: {name}"})
    if kunden_pos:
        anlegen("kunde", kunden_pos)
    if kassen_pos:
        anlegen("kasse", kassen_pos, kasse["id"])
    flash(f"{len(erzeugt)} Rechnung(en) erzeugt.", "ok")
    return redirect(url_for("versorgungen.detail", vid=vid))


@bp.route("/<int:vid>/loeschen", methods=["POST"])
def loeschen(vid):
    v = hole_oder_404("versorgungen", vid)
    db.execute("DELETE FROM versorgungen WHERE id = ?", (vid,))
    flash("Versorgung gelöscht.", "ok")
    return redirect(url_for("kunden.detail", kid=v["kunde_id"]))
