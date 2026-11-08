from datetime import date, timedelta

from flask import Blueprint, render_template

from .. import db
from .rechnungen import SUMME_SQL
from .reparaturen import OFFEN as REP_OFFEN
from .versorgungen import OFFEN as VERS_OFFEN

bp = Blueprint("dashboard", __name__)

FOLGEVERSORGUNG_JAHRE = 6


@bp.route("/")
def index():
    heute = date.today()
    morgen = heute + timedelta(days=1)
    termine_heute = db.query(
        "SELECT t.*, ku.vorname, ku.nachname, ku.telefon FROM termine t LEFT JOIN kunden ku ON ku.id = t.kunde_id "
        "WHERE t.beginn >= ? AND t.beginn < ? ORDER BY t.beginn", (heute.isoformat(), morgen.isoformat()))
    termine_bald = db.query(
        "SELECT t.*, ku.vorname, ku.nachname FROM termine t LEFT JOIN kunden ku ON ku.id = t.kunde_id "
        "WHERE t.beginn >= ? AND t.beginn < ? ORDER BY t.beginn LIMIT 15",
        (morgen.isoformat(), (heute + timedelta(days=8)).isoformat()))
    versorgungen = db.query(
        f"SELECT v.*, ku.vorname, ku.nachname FROM versorgungen v JOIN kunden ku ON ku.id = v.kunde_id "
        f"WHERE v.status IN ({','.join('?' * len(VERS_OFFEN))}) ORDER BY v.beginn", VERS_OFFEN)
    offene_rechnungen = db.query(
        f"SELECT r.*, {SUMME_SQL} AS summe, ku.vorname, ku.nachname, ka.name AS kasse FROM rechnungen r "
        "LEFT JOIN kunden ku ON ku.id = r.kunde_id LEFT JOIN krankenkassen ka ON ka.id = r.krankenkasse_id "
        "WHERE r.status = 'offen' ORDER BY r.faellig_am")
    ueberfaellig = [r for r in offene_rechnungen if r["faellig_am"] and r["faellig_am"] < heute.isoformat()]
    lager = db.query("SELECT * FROM artikel WHERE aktiv = 1 AND mindestbestand > 0 AND bestand <= mindestbestand "
                     "ORDER BY bestand")
    reparaturen = db.query(
        f"SELECT r.*, ku.vorname, ku.nachname FROM reparaturen r JOIN kunden ku ON ku.id = r.kunde_id "
        f"WHERE r.status IN ({','.join('?' * len(REP_OFFEN))}) ORDER BY r.eingang", REP_OFFEN)
    stichtag = heute.replace(year=heute.year - FOLGEVERSORGUNG_JAHRE) if not (heute.month == 2 and heute.day == 29) \
        else heute.replace(year=heute.year - FOLGEVERSORGUNG_JAHRE, day=28)
    folgeversorgung = db.query(
        "SELECT ku.id, ku.vorname, ku.nachname, ku.telefon, MAX(v.abgabe_datum) AS letzte FROM kunden ku "
        "JOIN versorgungen v ON v.kunde_id = ku.id WHERE v.abgabe_datum IS NOT NULL "
        "AND v.status != 'Abgebrochen' GROUP BY ku.id HAVING letzte <= ? ORDER BY letzte LIMIT 20",
        (stichtag.isoformat(),))
    geburtstage = db.query("SELECT id, vorname, nachname, geburtsdatum FROM kunden "
                           "WHERE substr(geburtsdatum, 6, 5) = ?", (heute.isoformat()[5:],))
    return render_template(
        "dashboard.html", termine_heute=termine_heute, termine_bald=termine_bald, versorgungen=versorgungen,
        offene_rechnungen=offene_rechnungen, ueberfaellig=ueberfaellig,
        offen_summe=round(sum(r["summe"] for r in offene_rechnungen), 2), lager=lager, reparaturen=reparaturen,
        folgeversorgung=folgeversorgung, geburtstage=geburtstage, jahre=FOLGEVERSORGUNG_JAHRE,
        anzahl_kunden=db.query("SELECT COUNT(*) AS n FROM kunden", one=True)["n"])
