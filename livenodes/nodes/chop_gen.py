"""CHOP generators: channels made from nothing but time."""
import math
import time as _time

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, StringProperty
from mathutils import noise as mnoise

from ..core.data import Channels
from ..core.tree import LNNode


def _names(text, fallback="chan1"):
    return text.split() or [fallback]


class LN_ConstantCHOP(LNNode, bpy.types.Node):
    """Fixed values, one per named channel"""
    bl_idname = "LN_ConstantCHOP"
    bl_label = "Constant CHOP"
    ln_category = "CHOP Generate"

    names: StringProperty(name="Names", default="chan1", description="Space separated channel names (up to 8)")
    values: FloatVectorProperty(name="Values", size=8, default=(1.0, 0, 0, 0, 0, 0, 0, 0))

    def ln_init(self):
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "names", text="")
        col = layout.column(align=True)
        for i, n in enumerate(_names(self.names)[:8]):
            col.prop(self, "values", index=i, text=n)

    def cook(self, ctx, inp):
        names = _names(self.names)[:8]
        vals = ctx.p.values
        return Channels(names, [[vals[i]] for i in range(len(names))])


WAVES = [('SINE', "Sine", ""), ('TRIANGLE', "Triangle", ""), ('RAMP', "Ramp", "Sawtooth 0..1"),
         ('SQUARE', "Square", ""), ('PULSE', "Pulse", "Single-frame pulse each cycle"),
         ('RANDOM', "Random", "New random value each cycle"), ('SMOOTH', "Smooth Random", "Interpolated random")]


def _hash01(i, seed):
    x = math.sin(i * 127.1 + seed * 311.7) * 43758.5453
    return x - math.floor(x)


class LN_LfoCHOP(LNNode, bpy.types.Node):
    """Low frequency oscillator"""
    bl_idname = "LN_LfoCHOP"
    bl_label = "LFO CHOP"
    ln_category = "CHOP Generate"

    channel: StringProperty(name="Channel", default="lfo")
    wave: EnumProperty(name="Wave", items=WAVES, default='SINE')
    frequency: FloatProperty(name="Frequency", default=1.0, description="Cycles per second")
    amplitude: FloatProperty(name="Amplitude", default=1.0)
    offset: FloatProperty(name="Offset", default=0.0)
    phase: FloatProperty(name="Phase", default=0.0, description="Phase offset in cycles")
    bias: FloatProperty(name="Bias", default=0.5, min=0.0, max=1.0, description="Duty cycle of square and triangle")
    unipolar: BoolProperty(name="0..1", default=False, description="Output 0..1 instead of -1..1")
    seed: IntProperty(name="Seed", default=0)

    def ln_init(self):
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "wave", text="")
        col = layout.column(align=True)
        col.prop(self, "frequency")
        col.prop(self, "amplitude")
        col.prop(self, "offset")
        col.prop(self, "phase")
        if self.wave in {'SQUARE', 'TRIANGLE'}:
            col.prop(self, "bias")
        layout.prop(self, "unipolar")

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "channel")
        layout.prop(self, "seed")

    def cook(self, ctx, inp):
        p = ctx.p
        st = ctx.state
        # accumulate phase so frequency can be modulated without jumps
        acc = st.get("acc", 0.0) + p.frequency * ctx.dt
        st["acc"] = acc
        ph = acc + p.phase
        cyc = math.floor(ph)
        x = ph - cyc
        wave = self.wave
        pulse = 0.0
        if wave == 'SINE':
            v = math.sin(x * math.tau)
        elif wave == 'TRIANGLE':
            b = min(max(p.bias, 1e-4), 1 - 1e-4)
            v = (x / b if x < b else (1 - x) / (1 - b)) * 2 - 1
        elif wave == 'RAMP':
            v = x * 2 - 1
        elif wave == 'SQUARE':
            v = 1.0 if x < p.bias else -1.0
        elif wave == 'PULSE':
            pulse = 1.0 if cyc != st.get("cyc") else 0.0
            v = pulse * 2 - 1
        elif wave == 'RANDOM':
            v = _hash01(cyc, self.seed) * 2 - 1
        else:
            a, b = _hash01(cyc, self.seed), _hash01(cyc + 1, self.seed)
            s = x * x * (3 - 2 * x)
            v = (a + (b - a) * s) * 2 - 1
        st["cyc"] = cyc
        if p.unipolar:
            v = v * 0.5 + 0.5
        return Channels([self.channel or "lfo"], [[v * p.amplitude + p.offset]])


class LN_NoiseCHOP(LNNode, bpy.types.Node):
    """Smooth or random noise per channel"""
    bl_idname = "LN_NoiseCHOP"
    bl_label = "Noise CHOP"
    ln_category = "CHOP Generate"

    names: StringProperty(name="Names", default="noise", description="Space separated channel names")
    kind: EnumProperty(name="Type", items=[('SMOOTH', "Smooth", "Perlin noise"), ('FRACTAL', "Fractal", "Layered Perlin noise"),
                                           ('RANDOM', "Random", "White noise"), ('BROWNIAN', "Brownian", "Random walk")], default='SMOOTH')
    speed: FloatProperty(name="Speed", default=1.0, description="How fast the noise evolves")
    amplitude: FloatProperty(name="Amplitude", default=1.0)
    offset: FloatProperty(name="Offset", default=0.0)
    roughness: FloatProperty(name="Roughness", default=0.5, min=0.0, max=1.0)
    seed: IntProperty(name="Seed", default=0)

    def ln_init(self):
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "kind", text="")
        col = layout.column(align=True)
        col.prop(self, "speed")
        col.prop(self, "amplitude")
        col.prop(self, "offset")
        if self.kind == 'FRACTAL':
            col.prop(self, "roughness")

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "names")
        layout.prop(self, "seed")

    def cook(self, ctx, inp):
        p = ctx.p
        st = ctx.state
        names = _names(self.names, "noise")
        pos = st.get("pos", 0.0) + p.speed * ctx.dt
        st["pos"] = pos
        kind = self.kind
        vals = []
        if kind in {'RANDOM', 'BROWNIAN'}:
            rng = st.get("rng")
            if rng is None:
                rng = st["rng"] = np.random.default_rng(self.seed)
            r = rng.uniform(-1.0, 1.0, len(names))
            if kind == 'BROWNIAN':
                walk = st.get("walk")
                if walk is None or len(walk) != len(names):
                    walk = np.zeros(len(names))
                walk = np.clip(walk + r * abs(p.speed) * math.sqrt(ctx.dt), -1.0, 1.0)
                st["walk"] = walk
                r = walk
            vals = list(r)
        else:
            for i in range(len(names)):
                q = (pos, i * 13.37 + self.seed * 7.13, 0.5)
                if kind == 'FRACTAL':
                    v = mnoise.fractal(q, p.roughness * 2.0, 2.0, 4, noise_basis='PERLIN_ORIGINAL')
                else:
                    v = mnoise.noise(q, noise_basis='PERLIN_ORIGINAL') * 2.0
                vals.append(v)
        return Channels(names, [[v * p.amplitude + p.offset] for v in vals])


class LN_TimeCHOP(LNNode, bpy.types.Node):
    """Engine clock: seconds, frame, delta and frame rate"""
    bl_idname = "LN_TimeCHOP"
    bl_label = "Time CHOP"
    ln_category = "CHOP Generate"
    ln_params = False

    wall_clock: BoolProperty(name="Wall Clock", default=False, description="Also output the time of day")

    def ln_init(self):
        self.add_out('CHOP')

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "wall_clock")

    def cook(self, ctx, inp):
        d = {"seconds": ctx.time, "frame": ctx.frame, "delta": ctx.dt, "fps": ctx.engine.fps_actual}
        if self.wall_clock:
            lt = _time.localtime()
            d.update(hour=lt.tm_hour, minute=lt.tm_min, second=lt.tm_sec)
        return Channels.from_dict(d)


class LN_OT_timer_action(bpy.types.Operator):
    """Start, pause or reset a timer node"""
    bl_idname = "livenodes.timer_action"
    bl_label = "Timer"
    bl_options = {'INTERNAL'}

    tree: StringProperty()
    node: StringProperty()
    action: StringProperty()

    def execute(self, context):
        from ..core.engine import ENGINE
        st = ENGINE.states.setdefault(f"{self.tree}\x00{self.node}", {})
        if self.action == 'START':
            st["t"] = 0.0
            st["cycles"] = 0
            st["run"] = True
        elif self.action == 'PAUSE':
            st["run"] = not st.get("run", False)
        elif self.action == 'TAP':
            taps = [t for t in st.get("taps", []) if _time.perf_counter() - t < 3.0]
            taps.append(_time.perf_counter())
            st["taps"] = taps[-8:]
            if len(taps) >= 2:
                tree = bpy.data.node_groups.get(self.tree)
                node = tree.nodes.get(self.node) if tree else None
                if node is not None:
                    node.bpm = round(60.0 * (len(taps) - 1) / (taps[-1] - taps[0]), 1)
        elif self.action == 'RESET':
            st["t"] = 0.0
            st["cycles"] = 0
            st["run"] = False
            st["beats"] = 0.0
        return {'FINISHED'}


def _action(layout, node, action, text, icon='NONE'):
    op = layout.operator("livenodes.timer_action", text=text, icon=icon)
    op.tree = node.id_data.name
    op.node = node.name
    op.action = action


class LN_TimerCHOP(LNNode, bpy.types.Node):
    """Countdown / stopwatch with start, pause and looping"""
    bl_idname = "LN_TimerCHOP"
    bl_label = "Timer CHOP"
    ln_category = "CHOP Generate"

    length: FloatProperty(name="Length", default=4.0, min=0.001, description="Seconds")
    mode: EnumProperty(name="On Done", items=[('ONCE', "Once", ""), ('LOOP', "Loop", ""), ('PINGPONG', "Ping Pong", "")], default='ONCE')
    autostart: BoolProperty(name="Autostart", default=True)

    def ln_init(self):
        self.add_in('CHOP', "Trigger")
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "length")
        layout.prop(self, "mode", text="")
        row = layout.row(align=True)
        _action(row, self, 'START', "Start", 'PLAY')
        _action(row, self, 'PAUSE', "", 'PAUSE')
        _action(row, self, 'RESET', "", 'LOOP_BACK')

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "autostart")

    def cook(self, ctx, inp):
        p = ctx.p
        st = ctx.state
        if "t" not in st:
            st.update(t=0.0, cycles=0, run=self.autostart)
        trig = inp.chop("Trigger").first() > 0.5
        if trig and not st.get("trig"):
            st.update(t=0.0, cycles=0, run=True)
        st["trig"] = trig
        done = 0.0
        if st["run"]:
            st["t"] += ctx.dt
            if st["t"] >= p.length:
                if self.mode == 'ONCE':
                    st["t"] = p.length
                    st["run"] = False
                else:
                    st["t"] -= p.length
                    st["cycles"] += 1
                done = 1.0
        frac = st["t"] / p.length
        if self.mode == 'ONCE' and not st["run"] and st["t"] >= p.length:
            done = 1.0
        if self.mode == 'PINGPONG' and st["cycles"] % 2:
            frac = 1.0 - frac
        return Channels.from_dict({"fraction": frac, "seconds": st["t"], "done": done,
                                   "cycles": st["cycles"], "running": 1.0 if st["run"] else 0.0})


class LN_BeatCHOP(LNNode, bpy.types.Node):
    """Tempo clock: beat ramps, pulses and counters, with tap tempo"""
    bl_idname = "LN_BeatCHOP"
    bl_label = "Beat CHOP"
    ln_category = "CHOP Generate"

    bpm: FloatProperty(name="BPM", default=120.0, min=1.0, max=999.0)
    beats_per_bar: IntProperty(name="Beats / Bar", default=4, min=1, max=32)
    multiplier: FloatProperty(name="Multiplier", default=1.0, min=0.0625, max=16.0, description="Speed up or slow down the ramp (0.5 = half time)")

    def ln_init(self):
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "bpm")
        layout.prop(self, "beats_per_bar")
        layout.prop(self, "multiplier")
        row = layout.row(align=True)
        _action(row, self, 'TAP', "Tap")
        _action(row, self, 'RESET', "Resync")

    def cook(self, ctx, inp):
        p = ctx.p
        st = ctx.state
        beats = st.get("beats", 0.0) + p.bpm / 60.0 * p.multiplier * ctx.dt
        st["beats"] = beats
        beat = math.floor(beats)
        pulse = 1.0 if beat != st.get("last") else 0.0
        st["last"] = beat
        ramp = beats - beat
        bpb = max(p.beats_per_bar, 1)
        return Channels.from_dict({
            "ramp": ramp, "pulse": pulse, "sine": math.sin(ramp * math.tau) * 0.5 + 0.5,
            "beat": beat % bpb, "bar": beat // bpb, "bar_ramp": (beats / bpb) % 1.0, "count": beat})


class LN_PatternCHOP(LNNode, bpy.types.Node):
    """A multi-sample shape: lookup curves, tables for instancing"""
    bl_idname = "LN_PatternCHOP"
    bl_label = "Pattern CHOP"
    ln_category = "CHOP Generate"

    channel: StringProperty(name="Channel", default="pattern")
    shape: EnumProperty(name="Shape", items=[('SINE', "Sine", ""), ('RAMP', "Ramp", ""), ('TRIANGLE', "Triangle", ""),
                                             ('SQUARE', "Square", ""), ('GAUSSIAN', "Gaussian", ""), ('RANDOM', "Random", "")], default='SINE')
    samples: IntProperty(name="Samples", default=64, min=1, max=65536)
    cycles: FloatProperty(name="Cycles", default=1.0)
    phase: FloatProperty(name="Phase", default=0.0)
    amplitude: FloatProperty(name="Amplitude", default=1.0)
    offset: FloatProperty(name="Offset", default=0.0)
    seed: IntProperty(name="Seed", default=0)

    def ln_init(self):
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "shape", text="")
        col = layout.column(align=True)
        col.prop(self, "samples")
        col.prop(self, "cycles")
        col.prop(self, "phase")
        col.prop(self, "amplitude")
        col.prop(self, "offset")

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "channel")
        layout.prop(self, "seed")

    def cook(self, ctx, inp):
        p = ctx.p
        n = max(p.samples, 1)
        x = np.arange(n, dtype=np.float32) / n * p.cycles + p.phase
        f = x - np.floor(x)
        shape = self.shape
        if shape == 'SINE':
            v = np.sin(x * math.tau)
        elif shape == 'RAMP':
            v = f
        elif shape == 'TRIANGLE':
            v = 1.0 - np.abs(f * 2.0 - 1.0)
        elif shape == 'SQUARE':
            v = np.where(f < 0.5, 1.0, 0.0)
        elif shape == 'GAUSSIAN':
            v = np.exp(-((f - 0.5) * 6.0) ** 2)
        else:
            v = np.random.default_rng(self.seed).uniform(0.0, 1.0, n)
        return Channels([self.channel or "pattern"], (v * p.amplitude + p.offset).reshape(1, n), rate=n)


class LN_TriggerCHOP(LNNode, bpy.types.Node):
    """Attack / decay / sustain / release envelope fired by a rising input"""
    bl_idname = "LN_TriggerCHOP"
    bl_label = "Trigger CHOP"
    ln_category = "CHOP Generate"

    threshold: FloatProperty(name="Threshold", default=0.5)
    attack: FloatProperty(name="Attack", default=0.05, min=0.0, subtype='TIME_ABSOLUTE')
    decay: FloatProperty(name="Decay", default=0.2, min=0.0, subtype='TIME_ABSOLUTE')
    sustain: FloatProperty(name="Sustain", default=0.0, min=0.0, max=1.0)
    release: FloatProperty(name="Release", default=0.3, min=0.0, subtype='TIME_ABSOLUTE')
    peak: FloatProperty(name="Peak", default=1.0)

    def ln_init(self):
        self.add_in('CHOP', "In")
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        col = layout.column(align=True)
        for name in ("threshold", "attack", "decay", "sustain", "release", "peak"):
            col.prop(self, name)

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return src
        p = ctx.p
        st = ctx.state
        n = src.num_channels
        if st.get("n") != n:
            st.update(n=n, level=np.zeros(n), stage=np.zeros(n, dtype=np.int8), gate=np.zeros(n, dtype=bool))
        gate = src.data[:, 0] > p.threshold
        level, stage = st["level"], st["stage"]
        rising = gate & ~st["gate"]
        stage[rising] = 1
        st["gate"] = gate
        dt = ctx.dt
        for i in range(n):
            s = stage[i]
            if s == 1:    # attack
                level[i] += dt / max(p.attack, 1e-6)
                if level[i] >= 1.0:
                    level[i] = 1.0
                    stage[i] = 2
            elif s == 2:  # decay to sustain
                level[i] -= dt / max(p.decay, 1e-6) * (1.0 - p.sustain)
                if level[i] <= p.sustain:
                    level[i] = p.sustain
                    stage[i] = 3
            elif s == 3:  # sustain while gate held
                if not gate[i]:
                    stage[i] = 4
            elif s == 4:  # release
                level[i] -= dt / max(p.release, 1e-6)
                if level[i] <= 0.0:
                    level[i] = 0.0
                    stage[i] = 0
        return src.replace((level * p.peak).reshape(n, 1))


classes = (LN_OT_timer_action, LN_ConstantCHOP, LN_LfoCHOP, LN_NoiseCHOP, LN_TimeCHOP, LN_TimerCHOP,
           LN_BeatCHOP, LN_PatternCHOP, LN_TriggerCHOP)
