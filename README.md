# HörWin – Verwaltungsprogramm für Hörakustiker

Webbasierte Praxis- und Warenwirtschaftssoftware für Hörakustik-Fachgeschäfte.
Läuft lokal auf einem Rechner im Geschäft (oder im internen Netz) und wird im Browser bedient.
Technik: Python 3.10+, Flask, SQLite – keine externe Datenbank nötig.

## Funktionen

| Bereich | Inhalt |
|---|---|
| **Übersicht** | Termine heute/7 Tage, laufende Versorgungen, offene & überfällige Rechnungen, offene Reparaturen, Mindestbestand-Warnungen, Kunden mit möglicher Folgeversorgung (≥ 6 Jahre), Geburtstage |
| **Kunden** | Stammdaten, Kostenträger, Versichertennr., Zuzahlungsbefreiung, HNO-Arzt, DSGVO-Einwilligung, Suche, CSV-Export, Kundenakte mit allen Vorgängen, Löschen mit Bestätigung |
| **Audiogramme** | Tonaudiogramm (Luft-/Knochenleitung, rechts/links, 125 Hz–8 kHz), Sprachverstehen, grafische Darstellung, PTA4 und WHO-Schweregrad |
| **Versorgungen** | Ablauf Beratung → Vergleichsanpassung → KV eingereicht → Genehmigt → Abgegeben → Nachsorge → Abgeschlossen; Geräte mit Seriennummer; automatische Aufteilung in Kassenanteil (Festbetrag), gesetzliche Zuzahlung (10 %, min. 5 €, max. 10 €) und Eigenanteil; druckbarer Kostenvoranschlag mit Mehrkostenerklärung; Rechnungen an Kunde und Kostenträger per Knopfdruck; Lagerabbuchung und Nachsorgetermin bei Abgabe |
| **Termine** | Wochenansicht, Terminarten, Erledigt-Markierung |
| **Rechnungen** | Freier Verkauf (Batterien, Zubehör, Service) mit Lagerabbuchung, fortlaufende Nummern (JJJJ-NNNN), MwSt.-Ausweis je Satz, Zahlungseingang, Storno mit Lagerrückbuchung, Druck/PDF |
| **Reparaturen** | Eingang, Fehler, Status (Werkstatt/Hersteller/abholbereit), Garantie, Liegezeit |
| **Artikel & Lager** | Hörgeräte, Otoplastiken, Batterien, Zubehör, Dienstleistungen; Hilfsmittelnummer, Bestand, Mindestbestand, Schnellbuchung |
| **Kostenträger** | Krankenkassen/PKV/BG mit IK-Nummer und Festbetrag |
| **Einstellungen** | Firmendaten für Briefkopf, Benutzerverwaltung, Datenbanksicherung zum Download |

## Installation & Start

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Danach im Browser **http://127.0.0.1:5000** öffnen. Beim ersten Aufruf legen Sie den ersten Benutzer an.

Optional Demodaten (fiktive Personen, Login `demo` / `demo1234`) in eine leere Datenbank laden:

```bash
python beispieldaten.py
```

Für den Zugriff von anderen Rechnern im Geschäftsnetz: `HOERWIN_HOST=0.0.0.0 python run.py`
(Port mit `HOERWIN_PORT` änderbar). Dann unbedingt hinter HTTPS (z. B. Reverse-Proxy) betreiben.

## Daten & Datenschutz

* Alle Daten liegen in `instance/hoerwin.sqlite`. Sicherungen über ⚙ Einstellungen → „Sicherung herunterladen“
  oder durch Kopieren dieser Datei bei gestopptem Programm.
* Audiogramme sind Gesundheitsdaten (Art. 9 DSGVO): Rechner verschlüsseln, Sicherungen verschlüsselt aufbewahren,
  jedem Mitarbeiter einen eigenen Benutzer geben.
* Anmeldung mit gehashten Passwörtern, CSRF-Schutz für alle Formulare.

## Hinweise / Grenzen

* Festbeträge und Vertragspreise unterscheiden sich je Kasse und Vertrag – bitte je Kostenträger pflegen.
* Die elektronische Abrechnung mit den Krankenkassen (§ 302 SGB V, DTA) ist **nicht** enthalten; die Kassenrechnung
  dient als Grundlage bzw. für Kostenträger mit Papierabrechnung.
* Keine Steuer- oder Rechtsberatung: Rechnungsangaben (z. B. Pflichtangaben nach § 14 UStG) vor dem Produktiveinsatz prüfen.

## Entwicklung

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Aufbau: `hoerwin/fachlogik.py` (Berechnungen), `hoerwin/views/` (Module), `hoerwin/templates/` (Oberfläche),
`hoerwin/db.py` (Schema).
