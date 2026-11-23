"""Request id that follows one user action through every service (for log tracing)."""
import contextvars
import uuid

request_id = contextvars.ContextVar("tr_request_id", default="")


def new_request_id():
    return uuid.uuid4().hex[:12]


def current_request_id():
    return request_id.get() or new_request_id()
