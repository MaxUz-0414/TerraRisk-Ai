"""
Satellite pictures of a parcel: true colour, vegetation, heat and water.

render_layer(geometry, layer, features=None) -> (jpeg_bytes, "image/jpeg")

How the picture is made (1600 x 1000 px, the same box for every layer, so tabs line up):
  * USE_FAKE_DATA=True : a generated illustration, clearly labelled "Demo illustration".
  * USE_FAKE_DATA=False:
      1. a sharp base photo from Esri World Imagery (see basemap.py); falls back to Sentinel-2 if Esri is unreachable
      2. the data layer from Google Earth Engine drawn on top: NDVI (Sentinel-2), land temperature (Landsat 8/9),
         flood-prone ground and water (MERIT Hydro + JRC Global Surface Water)
  * Always drawn by us (so the lines are crisp): parcel outline, scale bar, north arrow, legend, source line.
"""
import io
import logging
import math
import random
from datetime import date

from tr_common.config import env_bool

from . import basemap, gee
from .geo import from_mercator, ring_points, to_mercator

logger = logging.getLogger(__name__)

LAYERS = {
    "truecolor": "True color",
    "ndvi": "Vegetation",
    "heat": "Heat",
    "water": "Water",
}
W, H = 1600, 1000
OUTLINE = (250, 204, 21)          # yellow
OVERLAY_OPACITY = {"ndvi": 0.68, "heat": 0.62, "water": 0.85, "truecolor": 0.0}

NDVI_RAMP = [(0.0, (185, 28, 28)), (0.25, (245, 158, 11)), (0.45, (253, 224, 71)), (0.65, (132, 204, 22)),
             (0.85, (21, 128, 61)), (1.0, (20, 83, 45))]
HEAT_RAMP = [(0.0, (43, 131, 186)), (0.25, (171, 221, 164)), (0.5, (255, 255, 191)), (0.75, (253, 174, 97)), (1.0, (215, 25, 28))]
NDVI_HEX = ["#b91c1c", "#f59e0b", "#fde047", "#84cc16", "#15803d", "#14532d"]
HEAT_HEX = ["#2b83ba", "#abdda4", "#ffffbf", "#fdae61", "#d7191c"]


# --------------------------------------------------------------------------- the map box
def make_frame(geometry):
    """Mercator box around the parcel, 16:10, never tighter than 1.2 km, parcel fills about half the width and never wider than 12 km."""
    points = [to_mercator(lng, lat) for lng, lat in ring_points(geometry)]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    k = math.cos(math.radians(from_mercator(cx, cy)[1]))  # ground metres per mercator metre
    ground_w, ground_h = (max(xs) - min(xs)) * k, (max(ys) - min(ys)) * k
    ground = min(max(ground_w * 1.9, ground_h * 1.9 * W / H, 1200.0), 12000.0)
    mw = ground / k
    mh = mw * H / W
    return {"x0": cx - mw / 2, "x1": cx + mw / 2, "y0": cy - mh / 2, "y1": cy + mh / 2, "w": W, "h": H,
            "ground_w": ground, "k": k, "m_per_px": ground / W}


def to_pixels(frame, lng, lat):
    x, y = to_mercator(lng, lat)
    return ((x - frame["x0"]) / (frame["x1"] - frame["x0"]) * frame["w"],
            (frame["y1"] - y) / (frame["y1"] - frame["y0"]) * frame["h"])


def center_of(geometry):
    from .geo import centroid

    return centroid(geometry)


# --------------------------------------------------------------------------- public entry point
def render_layer(geometry, layer, features=None):
    if layer not in LAYERS:
        raise ValueError(f"Unknown layer {layer!r}")
    frame = make_frame(geometry)
    if env_bool("USE_FAKE_DATA", True):
        base, source = demo_base(geometry, layer, features or {}, frame), "Demo illustration, not a real satellite image"
    else:
        base, source = live_base(geometry, layer, frame)
    return _finish(base, geometry, layer, frame, source), "image/jpeg"


# --------------------------------------------------------------------------- live (Earth Engine + Esri)
def live_base(geometry, layer, frame):
    """(PIL RGB image, source text)."""
    from PIL import Image

    photo, photo_source = None, ""
    try:
        photo = basemap.fetch_base(frame)
        photo_source = "Imagery: Esri, Maxar, Earthstar Geographics"
    except Exception as exc:
        logger.warning("No Esri base picture (%s); using Sentinel-2", exc)
    if layer == "truecolor":
        if photo is not None:
            return photo, photo_source
        return _gee_image(_gee_truecolor, frame).convert("RGB"), "Imagery: Copernicus Sentinel-2 via Google Earth Engine"

    overlay = _gee_image(_gee_layer_factory(layer), frame)  # RGBA, transparent where there is no data
    if photo is None:
        photo = _gee_image(_gee_truecolor, frame).convert("RGB")
        photo_source = "Imagery: Copernicus Sentinel-2"
    return _blend(photo, overlay, OVERLAY_OPACITY[layer]), f"{photo_source} + {_layer_source(layer)} via Google Earth Engine"


def _layer_source(layer):
    return {"ndvi": "Sentinel-2 NDVI", "heat": "Landsat 8/9 temperature", "water": "MERIT Hydro + JRC surface water"}[layer]


def _blend(photo, overlay, opacity):
    """Draw the data layer over the photo; the photo is slightly darkened so the colours stand out."""
    from PIL import Image, ImageEnhance

    photo = ImageEnhance.Brightness(photo.convert("RGB")).enhance(0.82).convert("RGBA")
    overlay = overlay.convert("RGBA").resize(photo.size, Image.BICUBIC)
    alpha = overlay.getchannel("A").point(lambda a: int(a * opacity))
    overlay.putalpha(alpha)
    return Image.alpha_composite(photo, overlay).convert("RGB")


def _gee_image(factory, frame):
    """Download an Earth Engine picture for exactly this frame."""
    import requests
    from PIL import Image

    ee = gee._init_ee()
    lng0, lat0 = from_mercator(frame["x0"], frame["y0"])
    lng1, lat1 = from_mercator(frame["x1"], frame["y1"])
    region = ee.Geometry.Rectangle([lng0, lat0, lng1, lat1], "EPSG:4326", False)
    image = factory(ee, region)
    url = image.getThumbURL({"region": region, "dimensions": f"{frame['w']}x{frame['h']}", "format": "png", "crs": "EPSG:3857"})
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    picture = Image.open(io.BytesIO(response.content))
    picture.load()
    return picture.convert("RGBA")


def _sentinel(ee, region):
    """Cloud-free median of recent Sentinel-2 images (widens the time window when the sky was cloudy)."""
    end = ee.Date(date.today().isoformat())
    for days in (120, 365):
        collection = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(region)
                      .filterDate(end.advance(-days, "day"), end)
                      .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30)))
        if collection.size().getInfo() > 0:
            return collection.map(lambda img: img.resample("bicubic")).median()   # bicubic = smooth, not blocky
    raise ValueError("No clear Sentinel-2 images found for this place.")


def _gee_truecolor(ee, region):
    return _sentinel(ee, region).visualize(bands=["B4", "B3", "B2"], min=0, max=2800, gamma=1.2)


def _gee_layer_factory(layer):
    def factory(ee, region):
        if layer == "ndvi":
            return _sentinel(ee, region).normalizedDifference(["B8", "B4"]).visualize(min=0, max=0.9, palette=NDVI_HEX)
        if layer == "heat":
            end = ee.Date(date.today().isoformat())
            collection = (ee.ImageCollection("LANDSAT/LC09/C02/T1_L2").merge(ee.ImageCollection("LANDSAT/LC08/C02/T1_L2"))
                          .filterBounds(region).filterDate(end.advance(-180, "day"), end)
                          .filter(ee.Filter.lt("CLOUD_COVER", 40)).select("ST_B10"))
            celsius = collection.map(lambda img: img.resample("bicubic")).median().multiply(0.00341802).add(149.0).subtract(273.15)
            return celsius.visualize(min=15, max=45, palette=HEAT_HEX)
        # water: ground within 5 m of the nearest channel (flood-prone) plus permanent water
        low = ee.Image("MERIT/Hydro/v1_0_1").select("hnd").lt(5).selfMask().visualize(palette=["#38bdf8"], opacity=0.55)
        water = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").gt(20).selfMask().visualize(palette=["#0369a1"])
        return low.blend(water)
    return factory


# --------------------------------------------------------------------------- demo illustration
def hash_seed(text):
    """A stable integer from text (Python's built-in hash() changes between runs)."""
    value = 0
    for char in text:
        value = (value * 131 + ord(char)) % (2 ** 32)
    return value


def _ramp(values, stops):
    import numpy as np

    positions = [p for p, _ in stops]
    channels = [np.interp(values, positions, [c[i] for _, c in stops]) for i in range(3)]
    return np.stack(channels, axis=-1).astype("uint8")


def _noise(rng, cell):
    import numpy as np
    from PIL import Image

    small = rng.random((H // cell + 2, W // cell + 2))
    image = Image.fromarray((small * 255).astype("uint8")).resize((W, H), Image.BICUBIC)
    return np.asarray(image, dtype="float32") / 255


def demo_base(geometry, layer, features, frame):
    """A deterministic illustration that matches the parcel's numbers (river distance, built-up share, flood zone)."""
    import numpy as np
    from PIL import Image, ImageDraw

    lat, lng = center_of(geometry)
    seed = f"{round(lat, 3)}:{round(lng, 3)}"
    rng = np.random.default_rng(hash_seed(seed))
    py = random.Random(seed)
    px_per_m = 1 / frame["m_per_px"]
    sc = W / 900

    field = 0.55 * _noise(rng, int(150 * sc)) + 0.30 * _noise(rng, int(45 * sc)) + 0.15 * _noise(rng, int(14 * sc))
    field = (field - field.min()) / max(1e-6, field.max() - field.min())

    shape = [to_pixels(frame, lg, lt) for lg, lt in ring_points(geometry)]
    built_share = features.get("built_up_pct")
    patches = int(round((built_share if isinstance(built_share, (int, float)) else 15) / 6))
    built = Image.new("L", (W, H), 0)
    draw_built = ImageDraw.Draw(built)
    for _ in range(max(0, min(patches, 14))):
        x, y = py.randint(int(40 * sc), int(W - 160 * sc)), py.randint(int(40 * sc), int(H - 120 * sc))
        if abs(x - W / 2) < 90 * sc and abs(y - H / 2) < 70 * sc:
            continue
        draw_built.rectangle([x, y, x + py.randint(int(40 * sc), int(130 * sc)), y + py.randint(int(30 * sc), int(90 * sc))], fill=255)
    built_mask = np.asarray(built, dtype="float32") / 255

    dist_m = features.get("dist_to_river_m")
    half_height = max([abs(y - H / 2) for _, y in shape] or [0])  # distance is measured from the parcel EDGE
    offset = min(float(dist_m) * px_per_m + half_height, 0.46 * H) if isinstance(dist_m, (int, float)) else 0.3 * H
    offset *= py.choice([-1, 1])
    phase, amplitude = py.uniform(0, 6.28), py.uniform(18, 40) * sc
    ys, xs = np.mgrid[0:H, 0:W]
    centre_line = H / 2 + offset + amplitude * np.sin(xs / (140.0 * sc) + phase) + 0.12 * (xs - W / 2)
    distance_to_river = np.abs(ys - centre_line)
    river = (distance_to_river < 11 * sc).astype("float32")
    river_rgb = np.array([56, 140, 200], dtype="uint8")

    if layer == "ndvi":
        green = np.clip(0.25 + 0.65 * field - 0.55 * built_mask - 0.4 * river, 0, 1)
        rgb = _ramp(green, NDVI_RAMP)
    elif layer == "heat":
        cooling = np.clip(1 - distance_to_river / (160 * sc), 0, 1)
        warm = np.clip(0.30 + 0.25 * (1 - field) + 0.55 * built_mask - 0.45 * river - 0.25 * cooling, 0, 1)
        rgb = _ramp(warm, HEAT_RAMP)
    else:
        rgb = _ramp(field, [(0, (46, 78, 40)), (0.4, (63, 96, 52)), (0.65, (98, 110, 62)), (0.85, (132, 118, 84)), (1, (158, 140, 104))])
        rgb = np.where(built_mask[..., None] > 0.5, np.array([150, 142, 128], dtype="uint8"), rgb)
        if layer == "water":
            hand = features.get("hand_m")
            width = 150 * sc * min(1.0, max(0.0, (15 - hand) / 15)) if isinstance(hand, (int, float)) else 60 * sc
            zone = (distance_to_river < 11 * sc + width)[..., None]
            rgb = np.where(zone, (0.62 * rgb + 0.38 * np.array([14, 165, 233])).astype("uint8"), rgb)
    rgb = np.where(river[..., None] > 0.5, river_rgb, rgb)
    return Image.fromarray(rgb.astype("uint8"), "RGB")


# --------------------------------------------------------------------------- annotations (all layers)
def _font(size):
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # old Pillow
        return ImageFont.load_default()


def _text_size(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _chip(draw, xy, text, font, fill=(5, 11, 20, 215), color=(226, 232, 240, 255), pad=10):
    w, h = _text_size(draw, text, font)
    x, y = xy
    draw.rounded_rectangle([x, y, x + w + 2 * pad, y + h + 2 * pad - 2], radius=8, fill=fill)
    draw.text((x + pad, y + pad - 3), text, fill=color, font=font)
    return w + 2 * pad, h + 2 * pad


def _nice_length(meters_per_px, target_px=200):
    for length in (20, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000):
        if length / meters_per_px >= target_px * 0.6:
            return length
    return 10000


def _finish(base, geometry, layer, frame, source):
    """Parcel outline, title, legend, scale bar, north arrow and source line on top of the base picture."""
    from PIL import Image, ImageDraw

    base = base.convert("RGB").resize((W, H), Image.LANCZOS) if base.size != (W, H) else base.convert("RGB")
    ss = 2  # draw at 2x and shrink: smooth lines
    overlay = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    shape = [to_pixels(frame, lg, lt) for lg, lt in ring_points(geometry)]
    big = [(x * ss, y * ss) for x, y in shape]
    if geometry.get("type") == "Polygon" and len(big) >= 3:
        draw.polygon(big, fill=OUTLINE + (38,))
        draw.line(big + [big[0]], fill=(0, 0, 0, 170), width=9 * ss // 2 + 2, joint="curve")
        draw.line(big + [big[0]], fill=OUTLINE + (255,), width=5 * ss // 2 + 1, joint="curve")
    else:
        cx, cy = big[0]
        for radius, width, color in ((26, 12, (0, 0, 0, 170)), (26, 6, OUTLINE + (255,))):
            draw.ellipse([cx - radius * ss, cy - radius * ss, cx + radius * ss, cy + radius * ss], outline=color, width=width)
        draw.line([cx - 40 * ss, cy, cx - 12 * ss, cy], fill=OUTLINE + (255,), width=4 * ss)
        draw.line([cx + 12 * ss, cy, cx + 40 * ss, cy], fill=OUTLINE + (255,), width=4 * ss)
        draw.line([cx, cy - 40 * ss, cx, cy - 12 * ss], fill=OUTLINE + (255,), width=4 * ss)
        draw.line([cx, cy + 12 * ss, cx, cy + 40 * ss], fill=OUTLINE + (255,), width=4 * ss)
    overlay = overlay.resize((W, H), Image.LANCZOS)
    image = Image.alpha_composite(base.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(image)

    # title chip (top left)
    title_font, small, tiny = _font(26), _font(20), _font(17)
    _chip(draw, (20, 20), f"{LAYERS[layer]}  ·  {_period(layer)}", title_font)

    # north arrow (top right)
    nx, ny = W - 54, 62
    draw.ellipse([nx - 30, ny - 30, nx + 30, ny + 30], fill=(5, 11, 20, 200))
    draw.polygon([(nx, ny - 22), (nx - 11, ny + 14), (nx, ny + 6), (nx + 11, ny + 14)], fill=(241, 245, 249, 255))
    draw.text((nx - 7, ny + 12), "N", fill=(250, 204, 21, 255), font=_font(16))

    # scale bar (bottom right)
    length = _nice_length(frame["m_per_px"])
    bar = length / frame["m_per_px"]
    label = f"{length} m" if length < 1000 else f"{length // 1000} km"
    sx, sy = W - 40 - bar, H - 78
    lw, lh = _text_size(draw, label, small)
    draw.rounded_rectangle([sx - 14, sy - lh - 22, W - 26, sy + 24], radius=8, fill=(5, 11, 20, 205))
    draw.text((sx, sy - lh - 14), label, fill=(226, 232, 240, 255), font=small)
    draw.line([sx, sy + 8, sx + bar, sy + 8], fill=(241, 245, 249, 255), width=4)
    draw.line([sx, sy, sx, sy + 16], fill=(241, 245, 249, 255), width=4)
    draw.line([sx + bar, sy, sx + bar, sy + 16], fill=(241, 245, 249, 255), width=4)

    _legend(draw, layer, small, tiny)

    # source line (bottom)
    text = source
    tw, th = _text_size(draw, text, tiny)
    draw.rectangle([0, H - th - 18, tw + 28, H], fill=(5, 11, 20, 215))
    draw.text((14, H - th - 11), text, fill=(203, 213, 225, 255), font=tiny)

    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=90, subsampling=0, optimize=True)
    return buffer.getvalue()


def _period(layer):
    if env_bool("USE_FAKE_DATA", True):
        return "demo"
    today = date.today()
    return {"truecolor": "latest imagery", "ndvi": "last 4 months", "heat": "last 6 months", "water": "all-time water"}[layer] + f" · {today:%b %Y}"


def _legend(draw, layer, font, small):
    """Colour key, bottom left (above the source line)."""
    x, y = 20, H - 130
    if layer in ("ndvi", "heat"):
        ramp, low, high = (NDVI_RAMP, "Bare / dry", "Dense plants") if layer == "ndvi" else (HEAT_RAMP, "15 °C cool", "45 °C hot")
        w = 360
        draw.rounded_rectangle([x, y - 6, x + w + 28, y + 70], radius=8, fill=(5, 11, 20, 205))
        for i in range(w):
            t = i / (w - 1)
            color = _interp(ramp, t)
            draw.line([x + 14 + i, y + 6, x + 14 + i, y + 30], fill=color + (255,))
        draw.text((x + 14, y + 36), low, fill=(226, 232, 240, 255), font=small)
        tw, _ = _text_size(draw, high, small)
        draw.text((x + 14 + w - tw, y + 36), high, fill=(226, 232, 240, 255), font=small)
    elif layer == "water":
        draw.rounded_rectangle([x, y - 6, x + 500, y + 70], radius=8, fill=(5, 11, 20, 205))
        draw.rectangle([x + 14, y + 8, x + 40, y + 26], fill=(3, 105, 161, 255))
        draw.text((x + 50, y + 8), "Open water", fill=(226, 232, 240, 255), font=font)
        draw.rectangle([x + 14, y + 38, x + 40, y + 56], fill=(56, 189, 248, 190))
        draw.text((x + 50, y + 38), "Low ground, under 5 m above the channel (floods first)", fill=(226, 232, 240, 255), font=small)


def _interp(ramp, t):
    for (p0, c0), (p1, c1) in zip(ramp, ramp[1:]):
        if t <= p1:
            u = 0 if p1 == p0 else (t - p0) / (p1 - p0)
            return tuple(int(c0[i] + (c1[i] - c0[i]) * u) for i in range(3))
    return ramp[-1][1]


def placeholder_png(message="Image not available right now"):
    """A small dark card shown when the picture cannot be made (never cached)."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (W, H), (10, 20, 34))
    draw = ImageDraw.Draw(image)
    font = _font(34)
    w, h = _text_size(draw, message, font)
    draw.text(((W - w) / 2, H / 2 - h), message, fill=(148, 163, 184), font=font)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()
