"""Fachliche Berechnungen: Audiogramm, Kassenabrechnung, Rechnungssummen."""
import json
import math
from datetime import date

FREQUENZEN = [125, 250, 500, 750, 1000, 1500, 2000, 3000, 4000, 6000, 8000]
KURVEN = {
    "r_ll": "Rechts Luftleitung",
    "r_kl": "Rechts Knochenleitung",
    "l_ll": "Links Luftleitung",
    "l_kl": "Links Knochenleitung",
}

# WHO-Einteilung (2021) nach 4-Frequenz-Mittelwert (500/1000/2000/4000 Hz)
WHO_GRADE = [
    (20, "normal"),
    (35, "leichtgradig"),
    (50, "mittelgradig"),
    (65, "mittel- bis hochgradig"),
    (80, "hochgradig"),
    (95, "an Taubheit grenzend (schwer)"),
    (math.inf, "vollständiger Hörverlust / Taubheit"),
]

FESTE_ZUZAHLUNG_MIN = 5.0
FESTE_ZUZAHLUNG_MAX = 10.0


# ---------------------------------------------------------------- Audiogramm

def parse_werte(text):
    try:
        daten = json.loads(text or "{}")
    except ValueError:
        daten = {}
    return {k: {int(f): v for f, v in daten.get(k, {}).items()} for k in KURVEN}


def werte_aus_formular(form):
    """Liest Felder wie ``r_ll_1000`` und liefert ein JSON-serialisierbares Dict."""
    daten = {}
    for kurve in KURVEN:
        reihe = {}
        for f in FREQUENZEN:
            roh = (form.get(f"{kurve}_{f}") or "").strip().replace(",", ".")
            if roh == "":
                continue
            wert = float(roh)
            if not -10 <= wert <= 120:
                raise ValueError(f"{KURVEN[kurve]} bei {f} Hz: {roh} dB liegt außerhalb von -10…120 dB HL")
            reihe[str(f)] = wert
        daten[kurve] = reihe
    return daten


def pta4(reihe):
    """4-Frequenz-Mittelwert (PTA4) oder None, wenn Werte fehlen."""
    noetig = [500, 1000, 2000, 4000]
    if not all(f in reihe for f in noetig):
        return None
    return sum(reihe[f] for f in noetig) / 4


def who_grad(mittelwert):
    if mittelwert is None:
        return "–"
    for grenze, text in WHO_GRADE:
        if mittelwert < grenze:
            return text
    return WHO_GRADE[-1][1]


def audiogramm_auswertung(werte):
    erg = {}
    for seite, kurve in (("rechts", "r_ll"), ("links", "l_ll")):
        m = pta4(werte[kurve])
        erg[seite] = {"pta4": m, "grad": who_grad(m)}
    return erg


def audiogramm_svg(werte, breite=520, hoehe=380):
    """Erzeugt ein Tonaudiogramm als SVG (rechts rot ○, links blau ×, KL als < >)."""
    rand_l, rand_o, rand_r, rand_u = 48, 28, 16, 30
    pb, ph = breite - rand_l - rand_r, hoehe - rand_o - rand_u
    lmin, lmax = math.log2(125), math.log2(8000)

    def x(f):
        return rand_l + (math.log2(f) - lmin) / (lmax - lmin) * pb

    def y(db):
        return rand_o + (db + 10) / 130 * ph

    t = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {breite} {hoehe}" '
         f'class="audiogramm" role="img" aria-label="Tonaudiogramm">']
    t.append(f'<rect x="{rand_l}" y="{rand_o}" width="{pb}" height="{ph}" class="ag-feld"/>')
    for db in range(-10, 121, 10):
        t.append(f'<line x1="{rand_l}" x2="{rand_l + pb}" y1="{y(db):.1f}" y2="{y(db):.1f}" '
                 f'class="ag-gitter{" ag-null" if db == 0 else ""}"/>')
        t.append(f'<text x="{rand_l - 6}" y="{y(db) + 4:.1f}" text-anchor="end" class="ag-text">{db}</text>')
    for f in FREQUENZEN:
        t.append(f'<line x1="{x(f):.1f}" x2="{x(f):.1f}" y1="{rand_o}" y2="{rand_o + ph}" class="ag-gitter"/>')
        label = f"{f // 1000}k" if f >= 1000 and f % 1000 == 0 else (f"{f / 1000:g}k" if f >= 1000 else str(f))
        t.append(f'<text x="{x(f):.1f}" y="{rand_o - 8}" text-anchor="middle" class="ag-text">{label}</text>')
    t.append(f'<text x="12" y="{rand_o + ph / 2:.0f}" transform="rotate(-90 12 {rand_o + ph / 2:.0f})" '
             f'text-anchor="middle" class="ag-text">dB HL</text>')
    t.append(f'<text x="{rand_l + pb / 2:.0f}" y="{hoehe - 8}" text-anchor="middle" class="ag-text">Frequenz (Hz)</text>')

    for kurve, klasse in (("r_ll", "ag-rechts"), ("l_ll", "ag-links"),
                          ("r_kl", "ag-rechts ag-kl"), ("l_kl", "ag-links ag-kl")):
        punkte = sorted(werte[kurve].items())
        if not punkte:
            continue
        if len(punkte) > 1:
            pfad = " ".join(f"{x(f):.1f},{y(v):.1f}" for f, v in punkte)
            t.append(f'<polyline points="{pfad}" class="ag-linie {klasse}"/>')
        for f, v in punkte:
            px, py = x(f), y(v)
            if kurve == "r_ll":
                t.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="6" class="ag-symbol {klasse}"/>')
            elif kurve == "l_ll":
                t.append(f'<path d="M{px - 5:.1f},{py - 5:.1f}L{px + 5:.1f},{py + 5:.1f}'
                         f'M{px + 5:.1f},{py - 5:.1f}L{px - 5:.1f},{py + 5:.1f}" class="ag-symbol {klasse}"/>')
            elif kurve == "r_kl":
                t.append(f'<path d="M{px - 2:.1f},{py - 6:.1f}L{px - 9:.1f},{py:.1f}L{px - 2:.1f},{py + 6:.1f}" '
                         f'class="ag-symbol {klasse}"/>')
            else:
                t.append(f'<path d="M{px + 2:.1f},{py - 6:.1f}L{px + 9:.1f},{py:.1f}L{px + 2:.1f},{py + 6:.1f}" '
                         f'class="ag-symbol {klasse}"/>')
    t.append("</svg>")
    return "".join(t)


# ---------------------------------------------------------- Kassenabrechnung

def gesetzliche_zuzahlung(kassenleistung):
    """§ 61 SGB V: 10 % des Abgabepreises, mindestens 5 €, höchstens 10 €, nie mehr als die Leistung."""
    if kassenleistung <= 0:
        return 0.0
    z = min(max(0.10 * kassenleistung, FESTE_ZUZAHLUNG_MIN), FESTE_ZUZAHLUNG_MAX)
    return round(min(z, kassenleistung), 2)


def versorgung_berechnung(geraete, kasse, zuzahlungsbefreit):
    """Teilt jeden Gerätepreis in Kassenanteil, Zuzahlung und Eigenanteil auf."""
    gesetzlich = bool(kasse) and kasse["art"] == "gesetzlich"
    festbetrag = float(kasse["festbetrag"] or 0) if gesetzlich else 0.0
    zeilen, summe = [], {"preis": 0.0, "kasse": 0.0, "zuzahlung": 0.0, "eigenanteil": 0.0, "kunde": 0.0}
    for g in geraete:
        preis = float(g["preis"] or 0)
        leistung = min(preis, festbetrag)
        zuzahlung = 0.0 if zuzahlungsbefreit else gesetzliche_zuzahlung(leistung)
        zeile = {
            "geraet": g,
            "preis": round(preis, 2),
            "kasse": round(leistung - zuzahlung, 2),
            "zuzahlung": zuzahlung,
            "eigenanteil": round(preis - leistung, 2),
        }
        zeile["kunde"] = round(zeile["eigenanteil"] + zuzahlung, 2)
        zeilen.append(zeile)
        for k in summe:
            summe[k] = round(summe[k] + zeile[k], 2)
    return {"zeilen": zeilen, "summe": summe, "gesetzlich": gesetzlich, "festbetrag": festbetrag}


# --------------------------------------------------------------- Rechnungen

def rechnung_summen(positionen):
    """Positionen enthalten Bruttopreise; liefert Brutto, Netto und MwSt je Satz."""
    brutto, je_satz = 0.0, {}
    for p in positionen:
        b = round(float(p["menge"]) * float(p["einzelpreis"]), 2)
        brutto += b
        je_satz[float(p["mwst"])] = je_satz.get(float(p["mwst"]), 0.0) + b
    steuern = {satz: round(b - b / (1 + satz / 100), 2) for satz, b in sorted(je_satz.items())}
    brutto = round(brutto, 2)
    return {"brutto": brutto, "steuern": steuern, "netto": round(brutto - sum(steuern.values()), 2)}


def alter(geburtsdatum, stichtag=None):
    if not geburtsdatum:
        return None
    try:
        geb = date.fromisoformat(geburtsdatum)
    except ValueError:
        return None
    heute = stichtag or date.today()
    return heute.year - geb.year - ((heute.month, heute.day) < (geb.month, geb.day))
