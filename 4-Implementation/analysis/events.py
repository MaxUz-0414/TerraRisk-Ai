"""Tiny helper to store system events (errors/warnings) so the admin console can show them."""
import logging

logger = logging.getLogger(__name__)


def log_event(level, source, message):
    """Never raises: logging must not break a user request."""
    try:
        from .models import SystemEvent

        SystemEvent.objects.create(level=level, source=source[:40], message=str(message)[:500])
    except Exception:
        logger.exception("Could not store system event")
