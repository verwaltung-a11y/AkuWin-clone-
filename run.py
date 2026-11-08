"""Startet HörWin lokal: python run.py  →  http://127.0.0.1:5000"""
import os

from hoerwin import create_app

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("HOERWIN_HOST", "127.0.0.1")
    port = int(os.environ.get("HOERWIN_PORT", "5000"))
    try:
        from waitress import serve
    except ImportError:
        app.run(host=host, port=port, debug=False)
    else:
        print(f"HörWin läuft auf http://{host}:{port}")
        serve(app, host=host, port=port)
