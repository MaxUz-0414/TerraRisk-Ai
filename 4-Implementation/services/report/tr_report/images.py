"""Fetches the satellite pictures for a report from the satellite service (in parallel, never fatal)."""
import base64
import binascii
import contextvars
import logging
from concurrent.futures import ThreadPoolExecutor

from tr_common import registry

logger = logging.getLogger("tr.report")
LAYERS = ("truecolor", "ndvi", "heat", "water")


def decode_supplied(supplied):
    """The caller may pass ready-made pictures as {layer: base64}; ignore anything malformed."""
    out = {}
    for layer, text in (supplied or {}).items():
        if layer in LAYERS and isinstance(text, str):
            try:
                out[layer] = base64.b64decode(text, validate=True)
            except (binascii.Error, ValueError):
                logger.warning("Ignoring malformed picture for %s", layer)
    return out


def fetch_all(geometry, features, have=None):
    """{layer: jpeg bytes}; a layer that fails is simply missing and the PDF shows a placeholder."""
    have = dict(have or {})
    wanted = [layer for layer in LAYERS if layer not in have]
    if not wanted:
        return have
    client = registry.client("satellite")

    def one(layer):
        context = contextvars.copy_context()  # keeps the request id for log tracing
        try:
            reply = context.run(lambda: client.post(f"/v1/layers/{layer}", json={"geometry": geometry, "features": features or {}}, timeout=110))
            return layer, reply.content
        except Exception as exc:
            logger.warning("Satellite picture %s unavailable: %s", layer, exc)
            return layer, None

    with ThreadPoolExecutor(max_workers=len(wanted)) as pool:
        for layer, data in pool.map(one, wanted):
            if data:
                have[layer] = data
    return have
