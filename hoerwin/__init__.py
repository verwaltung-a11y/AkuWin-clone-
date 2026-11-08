"""HörWin – Verwaltungsprogramm für Hörakustik-Fachgeschäfte."""
import os
import secrets

from flask import Flask

from . import db, helpers


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "hoerwin.sqlite"),
        SECRET_KEY=None,
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)

    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = os.environ.get("HOERWIN_SECRET_KEY") or _persistenter_schluessel(app)

    db.init_app(app)
    helpers.register(app)

    from .auth import bp as auth_bp, register_guards
    from .views import (artikel, dashboard, einstellungen, kassen, kunden,
                        rechnungen, reparaturen, termine, versorgungen)

    register_guards(app)
    app.register_blueprint(auth_bp)
    for modul in (dashboard, kunden, kassen, artikel, versorgungen, termine,
                  rechnungen, reparaturen, einstellungen):
        app.register_blueprint(modul.bp)

    with app.app_context():
        db.init_db()
    return app


def _persistenter_schluessel(app):
    """Schlüssel einmalig erzeugen und im instance-Ordner ablegen (Sitzungen überleben Neustarts)."""
    pfad = os.path.join(app.instance_path, "secret_key")
    if not os.path.exists(pfad):
        with open(pfad, "w", encoding="utf-8") as f:
            f.write(secrets.token_hex(32))
        os.chmod(pfad, 0o600)
    with open(pfad, encoding="utf-8") as f:
        return f.read().strip()
