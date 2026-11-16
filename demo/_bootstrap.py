"""Shared setup for the demo scripts: works inside Blender (add-on installed or
not) and with the `bpy` Python module."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "demo")


def livenodes():
    """Return the registered add-on package, registering it from this repository if needed."""
    import bpy
    for name in list(sys.modules):
        if name.endswith("livenodes") and hasattr(sys.modules[name], "node_classes") and hasattr(bpy.types.Scene, "livenodes"):
            return sys.modules[name]
    if bpy.app.background:
        import gpu
        try:
            gpu.init()
        except Exception:
            pass  # already initialised (Blender binary)
    sys.path.insert(0, ROOT)
    import livenodes as pkg
    pkg.register()
    return pkg
