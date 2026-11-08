import pytest

from hoerwin import fachlogik as f


def test_zuzahlung_grenzen():
    assert f.gesetzliche_zuzahlung(733.59) == 10.0
    assert f.gesetzliche_zuzahlung(70.0) == 7.0
    assert f.gesetzliche_zuzahlung(30.0) == 5.0
    assert f.gesetzliche_zuzahlung(3.0) == 3.0
    assert f.gesetzliche_zuzahlung(0) == 0.0


def test_versorgung_gkv_mit_aufzahlung():
    kasse = {"art": "gesetzlich", "festbetrag": 733.59}
    b = f.versorgung_berechnung([{"preis": 1690.0}, {"preis": 1690.0}], kasse, zuzahlungsbefreit=False)
    z = b["zeilen"][0]
    assert z["kasse"] == 723.59
    assert z["zuzahlung"] == 10.0
    assert z["eigenanteil"] == 956.41
    assert z["kunde"] == 966.41
    assert b["summe"]["preis"] == 3380.0
    assert b["summe"]["kasse"] + b["summe"]["kunde"] == pytest.approx(3380.0)


def test_versorgung_befreit_und_aufzahlungsfrei():
    kasse = {"art": "gesetzlich", "festbetrag": 733.59}
    z = f.versorgung_berechnung([{"preis": 733.59}], kasse, zuzahlungsbefreit=True)["zeilen"][0]
    assert (z["kasse"], z["zuzahlung"], z["eigenanteil"]) == (733.59, 0.0, 0.0)


def test_versorgung_privat_zahlt_kunde_alles():
    b = f.versorgung_berechnung([{"preis": 2000.0}], {"art": "privat", "festbetrag": 900}, False)
    assert b["summe"]["kasse"] == 0 and b["summe"]["kunde"] == 2000.0


def test_rechnung_summen_mischsteuer():
    s = f.rechnung_summen([{"menge": 2, "einzelpreis": 11.90, "mwst": 19},
                           {"menge": 1, "einzelpreis": 10.70, "mwst": 7}])
    assert s["brutto"] == 34.50
    assert s["steuern"] == {7.0: 0.70, 19.0: 3.80}
    assert s["netto"] == 30.00


def test_pta4_und_who():
    reihe = {500: 30, 1000: 40, 2000: 50, 4000: 60}
    assert f.pta4(reihe) == 45
    assert f.who_grad(45) == "mittelgradig"
    assert f.who_grad(10) == "normal"
    assert f.pta4({500: 30}) is None


def test_werte_aus_formular_prueft_bereich():
    assert f.werte_aus_formular({"r_ll_1000": "35"})["r_ll"] == {"1000": 35.0}
    with pytest.raises(ValueError):
        f.werte_aus_formular({"r_ll_1000": "150"})


def test_svg_enthaelt_symbole():
    svg = f.audiogramm_svg(f.parse_werte('{"r_ll": {"1000": 40, "2000": 50}, "l_ll": {"1000": 45}}'))
    assert svg.startswith("<svg") and "<circle" in svg and "polyline" in svg
