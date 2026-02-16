from flask import Flask, render_template, abort, Response, session
from pathlib import Path
import random

app = Flask(__name__)
app.secret_key = "dev-secret-change-me"  # needed for session

BEE_IMAGES = [
    "bumbleBee.png",
    "carpenterBee.png",
    "cicadakiller.png",
    "dirtdauber.png",
    "honeyBee.png",
    "hoverfly.png",
    "paperwasp.png",
    "yellowjacket.png",
]

# map: beeId -> filename
BEE_FILES = {Path(f).stem: f for f in BEE_IMAGES}
BEE_IDS = list(BEE_FILES.keys())

NARR_DIR = Path("static/narratives")


@app.get("/")
def home():
    return render_template("index.html", bee_images=BEE_IMAGES)


@app.get("/interactive")
def interactive():
    order = session.get("bee_order", [])
    last = session.get("last_bee", None)

    # If deck is empty, refill + shuffle
    if not order:
        order = BEE_IDS.copy()
        random.shuffle(order)

        # optional: avoid immediate repeat across cycles
        if last and len(order) > 1 and order[0] == last:
            tries = 0
            while order[0] == last and tries < 10:
                random.shuffle(order)
                tries += 1

        session["bee_order"] = order

    bee_id = order.pop(0)
    session["bee_order"] = order
    session["last_bee"] = bee_id

    chosen_image = BEE_FILES[bee_id]
    return render_template("interactive.html", chosen_image=chosen_image, chosen_id=bee_id)


@app.get("/api/narrative/<bee_id>")
def narrative(bee_id: str):
    if bee_id not in BEE_FILES:
        abort(404)

    path = NARR_DIR / f"{bee_id}.txt"
    if not path.exists():
        abort(404)

    text = path.read_text(encoding="utf-8")
    return Response(text, mimetype="text/plain; charset=utf-8")


if __name__ == "__main__":
    app.run(debug=True)
