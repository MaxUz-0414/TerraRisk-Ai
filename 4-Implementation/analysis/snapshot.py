"""What a saved parcel shows: the persona view the user first saw (stored), or one rebuilt for parcels saved before snapshots existed."""
import logging

from core import services

logger = logging.getLogger(__name__)

IMAGERY_NOTES = {
    "demo": "Demo illustration, not a real satellite image.",
    "live": "Imagery: Esri World Imagery (Maxar, Earthstar Geographics) with Sentinel-2, Landsat 8/9 and other open data on top.",
}


def ensure_snapshot(parcel):
    """{"headline", "view", "scenarios"}. Raises services.Unavailable if it has to be rebuilt and the risk service is down."""
    snap = parcel.snapshot or {}
    if snap.get("view") and snap.get("headline"):
        return snap
    data = services.persona_view(parcel.features, parcel.risk_score, parcel.persona)
    snap = {**snap, "headline": data["headline"], "view": data["view"], "scenarios": data.get("scenarios", [])}
    parcel.snapshot = snap
    parcel.save(update_fields=["snapshot"])
    return snap


def ensure_place(parcel):
    """Parcels saved before place names existed get one the first time they are opened (once; failures are not retried)."""
    if parcel.place or parcel.data_mode:
        return
    parcel.data_mode = "legacy"
    try:
        place = services.reverse_place(parcel.center_lat, parcel.center_lng)
        parcel.place = (place.get("name") or "")[:160]
        parcel.country = (place.get("country") or "")[:80]
        parcel.country_code = (place.get("country_code") or "")[:2]
    except (services.Unavailable, services.Rejected) as exc:
        logger.info("No place name for parcel %s: %s", parcel.pk, exc)
    parcel.save(update_fields=["place", "country", "country_code", "data_mode"])


def report_data(parcel):
    """Everything the report service needs (it fetches the satellite pictures itself)."""
    snap = ensure_snapshot(parcel)
    view, features = snap["view"], parcel.features
    return {
        "parcel_id": parcel.public_id, "nickname": parcel.display_name, "place": parcel.place_display, "coords": parcel.coords_display,
        "area_ha": parcel.area_ha, "buffer_km": parcel.buffer_km, "persona": parcel.get_persona_display(),
        "date": parcel.created_at.strftime("%b %d, %Y"), "score": parcel.risk_score, "level": parcel.risk_level,
        "headline": snap["headline"], "verdict": view["verdict"], "question": view.get("question"), "cards": view.get("cards"),
        "factors": view.get("factors"), "checklist": view.get("checklist"), "flags": view.get("flags"), "scenarios": snap.get("scenarios"),
        "notes": view.get("notes"), "hazards": parcel.hazards, "advisory": parcel.advisory, "advisory_source": snap.get("advisory_source", ""),
        "features": features, "ndvi": features.get("ndvi_series"), "lst": features.get("lst_series"), "rain": features.get("rain_series"),
        "geometry": parcel.geometry,
        "imagery_note": IMAGERY_NOTES.get(parcel.data_mode, IMAGERY_NOTES["live"] if parcel.data_mode == "legacy" else ""),
    }
