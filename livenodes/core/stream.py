"""Video sharing senders: NDI (network), Spout (Windows), Syphon (macOS).

Each sender takes an RGBA uint8 image (height, width, 4), top row first,
straight (not premultiplied) alpha, and publishes it under a name other
applications can pick up (Resolume, OBS, TouchDesigner, MadMapper, vMix...).
"""
import importlib
import sys
import threading

from . import deps

PROTOCOLS = {
    'NDI': ("NDIlib", None, "NDI"),
    'SPOUT': ("SpoutGL", "win32", "Spout"),
    'SYPHON': ("syphon", "darwin", "Syphon"),
}

GL_RGBA = 0x1908


def check_platform(protocol):
    module, platform, label = PROTOCOLS[protocol]
    if platform is not None and sys.platform != platform:
        where = {"win32": "Windows", "darwin": "macOS"}[platform]
        raise RuntimeError(f"{label} is only available on {where}; use NDI on this system")
    return module


# -- NDI ------------------------------------------------------------------
_ndi_lock = threading.Lock()
_ndi_users = 0


class NdiSender:
    """NDI over the network. The SDK runtime ships with the ndi-python wheel."""

    def __init__(self, name):
        global _ndi_users
        self.ndi = ndi = deps.require("NDIlib")
        with _ndi_lock:
            if _ndi_users == 0 and not ndi.initialize():
                raise RuntimeError("NDI could not start (unsupported CPU?)")
            _ndi_users += 1
        settings = ndi.SendCreate()
        settings.ndi_name = name
        settings.clock_video = False  # never block Blender's main loop
        settings.clock_audio = False
        self.sender = ndi.send_create(settings)
        if self.sender is None:
            self._release()
            raise RuntimeError(f"could not create NDI sender '{name}'")
        self.frame = ndi.VideoFrameV2()
        self._keep = None  # async send: the buffer must stay alive until the next send

    def has_receivers(self):
        return self.ndi.send_get_no_connections(self.sender, 0) > 0

    def send(self, image, fps, alpha=True):
        ndi = self.ndi
        frame = self.frame
        frame.data = image
        frame.FourCC = ndi.FOURCC_VIDEO_TYPE_RGBA if alpha else ndi.FOURCC_VIDEO_TYPE_RGBX
        frame.frame_rate_N = int(round(fps * 1000))
        frame.frame_rate_D = 1000
        ndi.send_send_video_async_v2(self.sender, frame)
        self._keep = image

    def close(self):
        if self.sender is not None:
            self.ndi.send_destroy(self.sender)  # waits for the pending async frame
            self.sender = None
        self._keep = None
        self._release()

    def _release(self):
        global _ndi_users
        with _ndi_lock:
            _ndi_users -= 1
            if _ndi_users == 0:
                self.ndi.destroy()


# -- Spout ----------------------------------------------------------------
class SpoutSender:
    """Spout (DirectX texture sharing on Windows) via the SpoutGL module."""

    def __init__(self, name):
        import gpu
        check_platform('SPOUT')
        spout = deps.require("SpoutGL")
        try:
            self.gl_rgba = importlib.import_module("SpoutGL.enums").GL_RGBA
        except Exception:
            self.gl_rgba = GL_RGBA
        self.name = name
        self.sender = spout.SpoutSender()
        self.sender.setSenderName(name)
        # Blender may draw with Vulkan: then there is no OpenGL context and
        # Spout makes a hidden one of its own.
        self.own_gl = gpu.platform.backend_type_get() != 'OPENGL'
        if self.own_gl and not self.sender.createOpenGL():
            raise RuntimeError("Spout could not create an OpenGL context")

    def has_receivers(self):
        return True  # Spout does not report receivers

    def send(self, image, fps, alpha=True):
        h, w = image.shape[:2]
        if not self.sender.sendImage(image, w, h, self.gl_rgba, False, 0):
            raise RuntimeError("Spout could not send the frame")
        self.sender.setFrameSync(self.name)

    def close(self):
        self.sender.releaseSender()
        if self.own_gl:
            self.sender.closeOpenGL()


# -- Syphon ---------------------------------------------------------------
class SyphonSender:
    """Syphon (Metal texture sharing on macOS) via the syphon-python module."""

    def __init__(self, name):
        check_platform('SYPHON')
        syphon = deps.require("syphon")
        self.raw = importlib.import_module("syphon.utils.raw")
        self.np_utils = importlib.import_module("syphon.utils.numpy")
        self.server = syphon.SyphonMetalServer(name)
        self.texture = None
        self.size = None

    def has_receivers(self):
        return bool(self.server.has_clients)

    def send(self, image, fps, alpha=True):
        h, w = image.shape[:2]
        if self.size != (w, h):
            self.texture = self.raw.create_mtl_texture(self.server.device, w, h)
            self.size = (w, h)
        self.np_utils.copy_image_to_mtl_texture(image, self.texture)
        self.server.publish_frame_texture(self.texture)

    def close(self):
        self.server.stop()


SENDERS = {'NDI': NdiSender, 'SPOUT': SpoutSender, 'SYPHON': SyphonSender}


def default_protocol():
    return {'win32': 'SPOUT', 'darwin': 'SYPHON'}.get(sys.platform, 'NDI')
