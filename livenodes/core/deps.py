"""Optional third party modules. Nothing here is required for the core."""
import importlib
import subprocess
import sys

# module name -> (pip package, what it enables, platform or None for all)
OPTIONAL = {
    "rtmidi": ("python-rtmidi", "MIDI In / MIDI Out", None),
    "sounddevice": ("sounddevice", "Audio Device In (live microphone / line in)", None),
    "cv2": ("opencv-python-headless", "Video In (webcam and movie files)", None),
    "NDIlib": ("ndi-python", "NDI Out (video over the network)", None),
    "SpoutGL": ("SpoutGL", "Spout Out (texture sharing)", "win32"),
    "syphon": ("syphon-python", "Syphon Out (texture sharing)", "darwin"),
}


def available_here():
    """Optional modules that make sense on this operating system."""
    return {m: v for m, v in OPTIONAL.items() if v[2] is None or v[2] == sys.platform}

_cache = {}


def load(name):
    """Import an optional module, or return None."""
    if name not in _cache:
        try:
            _cache[name] = importlib.import_module(name)
        except Exception:
            _cache[name] = None
    return _cache[name]


def require(name):
    mod = load(name)
    if mod is None:
        pkg = OPTIONAL.get(name, (name,))[0]
        raise RuntimeError(f"needs '{pkg}' - install it from the Live Nodes panel")
    return mod


def install(name):
    """pip-install into Blender's user modules folder. Returns (ok, log)."""
    import bpy

    pkg = OPTIONAL[name][0]
    target = bpy.utils.user_resource('SCRIPTS', path="modules", create=True)
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "--target", target, pkg]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except Exception as exc:
        return False, str(exc)
    if target not in sys.path:
        sys.path.append(target)
    importlib.invalidate_caches()
    _cache.pop(name, None)
    ok = res.returncode == 0 and load(name) is not None
    return ok, (res.stdout + res.stderr)[-2000:]
