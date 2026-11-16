"""TOP generators: textures made on the GPU."""
import os
import bpy
import numpy as np
from bpy.props import (BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty,
                       PointerProperty, StringProperty)

from ..core import gpu_util
from ..core.tree import LNTopNode

PASS_FRAG = "void main(){ fragColor = texture(uIn0, vUV); }"


def _color(name, default):
    return FloatVectorProperty(name=name, subtype='COLOR', size=4, min=0.0, soft_max=1.0, default=default)


class _Gen(LNTopNode):
    ln_category = "TOP Generate"

    def ln_init(self):
        self.add_out('TOP')


class LN_ConstantTOP(_Gen, bpy.types.Node):
    """A solid colour"""
    bl_idname = "LN_ConstantTOP"
    bl_label = "Constant TOP"

    rgba: _color("Color", (1.0, 1.0, 1.0, 1.0))

    def ln_draw(self, context, layout):
        layout.prop(self, "rgba", text="")

    def cook(self, ctx, inp):
        return self.run(ctx, "void main(){ fragColor = vec4(uColor.rgb * uColor.a, uColor.a); }",
                        {"uColor": ctx.p.rgba}, decl=(('VEC4', 'uColor'),))


NOISE_FRAG = """
void main(){
  vec2 q = (vUV - 0.5) * vec2(uRes.x / uRes.y, 1.0) * uScale + uOffset;
  vec3 p = vec3(q, uZ);
  vec3 c = vec3(0.0);
  if (uType == 2){
    c.x = ln_cell(p);
    if (uMono == 1) c = c.xxx;
    else { c.y = ln_cell(p + vec3(31.7, 11.1, 5.3)); c.z = ln_cell(p + vec3(-17.2, 47.3, 9.9)); }
    c = c * 2.0 - 1.0;
  } else if (uType == 3){
    c = ln_hash3(vec3(floor(vUV * uRes), floor(uZ * 60.0))) * 2.0 - 1.0;
    if (uMono == 1) c = c.xxx;
  } else {
    int o = (uType == 0) ? 1 : uOct;
    c.x = ln_fbm(p, o, uRough);
    if (uMono == 1) c = c.xxx;
    else { c.y = ln_fbm(p + vec3(31.7, 11.1, 5.3), o, uRough); c.z = ln_fbm(p + vec3(-17.2, 47.3, 9.9), o, uRough); }
    c *= 1.5;
  }
  fragColor = vec4(c * uAmp + uBase, 1.0);
}
"""
NOISE_DECL = (('VEC2', 'uOffset'), ('FLOAT', 'uScale'), ('FLOAT', 'uZ'), ('FLOAT', 'uRough'), ('FLOAT', 'uAmp'),
              ('FLOAT', 'uBase'), ('INT', 'uOct'), ('INT', 'uType'), ('INT', 'uMono'))


class LN_NoiseTOP(_Gen, bpy.types.Node):
    """Animated procedural noise"""
    bl_idname = "LN_NoiseTOP"
    bl_label = "Noise TOP"

    kind: EnumProperty(name="Type", items=[('SMOOTH', "Smooth", "Gradient noise"), ('FRACTAL', "Fractal", "Layered gradient noise"),
                                           ('CELL', "Cellular", "Distance to scattered points"), ('RANDOM', "Random", "Per-pixel white noise")],
                       default='FRACTAL')
    scale: FloatProperty(name="Scale", default=4.0)
    octaves: IntProperty(name="Octaves", default=4, min=1, max=8)
    roughness: FloatProperty(name="Roughness", default=0.5, min=0.0, max=1.0)
    speed: FloatProperty(name="Speed", default=0.25, description="How fast the pattern evolves")
    offset: FloatVectorProperty(name="Offset", size=2, default=(0.0, 0.0))
    amplitude: FloatProperty(name="Amplitude", default=0.5)
    base: FloatProperty(name="Offset Value", default=0.5)
    mono: BoolProperty(name="Monochrome", default=True)

    def ln_draw(self, context, layout):
        layout.prop(self, "kind", text="")
        col = layout.column(align=True)
        col.prop(self, "scale")
        if self.kind == 'FRACTAL':
            col.prop(self, "octaves")
            col.prop(self, "roughness")
        col.prop(self, "speed")
        layout.prop(self, "mono")

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "offset")
        layout.prop(self, "amplitude")
        layout.prop(self, "base")
        super().ln_draw_ext(context, layout)

    def cook(self, ctx, inp):
        p = ctx.p
        st = ctx.state
        z = st["z"] = st.get("z", 0.0) + p.speed * ctx.dt
        kind = {'SMOOTH': 0, 'FRACTAL': 1, 'CELL': 2, 'RANDOM': 3}[self.kind]
        return self.run(ctx, NOISE_FRAG, {
            "uOffset": p.offset, "uScale": p.scale, "uZ": z, "uRough": p.roughness, "uAmp": p.amplitude,
            "uBase": p.base, "uOct": p.octaves, "uType": kind, "uMono": p.mono}, decl=NOISE_DECL)


RAMP_FRAG = """
void main(){
  vec2 q = vUV - 0.5;
  float t;
  if (uType == 0) t = dot(q, vec2(cos(uAngle), sin(uAngle))) + 0.5;
  else if (uType == 1){ q.x *= uRes.x / uRes.y; t = length(q) * 2.0; }
  else t = atan(q.y, q.x) / 6.2831853 + 0.5 + uAngle / 6.2831853;
  t = t * uCycles + uPhase;
  if (uRepeat == 1) t = fract(t);
  else if (uRepeat == 2) t = 1.0 - abs(mod(t, 2.0) - 1.0);
  t = clamp(t, 0.0, 1.0);
  vec4 c = mix(uA, uB, t);
  fragColor = vec4(c.rgb * c.a, c.a);
}
"""
RAMP_DECL = (('VEC4', 'uA'), ('VEC4', 'uB'), ('FLOAT', 'uAngle'), ('FLOAT', 'uCycles'), ('FLOAT', 'uPhase'),
             ('INT', 'uType'), ('INT', 'uRepeat'))


class LN_RampTOP(_Gen, bpy.types.Node):
    """Linear, radial or angular gradient between two colours"""
    bl_idname = "LN_RampTOP"
    bl_label = "Ramp TOP"

    kind: EnumProperty(name="Type", items=[('LINEAR', "Linear", ""), ('RADIAL', "Radial", ""), ('ANGULAR', "Angular", "")], default='LINEAR')
    color_a: _color("Start", (0.0, 0.0, 0.0, 1.0))
    color_b: _color("End", (1.0, 1.0, 1.0, 1.0))
    angle: FloatProperty(name="Angle", default=0.0, subtype='ANGLE')
    cycles: FloatProperty(name="Cycles", default=1.0)
    phase: FloatProperty(name="Phase", default=0.0)
    repeat: EnumProperty(name="Repeat", items=[('CLAMP', "Clamp", ""), ('REPEAT', "Repeat", ""), ('MIRROR', "Mirror", "")], default='CLAMP')

    def ln_draw(self, context, layout):
        layout.prop(self, "kind", text="")
        row = layout.row(align=True)
        row.prop(self, "color_a", text="")
        row.prop(self, "color_b", text="")
        col = layout.column(align=True)
        col.prop(self, "angle")
        col.prop(self, "cycles")
        col.prop(self, "phase")
        layout.prop(self, "repeat", text="")

    def cook(self, ctx, inp):
        p = ctx.p
        return self.run(ctx, RAMP_FRAG, {
            "uA": p.color_a, "uB": p.color_b, "uAngle": p.angle, "uCycles": p.cycles, "uPhase": p.phase,
            "uType": {'LINEAR': 0, 'RADIAL': 1, 'ANGULAR': 2}[self.kind],
            "uRepeat": {'CLAMP': 0, 'REPEAT': 1, 'MIRROR': 2}[self.repeat]}, decl=RAMP_DECL)


SHAPE_FRAG = """
void main(){
  vec2 q = (vUV - 0.5 - uCenter) * vec2(uRes.x / uRes.y, 1.0);
  float cs = cos(uRot); float sn = sin(uRot);
  q = vec2(cs * q.x + sn * q.y, -sn * q.x + cs * q.y) / max(uSize, vec2(1.0e-5));
  float d;
  if (uType == 0) d = length(q) - uRadius;
  else if (uType == 1){ vec2 b = abs(q) - vec2(uRadius); d = length(max(b, vec2(0.0))) + min(max(b.x, b.y), 0.0); }
  else {
    float a = atan(q.x, q.y); float seg = 6.2831853 / float(max(uSides, 3));
    d = cos(floor(0.5 + a / seg) * seg - a) * length(q) - uRadius;
  }
  if (uBorder > 0.0) d = abs(d) - uBorder * 0.5;
  float s = max(uSoft, 1.0 / uRes.y);
  float m = 1.0 - smoothstep(-s, s, d);
  vec4 f = vec4(uFill.rgb * uFill.a, uFill.a); vec4 b = vec4(uBg.rgb * uBg.a, uBg.a);
  fragColor = mix(b, f, m);
}
"""
SHAPE_DECL = (('VEC4', 'uFill'), ('VEC4', 'uBg'), ('VEC2', 'uCenter'), ('VEC2', 'uSize'), ('FLOAT', 'uRadius'),
              ('FLOAT', 'uSoft'), ('FLOAT', 'uRot'), ('FLOAT', 'uBorder'), ('INT', 'uSides'), ('INT', 'uType'))


class LN_ShapeTOP(_Gen, bpy.types.Node):
    """Circle, rectangle or polygon with soft edges or an outline"""
    bl_idname = "LN_ShapeTOP"
    bl_label = "Shape TOP"

    kind: EnumProperty(name="Shape", items=[('CIRCLE', "Circle", ""), ('RECT', "Rectangle", ""), ('POLYGON', "Polygon", "")], default='CIRCLE')
    radius: FloatProperty(name="Radius", default=0.25, min=0.0)
    size: FloatVectorProperty(name="Size", size=2, default=(1.0, 1.0))
    center: FloatVectorProperty(name="Center", size=2, default=(0.0, 0.0))
    rotation: FloatProperty(name="Rotation", default=0.0, subtype='ANGLE')
    sides: IntProperty(name="Sides", default=6, min=3, max=64)
    softness: FloatProperty(name="Softness", default=0.0, min=0.0, soft_max=0.5)
    border: FloatProperty(name="Outline", default=0.0, min=0.0, description="Outline width (0 = filled)")
    fill: _color("Fill", (1.0, 1.0, 1.0, 1.0))
    background: _color("Background", (0.0, 0.0, 0.0, 0.0))

    def ln_draw(self, context, layout):
        layout.prop(self, "kind", text="")
        col = layout.column(align=True)
        col.prop(self, "radius")
        if self.kind == 'POLYGON':
            col.prop(self, "sides")
        col.prop(self, "rotation")
        col.prop(self, "softness")
        col.prop(self, "border")
        row = layout.row(align=True)
        row.prop(self, "fill", text="")
        row.prop(self, "background", text="")

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "center")
        layout.prop(self, "size")
        super().ln_draw_ext(context, layout)

    def cook(self, ctx, inp):
        p = ctx.p
        return self.run(ctx, SHAPE_FRAG, {
            "uFill": p.fill, "uBg": p.background, "uCenter": p.center, "uSize": p.size, "uRadius": p.radius,
            "uSoft": p.softness, "uRot": p.rotation, "uBorder": p.border, "uSides": p.sides,
            "uType": {'CIRCLE': 0, 'RECT': 1, 'POLYGON': 2}[self.kind]}, decl=SHAPE_DECL)


class LN_TextTOP(_Gen, bpy.types.Node):
    """Renders text; connect a DAT to show live data"""
    bl_idname = "LN_TextTOP"
    bl_label = "Text TOP"

    text: StringProperty(name="Text", default="LIVE")
    size: FloatProperty(name="Size", default=0.2, min=0.001, description="Line height as a fraction of the image height")
    position: FloatVectorProperty(name="Position", size=2, default=(0.5, 0.5), description="Anchor in the image (0..1)")
    align: EnumProperty(name="Align", items=[('LEFT', "Left", ""), ('CENTER', "Center", ""), ('RIGHT', "Right", "")], default='CENTER')
    font_color: _color("Color", (1.0, 1.0, 1.0, 1.0))
    background: _color("Background", (0.0, 0.0, 0.0, 0.0))
    font: EnumProperty(name="Font", items=[('DEFAULT', "Interface", "Blender's interface font"),
                                           ('MONO', "Monospace", "Blender's bundled DejaVu Sans Mono"),
                                           ('FILE', "File", "A .ttf / .otf / .woff2 font file")], default='DEFAULT')
    font_file: StringProperty(name="Font File", subtype='FILE_PATH')
    tracking: FloatProperty(name="Letter Spacing", default=0.0, soft_min=-0.2, soft_max=1.0,
                            description="Extra space between letters, as a fraction of the size")

    def ln_init(self):
        self.add_in('DAT', "Text")
        self.add_out('TOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "text", text="")
        layout.prop(self, "size")
        layout.prop(self, "align", text="")
        row = layout.row(align=True)
        row.prop(self, "font_color", text="")
        row.prop(self, "background", text="")

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "position")
        layout.prop(self, "font")
        if self.font == 'FILE':
            layout.prop(self, "font_file", text="")
        layout.prop(self, "tracking")
        super().ln_draw_ext(context, layout)

    def font_id(self):
        import blf
        if self.font == 'DEFAULT':
            return 0
        if self.font == 'MONO':
            path = os.path.join(bpy.utils.system_resource('DATAFILES', path="fonts"), "DejaVuSansMono.woff2")
        else:
            path = bpy.path.abspath(self.font_file)
        fid = _FONTS.get(path)
        if fid is None:
            fid = _FONTS[path] = blf.load(path) if path else -1
        if fid < 0:
            raise ValueError(f"cannot load font {path!r}")
        return fid

    def cook(self, ctx, inp):
        import blf
        import gpu
        from mathutils import Matrix
        p = ctx.p
        dat = inp.get("Text")
        text = dat if isinstance(dat, str) else self.text
        if isinstance(dat, (list, tuple)):
            text = "\n".join("  ".join(str(c) for c in row) for row in dat)
        w, h = self.out_size(ctx)
        tgt = self.target(ctx, (w, h))
        # text rarely changes: redraw only when what we would draw changes
        key = (text, w, h, ctx.tex_format, p.size, tuple(p.position), self.align, tuple(p.font_color),
               tuple(p.background), self.font, self.font_file, p.tracking)
        st = ctx.state
        if st.get("drawn") == key and st.get("drawn_target") is tgt.off:
            return tgt.texture
        st["drawn"], st["drawn_target"] = key, tgt.off
        px = max(p.size * h, 1.0)
        lines = text.split("\n")
        bg = p.background
        with tgt.off.bind():
            fb = gpu.state.active_framebuffer_get()
            fb.clear(color=(bg[0] * bg[3], bg[1] * bg[3], bg[2] * bg[3], bg[3]))
            with gpu.matrix.push_pop(), gpu.matrix.push_pop_projection():
                gpu.matrix.load_identity()
                gpu.matrix.load_projection_matrix(Matrix(((2 / w, 0, 0, -1), (0, 2 / h, 0, -1), (0, 0, -1, 0), (0, 0, 0, 1))))
                gpu.state.blend_set('ALPHA_PREMULT')
                font = self.font_id()
                blf.size(font, px)
                blf.color(font, *p.font_color)
                track = p.tracking * px
                y = p.position[1] * h + (len(lines) - 1) * px * 0.6 - px * 0.35
                for line in lines:
                    if track:
                        widths = [blf.dimensions(font, ch)[0] for ch in line]
                        tw = sum(widths) + track * max(len(line) - 1, 0)
                    else:
                        tw = blf.dimensions(font, line)[0]
                    x = p.position[0] * w - {'LEFT': 0.0, 'CENTER': tw * 0.5, 'RIGHT': tw}[self.align]
                    if track:
                        for ch, cw in zip(line, widths):
                            blf.position(font, x, y, 0)
                            blf.draw(font, ch)
                            x += cw + track
                    else:
                        blf.position(font, x, y, 0)
                        blf.draw(font, line)
                    y -= px * 1.2
                gpu.state.blend_set('NONE')
        return tgt.texture


_FONTS = {}


class LN_OT_new_shader(bpy.types.Operator):
    """Create a text block with a starter shader and assign it to this node"""
    bl_idname = "livenodes.new_shader"
    bl_label = "New Shader"
    bl_options = {'INTERNAL', 'UNDO'}

    tree: StringProperty()
    node: StringProperty()

    TEMPLATE = """// Live Nodes GLSL TOP
// Available: vUV (0..1), uTime, uRes, uMouse, uP0..uP3 (vec4, from the Uniforms input),
// uIn0..uIn3 (input textures), and helpers ln_noise(vec3), ln_fbm(vec3, octaves, roughness),
// ln_hsv2rgb(vec3), ln_luma(vec3).
// Shadertoy code works too: define  void mainImage(out vec4 fragColor, in vec2 fragCoord).
void main(){
  vec2 p = (vUV - 0.5) * vec2(uRes.x / uRes.y, 1.0);
  float d = length(p) + ln_noise(vec3(p * 3.0, uTime * 0.4)) * 0.15;
  float rings = 0.5 + 0.5 * sin(d * 40.0 - uTime * 3.0);
  vec3 col = ln_hsv2rgb(vec3(d + uTime * 0.05, 0.7, rings));
  fragColor = vec4(col, 1.0);
}
"""

    def execute(self, context):
        tree = bpy.data.node_groups.get(self.tree)
        node = tree.nodes.get(self.node) if tree else None
        if node is None:
            return {'CANCELLED'}
        text = bpy.data.texts.new("live_shader.glsl")
        text.write(self.TEMPLATE)
        node.source = text
        return {'FINISHED'}


GLSL_DECL = (('VEC4', 'uP0'), ('VEC4', 'uP1'), ('VEC4', 'uP2'), ('VEC4', 'uP3'), ('VEC4', 'uMouse'))
SHADERTOY_PRE = """
#define iTime uTime
#define iResolution vec3(uRes, 1.0)
#define iMouse vec4(uMouse.xy * uRes, uMouse.zw)
#define iChannel0 uIn0
#define iChannel1 uIn1
#define iChannel2 uIn2
#define iChannel3 uIn3
"""
SHADERTOY_POST = "\nvoid main(){ vec4 c = vec4(0.0, 0.0, 0.0, 1.0); mainImage(c, vUV * uRes); fragColor = c; }\n"


class LN_GlslTOP(LNTopNode, bpy.types.Node):
    """Your own fragment shader, with textures and channels as inputs"""
    bl_idname = "LN_GlslTOP"
    bl_label = "GLSL TOP"
    ln_category = "TOP Generate"
    ln_params = False

    source: PointerProperty(name="Shader", type=bpy.types.Text)

    def ln_init(self):
        for i in range(4):
            self.add_in('TOP', f"In {i}")
        self.add_in('CHOP', "Uniforms")
        self.add_out('TOP')

    def ln_draw(self, context, layout):
        row = layout.row(align=True)
        row.prop(self, "source", text="")
        if self.source is None:
            op = row.operator("livenodes.new_shader", text="", icon='ADD')
            op.tree = self.id_data.name
            op.node = self.name

    def ln_draw_ext(self, context, layout):
        layout.label(text="Uniforms input fills uP0..uP3,")
        layout.label(text="four channels per vec4, in order.")
        super().ln_draw_ext(context, layout)

    def cook(self, ctx, inp):
        if self.source is None:
            raise ValueError("no shader text assigned")
        src = self.source.as_string()
        if "mainImage" in src:
            src = SHADERTOY_PRE + src + SHADERTOY_POST
        textures = [inp.get(f"In {i}") for i in range(4)]
        vals = np.zeros(16, dtype=np.float32)
        uni = inp.chop("Uniforms")
        if uni:
            flat = uni.data[:, 0][:16]
            vals[:len(flat)] = flat
        m = ctx.engine.mouse
        uniforms = {f"uP{i}": vals[i * 4:i * 4 + 4] for i in range(4)}
        uniforms["uMouse"] = (m["x"], m["y"], m["left"], m["right"])
        size = self.out_size(ctx, next((t for t in textures if t is not None), None))
        return self.run(ctx, src, uniforms, textures, size=size, decl=GLSL_DECL)


class LN_ChopToTOP(LNTopNode, bpy.types.Node):
    """Turns channels into a texture: one row per channel, one pixel per sample"""
    bl_idname = "LN_ChopToTOP"
    bl_label = "CHOP to TOP"
    ln_category = "TOP Generate"
    ln_params = False

    def ln_init(self):
        self.add_in('CHOP', "In")
        self.add_out('TOP')

    def ln_draw_ext(self, context, layout):
        pass

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return gpu_util.black()
        d = src.data
        img = np.empty((d.shape[0], d.shape[1], 4), dtype=np.float32)
        img[..., 0] = img[..., 1] = img[..., 2] = d
        img[..., 3] = 1.0
        tex = ctx.state["tex"] = gpu_util.texture_from_array(img, 'RGBA32F')
        return tex


class LN_FeedbackTOP(LNTopNode, bpy.types.Node):
    """Outputs what another TOP rendered on the previous frame: trails, echoes, reaction loops"""
    bl_idname = "LN_FeedbackTOP"
    bl_label = "Feedback TOP"
    ln_category = "TOP Generate"
    ln_params = False

    target_node: StringProperty(name="Target", description="TOP whose previous frame is returned (place it downstream of this node)")
    reset: BoolProperty(name="Reset", default=False, description="Hold to restart the loop from the Initial input")

    def ln_init(self):
        self.add_in('TOP', "Initial")
        self.add_out('TOP')

    def ln_draw(self, context, layout):
        layout.prop_search(self, "target_node", self.id_data, "nodes", text="")
        layout.prop(self, "reset", toggle=True)

    def cook(self, ctx, inp):
        prev = ctx.output_of(self.target_node) if self.target_node and not self.reset else None
        if prev is None or not hasattr(prev, "width"):
            prev = inp.get("Initial")
        if prev is None:
            prev = gpu_util.black()
            return self.run(ctx, PASS_FRAG, {}, [prev], size=self.out_size(ctx))
        # copy: the target will overwrite its own buffer later this frame
        return self.run(ctx, PASS_FRAG, {}, [prev])


classes = (LN_OT_new_shader, LN_ConstantTOP, LN_NoiseTOP, LN_RampTOP, LN_ShapeTOP, LN_TextTOP, LN_GlslTOP,
           LN_ChopToTOP, LN_FeedbackTOP)
