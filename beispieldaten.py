"""Füllt eine leere HörWin-Datenbank mit Demodaten (fiktive Personen).

    python beispieldaten.py
"""
import json
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

from hoerwin import create_app, db


def main():
    app = create_app()
    with app.app_context():
        if db.query("SELECT 1 FROM kunden LIMIT 1", one=True):
            print("Die Datenbank enthält bereits Kunden – keine Demodaten angelegt.")
            return
        if not db.query("SELECT 1 FROM benutzer LIMIT 1", one=True):
            db.insert("benutzer", {"benutzername": "demo", "name": "Demo",
                                   "passwort_hash": generate_password_hash("demo1234")})
            print("Benutzer 'demo' mit Passwort 'demo1234' angelegt – bitte nach dem ersten Login ändern!")
        for k, v in {"firma_name": "Hörakustik Muster", "firma_strasse": "Musterstraße 1",
                     "firma_plz_ort": "12345 Musterstadt", "firma_telefon": "01234 567890",
                     "firma_email": "info@example.org", "firma_ik": "590000000",
                     "firma_bank": "IBAN DE00 0000 0000 0000 0000 00 · Musterbank"}.items():
            if not db.einstellung(k):
                db.setze_einstellung(k, v)

        kasse_gkv = db.insert("krankenkassen", {"name": "Musterkasse (GKV)", "ik_nummer": "100000001",
                                                "art": "gesetzlich", "festbetrag": 733.59,
                                                "strasse": "Kassenweg 5", "plz": "12345", "ort": "Musterstadt"})
        kasse_pkv = db.insert("krankenkassen", {"name": "Private Beispielversicherung", "art": "privat"})

        artikel = {}
        for kat, herst, bez, bauform, preis, bestand, mindest in [
            ("Hörgerät", "Hersteller A", "Basis 2 RIC", "RIC/RITE", 733.59, 4, 2),
            ("Hörgerät", "Hersteller A", "Komfort 5 RIC", "RIC/RITE", 1690.00, 2, 1),
            ("Hörgerät", "Hersteller B", "Premium 7 HdO", "HdO", 2490.00, 1, 1),
            ("Otoplastik", "Labor C", "Otoplastik weich", None, 60.00, 0, 0),
            ("Batterie", "Hersteller D", "Batterien Größe 312 (6 Stk.)", None, 4.50, 30, 20),
            ("Batterie", "Hersteller D", "Batterien Größe 13 (6 Stk.)", None, 4.50, 8, 20),
            ("Pflegemittel", "Hersteller E", "Reinigungstücher (25 Stk.)", None, 6.90, 15, 5),
            ("Gehörschutz", "Labor C", "Gehörschutz individuell", None, 149.00, 0, 0),
            ("Dienstleistung", None, "Reinigung & Service", None, 15.00, 0, 0),
        ]:
            artikel[bez] = db.insert("artikel", {"kategorie": kat, "hersteller": herst, "bezeichnung": bez,
                                                 "bauform": bauform, "preis": preis, "bestand": bestand,
                                                 "mindestbestand": mindest, "mwst": 19,
                                                 "hilfsmittelnummer": "1399040000" if kat == "Hörgerät" else None})

        heute = date.today()
        kunden = []
        for i, (anrede, vn, nn, geb, kasse, befreit) in enumerate([
            ("Frau", "Erika", "Beispiel", "1948-03-12", kasse_gkv, 0),
            ("Herr", "Max", "Mustermann", "1955-07-30", kasse_gkv, 1),
            ("Frau", "Gisela", "Probe", "1940-11-02", kasse_pkv, 0),
            ("Herr", "Otto", "Normal", heute.replace(year=1950).isoformat(), kasse_gkv, 0),
        ]):
            kunden.append(db.insert("kunden", {
                "kundennummer": str(10001 + i), "anrede": anrede, "vorname": vn, "nachname": nn,
                "geburtsdatum": geb, "strasse": f"Beispielweg {i + 1}", "plz": "12345", "ort": "Musterstadt",
                "telefon": f"01234 1000{i}", "krankenkasse_id": kasse, "versichertennummer": f"A12345678{i}",
                "zuzahlungsbefreit": befreit, "einwilligung_dsgvo": 1, "hno_arzt": "Dr. med. Ohr, Musterstadt"}))

        werte = {"r_ll": {"250": 20, "500": 30, "1000": 40, "2000": 55, "4000": 65, "8000": 75},
                 "l_ll": {"250": 25, "500": 35, "1000": 45, "2000": 60, "4000": 70, "8000": 80},
                 "r_kl": {"500": 25, "1000": 35, "2000": 50, "4000": 60},
                 "l_kl": {"500": 30, "1000": 40, "2000": 55, "4000": 65}}
        db.insert("audiogramme", {"kunde_id": kunden[0], "datum": (heute - timedelta(days=20)).isoformat(),
                                  "werte": json.dumps(werte), "sprachverstehen_r": 70, "sprachverstehen_l": 60})

        v1 = db.insert("versorgungen", {"kunde_id": kunden[0], "beginn": (heute - timedelta(days=20)).isoformat(),
                                        "seite": "beidseitig", "status": "Vergleichsanpassung",
                                        "verordnung_datum": (heute - timedelta(days=25)).isoformat(),
                                        "verordnender_arzt": "Dr. med. Ohr"})
        for seite, sn in (("rechts", "SN-R-1001"), ("links", "SN-L-1002")):
            db.insert("versorgung_geraete", {"versorgung_id": v1, "artikel_id": artikel["Komfort 5 RIC"],
                                             "bezeichnung": "Hersteller A Komfort 5 RIC", "seite": seite,
                                             "seriennummer": sn, "preis": 1690.00})
        db.insert("versorgungen", {"kunde_id": kunden[1], "beginn": "2018-02-01", "seite": "beidseitig",
                                   "status": "Abgeschlossen", "abgabe_datum": "2018-04-15", "lager_gebucht": 1})

        for tage, std, art, k in [(0, "09:30", "Hörtest", kunden[3]), (0, "11:00", "Feinanpassung", kunden[0]),
                                  (1, "14:00", "Beratung", kunden[2]), (3, "10:00", "Nachsorge", kunden[1])]:
            db.insert("termine", {"kunde_id": k, "beginn": f"{(heute + timedelta(days=tage)).isoformat()}T{std}",
                                  "dauer_min": 45, "art": art})
        db.insert("reparaturen", {"kunde_id": kunden[1], "geraet": "Hersteller B Premium 7 HdO",
                                  "seriennummer": "SN-9981", "eingang": (heute - timedelta(days=5)).isoformat(),
                                  "fehler": "Kein Ton auf rechter Seite, Hörer vermutlich defekt",
                                  "status": "Beim Hersteller", "garantie": 1})
        print("Demodaten angelegt.")


if __name__ == "__main__":
    main()
