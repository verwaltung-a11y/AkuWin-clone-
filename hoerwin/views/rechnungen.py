from datetime import date, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import db, fachlogik
from ..helpers import hole_oder_404, kunden_optionen, naechste_nummer

bp = Blueprint("rechnungen", __name__, url_prefix="/rechnungen")

SUMME_SQL = "(SELECT COALESCE(SUM(ROUND(menge * einzelpreis, 2)), 0) FROM rechnung_positionen WHERE rechnung_id = r.id)"


@bp.route("/")
def liste():
    status = request.args.get("status", "offen")
    sql = (f"SELECT r.*, {SUMME_SQL} AS summe, ku.vorname, ku.nachname, ka.name AS kasse FROM rechnungen r "
           "LEFT JOIN kunden ku ON ku.id = r.kunde_id LEFT JOIN krankenkassen ka ON ka.id = r.krankenkasse_id")
    if status in ("offen", "bezahlt", "storniert"):
        rows = db.query(sql + " WHERE r.status = ? ORDER BY r.nummer DESC", (status,))
    else:
        rows = db.query(sql + " ORDER BY r.nummer DESC")
    gesamt = round(sum(r["summe"] for r in rows), 2)
    return render_template("rechnungen/liste.html", rows=rows, status=status, gesamt=gesamt)


@bp.route("/neu", methods=["GET", "POST"])
def neu():
    """Freier Verkauf (Batterien, Zubehör, Dienstleistungen) an einen Kunden."""
    if request.method == "POST":
        kunde_id = request.form.get("kunde_id")
        if not kunde_id or not db.query("SELECT 1 FROM kunden WHERE id = ?", (kunde_id,), one=True):
            flash("Bitte einen Kunden wählen.", "fehler")
            return redirect(url_for("rechnungen.neu"))
        positionen = []
        for i in range(10):
            aid = request.form.get(f"artikel_{i}")
            frei = request.form.get(f"text_{i}", "").strip()
            if not aid and not frei:
                continue
            try:
                menge = float(request.form.get(f"menge_{i}", "1").replace(",", ".") or 1)
                preis_roh = request.form.get(f"preis_{i}", "").replace(",", ".").strip()
            except ValueError:
                flash(f"Ungültige Menge in Zeile {i + 1}.", "fehler")
                return redirect(url_for("rechnungen.neu"))
            artikel = db.query("SELECT * FROM artikel WHERE id = ?", (aid,), one=True) if aid else None
            try:
                preis = float(preis_roh) if preis_roh else float(artikel["preis"] if artikel else 0)
            except ValueError:
                flash(f"Ungültiger Preis in Zeile {i + 1}.", "fehler")
                return redirect(url_for("rechnungen.neu"))
            positionen.append({"artikel_id": artikel["id"] if artikel else None, "menge": menge,
                               "bezeichnung": frei or f"{artikel['hersteller'] or ''} {artikel['bezeichnung']}".strip(),
                               "einzelpreis": preis, "mwst": float(artikel["mwst"]) if artikel else 19.0})
        if not positionen:
            flash("Bitte mindestens eine Position erfassen.", "fehler")
            return redirect(url_for("rechnungen.neu"))
        heute = date.today()
        rid = db.insert("rechnungen", {"nummer": naechste_nummer(), "datum": heute.isoformat(),
                                       "faellig_am": (heute + timedelta(days=14)).isoformat(),
                                       "kunde_id": int(kunde_id), "empfaenger": "kunde",
                                       "status": "bezahlt" if request.form.get("bar") else "offen",
                                       "bezahlt_am": heute.isoformat() if request.form.get("bar") else None,
                                       "notiz": request.form.get("notiz", "").strip() or None})
        for p in positionen:
            db.insert("rechnung_positionen", {"rechnung_id": rid, **p})
            if p["artikel_id"]:
                db.execute("UPDATE artikel SET bestand = bestand - ? WHERE id = ? AND kategorie != 'Dienstleistung'",
                           (p["menge"], p["artikel_id"]))
        flash("Rechnung erstellt.", "ok")
        return redirect(url_for("rechnungen.detail", rid=rid))
    artikel = db.query("SELECT * FROM artikel WHERE aktiv = 1 ORDER BY kategorie, hersteller, bezeichnung")
    return render_template("rechnungen/neu.html", kunden=kunden_optionen(), artikel=artikel,
                           kunde_id=request.args.get("kunde", ""))


def _lade(rid):
    r = db.query("SELECT r.*, ku.anrede, ku.vorname, ku.nachname, ku.strasse, ku.plz, ku.ort, ku.kundennummer, "
                 "ku.versichertennummer, ka.name AS kasse, ka.ik_nummer, ka.strasse AS k_strasse, ka.plz AS k_plz, "
                 "ka.ort AS k_ort FROM rechnungen r LEFT JOIN kunden ku ON ku.id = r.kunde_id "
                 "LEFT JOIN krankenkassen ka ON ka.id = r.krankenkasse_id WHERE r.id = ?", (rid,), one=True)
    if r is None:
        return None, None, None
    pos = db.query("SELECT * FROM rechnung_positionen WHERE rechnung_id = ? ORDER BY id", (rid,))
    return r, pos, fachlogik.rechnung_summen(pos)


@bp.route("/<int:rid>")
def detail(rid):
    r, pos, summen = _lade(rid)
    if r is None:
        return render_template("fehler.html", meldung="Rechnung nicht gefunden."), 404
    return render_template("rechnungen/detail.html", r=r, pos=pos, s=summen)


@bp.route("/<int:rid>/druck")
def druck(rid):
    r, pos, summen = _lade(rid)
    if r is None:
        return render_template("fehler.html", meldung="Rechnung nicht gefunden."), 404
    return render_template("druck/rechnung.html", r=r, pos=pos, s=summen)


@bp.route("/<int:rid>/status", methods=["POST"])
def status(rid):
    r = hole_oder_404("rechnungen", rid)
    neu = request.form.get("status")
    if neu == "bezahlt" and r["status"] == "offen":
        db.update("rechnungen", rid, {"status": "bezahlt",
                                      "bezahlt_am": request.form.get("bezahlt_am") or date.today().isoformat()})
    elif neu == "offen" and r["status"] == "bezahlt":
        db.update("rechnungen", rid, {"status": "offen", "bezahlt_am": None})
    elif neu == "storniert" and r["status"] != "storniert":
        db.update("rechnungen", rid, {"status": "storniert"})
        # Lagerbestand für frei verkaufte Artikel zurückbuchen
        if not r["versorgung_id"]:
            for p in db.query("SELECT artikel_id, menge FROM rechnung_positionen WHERE rechnung_id = ? "
                              "AND artikel_id IS NOT NULL", (rid,)):
                db.execute("UPDATE artikel SET bestand = bestand + ? WHERE id = ? AND kategorie != 'Dienstleistung'",
                           (p["menge"], p["artikel_id"]))
    else:
        flash("Statuswechsel nicht möglich.", "fehler")
        return redirect(url_for("rechnungen.detail", rid=rid))
    flash(f"Rechnung {r['nummer']}: {neu}.", "ok")
    return redirect(url_for("rechnungen.detail", rid=rid))
