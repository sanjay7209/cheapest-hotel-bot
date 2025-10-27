import json
import os
from datetime import datetime, timedelta
from dateutil import parser as dateparser
import pytz
from openai import OpenAI

NY_TZ = pytz.timezone("America/New_York")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
_openai_key = os.getenv("OPENAI_API_KEY")
if not _openai_key:
    raise RuntimeError("OPENAI_API_KEY is not set. Add it to your .env file.")
_openai_client = OpenAI(api_key=_openai_key)

SCHEMA = {
  "type":"object","required":["intent"],
  "properties":{
    "intent":{"enum":["find_cheapest_hotel"]},
    "zip":{"type":"string"},
    "city":{"type":"string"},
    "state":{"type":"string"},
    "country":{"type":"string"},
    "radius":{"type":"object","properties":{
      "value":{"type":"number"},"unit":{"enum":["mile","km"]}
    }},
    "check_in_text":{"type":"string"},
    "check_out_text":{"type":"string"},
    "nights":{"type":"integer"},
    "adults":{"type":"integer"},
    "children":{"type":"integer"},
    "currency":{"type":"string"},
    "constraints":{"type":"array","items":{"type":"string"}},
    "confidence":{"type":"number"}
  }
}

SYSTEM = """You extract hotel search parameters from user text.
Return STRICTLY valid minified JSON matching the provided JSON Schema.
- If dates are relative (e.g., "next weekend"), put them in check_in_text/check_out_text or use nights.
- Include a confidence score 0..1.
- Do not add keys not in the schema. Do not include explanations or markdown.
"""

def extract_slots(user_text: str) -> dict:
    schema_str = json.dumps(SCHEMA, separators=(",",":"))
    prompt = f"{SYSTEM}\nJSON Schema:\n{schema_str}\n\nUser: {user_text}"
    resp = _openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0,
        messages=[{"role":"user","content": prompt}]
    )
    text = resp.choices[0].message.content.strip()
    return json.loads(text)

# ---------- Normalization / validation ----------

def _resolve_relative_dates(check_in_text, check_out_text, nights):
    now = datetime.now(NY_TZ).date()

    def _parse(txt):
        if not txt: return None
        try:
            return dateparser.parse(txt).date()
        except:
            return None

    # Recognize "next weekend": Saturday start
    if check_in_text and "next weekend" in check_in_text.lower():
        days_ahead = (5 - now.weekday()) % 7  # 5=Sat
        start = now + timedelta(days=days_ahead)
        if start <= now:
            start = start + timedelta(days=7)
        ci = start
        co = ci + timedelta(days=(nights or 1))
        return ci.isoformat(), co.isoformat()

    ci = _parse(check_in_text)
    co = _parse(check_out_text)
    if ci and co:
        return ci.isoformat(), co.isoformat()
    if ci and nights:
        return ci.isoformat(), (ci + timedelta(days=nights)).isoformat()
    if nights:
        # assume upcoming Friday
        days_to_fri = (4 - now.weekday()) % 7  # 4=Fri
        ci = now + timedelta(days=days_to_fri)
        return ci.isoformat(), (ci + timedelta(days=nights)).isoformat()
    return None, None

def _normalize_radius(radius):
    if not radius: return None
    try:
        val = float(radius.get("value", 0))
        unit = (radius.get("unit") or "mile").lower()
        unit = "mile" if "mi" in unit else ("km" if "k" in unit else "mile")
        if unit == "mile":
            val = max(1, min(int(round(val)), 50))
        else:
            val = max(1, min(int(round(val)), 80))
        return {"value": val, "unit": unit}
    except:
        return None

def normalize_and_validate(raw: dict):
    radius = _normalize_radius(raw.get("radius"))
    ci, co = _resolve_relative_dates(raw.get("check_in_text"), raw.get("check_out_text"), raw.get("nights"))
    zip_code = (raw.get("zip") or "").strip()
    city = (raw.get("city") or "").strip()
    state = (raw.get("state") or "").strip()
    country = (raw.get("country") or "US").strip() or "US"
    adults = int(raw.get("adults") or 2)
    children = int(raw.get("children") or 0)
    currency = (raw.get("currency") or "USD").strip()
    constraints = raw.get("constraints") or []
    confidence = float(raw.get("confidence") or 0.0)

    missing = []
    if not (zip_code or city): missing.append("ZIP or city")
    if not radius: missing.append("radius")
    if not (ci and co): missing.append("dates")

    ok = (len(missing) == 0) and (confidence >= 0.6)
    if not ok:
        need = ", ".join(missing) if missing else "a bit more detail"
        return {"ok": False, "question": f"I still need {need}. What ZIP/city, radius, and exact dates?"}

    return {
        "ok": True,
        "slots": {
            "zip": zip_code or None,
            "city": city or None,
            "state": state or None,
            "country": country,
            "radius": f"{radius['value']} {'mi' if radius['unit']=='mile' else 'km'}",
            "check_in": ci,
            "check_out": co,
            "adults": adults,
            "children": children,
            "currency": currency,
            "constraints": constraints
        }
    }
