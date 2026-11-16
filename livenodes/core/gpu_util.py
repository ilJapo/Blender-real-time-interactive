"""GPU helpers for the TOP family: shader cache, render targets, textures."""
import gpu
import numpy as np
from gpu_extras.batch import batch_for_shader

VERT = "void main(){ vUV = pos * 0.5 + 0.5; gl_Position = vec4(pos, 0.0, 1.0); }"

# Shared GLSL helpers, prepended to every built-in fragment shader.
COMMON = """
float ln_luma(vec3 c){ return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
vec3 ln_rgb2hsv(vec3 c){
  vec4 K = vec4(0.0, -1.0/3.0, 2.0/3.0, -1.0);
  vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
  vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
  float d = q.x - min(q.w, q.y);
  float e = 1.0e-10;
  return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}
vec3 ln_hsv2rgb(vec3 c){
  vec3 p = abs(fract(c.xxx + vec3(0.0, 2.0/3.0, 1.0/3.0)) * 6.0 - 3.0);
  return c.z * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y);
}
vec3 ln_hash3(vec3 p){
  p = vec3(dot(p, vec3(127.1, 311.7, 74.7)), dot(p, vec3(269.5, 183.3, 246.1)), dot(p, vec3(113.5, 271.9, 124.6)));
  return fract(sin(p) * 43758.5453123);
}
float ln_grad(vec3 i, vec3 f, vec3 o){ return dot(ln_hash3(i + o) * 2.0 - 1.0, f - o); }
float ln_noise(vec3 p){
  vec3 i = floor(p); vec3 f = fract(p);
  vec3 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
  float a = mix(mix(ln_grad(i, f, vec3(0,0,0)), ln_grad(i, f, vec3(1,0,0)), u.x),
                mix(ln_grad(i, f, vec3(0,1,0)), ln_grad(i, f, vec3(1,1,0)), u.x), u.y);
  float b = mix(mix(ln_grad(i, f, vec3(0,0,1)), ln_grad(i, f, vec3(1,0,1)), u.x),
                mix(ln_grad(i, f, vec3(0,1,1)), ln_grad(i, f, vec3(1,1,1)), u.x), u.y);
  return mix(a, b, u.z) * 1.15;
}
float ln_fbm(vec3 p, int oct, float rough){
  float s = 0.0; float a = 0.5; float n = 0.0;
  for (int k = 0; k < 8; k++){
    if (k >= oct) break;
    s += a * ln_noise(p); n += a; p = p * 2.0 + vec3(17.3, 9.1, 4.7); a *= rough;
  }
  return s / max(n, 1.0e-5);
}
float ln_cell(vec3 p){
  vec3 i = floor(p); vec3 f = fract(p); float d = 8.0;
  for (int z = -1; z <= 1; z++) for (int y = -1; y <= 1; y++) for (int x = -1; x <= 1; x++){
    vec3 o = vec3(float(x), float(y), float(z));
    vec3 r = o + ln_hash3(i + o) - f;
    d = min(d, dot(r, r));
  }
  return sqrt(d);
}
/* extend: 0 hold, 1 repeat, 2 mirror, 3 zero */
vec2 ln_wrap(vec2 uv, int mode){
  if (mode == 1) return fract(uv);
  if (mode == 2) return 1.0 - abs(mod(uv, 2.0) - 1.0);
  return clamp(uv, 0.0, 1.0);
}
float ln_inside(vec2 uv){ vec2 s = step(vec2(0.0), uv) * step(uv, vec2(1.0)); return s.x * s.y; }
"""

_shaders = {}
_tex_cache = {}


class ShaderError(RuntimeError):
    pass


def shader(frag, uniforms=(), samplers=0, common=True):
    """Compile (or fetch) a full-screen fragment shader.

    `uniforms` is a tuple of (TYPE, name). `uRes` (vec2) and `uTime` (float)
    are always declared; inputs are `uIn0..uInN`.
    Push constants are kept under 128 bytes, the portable minimum.
    """
    key = (frag, uniforms, samplers, common)
    hit = _shaders.get(key)
    if hit is not None:
        if isinstance(hit, Exception):
            raise hit
        return hit
    info = gpu.types.GPUShaderCreateInfo()
    iface = gpu.types.GPUStageInterfaceInfo("ln_iface")
    iface.smooth('VEC2', 'vUV')
    info.vertex_in(0, 'VEC2', 'pos')
    info.vertex_out(iface)
    info.fragment_out(0, 'VEC4', 'fragColor')
    info.push_constant('VEC2', 'uRes')
    info.push_constant('FLOAT', 'uTime')
    for typ, name in uniforms:
        info.push_constant(typ, name)
    for i in range(samplers):
        info.sampler(i, 'FLOAT_2D', f'uIn{i}')
    info.vertex_source(VERT)
    info.fragment_source((COMMON if common else "") + frag)
    try:
        sh = gpu.shader.create_from_info(info)
    except Exception as exc:
        err = ShaderError("GLSL compile error (details in the system console)")
        _shaders[key] = err
        raise err from exc
    batch = batch_for_shader(sh, 'TRI_STRIP', {"pos": [(-1, -1), (1, -1), (-1, 1), (1, 1)]})
    types = {name: typ for typ, name in uniforms}
    _shaders[key] = (sh, batch, types)
    return _shaders[key]


class Target:
    """A resizable off-screen colour buffer."""

    __slots__ = ("off", "size", "fmt")

    def __init__(self):
        self.off = None
        self.size = None
        self.fmt = None

    def ensure(self, width, height, fmt='RGBA16F'):
        size = (max(1, int(width)), max(1, int(height)))
        if self.off is None or self.size != size or self.fmt != fmt:
            self.free()
            self.off = gpu.types.GPUOffScreen(size[0], size[1], format=fmt)
            self.size = size
            self.fmt = fmt
        return self

    @property
    def texture(self):
        return self.off.texture_color

    def free(self):
        if self.off is not None:
            try:
                self.off.free()
            except Exception:
                pass
            self.off = None


def draw(target, compiled, uniforms, textures, time=0.0):
    """Run a full-screen pass into `target`; returns its texture."""
    sh, batch, types = compiled
    with target.off.bind():
        gpu.state.blend_set('NONE')
        gpu.state.depth_test_set('NONE')
        sh.bind()
        for i, tex in enumerate(textures):
            sh.uniform_sampler(f'uIn{i}', tex if tex is not None else black())
        _set(sh, 'uRes', 'VEC2', (float(target.size[0]), float(target.size[1])))
        _set(sh, 'uTime', 'FLOAT', float(time))
        for name, value in uniforms.items():
            _set(sh, name, types[name], value)
        batch.draw(sh)
    return target.off.texture_color


def _set(sh, name, typ, value):
    try:
        if typ == 'INT' or typ == 'BOOL':
            sh.uniform_int(name, int(value))
        elif typ == 'FLOAT':
            sh.uniform_float(name, float(value))
        else:
            sh.uniform_float(name, tuple(float(v) for v in value))
    except ValueError:
        pass  # optimised out by the driver


def texture_from_array(arr, fmt='RGBA16F'):
    """(h, w, 4) float array -> GPUTexture."""
    arr = np.ascontiguousarray(arr, dtype=np.float32)
    h, w = arr.shape[:2]
    buf = gpu.types.Buffer('FLOAT', arr.size, arr.ravel())
    return gpu.types.GPUTexture((w, h), format=fmt, data=buf)


def read_pixels(texture):
    """GPUTexture -> (h, w, 4) float32 array."""
    buf = texture.read()
    return np.asarray(buf, dtype=np.float32).reshape(texture.height, texture.width, -1)


def black():
    tex = _tex_cache.get("black")
    if tex is None:
        tex = _tex_cache["black"] = texture_from_array(np.zeros((1, 1, 4), np.float32))
    return tex


def display_shader():
    """Screen-space textured quad with optional linear -> sRGB conversion."""
    hit = _shaders.get("display")
    if hit is None:
        info = gpu.types.GPUShaderCreateInfo()
        iface = gpu.types.GPUStageInterfaceInfo("ln_disp_iface")
        iface.smooth('VEC2', 'vUV')
        info.vertex_in(0, 'VEC2', 'pos')
        info.vertex_in(1, 'VEC2', 'uv')
        info.vertex_out(iface)
        info.fragment_out(0, 'VEC4', 'fragColor')
        info.push_constant('MAT4', 'uMVP')
        info.push_constant('INT', 'uSRGB')
        info.push_constant('FLOAT', 'uAlpha')
        info.sampler(0, 'FLOAT_2D', 'uIn0')
        info.vertex_source("void main(){ vUV = uv; gl_Position = uMVP * vec4(pos, 0.0, 1.0); }")
        info.fragment_source(
            "void main(){ vec4 c = texture(uIn0, vUV); vec3 rgb = max(c.rgb, vec3(0.0));"
            " if (uSRGB == 1) rgb = mix(rgb * 12.92, 1.055 * pow(rgb, vec3(1.0/2.4)) - 0.055, step(vec3(0.0031308), rgb));"
            " fragColor = vec4(rgb, mix(1.0, clamp(c.a, 0.0, 1.0), uAlpha)); }")
        hit = _shaders["display"] = gpu.shader.create_from_info(info)
    return hit


def draw_texture(texture, x, y, w, h, srgb=True, use_alpha=False):
    """Draw `texture` into the current framebuffer at pixel rect (x, y, w, h)."""
    sh = display_shader()
    batch = batch_for_shader(sh, 'TRI_STRIP', {
        "pos": [(x, y), (x + w, y), (x, y + h), (x + w, y + h)],
        "uv": [(0, 0), (1, 0), (0, 1), (1, 1)],
    })
    gpu.state.blend_set('ALPHA' if use_alpha else 'NONE')
    sh.bind()
    sh.uniform_float('uMVP', gpu.matrix.get_projection_matrix() @ gpu.matrix.get_model_view_matrix())
    sh.uniform_int('uSRGB', 1 if srgb else 0)
    sh.uniform_float('uAlpha', 1.0 if use_alpha else 0.0)
    sh.uniform_sampler('uIn0', texture)
    batch.draw(sh)
    gpu.state.blend_set('NONE')


def free_all():
    _shaders.clear()
    _tex_cache.clear()
