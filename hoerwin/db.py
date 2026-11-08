import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS benutzer (
    id INTEGER PRIMARY KEY,
    benutzername TEXT UNIQUE NOT NULL,
    passwort_hash TEXT NOT NULL,
    name TEXT,
    erstellt TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS einstellungen (
    schluessel TEXT PRIMARY KEY,
    wert TEXT
);

CREATE TABLE IF NOT EXISTS krankenkassen (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    ik_nummer TEXT,
    art TEXT NOT NULL DEFAULT 'gesetzlich',
    festbetrag REAL NOT NULL DEFAULT 0,
    strasse TEXT, plz TEXT, ort TEXT,
    telefon TEXT, email TEXT,
    notiz TEXT
);

CREATE TABLE IF NOT EXISTS kunden (
    id INTEGER PRIMARY KEY,
    kundennummer TEXT UNIQUE,
    anrede TEXT,
    vorname TEXT,
    nachname TEXT NOT NULL,
    geburtsdatum TEXT,
    strasse TEXT, plz TEXT, ort TEXT,
    telefon TEXT, mobil TEXT, email TEXT,
    krankenkasse_id INTEGER REFERENCES krankenkassen(id) ON DELETE SET NULL,
    versichertennummer TEXT,
    zuzahlungsbefreit INTEGER NOT NULL DEFAULT 0,
    hno_arzt TEXT,
    einwilligung_dsgvo INTEGER NOT NULL DEFAULT 0,
    notiz TEXT,
    erstellt TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audiogramme (
    id INTEGER PRIMARY KEY,
    kunde_id INTEGER NOT NULL REFERENCES kunden(id) ON DELETE CASCADE,
    datum TEXT NOT NULL,
    werte TEXT NOT NULL,
    sprachverstehen_r INTEGER,
    sprachverstehen_l INTEGER,
    bemerkung TEXT
);

CREATE TABLE IF NOT EXISTS artikel (
    id INTEGER PRIMARY KEY,
    artikelnummer TEXT,
    kategorie TEXT NOT NULL DEFAULT 'Hörgerät',
    hersteller TEXT,
    bezeichnung TEXT NOT NULL,
    bauform TEXT,
    hilfsmittelnummer TEXT,
    preis REAL NOT NULL DEFAULT 0,
    mwst REAL NOT NULL DEFAULT 19,
    bestand INTEGER NOT NULL DEFAULT 0,
    mindestbestand INTEGER NOT NULL DEFAULT 0,
    aktiv INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS versorgungen (
    id INTEGER PRIMARY KEY,
    kunde_id INTEGER NOT NULL REFERENCES kunden(id) ON DELETE CASCADE,
    beginn TEXT,
    seite TEXT,
    status TEXT NOT NULL DEFAULT 'Beratung',
    verordnung_datum TEXT,
    verordnender_arzt TEXT,
    genehmigt_datum TEXT,
    abgabe_datum TEXT,
    lager_gebucht INTEGER NOT NULL DEFAULT 0,
    notiz TEXT
);

CREATE TABLE IF NOT EXISTS versorgung_geraete (
    id INTEGER PRIMARY KEY,
    versorgung_id INTEGER NOT NULL REFERENCES versorgungen(id) ON DELETE CASCADE,
    artikel_id INTEGER REFERENCES artikel(id) ON DELETE SET NULL,
    bezeichnung TEXT NOT NULL,
    seite TEXT,
    seriennummer TEXT,
    preis REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS termine (
    id INTEGER PRIMARY KEY,
    kunde_id INTEGER REFERENCES kunden(id) ON DELETE CASCADE,
    beginn TEXT NOT NULL,
    dauer_min INTEGER NOT NULL DEFAULT 30,
    art TEXT,
    notiz TEXT,
    erledigt INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS rechnungen (
    id INTEGER PRIMARY KEY,
    nummer TEXT UNIQUE NOT NULL,
    datum TEXT NOT NULL,
    faellig_am TEXT,
    kunde_id INTEGER REFERENCES kunden(id) ON DELETE SET NULL,
    krankenkasse_id INTEGER REFERENCES krankenkassen(id) ON DELETE SET NULL,
    empfaenger TEXT NOT NULL DEFAULT 'kunde',
    versorgung_id INTEGER REFERENCES versorgungen(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'offen',
    bezahlt_am TEXT,
    notiz TEXT
);

CREATE TABLE IF NOT EXISTS rechnung_positionen (
    id INTEGER PRIMARY KEY,
    rechnung_id INTEGER NOT NULL REFERENCES rechnungen(id) ON DELETE CASCADE,
    artikel_id INTEGER REFERENCES artikel(id) ON DELETE SET NULL,
    bezeichnung TEXT NOT NULL,
    menge REAL NOT NULL DEFAULT 1,
    einzelpreis REAL NOT NULL DEFAULT 0,
    mwst REAL NOT NULL DEFAULT 19
);

CREATE TABLE IF NOT EXISTS reparaturen (
    id INTEGER PRIMARY KEY,
    kunde_id INTEGER NOT NULL REFERENCES kunden(id) ON DELETE CASCADE,
    geraet TEXT,
    seriennummer TEXT,
    eingang TEXT,
    fehler TEXT,
    status TEXT NOT NULL DEFAULT 'Eingegangen',
    versand_hersteller TEXT,
    rueckgabe TEXT,
    garantie INTEGER NOT NULL DEFAULT 0,
    kosten REAL NOT NULL DEFAULT 0,
    notiz TEXT
);

CREATE INDEX IF NOT EXISTS ix_kunden_name ON kunden(nachname, vorname);
CREATE INDEX IF NOT EXISTS ix_termine_beginn ON termine(beginn);
CREATE INDEX IF NOT EXISTS ix_rechnungen_status ON rechnungen(status);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    get_db().executescript(SCHEMA)
    get_db().commit()


def init_app(app):
    app.teardown_appcontext(close_db)


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    conn = get_db()
    cur = conn.execute(sql, args)
    conn.commit()
    return cur.lastrowid


def insert(table, data):
    cols = ", ".join(data)
    marks = ", ".join("?" for _ in data)
    return execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(data.values()))


def update(table, row_id, data):
    sets = ", ".join(f"{k} = ?" for k in data)
    execute(f"UPDATE {table} SET {sets} WHERE id = ?", (*data.values(), row_id))


def einstellung(schluessel, standard=""):
    row = query("SELECT wert FROM einstellungen WHERE schluessel = ?", (schluessel,), one=True)
    return row["wert"] if row and row["wert"] is not None else standard


def setze_einstellung(schluessel, wert):
    execute("INSERT INTO einstellungen (schluessel, wert) VALUES (?, ?) "
            "ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert", (schluessel, wert))
