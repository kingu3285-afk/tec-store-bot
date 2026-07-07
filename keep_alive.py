import logging
import os
from threading import Thread

from flask import Flask

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

app = Flask(__name__)


@app.route("/")
def home():
    return "✅ Bot is alive and running!", 200


@app.route("/health")
def health():
    return {"status": "ok", "bot": "running"}, 200


def _run():
    port = int(os.environ.get("PORT", os.environ.get("KEEP_ALIVE_PORT", 6000)))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    t = Thread(target=_run, daemon=True)
    t.start()
    logging.getLogger(__name__).info("🌐 Keep-alive server started")
