"""Jinja-Filter, Formular-Hilfen und gemeinsam genutzte Funktionen."""
from datetime import date, datetime

from flask import abort, request

from . import db


def euro(wert):
    try:
        betrag = float(wert or 0)
    except (TypeError, ValueError):
        return wert
    text = f"{betrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} €"


def datum(wert):
    if not wert:
        return ""
    try:
        if len(wert) > 10:
            return datetime.fromisoformat(wert).strftime("%d.%m.%Y %H:%M")
        return date.fromisoformat(wert).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return wert


def uhrzeit(wert):
    try:
        return datetime.fromisoformat(wert).strftime("%H:%M")
    except (TypeError, ValueError):
        return ""


def zahl(wert):
    if wert is None:
        return ""
    return f"{wert:g}".replace(".", ",")


def norm(wert):
    """Vereinheitlicht Werte für Vergleiche in Auswahllisten (19.0 == "19", None == "")."""
    if wert is None:
        return ""
    if isinstance(wert, float) and wert.is_integer():
        return str(int(wert))
    text = str(wert)
    return text[:-2] if text.endswith(".0") else text


def tage_seit(wert):
    try:
        return (date.today() - date.fromisoformat(wert)).days
    except (TypeError, ValueError):
        return ""


def register(app):
    app.jinja_env.filters.update(euro=euro, datum=datum, uhrzeit=uhrzeit, zahl=zahl, norm=norm,
                                 tage_seit=tage_seit)

    @app.context_processor
    def globals_():
        return {"heute": date.today().isoformat(), "firma": lambda k, s="": db.einstellung(k, s)}


# ------------------------------------------------------------------ Formulare

class Feld:
    """Beschreibt ein Formularfeld. ``art``: text, textarea, date, number, money, select, check, email, tel."""

    def __init__(self, name, label, art="text", pflicht=False, optionen=None, breit=False, hilfe=None):
        self.name, self.label, self.art = name, label, art
        self.pflicht, self.optionen, self.breit, self.hilfe = pflicht, optionen, breit, hilfe

    def optionen_liste(self):
        opts = self.optionen() if callable(self.optionen) else (self.optionen or [])
        return [(o, o) if isinstance(o, str) else o for o in opts]


def formular_daten(felder, form):
    """Liest und validiert Formulardaten. Gibt (daten, fehler) zurück."""
    daten, fehler = {}, []
    for f in felder:
        if f.art == "check":
            daten[f.name] = 1 if form.get(f.name) else 0
            continue
        roh = (form.get(f.name) or "").strip()
        if f.art == "select" and not roh and not f.pflicht:
            werte = [str(v) for v, _ in f.optionen_liste()]
            if werte and "" not in werte:
                roh = werte[0]  # Auswahl ohne Leer-Option: erste Option als Standard
        if f.pflicht and not roh:
            fehler.append(f"„{f.label}“ ist ein Pflichtfeld.")
            continue
        if f.art in ("number", "money"):
            if roh == "":
                daten[f.name] = 0
                continue
            try:
                wert = float(roh.replace(".", "").replace(",", ".") if "," in roh else roh)
            except ValueError:
                fehler.append(f"„{f.label}“ muss eine Zahl sein.")
                continue
            daten[f.name] = int(wert) if f.art == "number" and wert.is_integer() else wert
        elif f.art == "date" and roh:
            try:
                date.fromisoformat(roh)
            except ValueError:
                fehler.append(f"„{f.label}“ ist kein gültiges Datum.")
                continue
            daten[f.name] = roh
        elif f.art == "select" and roh:
            erlaubt = {str(v) for v, _ in f.optionen_liste()}
            if roh not in erlaubt:
                fehler.append(f"Ungültige Auswahl bei „{f.label}“.")
                continue
            daten[f.name] = int(roh) if roh.isdigit() and f.name.endswith("_id") else roh
        else:
            daten[f.name] = roh or None
    return daten, fehler


def hole_oder_404(tabelle, row_id):
    row = db.query(f"SELECT * FROM {tabelle} WHERE id = ?", (row_id,), one=True)
    if row is None:
        abort(404)
    return row


def kunden_optionen():
    rows = db.query("SELECT id, nachname, vorname, kundennummer FROM kunden ORDER BY nachname, vorname")
    return [("", "– bitte wählen –")] + [
        (str(r["id"]), f"{r['nachname']}, {r['vorname'] or ''} ({r['kundennummer']})") for r in rows]


def kassen_optionen():
    rows = db.query("SELECT id, name FROM krankenkassen ORDER BY name")
    return [("", "– keine –")] + [(str(r["id"]), r["name"]) for r in rows]


def seite_suche():
    return (request.args.get("q") or "").strip()


def naechste_nummer():
    """Fortlaufende Rechnungsnummer im Format JJJJ-NNNN."""
    jahr = date.today().year
    row = db.query("SELECT nummer FROM rechnungen WHERE nummer LIKE ? ORDER BY nummer DESC LIMIT 1",
                   (f"{jahr}-%",), one=True)
    lfd = int(row["nummer"].split("-")[1]) + 1 if row else 1
    return f"{jahr}-{lfd:04d}"
