from flask import flash, redirect, render_template, request

from .. import db
from ..helpers import formular_daten


def formular_seite(felder, titel, tabelle, ziel, row=None, vorbelegung=None, abbrechen=None, vorher=None):
    """Gemeinsamer Ablauf für Anlegen/Bearbeiten: Formular zeigen, prüfen, speichern.

    ``ziel`` ist eine Funktion, die die ID des gespeicherten Datensatzes auf eine URL abbildet.
    ``vorher`` darf die Daten vor dem Speichern ergänzen und eine Fehlerliste zurückgeben.
    """
    werte = dict(row) if row else dict(vorbelegung or {})
    if request.method == "POST":
        daten, fehler = formular_daten(felder, request.form)
        if not fehler and vorher:
            fehler = vorher(daten) or []
        if not fehler:
            if row:
                db.update(tabelle, row["id"], daten)
                neue_id = row["id"]
            else:
                neue_id = db.insert(tabelle, daten)
            flash("Gespeichert.", "ok")
            return redirect(ziel(neue_id))
        for f in fehler:
            flash(f, "fehler")
        werte.update(request.form.to_dict())
    return render_template("formular.html", felder=felder, titel=titel, werte=werte, abbrechen=abbrechen)
