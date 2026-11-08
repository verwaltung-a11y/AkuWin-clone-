import re

from hoerwin import db


def test_einrichtung_und_login_pflicht(client):
    assert client.get("/").headers["Location"].endswith("/einrichtung")
    client.post("/einrichtung", data={"benutzername": "a", "passwort": "geheim123", "passwort2": "geheim123"})
    assert "/login" in client.get("/kunden/").headers["Location"]
    r = client.post("/login", data={"benutzername": "a", "passwort": "falsch"})
    assert "falsch" in r.get_data(as_text=True)


def test_csrf_wird_geprueft(angemeldet):
    r = angemeldet.c.post("/kostentraeger/neu", data={"name": "X"})
    assert r.status_code == 400


def test_offene_weiterleitung_verhindert(client):
    client.post("/einrichtung", data={"benutzername": "a", "passwort": "geheim123", "passwort2": "geheim123"})
    r = client.post("/login?weiter=//boese.example", data={"benutzername": "a", "passwort": "geheim123"})
    assert r.headers["Location"] == "/"


def test_token_in_makro_formularen(angemeldet, app):
    """Formulare aus importierten Makros (z. B. Status-Knöpfe) müssen ein gültiges Token tragen."""
    kid = _anlegen(angemeldet, app)
    angemeldet.post("/versorgungen/neu", data={"kunde_id": str(kid), "beginn": "2026-01-10"})
    html = angemeldet.get("/versorgungen/1").get_data(as_text=True)
    tokens = set(re.findall(r'name="csrf_token" value="([^"]*)"', html))
    assert len(tokens) == 1 and "" not in tokens


def test_alle_seiten_erreichbar(angemeldet):
    for url in ["/", "/kunden/", "/kunden/neu", "/kostentraeger/", "/kostentraeger/neu", "/artikel/",
                "/artikel/neu", "/versorgungen/", "/versorgungen/neu", "/termine/", "/termine/neu",
                "/rechnungen/", "/rechnungen/neu", "/reparaturen/", "/reparaturen/neu", "/einstellungen/",
                "/benutzer", "/kunden/export.csv", "/einstellungen/sicherung"]:
        assert angemeldet.get(url).status_code == 200, url


def _anlegen(c, app):
    c.post("/kostentraeger/neu", data={"name": "Testkasse", "art": "gesetzlich", "festbetrag": "733,59"})
    c.post("/kunden/neu", data={"nachname": "Muster", "vorname": "Anna", "krankenkasse_id": "1",
                                "geburtsdatum": "1950-01-01", "einwilligung_dsgvo": "1"})
    c.post("/artikel/neu", data={"bezeichnung": "Komfort RIC", "kategorie": "Hörgerät", "preis": "1690",
                                 "mwst": "19", "bestand": "3", "aktiv": "1"})
    c.post("/artikel/neu", data={"bezeichnung": "Batterien 312", "kategorie": "Batterie", "preis": "4,50",
                                 "mwst": "19", "bestand": "10", "aktiv": "1"})
    with app.app_context():
        return db.query("SELECT id FROM kunden", one=True)["id"]


def test_kunde_mit_kasse_und_kundennummer(angemeldet, app):
    kid = _anlegen(angemeldet, app)
    seite = angemeldet.get(f"/kunden/{kid}").get_data(as_text=True)
    assert "Testkasse" in seite and "10001" in seite
    assert "Muster" in angemeldet.get("/kunden/?q=mus").get_data(as_text=True)


def test_audiogramm_speichern_und_anzeigen(angemeldet, app):
    kid = _anlegen(angemeldet, app)
    daten = {"datum": "2026-01-15", "r_ll_500": "30", "r_ll_1000": "40", "r_ll_2000": "50", "r_ll_4000": "60"}
    r = angemeldet.post(f"/kunden/{kid}/audiogramm/neu", data=daten)
    assert r.status_code == 302
    seite = angemeldet.get(f"/kunden/{kid}").get_data(as_text=True)
    assert "<svg" in seite and "mittelgradig" in seite
    r = angemeldet.post(f"/kunden/{kid}/audiogramm/neu", data={"datum": "2026-01-15", "l_ll_500": "200"})
    assert "außerhalb" in r.get_data(as_text=True)


def test_versorgung_komplett(angemeldet, app):
    kid = _anlegen(angemeldet, app)
    r = angemeldet.post("/versorgungen/neu", data={"kunde_id": str(kid), "beginn": "2026-01-10",
                                                    "seite": "beidseitig", "status": "Beratung"})
    vid = int(r.headers["Location"].rstrip("/").split("/")[-1])
    for seite in ("rechts", "links"):
        angemeldet.post(f"/versorgungen/{vid}/geraet", data={"artikel_id": "1", "seite": seite,
                                                             "seriennummer": f"SN-{seite}"})
    detail = angemeldet.get(f"/versorgungen/{vid}").get_data(as_text=True)
    assert "723,59 €" in detail and "966,41 €" in detail
    assert angemeldet.get(f"/versorgungen/{vid}/kostenvoranschlag").status_code == 200

    angemeldet.post(f"/versorgungen/{vid}/status", data={"status": "Abgegeben"})
    angemeldet.post(f"/versorgungen/{vid}/status", data={"status": "Abgegeben"})  # doppelt: kein Doppelabzug
    with app.app_context():
        assert db.query("SELECT bestand FROM artikel WHERE id = 1", one=True)["bestand"] == 1
        assert db.query("SELECT COUNT(*) AS n FROM termine WHERE art = 'Nachsorge'", one=True)["n"] == 1

    angemeldet.post(f"/versorgungen/{vid}/rechnungen")
    r2 = angemeldet.post(f"/versorgungen/{vid}/rechnungen", follow_redirects=True)
    assert "bereits Rechnungen" in r2.get_data(as_text=True)
    with app.app_context():
        rechnungen = db.query("SELECT r.*, (SELECT SUM(menge*einzelpreis) FROM rechnung_positionen "
                              "WHERE rechnung_id = r.id) AS s FROM rechnungen r ORDER BY id")
        assert [(x["empfaenger"], round(x["s"], 2)) for x in rechnungen] == [("kunde", 1932.82), ("kasse", 1447.18)]
        assert re.fullmatch(r"\d{4}-0001", rechnungen[0]["nummer"])
        assert rechnungen[1]["nummer"].endswith("-0002")
    druck = angemeldet.get(f"/rechnungen/{rechnungen[1]['id']}/druck").get_data(as_text=True)
    assert "Testkasse" in druck and "1.447,18 €" in druck


def test_verkauf_bucht_lager_und_storno(angemeldet, app):
    kid = _anlegen(angemeldet, app)
    r = angemeldet.post("/rechnungen/neu", data={"kunde_id": str(kid), "artikel_0": "2", "menge_0": "3",
                                                  "text_1": "Beratung", "preis_1": "0", "bar": "1"})
    rid = int(r.headers["Location"].split("/")[-1])
    with app.app_context():
        assert db.query("SELECT bestand FROM artikel WHERE id = 2", one=True)["bestand"] == 7
        assert db.query("SELECT status FROM rechnungen WHERE id = ?", (rid,), one=True)["status"] == "bezahlt"
    seite = angemeldet.get(f"/rechnungen/{rid}").get_data(as_text=True)
    assert "13,50 €" in seite
    angemeldet.post(f"/rechnungen/{rid}/status", data={"status": "storniert"})
    with app.app_context():
        assert db.query("SELECT bestand FROM artikel WHERE id = 2", one=True)["bestand"] == 10


def test_termin_und_reparatur(angemeldet, app):
    kid = _anlegen(angemeldet, app)
    r = angemeldet.post("/termine/neu", data={"kunde_id": str(kid), "beginn": "2026-03-02T10:30",
                                              "dauer_min": "30", "art": "Hörtest"})
    assert r.status_code == 302
    assert "Hörtest" in angemeldet.get("/termine/?ab=2026-03-04").get_data(as_text=True)
    r = angemeldet.post("/reparaturen/neu", data={"kunde_id": str(kid), "geraet": "Komfort RIC",
                                                  "eingang": "2026-03-01", "status": "Eingegangen"})
    assert r.status_code == 302
    assert "Komfort RIC" in angemeldet.get("/reparaturen/").get_data(as_text=True)


def test_kunde_loeschen_braucht_bestaetigung(angemeldet, app):
    kid = _anlegen(angemeldet, app)
    angemeldet.post(f"/kunden/{kid}/loeschen", data={"bestaetigung": "falsch"})
    assert angemeldet.get(f"/kunden/{kid}").status_code == 200
    angemeldet.post(f"/kunden/{kid}/loeschen", data={"bestaetigung": "Muster"})
    assert angemeldet.get(f"/kunden/{kid}").status_code == 404


def test_csv_export_schuetzt_vor_formeln(angemeldet, app):
    angemeldet.post("/kunden/neu", data={"nachname": "=HYPERLINK(1)"})
    csv = angemeldet.get("/kunden/export.csv").get_data(as_text=True)
    assert "'=HYPERLINK(1)" in csv
