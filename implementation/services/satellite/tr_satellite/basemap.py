"""A sharp high-resolution base picture (Esri World Imagery) for the same box as the data layers.

Why: Sentinel-2 is 10 m per pixel, so a small parcel looks blurry when stretched. Esri World Imagery is
about 0.3 to 1 m in most places. We use it as the background and draw the data layers on top.

fetch_base(frame) -> PIL RGB image of exactly frame["w"] x frame["h"]
  1. Esri "export" endpoint (one request)
  2. fallback: stitch the same XYZ tiles the map page uses
Raises RuntimeError when neither works (the caller then falls back to a Sentinel-2 picture).
"""
import io
import logging
import math

from tr_common.config import env_str

from .geo import EARTH_R

logger = logging.getLogger(__name__)

EXPORT_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export"
TILE_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
HEADERS = {"User-Agent": "TerraRiskAI/1.0 (satellite service)"}
MAX_TILES = 40


def _open(content):
    from PIL import Image

    image = Image.open(io.BytesIO(content))
    image.load()
    return image.convert("RGB")


def _export(frame, timeout):
    import requests

    params = {"bbox": f"{frame['x0']},{frame['y0']},{frame['x1']},{frame['y1']}", "bboxSR": 3857, "imageSR": 3857,
              "size": f"{frame['w']},{frame['h']}", "format": "jpg", "f": "image", "transparent": "false"}
    response = requests.get(env_str("ESRI_EXPORT_URL") or EXPORT_URL, params=params, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    if "image" not in response.headers.get("Content-Type", ""):
        raise RuntimeError("Esri export did not return an image")
    return _open(response.content)


def _stitch(frame, timeout):
    import requests
    from PIL import Image

    world = 2 * math.pi * EARTH_R
    width_m = frame["x1"] - frame["x0"]
    # highest zoom that still has tiles (17 almost everywhere) and keeps the request small
    zoom = 17
    while zoom > 8 and (math.ceil(width_m / (world / 2 ** zoom)) + 2) * (math.ceil((frame["y1"] - frame["y0"]) / (world / 2 ** zoom)) + 2) > MAX_TILES:
        zoom -= 1
    tile_m = world / 2 ** zoom
    tx0, tx1 = int((frame["x0"] + world / 2) // tile_m), int((frame["x1"] + world / 2) // tile_m)
    ty0, ty1 = int((world / 2 - frame["y1"]) // tile_m), int((world / 2 - frame["y0"]) // tile_m)
    if (tx1 - tx0 + 1) * (ty1 - ty0 + 1) > MAX_TILES:
        raise RuntimeError("Too many tiles for this frame")
    canvas = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256), (30, 40, 30))
    session = requests.Session()
    got = 0
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            response = session.get(TILE_URL.format(z=zoom, x=tx, y=ty), headers=HEADERS, timeout=timeout)
            if response.status_code == 200:
                canvas.paste(_open(response.content), ((tx - tx0) * 256, (ty - ty0) * 256))
                got += 1
    if not got:
        raise RuntimeError("No tiles could be downloaded")
    px = 256 / tile_m  # canvas pixels per mercator metre
    left = (frame["x0"] + world / 2 - tx0 * tile_m) * px
    top = ((world / 2 - frame["y1"]) - ty0 * tile_m) * px
    right = left + (frame["x1"] - frame["x0"]) * px
    bottom = top + (frame["y1"] - frame["y0"]) * px
    return canvas.crop((int(left), int(top), int(math.ceil(right)), int(math.ceil(bottom)))).resize((frame["w"], frame["h"]), Image.LANCZOS)


def fetch_base(frame, timeout=25):
    try:
        return _export(frame, timeout)
    except Exception as exc:
        logger.warning("Esri export failed (%s); trying tiles", exc)
    return _stitch(frame, timeout)
