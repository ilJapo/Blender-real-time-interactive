"""TOP filters and compositing."""
import math

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty

from ..core.tree import LNTopNode
from .top_gen import PASS_FRAG, _color

EXTEND = [('HOLD', "Hold", "Repeat the edge pixels"), ('REPEAT', "Repeat", "Tile"),
          ('MIRROR', "Mirror", "Tile, flipping every other copy"), ('ZERO', "Zero", "Transparent outside")]
EXTEND_ID = {'HOLD': 0, 'REPEAT': 1, 'MIRROR': 2, 'ZERO': 3}


class _Filter(LNTopNode):
    ln_category = "TOP Filter"

    def ln_init(self):
        self.add_in('TOP', "In")
        self.add_out('TOP')


LEVEL_FRAG = """
void main(){
  vec4 c = texture(uIn0, vUV);
  vec3 rgb = c.a > 1.0e-5 ? c.rgb / c.a : c.rgb;
  rgb = (rgb - uBlack) / max(uWhite - uBlack, 1.0e-5);
  rgb = mix(rgb, 1.0 - rgb, uInvert);
  rgb = (rgb * uBright - 0.5) * uContrast + 0.5;
  rgb = pow(max(rgb, vec3(0.0)), vec3(1.0 / max(uGamma, 1.0e-3)));
  if (uHue != 0.0 || uSat != 1.0){
    vec3 hsv = ln_rgb2hsv(rgb);
    hsv.x = fract(hsv.x + uHue); hsv.y *= uSat;
    rgb = ln_hsv2rgb(hsv);
  }
  if (uClamp == 1) rgb = clamp(rgb, 0.0, 1.0);
  float a = c.a * uOpacity;
  fragColor = vec4(rgb * a, a);
}
"""
LEVEL_DECL = (('FLOAT', 'uBlack'), ('FLOAT', 'uWhite'), ('FLOAT', 'uInvert'), ('FLOAT', 'uBright'), ('FLOAT', 'uContrast'),
              ('FLOAT', 'uGamma'), ('FLOAT', 'uHue'), ('FLOAT', 'uSat'), ('FLOAT', 'uOpacity'), ('INT', 'uClamp'))


class LN_LevelTOP(_Filter, bpy.types.Node):
    """Brightness, contrast, gamma, hue, saturation, invert and opacity"""
    bl_idname = "LN_LevelTOP"
    bl_label = "Level TOP"

    brightness: FloatProperty(name="Brightness", default=1.0, min=0.0)
    contrast: FloatProperty(name="Contrast", default=1.0, min=0.0)
    gamma: FloatProperty(name="Gamma", default=1.0, min=0.01)
    hue: FloatProperty(name="Hue Shift", default=0.0, description="In turns: 1.0 is a full rotation")
    saturation: FloatProperty(name="Saturation", default=1.0, min=0.0)
    opacity: FloatProperty(name="Opacity", default=1.0, min=0.0, max=1.0)
    invert: FloatProperty(name="Invert", default=0.0, min=0.0, max=1.0)
    black: FloatProperty(name="Black Level", default=0.0)
    white: FloatProperty(name="White Level", default=1.0)
    clamp: BoolProperty(name="Clamp", default=False, description="Clamp colours to 0..1")

    def ln_draw(self, context, layout):
        col = layout.column(align=True)
        for name in ("brightness", "contrast", "gamma", "hue", "saturation", "opacity"):
            col.prop(self, name)

    def ln_draw_ext(self, context, layout):
        col = layout.column(align=True)
        col.prop(self, "invert")
        col.prop(self, "black")
        col.prop(self, "white")
        col.prop(self, "clamp")
        super().ln_draw_ext(context, layout)

    def cook(self, ctx, inp):
        src = inp.get("In")
        if src is None:
            return None
        p = ctx.p
        return self.run(ctx, LEVEL_FRAG, {
            "uBlack": p.black, "uWhite": p.white, "uInvert": p.invert, "uBright": p.brightness,
            "uContrast": p.contrast, "uGamma": p.gamma, "uHue": p.hue, "uSat": p.saturation,
            "uOpacity": p.opacity, "uClamp": p.clamp}, [src], decl=LEVEL_DECL)


BLUR_FRAG = """
void main(){
  float r = max(uRadius, 0.0);
  if (r < 0.01){ fragColor = texture(uIn0, vUV); return; }
  float n = min(ceil(r), 24.0);
  float stp = r / n;
  float sigma = r * 0.5;
  vec4 acc = vec4(0.0); float wsum = 0.0;
  for (int i = -24; i <= 24; i++){
    float fi = float(i);
    if (abs(fi) > n) continue;
    float x = fi * stp;
    float w = exp(-0.5 * x * x / (sigma * sigma));
    acc += texture(uIn0, vUV + uDir * x / uRes) * w; wsum += w;
  }
  fragColor = acc / wsum;
}
"""
BLUR_DECL = (('VEC2', 'uDir'), ('FLOAT', 'uRadius'))


def blur(node, ctx, src, radius, size, slots=(0, 1), aspect=(1.0, 1.0)):
    tmp = node.run(ctx, BLUR_FRAG, {"uDir": (aspect[0], 0.0), "uRadius": radius}, [src], size=size, slot=slots[0], decl=BLUR_DECL)
    return node.run(ctx, BLUR_FRAG, {"uDir": (0.0, aspect[1]), "uRadius": radius}, [tmp], size=size, slot=slots[1], decl=BLUR_DECL)


class LN_BlurTOP(_Filter, bpy.types.Node):
    """Gaussian blur"""
    bl_idname = "LN_BlurTOP"
    bl_label = "Blur TOP"

    radius: FloatProperty(name="Radius", default=8.0, min=0.0, description="In pixels")
    horizontal: FloatProperty(name="Horizontal", default=1.0, min=0.0)
    vertical: FloatProperty(name="Vertical", default=1.0, min=0.0)

    def ln_draw(self, context, layout):
        layout.prop(self, "radius")

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "horizontal")
        layout.prop(self, "vertical")
        super().ln_draw_ext(context, layout)

    def cook(self, ctx, inp):
        src = inp.get("In")
        if src is None:
            return None
        p = ctx.p
        return blur(self, ctx, src, p.radius, self.out_size(ctx, src), aspect=(p.horizontal, p.vertical))


TRANSFORM_FRAG = """
void main(){
  vec2 asp = vec2(uRes.x / uRes.y, 1.0);
  vec2 q = (vUV - uPivot - uT) * asp;
  float cs = cos(uRot); float sn = sin(uRot);
  q = vec2(cs * q.x + sn * q.y, -sn * q.x + cs * q.y) / asp;
  q = q / uS + uPivot;
  vec4 c = texture(uIn0, ln_wrap(q, uExtend));
  if (uExtend == 3) c = mix(vec4(uBg.rgb * uBg.a, uBg.a), c, ln_inside(q));
  fragColor = c;
}
"""
TRANSFORM_DECL = (('VEC4', 'uBg'), ('VEC2', 'uT'), ('VEC2', 'uS'), ('VEC2', 'uPivot'), ('FLOAT', 'uRot'), ('INT', 'uExtend'))


class LN_TransformTOP(_Filter, bpy.types.Node):
    """Move, rotate, scale and tile an image"""
    bl_idname = "LN_TransformTOP"
    bl_label = "Transform TOP"

    translate: FloatVectorProperty(name="Translate", size=2, default=(0.0, 0.0))
    rotate: FloatProperty(name="Rotate", default=0.0, subtype='ANGLE')
    scale: FloatVectorProperty(name="Scale", size=2, default=(1.0, 1.0))
    uniform_scale: FloatProperty(name="Uniform Scale", default=1.0)
    pivot: FloatVectorProperty(name="Pivot", size=2, default=(0.5, 0.5))
    extend: EnumProperty(name="Extend", items=EXTEND, default='ZERO')
    background: _color("Background", (0.0, 0.0, 0.0, 0.0))

    def ln_draw(self, context, layout):
        layout.prop(self, "translate")
        layout.prop(self, "rotate")
        layout.prop(self, "uniform_scale")
        layout.prop(self, "extend", text="")

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "scale")
        layout.prop(self, "pivot")
        layout.prop(self, "background")
        super().ln_draw_ext(context, layout)

    def cook(self, ctx, inp):
        src = inp.get("In")
        if src is None:
            return None
        p = ctx.p
        u = p.uniform_scale
        s = [v * u if abs(v * u) > 1e-6 else 1e-6 for v in p.scale]
        return self.run(ctx, TRANSFORM_FRAG, {
            "uBg": p.background, "uT": p.translate, "uS": s, "uPivot": p.pivot, "uRot": p.rotate,
            "uExtend": EXTEND_ID[self.extend]}, [src], decl=TRANSFORM_DECL)


BLEND_OPS = [('OVER', "Over", "Layer on top, using its alpha"), ('ADD', "Add", ""), ('SUBTRACT', "Subtract", ""),
             ('MULTIPLY', "Multiply", ""), ('SCREEN', "Screen", ""), ('DIFFERENCE', "Difference", ""),
             ('LIGHTEN', "Lighten", "Maximum"), ('DARKEN', "Darken", "Minimum"),
             ('INSIDE', "Inside", "Keep the base where the layer is opaque"),
             ('OUTSIDE', "Outside", "Keep the base where the layer is transparent"),
             ('UNDER', "Under", "Layer behind the base"), ('AVERAGE', "Average", "")]
BLEND_ID = {op[0]: i for i, op in enumerate(BLEND_OPS)}
COMPOSITE_FRAG = """
void main(){
  vec4 a = texture(uIn0, vUV);
  vec4 b = texture(uIn1, vUV) * uOpacity;
  float un = a.a + b.a - a.a * b.a;
  vec4 r;
  if (uOp == 0) r = b + a * (1.0 - b.a);
  else if (uOp == 1) r = vec4(a.rgb + b.rgb, min(a.a + b.a, 1.0));
  else if (uOp == 2) r = vec4(max(a.rgb - b.rgb, vec3(0.0)), a.a);
  else if (uOp == 3) r = vec4(a.rgb * b.rgb + a.rgb * (1.0 - b.a) + b.rgb * (1.0 - a.a), un);
  else if (uOp == 4) r = vec4(a.rgb + b.rgb - a.rgb * b.rgb, un);
  else if (uOp == 5) r = vec4(abs(a.rgb - b.rgb), un);
  else if (uOp == 6) r = vec4(max(a.rgb, b.rgb), max(a.a, b.a));
  else if (uOp == 7) r = vec4(min(a.rgb, b.rgb), un);
  else if (uOp == 8) r = a * b.a;
  else if (uOp == 9) r = a * (1.0 - b.a);
  else if (uOp == 10) r = a + b * (1.0 - a.a);
  else r = (a + b) * 0.5;
  fragColor = r;
}
"""
COMPOSITE_DECL = (('FLOAT', 'uOpacity'), ('INT', 'uOp'))


class LN_CompositeTOP(LNTopNode, bpy.types.Node):
    """Blends layers onto a base image"""
    bl_idname = "LN_CompositeTOP"
    bl_label = "Composite TOP"
    ln_category = "TOP Composite"

    operation: EnumProperty(name="Operation", items=BLEND_OPS, default='OVER')
    opacity: FloatProperty(name="Layer Opacity", default=1.0, min=0.0, max=1.0)

    def ln_init(self):
        self.add_in('TOP', "Base")
        self.add_in('TOP', "Layers", multi=True)
        self.add_out('TOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "operation", text="")
        layout.prop(self, "opacity")

    def cook(self, ctx, inp):
        base = inp.get("Base")
        layers = list(inp.all("Layers"))
        if base is None:
            if not layers:
                return None
            base = layers.pop(0)
        size = self.out_size(ctx, base)
        uni = {"uOpacity": ctx.p.opacity, "uOp": BLEND_ID[self.operation]}
        if not layers:
            return self.run(ctx, PASS_FRAG, {}, [base], size=size)
        acc = base
        for i, layer in enumerate(layers):  # ping-pong between two buffers
            acc = self.run(ctx, COMPOSITE_FRAG, uni, [acc, layer], size=size, slot=i % 2, decl=COMPOSITE_DECL)
        return acc


class LN_CrossTOP(LNTopNode, bpy.types.Node):
    """Crossfades between two images"""
    bl_idname = "LN_CrossTOP"
    bl_label = "Cross TOP"
    ln_category = "TOP Composite"

    factor: FloatProperty(name="Cross", default=0.5, min=0.0, max=1.0)

    def ln_init(self):
        self.add_in('TOP', "A")
        self.add_in('TOP', "B")
        self.add_out('TOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "factor", slider=True)

    def cook(self, ctx, inp):
        a, b = inp.get("A"), inp.get("B")
        if a is None and b is None:
            return None
        return self.run(ctx, "void main(){ fragColor = mix(texture(uIn0, vUV), texture(uIn1, vUV), uMix); }",
                        {"uMix": ctx.p.factor}, [a, b], size=self.out_size(ctx, a or b), decl=(('FLOAT', 'uMix'),))


class LN_SwitchTOP(LNTopNode, bpy.types.Node):
    """Picks one of several images by index, optionally blending neighbours"""
    bl_idname = "LN_SwitchTOP"
    bl_label = "Switch TOP"
    ln_category = "TOP Composite"

    index: FloatProperty(name="Index", default=0.0, min=0.0)
    blend: BoolProperty(name="Blend", default=False)

    def ln_init(self):
        self.add_in('TOP', "In", multi=True)
        self.add_out('TOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "index")
        layout.prop(self, "blend")

    def cook(self, ctx, inp):
        ins = inp.all("In")
        if not ins:
            return None
        idx = min(max(ctx.p.index, 0.0), len(ins) - 1)
        lo = int(math.floor(idx))
        if not ctx.p.blend or lo >= len(ins) - 1:
            return ins[int(round(idx)) if not ctx.p.blend else lo]
        return self.run(ctx, "void main(){ fragColor = mix(texture(uIn0, vUV), texture(uIn1, vUV), uMix); }",
                        {"uMix": idx - lo}, [ins[lo], ins[lo + 1]], decl=(('FLOAT', 'uMix'),))


class LN_DisplaceTOP(LNTopNode, bpy.types.Node):
    """Warps an image using the red and green of a second one"""
    bl_idname = "LN_DisplaceTOP"
    bl_label = "Displace TOP"
    ln_category = "TOP Filter"

    weight: FloatVectorProperty(name="Weight", size=2, default=(0.1, 0.1))
    midpoint: FloatProperty(name="Midpoint", default=0.5, description="Map value that means 'no displacement'")
    extend: EnumProperty(name="Extend", items=EXTEND, default='HOLD')

    def ln_init(self):
        self.add_in('TOP', "In")
        self.add_in('TOP', "Map")
        self.add_out('TOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "weight")
        layout.prop(self, "midpoint")
        layout.prop(self, "extend", text="")

    def cook(self, ctx, inp):
        src = inp.get("In")
        if src is None:
            return None
        p = ctx.p
        frag = ("void main(){ vec2 d = (texture(uIn1, vUV).rg - uMid) * uWeight; vec2 q = vUV + d;"
                " vec4 c = texture(uIn0, ln_wrap(q, uExtend)); if (uExtend == 3) c *= ln_inside(q); fragColor = c; }")
        if inp.get("Map") is None:
            return src
        return self.run(ctx, frag, {"uWeight": p.weight, "uMid": p.midpoint, "uExtend": EXTEND_ID[self.extend]},
                        [src, inp.get("Map")], decl=(('VEC2', 'uWeight'), ('FLOAT', 'uMid'), ('INT', 'uExtend')))


EDGE_FRAG = """
float lum(vec2 o){ return ln_luma(texture(uIn0, vUV + o / uRes).rgb); }
void main(){
  float w = max(uWidth, 0.25);
  float tl = lum(vec2(-w, w)); float t = lum(vec2(0.0, w)); float tr = lum(vec2(w, w));
  float l = lum(vec2(-w, 0.0)); float r = lum(vec2(w, 0.0));
  float bl = lum(vec2(-w, -w)); float b = lum(vec2(0.0, -w)); float br = lum(vec2(w, -w));
  float gx = (tr + 2.0 * r + br) - (tl + 2.0 * l + bl);
  float gy = (tl + 2.0 * t + tr) - (bl + 2.0 * b + br);
  float e = clamp(length(vec2(gx, gy)) * uStrength, 0.0, 1.0);
  vec4 src = texture(uIn0, vUV);
  vec4 edge = vec4(uColor.rgb * uColor.a, uColor.a) * e;
  fragColor = (uOver == 1) ? edge + src * (1.0 - edge.a) : edge;
}
"""


class LN_EdgeTOP(_Filter, bpy.types.Node):
    """Finds outlines"""
    bl_idname = "LN_EdgeTOP"
    bl_label = "Edge TOP"

    strength: FloatProperty(name="Strength", default=2.0, min=0.0)
    distance: FloatProperty(name="Width", default=1.0, min=0.25, description="Sample distance in pixels")
    edge_color: _color("Edge Color", (1.0, 1.0, 1.0, 1.0))
    over: BoolProperty(name="Over Source", default=False, description="Draw the edges on top of the input")

    def ln_draw(self, context, layout):
        layout.prop(self, "strength")
        layout.prop(self, "distance")
        layout.prop(self, "edge_color", text="")
        layout.prop(self, "over")

    def cook(self, ctx, inp):
        src = inp.get("In")
        if src is None:
            return None
        p = ctx.p
        return self.run(ctx, EDGE_FRAG, {"uColor": p.edge_color, "uStrength": p.strength, "uWidth": p.distance, "uOver": p.over},
                        [src], decl=(('VEC4', 'uColor'), ('FLOAT', 'uStrength'), ('FLOAT', 'uWidth'), ('INT', 'uOver')))


KEY_FRAG = """
void main(){
  vec4 c = texture(uIn0, vUV);
  vec3 rgb = c.a > 1.0e-5 ? c.rgb / c.a : c.rgb;
  float m;
  if (uMode == 0) m = smoothstep(uThresh - uSoft, uThresh + uSoft + 1.0e-5, ln_luma(rgb));
  else m = smoothstep(uThresh, uThresh + uSoft + 1.0e-5, distance(rgb, uKey.rgb));
  if (uInvert == 1) m = 1.0 - m;
  fragColor = (uMatte == 1) ? vec4(vec3(m), 1.0) : c * m;
}
"""


class LN_KeyTOP(_Filter, bpy.types.Node):
    """Threshold by brightness (luma key) or remove a colour (chroma key)"""
    bl_idname = "LN_KeyTOP"
    bl_label = "Key TOP"

    mode: EnumProperty(name="Mode", items=[('LUMA', "Luma", "Keep pixels brighter than the threshold"),
                                           ('CHROMA', "Chroma", "Remove pixels close to the key colour")], default='LUMA')
    key: _color("Key Color", (0.0, 1.0, 0.0, 1.0))
    threshold: FloatProperty(name="Threshold", default=0.5, min=0.0)
    softness: FloatProperty(name="Softness", default=0.05, min=0.0)
    invert: BoolProperty(name="Invert", default=False)
    matte: BoolProperty(name="Output Matte", default=False, description="Output the black and white mask")

    def ln_draw(self, context, layout):
        layout.prop(self, "mode", text="")
        if self.mode == 'CHROMA':
            layout.prop(self, "key", text="")
        layout.prop(self, "threshold")
        layout.prop(self, "softness")
        row = layout.row(align=True)
        row.prop(self, "invert", toggle=True)
        row.prop(self, "matte", toggle=True)

    def cook(self, ctx, inp):
        src = inp.get("In")
        if src is None:
            return None
        p = ctx.p
        return self.run(ctx, KEY_FRAG, {"uKey": p.key, "uThresh": p.threshold, "uSoft": p.softness,
                                        "uMode": 0 if self.mode == 'LUMA' else 1, "uInvert": p.invert, "uMatte": p.matte},
                        [src], decl=(('VEC4', 'uKey'), ('FLOAT', 'uThresh'), ('FLOAT', 'uSoft'), ('INT', 'uMode'),
                                     ('INT', 'uInvert'), ('INT', 'uMatte')))


MIRROR_FRAG = """
void main(){
  vec2 uv = vUV;
  if (uMode == 0){
    vec2 asp = vec2(uRes.x / uRes.y, 1.0);
    vec2 q = (uv - 0.5 - uCenter) * asp;
    float r = length(q);
    float seg = 6.2831853 / max(uSegments, 1.0);
    float a = mod(atan(q.y, q.x) + uRot, seg);
    a = abs(a - seg * 0.5) + uSpin;
    uv = r * vec2(cos(a), sin(a)) / asp + 0.5 + uCenter;
    uv = 1.0 - abs(mod(uv, 2.0) - 1.0);
  } else {
    if (uMode == 1 || uMode == 3) uv.x = 0.5 - abs(uv.x - 0.5);
    if (uMode == 2 || uMode == 3) uv.y = 0.5 - abs(uv.y - 0.5);
    if (uMode == 4) uv.x = 1.0 - uv.x;
    if (uMode == 5) uv.y = 1.0 - uv.y;
  }
  fragColor = texture(uIn0, uv);
}
"""


class LN_MirrorTOP(_Filter, bpy.types.Node):
    """Kaleidoscope, mirror and flip"""
    bl_idname = "LN_MirrorTOP"
    bl_label = "Mirror TOP"

    mode: EnumProperty(name="Mode", items=[('KALEIDO', "Kaleidoscope", ""), ('MIRROR_X', "Mirror X", ""), ('MIRROR_Y', "Mirror Y", ""),
                                           ('MIRROR_XY', "Mirror Both", ""), ('FLIP_X', "Flip X", ""), ('FLIP_Y', "Flip Y", "")],
                       default='KALEIDO')
    segments: FloatProperty(name="Segments", default=6.0, min=1.0, max=64.0)
    rotation: FloatProperty(name="Rotation", default=0.0, subtype='ANGLE')
    spin: FloatProperty(name="Source Spin", default=0.0, subtype='ANGLE', description="Rotates what is seen inside each segment")
    center: FloatVectorProperty(name="Center", size=2, default=(0.0, 0.0))

    def ln_draw(self, context, layout):
        layout.prop(self, "mode", text="")
        if self.mode == 'KALEIDO':
            col = layout.column(align=True)
            col.prop(self, "segments")
            col.prop(self, "rotation")
            col.prop(self, "spin")

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "center")
        super().ln_draw_ext(context, layout)

    def cook(self, ctx, inp):
        src = inp.get("In")
        if src is None:
            return None
        p = ctx.p
        modes = {'KALEIDO': 0, 'MIRROR_X': 1, 'MIRROR_Y': 2, 'MIRROR_XY': 3, 'FLIP_X': 4, 'FLIP_Y': 5}
        return self.run(ctx, MIRROR_FRAG, {"uCenter": p.center, "uSegments": p.segments, "uRot": p.rotation,
                                           "uSpin": p.spin, "uMode": modes[self.mode]}, [src],
                        decl=(('VEC2', 'uCenter'), ('FLOAT', 'uSegments'), ('FLOAT', 'uRot'), ('FLOAT', 'uSpin'), ('INT', 'uMode')))


class LN_PixelateTOP(_Filter, bpy.types.Node):
    """Mosaic blocks and colour posterising"""
    bl_idname = "LN_PixelateTOP"
    bl_label = "Pixelate TOP"

    block: FloatProperty(name="Block Size", default=16.0, min=1.0, description="In pixels")
    levels: IntProperty(name="Color Levels", default=0, min=0, max=256, description="Posterise to this many levels (0 = off)")

    def ln_draw(self, context, layout):
        layout.prop(self, "block")
        layout.prop(self, "levels")

    def cook(self, ctx, inp):
        src = inp.get("In")
        if src is None:
            return None
        p = ctx.p
        frag = ("void main(){ vec2 g = max(vec2(uBlock), vec2(1.0)) / uRes; vec4 c = texture(uIn0, (floor(vUV / g) + 0.5) * g);"
                " if (uLevels > 1.5) c.rgb = floor(c.rgb * uLevels) / (uLevels - 1.0); fragColor = c; }")
        return self.run(ctx, frag, {"uBlock": p.block, "uLevels": float(p.levels)}, [src],
                        decl=(('FLOAT', 'uBlock'), ('FLOAT', 'uLevels')))


class LN_RgbSplitTOP(_Filter, bpy.types.Node):
    """Offsets red and blue for a chromatic aberration look"""
    bl_idname = "LN_RgbSplitTOP"
    bl_label = "RGB Split TOP"

    amount: FloatProperty(name="Amount", default=0.01)
    angle: FloatProperty(name="Angle", default=0.0, subtype='ANGLE')
    radial: BoolProperty(name="Radial", default=False, description="Grow the offset away from the centre")

    def ln_draw(self, context, layout):
        layout.prop(self, "amount")
        layout.prop(self, "angle")
        layout.prop(self, "radial")

    def cook(self, ctx, inp):
        src = inp.get("In")
        if src is None:
            return None
        p = ctx.p
        frag = ("void main(){ vec2 d = (uRadial == 1) ? (vUV - 0.5) * uAmount * 2.0 : vec2(cos(uAngle), sin(uAngle)) * uAmount;"
                " vec4 c = texture(uIn0, vUV); float r = texture(uIn0, vUV + d).r; float b = texture(uIn0, vUV - d).b;"
                " fragColor = vec4(r, c.g, b, c.a); }")
        return self.run(ctx, frag, {"uAmount": p.amount, "uAngle": p.angle, "uRadial": p.radial}, [src],
                        decl=(('FLOAT', 'uAmount'), ('FLOAT', 'uAngle'), ('INT', 'uRadial')))


LOOKUP_FRAG = """
void main(){
  vec4 c = texture(uIn0, vUV);
  vec3 rgb = c.a > 1.0e-5 ? c.rgb / c.a : c.rgb;
  float t = clamp(ln_luma(rgb), 0.0, 1.0);
  vec4 m = (uUseMap == 1) ? texture(uIn1, vec2(t, 0.5)) : mix(uA, uB, t);
  fragColor = vec4(m.rgb, 1.0) * m.a * c.a;
}
"""


class LN_LookupTOP(LNTopNode, bpy.types.Node):
    """Recolours an image by brightness, through two colours or a ramp texture"""
    bl_idname = "LN_LookupTOP"
    bl_label = "Lookup TOP"
    ln_category = "TOP Filter"

    color_a: _color("Dark", (0.02, 0.0, 0.1, 1.0))
    color_b: _color("Bright", (1.0, 0.6, 0.1, 1.0))

    def ln_init(self):
        self.add_in('TOP', "In")
        self.add_in('TOP', "Ramp")
        self.add_out('TOP')

    def ln_draw(self, context, layout):
        row = layout.row(align=True)
        row.prop(self, "color_a", text="")
        row.prop(self, "color_b", text="")

    def cook(self, ctx, inp):
        src = inp.get("In")
        if src is None:
            return None
        p = ctx.p
        ramp = inp.get("Ramp")
        return self.run(ctx, LOOKUP_FRAG, {"uA": p.color_a, "uB": p.color_b, "uUseMap": ramp is not None}, [src, ramp],
                        decl=(('VEC4', 'uA'), ('VEC4', 'uB'), ('INT', 'uUseMap')))


class LN_BloomTOP(_Filter, bpy.types.Node):
    """Glow around bright areas"""
    bl_idname = "LN_BloomTOP"
    bl_label = "Bloom TOP"

    threshold: FloatProperty(name="Threshold", default=0.6, min=0.0)
    radius: FloatProperty(name="Radius", default=16.0, min=0.0)
    intensity: FloatProperty(name="Intensity", default=1.0, min=0.0)

    def ln_draw(self, context, layout):
        col = layout.column(align=True)
        col.prop(self, "threshold")
        col.prop(self, "radius")
        col.prop(self, "intensity")

    def cook(self, ctx, inp):
        src = inp.get("In")
        if src is None:
            return None
        p = ctx.p
        size = self.out_size(ctx, src)
        half = (max(size[0] // 2, 1), max(size[1] // 2, 1))
        bright = self.run(ctx, "void main(){ vec4 c = texture(uIn0, vUV); fragColor = vec4(max(c.rgb - uThresh, vec3(0.0)), c.a); }",
                          {"uThresh": p.threshold}, [src], size=half, slot=1, decl=(('FLOAT', 'uThresh'),))
        glow = blur(self, ctx, bright, p.radius * 0.5, half, slots=(2, 3))
        glow = blur(self, ctx, glow, p.radius, half, slots=(1, 2))
        return self.run(ctx, "void main(){ vec4 a = texture(uIn0, vUV); fragColor = vec4(a.rgb + texture(uIn1, vUV).rgb * uGain, a.a); }",
                        {"uGain": p.intensity}, [src, glow], size=size, slot=0, decl=(('FLOAT', 'uGain'),))


class LN_NormalMapTOP(_Filter, bpy.types.Node):
    """Turns brightness into a tangent-space normal map for materials"""
    bl_idname = "LN_NormalMapTOP"
    bl_label = "Normal Map TOP"

    strength: FloatProperty(name="Strength", default=4.0)

    def ln_draw(self, context, layout):
        layout.prop(self, "strength")

    def cook(self, ctx, inp):
        src = inp.get("In")
        if src is None:
            return None
        frag = ("float h(vec2 o){ return ln_luma(texture(uIn0, vUV + o / uRes).rgb); }"
                "void main(){ float dx = h(vec2(1.0, 0.0)) - h(vec2(-1.0, 0.0)); float dy = h(vec2(0.0, 1.0)) - h(vec2(0.0, -1.0));"
                " vec3 n = normalize(vec3(-dx * uStrength, -dy * uStrength, 1.0)); fragColor = vec4(n * 0.5 + 0.5, 1.0); }")
        return self.run(ctx, frag, {"uStrength": ctx.p.strength}, [src], decl=(('FLOAT', 'uStrength'),))


def homography(src, dst):
    """3x3 matrix mapping the 4 `src` points onto the 4 `dst` points."""
    a = []
    b = []
    for (x, y), (u, v) in zip(src, dst):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b.extend((u, v))
    h = np.linalg.solve(np.array(a, dtype=np.float64), np.array(b, dtype=np.float64))
    return np.append(h, 1.0).reshape(3, 3)


CORNER_FRAG = """
void main(){
  vec3 q = vec3(vUV, 1.0);
  vec3 s = vec3(dot(uH0.xyz, q), dot(uH1.xyz, q), dot(uH2.xyz, q));
  vec2 uv = s.xy / s.z;
  fragColor = texture(uIn0, clamp(uv, 0.0, 1.0)) * ln_inside(uv) * step(0.0, s.z);
}
"""


class LN_CornerPinTOP(_Filter, bpy.types.Node):
    """Projection mapping: pins the four image corners anywhere in the output"""
    bl_idname = "LN_CornerPinTOP"
    bl_label = "Corner Pin TOP"

    bottom_left: FloatVectorProperty(name="Bottom Left", size=2, default=(0.0, 0.0))
    bottom_right: FloatVectorProperty(name="Bottom Right", size=2, default=(1.0, 0.0))
    top_right: FloatVectorProperty(name="Top Right", size=2, default=(1.0, 1.0))
    top_left: FloatVectorProperty(name="Top Left", size=2, default=(0.0, 1.0))

    def ln_draw(self, context, layout):
        col = layout.column(align=True)
        for name in ("top_left", "top_right", "bottom_left", "bottom_right"):
            col.prop(self, name, text="")

    def cook(self, ctx, inp):
        src = inp.get("In")
        if src is None:
            return None
        p = ctx.p
        corners = [p.bottom_left, p.bottom_right, p.top_right, p.top_left]
        try:
            # inverse mapping: output position -> source uv
            h = homography([tuple(c) for c in corners], [(0, 0), (1, 0), (1, 1), (0, 1)])
        except np.linalg.LinAlgError:
            raise ValueError("corners are degenerate (three of them on one line)")
        rows = {f"uH{i}": (h[i, 0], h[i, 1], h[i, 2], 0.0) for i in range(3)}
        return self.run(ctx, CORNER_FRAG, rows, [src], decl=(('VEC4', 'uH0'), ('VEC4', 'uH1'), ('VEC4', 'uH2')))


class LN_ResolutionTOP(_Filter, bpy.types.Node):
    """Resamples the image to another resolution"""
    bl_idname = "LN_ResolutionTOP"
    bl_label = "Resolution TOP"
    ln_params = False

    def ln_draw(self, context, layout):
        LNTopNode.ln_draw_ext(self, context, layout)

    def ln_draw_ext(self, context, layout):
        pass

    def cook(self, ctx, inp):
        src = inp.get("In")
        if src is None:
            return None
        return self.run(ctx, PASS_FRAG, {}, [src])


class LN_NullTOP(_Filter, bpy.types.Node):
    """Passes the image through: a stable place to connect from"""
    bl_idname = "LN_NullTOP"
    bl_label = "Null TOP"
    ln_params = False

    def ln_draw_ext(self, context, layout):
        pass

    def cook(self, ctx, inp):
        return inp.get("In")


classes = (LN_LevelTOP, LN_BlurTOP, LN_TransformTOP, LN_CornerPinTOP, LN_CompositeTOP, LN_CrossTOP, LN_SwitchTOP, LN_DisplaceTOP,
           LN_EdgeTOP, LN_KeyTOP, LN_MirrorTOP, LN_PixelateTOP, LN_RgbSplitTOP, LN_LookupTOP, LN_BloomTOP,
           LN_NormalMapTOP, LN_ResolutionTOP, LN_NullTOP)
