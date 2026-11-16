"""GLSL for the Pulsar demo. Uniform pack (from the Brain script):
uP0 = bass, mid, high, kick      uP1 = level, hue, intensity, bar ramp
uP2 = beat ramp, glitch, flash, time    uP3 = spare
"""

ECLIPSE = r"""// PULSAR / eclipse - a black sun whose corona is the audio spectrum.
// uIn0 = spectrum (CHOP to TOP, 1 row), uP0..uP2 = audio + controls (see the Brain script)
#define BASS uP0.x
#define MID uP0.y
#define HIGH uP0.z
#define KICK uP0.w
#define LEVEL uP1.x
#define HUE uP1.y
#define INTENSITY uP1.z
#define T uP2.w

// palette, linear RGB: indigo #1B1440, violet #7B5CFF, coral #FF5A36, warm white #FFF4E6
vec3 palette(float t){
  vec3 indigo = vec3(0.0103, 0.0070, 0.0513);
  vec3 violet = vec3(0.198, 0.107, 1.0);
  vec3 coral  = vec3(1.0, 0.102, 0.037);
  vec3 white  = vec3(1.0, 0.905, 0.791);
  t = clamp(t, 0.0, 1.0);
  vec3 c = mix(indigo, violet, smoothstep(0.0, 0.35, t));
  c = mix(c, coral, smoothstep(0.35, 0.75, t));
  return mix(c, white, smoothstep(0.75, 1.0, t));
}

float spectrum(float u){
  u = mix(0.015, 0.985, clamp(u, 0.0, 1.0));
  float w = 1.0 / 64.0;
  return (texture(uIn0, vec2(u - w, 0.5)).r + 2.0 * texture(uIn0, vec2(u, 0.5)).r + texture(uIn0, vec2(u + w, 0.5)).r) * 0.25;
}

void main(){
  vec2 p = (vUV - 0.5) * vec2(uRes.x / uRes.y, 1.0);
  float r = length(p);
  float R = 0.2 * (1.0 + 0.06 * KICK + 0.05 * BASS);           // same scale as the 3D core
  float d = r - R;
  // angle from the bottom, mirrored left/right: lows at the bottom, highs on top
  float b = atan(p.x, -p.y);
  float u = abs(b) / 3.14159265;
  // tilt the spectrum up towards the highs (they carry less energy), then keep the peaks
  float s = smoothstep(0.3, 1.0, spectrum(u) * (0.85 + 0.55 * u));
  s *= s;

  float flame = ln_fbm(vec3(u * 7.0, d * 9.0 - T * 1.3, T * 0.17), 4, 0.55) * 0.5 + 0.5;
  float reach = 0.006 + (0.03 + 0.11 * INTENSITY) * s * (0.4 + 1.2 * flame);
  float corona = exp(-max(d, 0.0) / reach) * (0.15 + 1.1 * s) * step(0.0, d);
  float streaks = pow(max(ln_noise(vec3(u * 46.0, T * 0.35, 3.0)) * 0.5 + 0.5, 0.0), 7.0);
  streaks *= exp(-max(d, 0.0) * (4.0 - 1.5 * HIGH)) * (0.1 + 0.6 * HIGH) * step(0.0, d);
  float rim = exp(-abs(d) / (0.0022 + 0.002 * KICK)) * (0.7 + 2.2 * KICK);

  vec3 col = palette(s * 0.8 + flame * 0.35 - d * 2.0) * corona * (0.3 + 0.5 * INTENSITY);
  col += palette(0.45 + 0.4 * HIGH) * streaks * 0.35;
  col += vec3(1.0, 0.905, 0.791) * rim;
  col += vec3(0.0103, 0.0070, 0.0513) * 0.6 * exp(-r * 2.5) * (0.5 + LEVEL);   // faint nebula

  vec3 h = ln_hash3(vec3(floor(vUV * uRes / 2.0), 7.0));                        // sparse stars
  col += vec3(0.8, 0.85, 1.0) * step(0.9988, h.x) * (0.35 + 0.35 * sin(T * 1.7 + h.y * 40.0)) * step(0.0, d);

  if (HUE != 0.0){
    vec3 hsv = ln_rgb2hsv(max(col, vec3(0.0)));
    col = ln_hsv2rgb(vec3(fract(hsv.x + HUE), hsv.yz));
  }
  // premultiplied: the disc is opaque black and hides the trails behind it,
  // the corona has zero alpha so it adds light on top of them
  float disc = 1.0 - smoothstep(-0.0015, 0.0015, d);
  fragColor = vec4(col * (1.0 - disc), disc);
}
"""

FINISH = r"""// PULSAR / finish - tone mapping, flash, vignette, scanlines and film grain
#define KICK uP0.w
#define GLITCH uP2.y
#define FLASH uP2.z
#define T uP2.w

vec3 aces(vec3 x){ return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0); }

void main(){
  vec2 uv = vUV;
  // glitch: horizontal tearing in bands
  float band = floor(uv.y * 24.0 + floor(T * 18.0) * 7.0);
  float tear = (ln_hash3(vec3(band, floor(T * 18.0), 1.0)).x - 0.5) * step(0.82, ln_hash3(vec3(band, 2.0, floor(T * 9.0))).y);
  uv.x += tear * 0.08 * GLITCH;
  vec3 c = texture(uIn0, uv).rgb;
  c += vec3(1.0, 0.905, 0.791) * FLASH * 1.5;
  c = aces(c * (0.9 + 0.2 * KICK));
  vec2 q = vUV - 0.5;
  c *= mix(1.0, 0.25, smoothstep(0.35, 0.85, length(q * vec2(uRes.x / uRes.y, 1.0)) * 1.1));   // vignette
  c *= 0.965 + 0.035 * sin(vUV.y * uRes.y * 3.14159);                                         // scanlines
  float g = ln_hash3(vec3(vUV * uRes, floor(T * 60.0))).x - 0.5;                              // grain
  c += g * 0.045;
  // back to linear: the rest of the pipeline displays with an sRGB transform
  c = pow(max(c, vec3(0.0)), vec3(2.2));
  fragColor = vec4(c, 1.0);
}
"""

BRAIN = r'''"""PULSAR / brain - turns audio analysis and the Perform-panel controls into
named channels. The first 16 become the GLSL uniforms uP0..uP3 (keep the order);
the rest drive node parameters by name (rotate, amount, block, core_scale...)."""
import math

BPM = 124.0


def cook(ctx, inputs):
    c = inputs.chop("In").to_dict()
    g = c.get
    beats = g("position", 0.0) * BPM / 60.0
    kick = g("kick_env", 0.0)
    glitch = g("glitch", 0.0)
    intensity = 0.35 + 1.3 * g("intensity", 0.7)
    out = {
        # uP0
        "bass": g("bass", 0.0), "mid": g("mid", 0.0), "high": g("high", 0.0), "kick": kick,
        # uP1
        "level": g("level", 0.0), "hue": g("hue", 0.0), "intensity": intensity, "bar_ramp": (beats / 4.0) % 1.0,
        # uP2
        "beat_ramp": beats % 1.0, "glitch": glitch, "flash": g("flash", 0.0), "time": ctx.time,
        # uP3 (spare)
        "p12": 0.0, "p13": 0.0, "p14": 0.0, "p15": 0.0,
        # node parameters, matched by name
        "rotate": 0.0015 + 0.005 * g("mid", 0.0),               # feedback swirl (Transform TOP)
        "amount": 0.0015 + 0.004 * kick + 0.03 * glitch,       # chromatic split (RGB Split TOP)
        "block": 1.0 + 14.0 * glitch * glitch,                  # mosaic (Pixelate TOP)
        "core_scale": 1.0 + 0.06 * kick + 0.05 * g("bass", 0.0),
        "spin": ctx.time * 0.11,
        "energy": 1.2 + 3.0 * g("level", 0.0) + 2.5 * kick,
        "bar_num": math.floor(beats / 4.0) % 8 + 1, "beat_num": math.floor(beats) % 4 + 1,
    }
    return out
'''

RING = r'''"""PULSAR / ring - lays the spectrum out as 96 radial bars around the core.
Outputs one sample per bar: position (tx ty tz), length (sx), angle (rz) and
level (s), written into a mesh by CHOP to Mesh and instanced by Geometry Nodes."""
import numpy as np

BARS = 96
RADIUS = 1.18


def cook(ctx, inputs):
    spec = inputs.chop("In")
    s = spec.data[0] if spec else np.zeros(64)
    a = np.linspace(0.0, 2.0 * np.pi, BARS, endpoint=False)
    u = np.abs(((a / np.pi) + 1.0) % 2.0 - 1.0)              # mirrored: 0 at +X, 1 at -X
    v = np.interp(u * (len(s) - 1), np.arange(len(s)), s)
    length = 0.03 + 1.25 * v ** 1.6
    r = RADIUS + length * 0.5
    return {"tx": np.cos(a) * r, "ty": np.sin(a) * r, "tz": np.zeros(BARS),
            "sx": length, "rz": a, "s": v}
'''
