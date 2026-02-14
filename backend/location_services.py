"""Location services for address geocoding and GPS cross-verification"""

import json
import os
import math
from wsgiref import headers
from fastapi import params
import requests
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
print(f"[DEBUG] Google API Key loaded: {GOOGLE_API_KEY[:10] if GOOGLE_API_KEY else 'NOT FOUND'}")


# ==================== Haversine Distance ====================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two GPS coordinates in miles
    using Haversine formula
    """
    R = 3958.8  # Earth radius in miles

    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_r) * math.cos(lat2_r) *
         math.sin(delta_lon / 2) ** 2)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


# ==================== Geocoding ====================

def geocode_address(address: str) -> dict | None:
    """
    Convert a text address to lat/lng using Google Geocoding API

    Returns:
        dict: { "lat": float, "lng": float, "formatted_address": str } or None
    """
    try:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": address,
            "key": GOOGLE_API_KEY
        }

        headers = {"Referer": "http://localhost:8000/"}
        response = requests.get(url, params=params, headers=headers, timeout=5)
        
        data = response.json()

        if data.get("status") == "OK" and data.get("results"):
            result = data["results"][0]
            location = result["geometry"]["location"]
            return {
                "lat": location["lat"],
                "lng": location["lng"],
                "formatted_address": result.get("formatted_address", address)
            }

        print(f"Geocoding failed: {data.get('status')} - {data.get('error_message', '')}")
        return None

    except Exception as e:
        print(f"Geocoding error: {e}")
        return None


def reverse_geocode(lat: float, lng: float) -> dict | None:
    """
    Convert GPS coordinates to a human-readable address

    Returns:
        dict: { "formatted_address": str, "components": dict } or None
    """
    try:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "latlng": f"{lat},{lng}",
            "key": GOOGLE_API_KEY
        }

        headers = {"Referer": "http://localhost:8000/"}
        response = requests.get(url, params=params, headers=headers, timeout=5)
        
        data = response.json()

        if data.get("status") == "OK" and data.get("results"):
            result = data["results"][0]

            # Extract address components
            components = {}
            for component in result.get("address_components", []):
                types = component.get("types", [])
                if "locality" in types:
                    components["city"] = component["long_name"]
                elif "administrative_area_level_1" in types:
                    components["state"] = component["short_name"]
                elif "postal_code" in types:
                    components["zip"] = component["long_name"]
                elif "country" in types:
                    components["country"] = component["short_name"]

            return {
                "formatted_address": result.get("formatted_address", ""),
                "components": components
            }

        print(f"Reverse geocoding failed: {data.get('status')}")
        return None

    except Exception as e:
        print(f"Reverse geocoding error: {e}")
        return None


# ==================== Places Autocomplete ====================

def get_address_autocomplete(input_text: str, session_token: str = "") -> list:
    """
    Get address suggestions from Google Places Autocomplete API

    Returns:
        list: [ { "description": str, "place_id": str } ]
    """
    try:
        url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
        params = {
            "input": input_text,
            "types": "address",
            "key": GOOGLE_API_KEY,
            "sessiontoken": session_token
        }

        headers = {"Referer": "http://localhost:8000/"}
        response = requests.get(url, params=params, headers=headers, timeout=5)
        
        data = response.json()

        # Print FULL response to see exact error
        print(f"[Google Full Response]: {json.dumps(data, indent=2)}")

        if data.get("status") == "OK":
            return [
                {
                    "description": p["description"],
                    "place_id": p["place_id"]
                }
                for p in data.get("predictions", [])
            ]

        print(f"Autocomplete failed: {data.get('status')}")
        return []

    except Exception as e:
        print(f"Autocomplete error: {e}")
        return []


def get_place_details(place_id: str) -> dict | None:
    """
    Get structured address details from a Google Places place_id

    Returns:
        dict: { "street": str, "city": str, "state": str, "zip": str, "full": str }
    """
    try:
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": place_id,
            "fields": "formatted_address,address_components,geometry",
            "key": GOOGLE_API_KEY
        }

        headers = {"Referer": "http://localhost:8000/"}
        response = requests.get(url, params=params, headers=headers, timeout=5)
        
        data = response.json()

        if data.get("status") == "OK":
            result = data["result"]

            # Extract structured components
            address = {
                "street": "",
                "city": "",
                "state": "",
                "zip": "",
                "full": result.get("formatted_address", ""),
                "lat": result.get("geometry", {}).get("location", {}).get("lat"),
                "lng": result.get("geometry", {}).get("location", {}).get("lng"),
            }

            for component in result.get("address_components", []):
                types = component.get("types", [])
                if "street_number" in types:
                    address["street"] = component["long_name"] + " " + address["street"]
                elif "route" in types:
                    address["street"] = address["street"] + component["long_name"]
                elif "locality" in types:
                    address["city"] = component["long_name"]
                elif "administrative_area_level_1" in types:
                    address["state"] = component["short_name"]
                elif "postal_code" in types:
                    address["zip"] = component["long_name"]

            address["street"] = address["street"].strip()
            return address

        print(f"Place details failed: {data.get('status')}")
        return None

    except Exception as e:
        print(f"Place details error: {e}")
        return None


# ==================== Cross-Verification ====================

DISTANCE_THRESHOLD_MILES = 1.0   # Flag if GPS > 1 mile from typed address
CITY_STATE_MATCH_REQUIRED = True  # Flag if city/state don't match


def verify_location(
    typed_address: str,
    gps_lat: float,
    gps_lng: float
) -> dict:
    """
    Cross-verify GPS coordinates against typed address

    Returns:
        dict: {
            "verified": bool,
            "distance_miles": float,
            "flag": bool,
            "flag_reason": str,
            "gps_address": str,
            "typed_coords": { "lat", "lng" },
        }
    """
    result = {
        "verified": False,
        "distance_miles": None,
        "flag": False,
        "flag_reason": "",
        "gps_address": "",
        "typed_coords": None,
    }

    # Step 1: Geocode the typed address
    typed_coords = geocode_address(typed_address)
    if not typed_coords:
        result["flag"] = True
        result["flag_reason"] = "Could not verify typed address"
        return result

    result["typed_coords"] = typed_coords

    # Step 2: Reverse geocode the GPS coordinates
    gps_result = reverse_geocode(gps_lat, gps_lng)
    if gps_result:
        result["gps_address"] = gps_result["formatted_address"]

    # Step 3: Calculate distance
    distance = haversine_distance(
        typed_coords["lat"], typed_coords["lng"],
        gps_lat, gps_lng
    )
    result["distance_miles"] = round(distance, 2)

    print(f"Distance between typed address and GPS: {distance:.2f} miles")

    # Step 4: Flag logic
    if distance > DISTANCE_THRESHOLD_MILES:
        result["flag"] = True
        result["flag_reason"] = f"GPS location is {distance:.1f} miles from provided address"
    else:
        result["verified"] = True

    # Step 5: City/state cross-check (additional validation)
    if CITY_STATE_MATCH_REQUIRED and gps_result:
        gps_components = gps_result.get("components", {})
        gps_city = gps_components.get("city", "").lower()
        gps_state = gps_components.get("state", "").lower()

        # Check if GPS city/state appear in typed address
        typed_lower = typed_address.lower()
        if gps_city and gps_city not in typed_lower:
            if not result["flag"]:  # Only add reason if not already flagged
                result["flag"] = True
                result["flag_reason"] = f"City mismatch: GPS shows {gps_city.title()}"

    return result