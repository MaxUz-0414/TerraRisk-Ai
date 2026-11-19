"""TerraRisk `geocode` service: place search, reverse geocoding (what is this place called?) and IP location.

Uses free public services (OpenStreetMap Nominatim, ipwho.is), caches every answer in its own SQLite database and
keeps to Nominatim's usage policy (max 1 request per second, identifying User-Agent).
"""
