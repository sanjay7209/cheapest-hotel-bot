import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

from services.nlu import extract_slots, normalize_and_validate
from services.hotels import geocode_zip_or_city, find_cheapest

load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/api/chat")
def chat():
    data = request.get_json(force=True, silent=True) or {}
    user_text = (data.get("message") or "").strip()
    if not user_text:
        return jsonify({"reply": "Tell me what you need (location, dates, radius)."}), 200

    # 1) LLM → slots
    try:
        raw = extract_slots(user_text)
    except Exception as e:
        return jsonify({"reply": f"NLU error: {e}"}), 200

    # 2) Validate/normalize
    norm = normalize_and_validate(raw)
    if not norm["ok"]:
        return jsonify({"reply": norm["question"], "needs_more": True}), 200

    slots = norm["slots"]

    # 3) Geocode (ZIP or city/state)
    try:
        lat, lon = geocode_zip_or_city(
            zip_code=slots.get("zip"),
            city=slots.get("city"),
            state=slots.get("state"),
            country=slots.get("country"),
        )
    except Exception as e:
        return jsonify({"reply": f"I couldn't locate that area: {e}"}), 200

    # 4) Hotel search → cheapest
    try:
        best, top = find_cheapest(
            lat=lat,
            lon=lon,
            radius_str=slots["radius"],
            check_in=slots["check_in"],
            check_out=slots["check_out"],
            adults=slots["adults"],
            currency=slots["currency"],
        )
    except Exception as e:
        return jsonify({"reply": f"Search error: {e}"}), 200

    if not best:
        return jsonify({"reply": "No hotels found for those dates/area. Try widening the radius or changing dates."}), 200

    def fmt(h):
        dist = f"{h['distance']} {h['distance_unit']}" if h.get("distance") else "N/A"
        return {
            "name": h["name"],
            "total": f"{h['total']} {h['currency']}",
            "distance": dist,
            "check_in": h["check_in"],
            "check_out": h["check_out"],
            "booking_url": h.get("booking_url") or ""
        }

    return jsonify({
        "reply": f"Cheapest: {best['name']} — {best['total']} {best['currency']} (distance: {best.get('distance','N/A')} {best.get('distance_unit','')})",
        "best": fmt(best),
        "top": [fmt(x) for x in top]
    }), 200

if __name__ == "__main__":
    app.run(debug=True)
