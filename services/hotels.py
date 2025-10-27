import os
import re
from datetime import datetime
import requests
from amadeus import Client, ResponseError

# --- Init with basic hardening (strips + optional production toggle) ---
_client_id = (os.getenv("AMADEUS_CLIENT_ID") or "").strip()
_client_secret = (os.getenv("AMADEUS_CLIENT_SECRET") or "").strip()
if not _client_id or not _client_secret:
    raise RuntimeError("Amadeus credentials missing. Set AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET in .env")

_env = (os.getenv("AMADEUS_ENV") or "test").strip().lower()
kwargs = {}
if _env == "production":
    kwargs["hostname"] = "production"  # ONLY if you have live access

AMADEUS = Client(client_id=_client_id, client_secret=_client_secret, **kwargs)

def geocode_zip_or_city(zip_code=None, city=None, state=None, country="US"):
    url = "https://nominatim.openstreetmap.org/search"
    q = zip_code if zip_code else " ".join(x for x in [city, state, country] if x)
    params = {"q": q, "format":"jsonv2", "limit":1, "countrycodes": country.lower()}
    headers = {"User-Agent": "cheapest-hotel-bot/1.0"}
    r = requests.get(url, params=params, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()
    if not data:
        raise ValueError(f"Could not geocode location: {q}")
    return float(data[0]["lat"]), float(data[0]["lon"])

def _parse_radius(radius_str):
    s = (radius_str or "").lower()
    unit = "MILE" if "mi" in s else ("KM" if "k" in s else "MILE")
    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        raise ValueError("Invalid radius")
    val = int(digits)
    if unit == "MILE":
        val = max(1, min(val, 50))
    else:
        val = max(1, min(val, 80))
    return val, unit

# --------- NEW: simple pre-flight validator (catches common 400s) ----------
def _iso(d): 
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", d or ""))

def _validate_inputs(lat, lon, radius_str, check_in, check_out, adults, currency):
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Bad coordinates")
    if not _iso(check_in) or not _iso(check_out):
        raise ValueError("Dates must be YYYY-MM-DD")
    ci = datetime.strptime(check_in, "%Y-%m-%d").date()
    co = datetime.strptime(check_out, "%Y-%m-%d").date()
    if not (ci < co):
        raise ValueError("checkInDate must be before checkOutDate")
    if (co - ci).days > 28:
        raise ValueError("Stay length must be ≤ 28 nights")
    try:
        if int(adults) < 1:
            raise ValueError("adults must be ≥ 1")
    except Exception:
        raise ValueError("adults must be an integer ≥ 1")
    if currency and not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("currency must be ISO 4217 (e.g., USD)")

# --------- UPDATED: main search with logging + optional fallback ----------
def find_cheapest(lat, lon, radius_str, check_in, check_out, adults=2, currency="USD"):
    _validate_inputs(lat, lon, radius_str, check_in, check_out, adults, currency)
    rnum, runit = _parse_radius(radius_str)
    adults = int(adults)
    currency = (currency or "USD").upper()

    # Try geo-based Hotel Offers Search first
    try:
        resp = AMADEUS.shopping.hotel_offers_search.get(
            latitude=lat,
            longitude=lon,
            radius=rnum,
            radiusUnit=runit,          # "MILE" or "KM"
            checkInDate=check_in,      # YYYY-MM-DD
            checkOutDate=check_out,    # YYYY-MM-DD
            adults=adults,             # >=1
            currency=currency,         # ISO 4217
            bestRateOnly=True
        )
        items = resp.data or []
    except ResponseError as e:
        try:
            print("Amadeus error body:", e.response.body)
        except Exception:
            pass
        # Fallback: get hotelIds by geocode, then query offers by IDs
        try:
            hotels = AMADEUS.reference_data.locations.hotels.by_geocode.get(
                latitude=lat, longitude=lon, radius=rnum, radiusUnit=runit, hotelSource='ALL'
            )
            ids = [h.get("hotelId") for h in (hotels.data or []) if h.get("hotelId")]
            ids = ids[:20]  # keep it small
            if not ids:
                return None, []
            resp = AMADEUS.shopping.hotel_offers_search.get(
                hotelIds=",".join(ids),
                checkInDate=check_in,
                checkOutDate=check_out,
                adults=adults,
                currency=currency,
                bestRateOnly=True
            )
            items = resp.data or []
        except ResponseError as e2:
            try:
                print("Amadeus fallback error body:", e2.response.body)
            except Exception:
                pass
            raise RuntimeError(f"Hotel API error: [{getattr(e2.response, 'status_code', '??')}]")

    offers = []
    for item in items:
        hotel = item.get("hotel", {})
        name = hotel.get("name")
        dist = hotel.get("distance", {})
        distance = dist.get("value")
        dunit = dist.get("unit")
        for off in item.get("offers", []) or []:
            price = off.get("price", {}) or {}
            total = price.get("total") or price.get("grandTotal") or price.get("base")
            if not total:
                continue
            try:
                total_val = float(total)
            except:
                continue
            offers.append({
                "name": name,
                "total": total_val,
                "currency": price.get("currency", currency),
                "distance": distance,
                "distance_unit": dunit,
                "check_in": check_in,
                "check_out": check_out,
                "booking_url": off.get("self")
            })

    if not offers:
        return None, []
    offers.sort(key=lambda x: x["total"])
    return offers[0], offers[:10]
