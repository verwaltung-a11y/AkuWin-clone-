import re

import pytest

from hoerwin import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({"DATABASE": str(tmp_path / "test.sqlite"), "SECRET_KEY": "test", "TESTING": True})


class Client:
    """Testclient, der das CSRF-Token automatisch aus der Sitzung mitsendet."""

    def __init__(self, flask_client):
        self.c = flask_client

    def get(self, *a, **kw):
        return self.c.get(*a, **kw)

    def post(self, url, data=None, formular_von=None, **kw):
        """Holt das Token wie ein Browser aus dem gerenderten Formular der Seite."""
        seite = self.c.get(formular_von or "/einstellungen/")
        if seite.status_code != 200:
            seite = self.c.get("/login")
        token = re.search(r'name="csrf_token" value="([^"]*)"', seite.get_data(as_text=True)).group(1)
        return self.c.post(url, data={**(data or {}), "csrf_token": token}, **kw)


@pytest.fixture
def client(app):
    return Client(app.test_client())


@pytest.fixture
def angemeldet(client):
    client.post("/einrichtung", data={"benutzername": "admin", "passwort": "geheim123",
                                      "passwort2": "geheim123", "firma_name": "Test-Akustik"})
    r = client.post("/login", data={"benutzername": "admin", "passwort": "geheim123"})
    assert r.status_code == 302
    return client
