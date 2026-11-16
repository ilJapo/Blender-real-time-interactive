"""TOP inputs and outputs: images, video, webcam, the 3D scene, files, windows."""
import os

import bpy
import gpu
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty

from ..core import deps, gpu_util, services
from ..core.data import Channels
from ..core.tree import LNNode, LNTopNode
from .top_gen import PASS_FRAG

FLIP_FRAG = "void main(){ fragColor = texture(uIn0, vec2(vUV.x, 1.0 - vUV.y)); }"


class LN_ImageTOP(LNTopNode, bpy.types.Node):
    """An image from the blend file or from disk"""
    bl_idname = "LN_ImageTOP"
    bl_label = "Image TOP"
    ln_category = "TOP Input"
    ln_params = False

    image: PointerProperty(name="Image", type=bpy.types.Image)

    def ln_init(self):
        self.add_out('TOP')

    def ln_draw(self, context, layout):
        layout.template_ID(self, "image", open="image.open")

    def cook(self, ctx, inp):
        img = self.image
        if img is None:
            return gpu_util.black()
        st = ctx.state
        stamp = (img.name, img.size[0], img.size[1], img.filepath, img.is_dirty)
        tex = st.get("tex")
        if tex is None or st.get("stamp") != stamp:
            tex = st["tex"] = gpu.texture.from_image(img)
            st["stamp"] = stamp
        if self.res_mode == 'CUSTOM':
            return self.run(ctx, PASS_FRAG, {}, [tex])
        return tex


class _Capture:
    """Reads frames from a webcam or movie in a background thread."""

    def __init__(self, source, width=0, height=0):
        import threading
        cv2 = deps.require("cv2")
        self.cv2 = cv2
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise RuntimeError(f"cannot open video source {source!r}")
        if width:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height:
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.is_file = isinstance(source, str)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) if self.is_file else 0
        self.lock = threading.Lock()
        self.frame = None
        self.serial = 0
        self.seek_to = None
        self.alive = True
        self.thread = None
        if not self.is_file:
            self.thread = threading.Thread(target=self._run, daemon=True, name="LiveNodes-Video")
            self.thread.start()

    def _run(self):
        while self.alive:
            ok, frame = self.cap.read()
            if not ok:
                import time
                time.sleep(0.01)
                continue
            with self.lock:
                self.frame = frame
                self.serial += 1

    def read_file_frame(self, index):
        """Movie files are read on demand so playback follows the engine clock."""
        cv2 = self.cv2
        cur = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
        if index != cur:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = self.cap.read()
        if ok:
            self.frame = frame
            self.serial += 1
        return self.frame

    def latest(self):
        with self.lock:
            return self.frame, self.serial

    def close(self):
        self.alive = False
        if self.thread is not None:
            self.thread.join(timeout=1.0)
        self.cap.release()


def _frame_to_texture(frame):
    """BGR(A) uint8 from OpenCV -> GPU texture (flipped, linear)."""
    h, w = frame.shape[:2]
    rgba = np.empty((h, w, 4), dtype=np.float32)
    rgba[..., 0] = frame[..., 2]
    rgba[..., 1] = frame[..., 1]
    rgba[..., 2] = frame[..., 0]
    rgba[..., 3] = 255.0
    rgba = rgba[::-1] / 255.0
    rgba[..., :3] **= 2.2  # approximately sRGB -> linear
    return gpu_util.texture_from_array(rgba)


class LN_VideoDeviceTOP(LNTopNode, bpy.types.Node):
    """Live camera input (webcam, capture card)"""
    bl_idname = "LN_VideoDeviceTOP"
    bl_label = "Video Device In TOP"
    ln_category = "TOP Input"
    ln_params = False

    device: IntProperty(name="Device", default=0, min=0, max=16)
    capture_w: IntProperty(name="Request Width", default=1280, min=0)
    capture_h: IntProperty(name="Request Height", default=720, min=0)

    def ln_init(self):
        self.add_out('TOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "device")

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "capture_w")
        layout.prop(self, "capture_h")
        if deps.load("cv2") is None:
            layout.label(text="Needs 'opencv-python-headless'", icon='ERROR')

    def cook(self, ctx, inp):
        cap = services.get("video_dev", (self.device, self.capture_w, self.capture_h),
                           lambda: _Capture(self.device, self.capture_w, self.capture_h))
        frame, serial = cap.latest()
        st = ctx.state
        if frame is None:
            return st.get("tex") or gpu_util.black()
        if st.get("serial") != serial:
            st["tex"] = _frame_to_texture(frame)
            st["serial"] = serial
        return st["tex"]


class LN_MovieFileTOP(LNTopNode, bpy.types.Node):
    """Plays a movie file, in sync with the engine clock"""
    bl_idname = "LN_MovieFileTOP"
    bl_label = "Movie File In TOP"
    ln_category = "TOP Input"

    filepath: StringProperty(name="File", subtype='FILE_PATH')
    play: BoolProperty(name="Play", default=True)
    loop: BoolProperty(name="Loop", default=True)
    speed: FloatProperty(name="Speed", default=1.0)
    cue: FloatProperty(name="Position", default=0.0, min=0.0, max=1.0, description="Jump here (0..1) while Play is off")

    def ln_init(self):
        self.add_out('TOP')
        self.add_out('CHOP', "Info")

    def ln_draw(self, context, layout):
        layout.prop(self, "filepath", text="")
        row = layout.row(align=True)
        row.prop(self, "play", toggle=True, icon='PLAY')
        row.prop(self, "loop", toggle=True, icon='FILE_REFRESH', text="")
        layout.prop(self, "speed")
        layout.prop(self, "cue", slider=True)

    def cook(self, ctx, inp):
        p = ctx.p
        path = bpy.path.abspath(self.filepath)
        if not path:
            return None
        cap = services.get("movie", path, lambda: _Capture(path))
        st = ctx.state
        n = max(cap.frames, 1)
        pos = st.get("pos", 0.0)
        if p.play:
            pos += ctx.dt * cap.fps * p.speed
        else:
            pos = p.cue * (n - 1)
        pos = pos % n if p.loop else min(max(pos, 0.0), n - 1)
        st["pos"] = pos
        idx = int(pos)
        if st.get("idx") != idx or "tex" not in st:
            frame = cap.read_file_frame(idx)
            if frame is not None:
                st["tex"] = _frame_to_texture(frame)
            st["idx"] = idx
        tex = st.get("tex")
        if tex is not None and self.res_mode == 'CUSTOM':
            tex = self.run(ctx, PASS_FRAG, {}, [tex])
        info = Channels.from_dict({"index": idx, "fraction": idx / max(n - 1, 1), "length": n, "fps": cap.fps})
        return {"Out": tex, "Info": info}


class LN_RenderTOP(LNTopNode, bpy.types.Node):
    """Renders the 3D scene through a camera with the viewport engine (EEVEE / Workbench) every frame"""
    bl_idname = "LN_RenderTOP"
    bl_label = "Render TOP"
    ln_category = "TOP Input"
    ln_params = False

    camera: PointerProperty(name="Camera", type=bpy.types.Object, poll=lambda self, ob: ob.type == 'CAMERA')
    shading: EnumProperty(name="Shading", items=[('VIEWPORT', "As Viewport", "Use the shading of the 3D view used for drawing"),
                                                 ('RENDERED', "Rendered", "Force rendered (EEVEE) shading"),
                                                 ('MATERIAL', "Material Preview", ""),
                                                 ('SOLID', "Solid", "")], default='RENDERED')
    transparent: BoolProperty(name="Transparent", default=False, description="Leave the world background out")

    def ln_init(self):
        self.add_out('TOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "camera", text="", icon='CAMERA_DATA')
        layout.prop(self, "shading", text="")
        layout.prop(self, "transparent")

    def cook(self, ctx, inp):
        scene = ctx.scene
        cam = self.camera or scene.camera
        if cam is None:
            raise ValueError("no camera: set one here or in the scene")
        view = _find_view3d()
        if view is None:
            raise RuntimeError("needs a 3D Viewport open in some window")
        area, space, region = view
        w, h = self.out_size(ctx)
        tgt = self.target(ctx, (w, h))
        depsgraph = bpy.context.evaluated_depsgraph_get()
        view_matrix = cam.matrix_world.inverted()
        proj = cam.calc_matrix_camera(depsgraph, x=w, y=h, scale_x=scene.render.pixel_aspect_x, scale_y=scene.render.pixel_aspect_y)
        shading = space.shading
        old = shading.type
        if self.shading != 'VIEWPORT':
            shading.type = self.shading
        try:
            tgt.off.draw_view3d(scene, bpy.context.view_layer if bpy.context.view_layer else scene.view_layers[0],
                                space, region, view_matrix, proj, do_color_management=False,
                                draw_background=not self.transparent)
        finally:
            if shading.type != old:
                shading.type = old
        return tgt.texture


def _find_view3d():
    wm = bpy.context.window_manager
    for window in wm.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                if region is not None:
                    return area, area.spaces.active, region
    return None


class LN_TopToCHOP(LNNode, bpy.types.Node):
    """Samples an image into channels: average colour, or a row of pixels"""
    bl_idname = "LN_TopToCHOP"
    bl_label = "TOP to CHOP"
    ln_category = "TOP Convert"
    ln_params = False

    mode: EnumProperty(name="Mode", items=[('AVERAGE', "Average", "Mean colour of the whole image"),
                                           ('ROW', "Row", "Pixels of one row as samples"),
                                           ('POINT', "Point", "The colour at one position")], default='AVERAGE')
    samples: IntProperty(name="Samples", default=64, min=1, max=4096)
    position: bpy.props.FloatVectorProperty(name="Position", size=2, default=(0.5, 0.5), min=0.0, max=1.0)

    def ln_init(self):
        self.add_in('TOP', "In")
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "mode", text="")
        if self.mode == 'ROW':
            layout.prop(self, "samples")
        if self.mode != 'AVERAGE':
            layout.prop(self, "position")

    def cook(self, ctx, inp):
        tex = inp.get("In")
        if tex is None:
            return Channels.empty()
        # downsample on the GPU first so the readback stays cheap
        if self.mode == 'ROW':
            size = (self.samples, 1)
            frag = "void main(){ fragColor = texture(uIn0, vec2(vUV.x, uY)); }"
            small = _helper_pass(ctx, frag, tex, size, {"uY": self.position[1]}, (('FLOAT', 'uY'),))
        elif self.mode == 'POINT':
            frag = "void main(){ fragColor = texture(uIn0, uPos); }"
            small = _helper_pass(ctx, frag, tex, (1, 1), {"uPos": self.position}, (('VEC2', 'uPos'),))
        else:
            small = _helper_pass(ctx, PASS_FRAG, tex, (16, 16), {}, ())
        px = gpu_util.read_pixels(small).reshape(-1, 4)
        if self.mode == 'AVERAGE':
            px = px.mean(0, keepdims=True)
        return Channels(["r", "g", "b", "a"], px.T.copy(), rate=px.shape[0])


def _helper_pass(ctx, frag, tex, size, uniforms, decl):
    st = ctx.state
    tgt = st.get("helper")
    if tgt is None:
        tgt = st["helper"] = gpu_util.Target()
    tgt.ensure(size[0], size[1], 'RGBA32F')
    compiled = gpu_util.shader(frag, tuple(decl), 1)
    return gpu_util.draw(tgt, compiled, uniforms, [tex], ctx.time)


class LN_TopToImage(LNNode, bpy.types.Node):
    """Copies a texture into a Blender image: use it in materials, the compositor or the image editor"""
    bl_idname = "LN_TopToImage"
    bl_label = "TOP to Image"
    ln_category = "TOP Output"
    ln_family = 'OUT'
    ln_params = False

    image: PointerProperty(name="Image", type=bpy.types.Image)
    every: IntProperty(name="Every Nth Frame", default=1, min=1, max=60, description="Copying costs a GPU readback: skip frames to save time")

    def ln_init(self):
        self.add_in('TOP', "In")

    def ln_draw(self, context, layout):
        row = layout.row(align=True)
        row.prop(self, "image", text="")
        if self.image is None:
            op = row.operator("livenodes.new_image", text="", icon='ADD')
            op.tree = self.id_data.name
            op.node = self.name
        layout.prop(self, "every")

    def cook(self, ctx, inp):
        tex = inp.get("In")
        img = self.image
        if tex is None or img is None:
            return None
        if ctx.frame % self.every:
            return None
        if tuple(img.size) != (tex.width, tex.height):
            img.scale(tex.width, tex.height)
        px = gpu_util.read_pixels(tex)
        img.pixels.foreach_set(np.ascontiguousarray(px, dtype=np.float32).ravel())
        img.update()
        return None


class LN_OT_new_image(bpy.types.Operator):
    """Create a float image for this node"""
    bl_idname = "livenodes.new_image"
    bl_label = "New Live Image"
    bl_options = {'INTERNAL', 'UNDO'}

    tree: StringProperty()
    node: StringProperty()

    def execute(self, context):
        tree = bpy.data.node_groups.get(self.tree)
        node = tree.nodes.get(self.node) if tree else None
        if node is None:
            return {'CANCELLED'}
        s = context.scene.livenodes
        img = bpy.data.images.new("LiveTexture", s.res_x, s.res_y, alpha=True, float_buffer=True)
        img.use_fake_user = True
        node.image = img
        return {'FINISHED'}


class LN_OutTOP(LNNode, bpy.types.Node):
    """Final output: shown in output windows, the node editor backdrop and recordings"""
    bl_idname = "LN_OutTOP"
    bl_label = "Out TOP"
    ln_category = "TOP Output"
    ln_family = 'OUT'
    ln_params = False

    def ln_init(self):
        self.add_in('TOP', "In")

    def ln_draw(self, context, layout):
        row = layout.row(align=True)
        op = row.operator("livenodes.output_window", text="Window", icon='WINDOW')
        op.tree = self.id_data.name
        op.node = self.name
        op = row.operator("livenodes.output_window", text="Fullscreen", icon='FULLSCREEN_ENTER')
        op.tree = self.id_data.name
        op.node = self.name
        op.fullscreen = True

    def cook(self, ctx, inp):
        tex = inp.get("In")
        ctx.state["tex"] = tex
        return None


class LN_MovieFileOutTOP(LNNode, bpy.types.Node):
    """Records the input to an MP4 (OpenCV) or a PNG / EXR sequence"""
    bl_idname = "LN_MovieFileOutTOP"
    bl_label = "Movie File Out TOP"
    ln_category = "TOP Output"
    ln_family = 'OUT'
    ln_params = False

    filepath: StringProperty(name="Output", subtype='FILE_PATH', default="//live_recording")
    fmt: EnumProperty(name="Format", items=[('MP4', "MP4 Movie", "Needs OpenCV"), ('PNG', "PNG Sequence", ""),
                                            ('EXR', "EXR Sequence", "Float, lossless")], default='PNG')
    record: BoolProperty(name="Record", default=False)
    fps: FloatProperty(name="FPS", default=30.0, min=1.0)

    def ln_init(self):
        self.add_in('TOP', "In")
        self.add_in('CHOP', "Record")

    def ln_draw(self, context, layout):
        layout.prop(self, "filepath", text="")
        layout.prop(self, "fmt", text="")
        layout.prop(self, "record", toggle=True, icon='REC')

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "fps")

    def cook(self, ctx, inp):
        tex = inp.get("In")
        st = ctx.state
        gate = inp.chop("Record")
        recording = self.record or (bool(gate) and gate.first() > 0.5)
        if not recording or tex is None:
            self._finish(st)
            return None
        base = bpy.path.abspath(self.filepath)
        px = gpu_util.read_pixels(tex)
        if self.fmt == 'MP4':
            cv2 = deps.require("cv2")
            if "writer" not in st:
                os.makedirs(os.path.dirname(base) or ".", exist_ok=True)
                st["writer"] = cv2.VideoWriter(base + ".mp4", cv2.VideoWriter_fourcc(*"mp4v"), self.fps, (tex.width, tex.height))
                st["size"] = (tex.width, tex.height)
            if st["size"] != (tex.width, tex.height):
                raise ValueError("resolution changed while recording")
            rgb = np.clip(np.power(np.clip(px[::-1, :, :3], 0, 1), 1 / 2.2) * 255.0 + 0.5, 0, 255).astype(np.uint8)
            st["writer"].write(np.ascontiguousarray(rgb[:, :, ::-1]))
        else:
            st["count"] = st.get("count", 0) + 1
            holder = st.get("img")
            if holder is None or holder.image is None or holder.size != (tex.width, tex.height):
                if holder is not None:
                    holder.free()
                holder = st["img"] = _ImageHolder(bpy.data.images.new(
                    ".ln_record", tex.width, tex.height, alpha=True, float_buffer=self.fmt == 'EXR'))
            image = holder.image
            image.pixels.foreach_set(px.ravel())
            ext = ".png" if self.fmt == 'PNG' else ".exr"
            os.makedirs(os.path.dirname(base) or ".", exist_ok=True)
            image.filepath_raw = f"{base}_{st['count']:05d}{ext}"
            image.file_format = 'PNG' if self.fmt == 'PNG' else 'OPEN_EXR'
            image.save()
        return None

    @staticmethod
    def _finish(st):
        writer = st.pop("writer", None)
        if writer is not None:
            writer.release()
        st.pop("count", None)


class _ImageHolder:
    """Keeps a scratch image in node state and removes it on free."""

    def __init__(self, image):
        self.name = image.name

    @property
    def image(self):
        return bpy.data.images.get(self.name)

    @property
    def size(self):
        img = self.image
        return tuple(img.size) if img else (0, 0)

    def free(self):
        img = self.image
        if img is not None:
            bpy.data.images.remove(img)


classes = (LN_OT_new_image, LN_ImageTOP, LN_VideoDeviceTOP, LN_MovieFileTOP, LN_RenderTOP, LN_TopToCHOP,
           LN_TopToImage, LN_OutTOP, LN_MovieFileOutTOP)
