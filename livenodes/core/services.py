"""Shared background resources (sockets, MIDI ports, audio streams, captures).

Nodes ask for a service by (kind, key) every cook; the first request
creates it. Everything is closed when the engine stops.
"""
import threading

_lock = threading.Lock()
_services = {}


def get(kind, key, factory):
    k = (kind, key)
    svc = _services.get(k)
    if svc is None:
        with _lock:
            svc = _services.get(k)
            if svc is None:
                svc = factory()
                _services[k] = svc
    return svc


def drop(kind, key):
    svc = _services.pop((kind, key), None)
    if svc is not None:
        _close(svc)


def shutdown_all():
    with _lock:
        items = list(_services.values())
        _services.clear()
    for svc in items:
        _close(svc)


def _close(svc):
    try:
        svc.close()
    except Exception as exc:  # a failing close must not block the others
        print(f"[LiveNodes] error closing {svc!r}: {exc}")
