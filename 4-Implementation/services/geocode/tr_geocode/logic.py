"""Turns raw provider answers into the small, stable JSON the rest of TerraRisk uses."""
import ipaddress

from . import cache, providers

DAY = 86400


def _short_name(address):
    """'Ankazobe, Analamanga' style label from Nominatim's address parts."""
    for key in ("city", "town", "village", "municipality", "hamlet", "suburb", "county", "state_district"):
        if address.get(key):
            area = address.get("state") or address.get("region") or ""
            return f"{address[key]}, {area}" if area and area != address[key] else address[key]
    return address.get("state") or address.get("country") or ""


def search(query, limit=5):
    query = " ".join(query.split())[:120]
    key = f"s:{query.lower()}:{limit}"
    hit = cache.get(key, 30 * DAY)
    if hit is not None:
        return hit
    results = []
    for item in providers.nominatim_search(query, limit) or []:
        try:
            south, north, west, east = (float(v) for v in item.get("boundingbox", [0, 0, 0, 0]))
            address = item.get("address") or {}
            results.append({
                "display": item.get("display_name", ""), "short": _short_name(address) or item.get("name", ""),
                "lat": float(item["lat"]), "lng": float(item["lon"]), "bbox": [south, west, north, east],
                "type": item.get("type", ""), "country": address.get("country", ""), "country_code": (address.get("country_code") or "").upper(),
            })
        except (KeyError, TypeError, ValueError):
            continue
    cache.put(key, results)
    return results


def reverse(lat, lng):
    key = f"r:{round(lat, 3)}:{round(lng, 3)}"
    hit = cache.get(key, 90 * DAY)
    if hit is not None:
        return hit
    data = providers.nominatim_reverse(lat, lng) or {}
    address = data.get("address") or {}
    result = {
        "name": _short_name(address) or data.get("name", "") or "",
        "region": address.get("state") or address.get("region") or "",
        "country": address.get("country", ""), "country_code": (address.get("country_code") or "").upper(),
        "display": data.get("display_name", ""),
    }
    if result["name"] or result["country"]:  # do not cache "nothing found" (open sea, etc.) for 90 days
        cache.put(key, result)
    return result


def ip_location(ip):
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        raise ValueError("Not a valid IP address.")
    if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
        return {"ip": ip, "local": True, "country": "", "country_code": "", "city": "Local network", "lat": None, "lng": None}
    key = f"i:{ip}"
    hit = cache.get(key, 7 * DAY)
    if hit is not None:
        return hit
    data = providers.ip_lookup(ip) or {}
    if not data.get("success", False):
        return {"ip": ip, "local": False, "country": "", "country_code": "", "city": "", "lat": None, "lng": None}
    result = {"ip": ip, "local": False, "country": data.get("country", ""), "country_code": data.get("country_code", ""),
              "city": data.get("city", ""), "region": data.get("region", ""), "lat": data.get("latitude"), "lng": data.get("longitude")}
    cache.put(key, result)
    return result
