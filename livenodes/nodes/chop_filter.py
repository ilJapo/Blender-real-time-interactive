"""CHOP filters: reshape, smooth, combine and route channels."""
import math

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

from ..core.data import Channels, align, resample, unique_names
from ..core.tree import LNNode


class _Filter(LNNode):
    ln_category = "CHOP Filter"

    def ln_init(self):
        self.add_in('CHOP', "In")
        self.add_out('CHOP')


UNARY = [('NONE', "Off", ""), ('ABS', "Absolute", ""), ('NEGATE', "Negate", ""), ('SQRT', "Square Root", ""),
         ('SQUARE', "Square", ""), ('INVERSE', "1 / x", ""), ('SIGN', "Sign", ""), ('ROUND', "Round", ""),
         ('FLOOR', "Floor", ""), ('CEIL', "Ceiling", ""), ('SIN', "Sine", ""), ('COS', "Cosine", ""),
         ('LOG', "Log 10", ""), ('EXP', "Exp", "")]
COMBINE = [('NONE', "Off", ""), ('ADD', "Add", ""), ('SUBTRACT', "Subtract", ""), ('MULTIPLY', "Multiply", ""),
           ('DIVIDE', "Divide", ""), ('AVERAGE', "Average", ""), ('MIN', "Minimum", ""), ('MAX', "Maximum", ""),
           ('LENGTH', "Length", "")]


def _combine(arrays, op, axis=0):
    stack = np.stack(arrays) if isinstance(arrays, list) else arrays
    if op == 'ADD':
        return stack.sum(axis)
    if op == 'SUBTRACT':
        lead = np.take(stack, 0, axis)
        return lead * 2.0 - stack.sum(axis)
    if op == 'MULTIPLY':
        return stack.prod(axis)
    if op == 'DIVIDE':
        lead = np.take(stack, 0, axis)
        rest = stack.prod(axis) / np.where(lead == 0, 1.0, lead)
        return lead / np.where(rest == 0, 1.0, rest)
    if op == 'AVERAGE':
        return stack.mean(axis)
    if op == 'MIN':
        return stack.min(axis)
    if op == 'MAX':
        return stack.max(axis)
    return np.sqrt((stack * stack).sum(axis))


class LN_MathCHOP(_Filter, bpy.types.Node):
    """Arithmetic on channels: scale, remap ranges, combine inputs or channels"""
    bl_idname = "LN_MathCHOP"
    bl_label = "Math CHOP"

    unary: EnumProperty(name="Function", items=UNARY, default='NONE')
    combine_chops: EnumProperty(name="Combine Inputs", items=COMBINE, default='ADD',
                                description="How several connected inputs are merged, channel by channel")
    combine_channels: EnumProperty(name="Combine Channels", items=COMBINE, default='NONE',
                                   description="Collapse all channels into one")
    pre_add: FloatProperty(name="Pre-Add", default=0.0)
    multiply: FloatProperty(name="Multiply", default=1.0)
    post_add: FloatProperty(name="Post-Add", default=0.0)
    use_range: BoolProperty(name="Range", default=False, description="Remap From range to To range")
    from_low: FloatProperty(name="From Low", default=0.0)
    from_high: FloatProperty(name="From High", default=1.0)
    to_low: FloatProperty(name="To Low", default=0.0)
    to_high: FloatProperty(name="To High", default=1.0)
    clamp: BoolProperty(name="Clamp", default=False, description="Clamp the result to the To range")

    def ln_init(self):
        self.add_in('CHOP', "In", multi=True)
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "unary", text="")
        col = layout.column(align=True)
        col.prop(self, "pre_add")
        col.prop(self, "multiply")
        col.prop(self, "post_add")
        layout.prop(self, "use_range")
        if self.use_range:
            row = layout.row(align=True)
            row.prop(self, "from_low", text="")
            row.prop(self, "from_high", text="")
            row = layout.row(align=True)
            row.prop(self, "to_low", text="")
            row.prop(self, "to_high", text="")
            layout.prop(self, "clamp")

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "combine_chops")
        layout.prop(self, "combine_channels")

    def cook(self, ctx, inp):
        p = ctx.p
        names, arrays, rate = align(inp.all("In"))
        if not arrays:
            return Channels.empty()
        if len(arrays) > 1 and self.combine_chops != 'NONE':
            d = _combine(arrays, self.combine_chops)
        else:
            d = arrays[0].astype(np.float32, copy=True)
        u = self.unary
        if u != 'NONE':
            with np.errstate(all="ignore"):
                d = {'ABS': np.abs, 'NEGATE': np.negative, 'SQRT': lambda a: np.sqrt(np.abs(a)),
                     'SQUARE': np.square, 'INVERSE': lambda a: 1.0 / np.where(a == 0, 1.0, a), 'SIGN': np.sign,
                     'ROUND': np.round, 'FLOOR': np.floor, 'CEIL': np.ceil, 'SIN': np.sin, 'COS': np.cos,
                     'LOG': lambda a: np.log10(np.maximum(np.abs(a), 1e-12)), 'EXP': np.exp}[u](d)
        if self.combine_channels != 'NONE':
            d = _combine(d, self.combine_channels, axis=0).reshape(1, -1)
            names = [names[0]]
        d = (d + p.pre_add) * p.multiply + p.post_add
        if p.use_range:
            span = p.from_high - p.from_low
            d = (d - p.from_low) / (span if span else 1.0) * (p.to_high - p.to_low) + p.to_low
            if p.clamp:
                d = np.clip(d, min(p.to_low, p.to_high), max(p.to_low, p.to_high))
        return Channels(names, d, rate)


class LN_LagCHOP(_Filter, bpy.types.Node):
    """Smooths changes, with separate rise and fall times"""
    bl_idname = "LN_LagCHOP"
    bl_label = "Lag CHOP"

    lag_up: FloatProperty(name="Lag Up", default=0.2, min=0.0, subtype='TIME_ABSOLUTE')
    lag_down: FloatProperty(name="Lag Down", default=0.2, min=0.0, subtype='TIME_ABSOLUTE')

    def ln_draw(self, context, layout):
        col = layout.column(align=True)
        col.prop(self, "lag_up")
        col.prop(self, "lag_down")

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return src
        p = ctx.p
        st = ctx.state
        prev = st.get("v")
        if prev is None or prev.shape != src.data.shape:
            prev = src.data.astype(np.float64)
        up = 1.0 - math.exp(-ctx.dt / p.lag_up) if p.lag_up > 1e-6 else 1.0
        down = 1.0 - math.exp(-ctx.dt / p.lag_down) if p.lag_down > 1e-6 else 1.0
        diff = src.data - prev
        prev = prev + diff * np.where(diff > 0, up, down)
        st["v"] = prev
        return src.replace(prev)


class LN_SpringCHOP(_Filter, bpy.types.Node):
    """Follows the input like a mass on a spring: overshoot and wobble"""
    bl_idname = "LN_SpringCHOP"
    bl_label = "Spring CHOP"

    stiffness: FloatProperty(name="Stiffness", default=120.0, min=0.0)
    damping: FloatProperty(name="Damping", default=8.0, min=0.0)
    mass: FloatProperty(name="Mass", default=1.0, min=0.001)

    def ln_draw(self, context, layout):
        col = layout.column(align=True)
        col.prop(self, "stiffness")
        col.prop(self, "damping")
        col.prop(self, "mass")

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return src
        p = ctx.p
        st = ctx.state
        pos = st.get("pos")
        if pos is None or pos.shape != src.data.shape:
            pos = src.data.astype(np.float64)
            st["vel"] = np.zeros_like(pos)
        vel = st["vel"]
        steps = max(1, int(math.ceil(ctx.dt / 0.004)))  # sub-step for stability
        h = ctx.dt / steps
        for _ in range(steps):
            acc = (p.stiffness * (src.data - pos) - p.damping * vel) / p.mass
            vel = vel + acc * h
            pos = pos + vel * h
        st["pos"], st["vel"] = pos, vel
        return src.replace(pos)


class LN_SpeedCHOP(_Filter, bpy.types.Node):
    """Integrates the input over time (value = speed)"""
    bl_idname = "LN_SpeedCHOP"
    bl_label = "Speed CHOP"

    limit: EnumProperty(name="Limit", items=[('OFF', "Off", ""), ('CLAMP', "Clamp", ""), ('LOOP', "Loop", "")], default='OFF')
    low: FloatProperty(name="Min", default=0.0)
    high: FloatProperty(name="Max", default=1.0)

    def ln_init(self):
        self.add_in('CHOP', "In")
        self.add_in('CHOP', "Reset")
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "limit", text="")
        if self.limit != 'OFF':
            row = layout.row(align=True)
            row.prop(self, "low", text="")
            row.prop(self, "high", text="")

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return src
        p = ctx.p
        st = ctx.state
        acc = st.get("acc")
        if acc is None or acc.shape != src.data.shape or inp.chop("Reset").first() > 0.5:
            acc = np.zeros(src.data.shape, dtype=np.float64)
        acc = acc + src.data * ctx.dt
        if self.limit == 'CLAMP':
            acc = np.clip(acc, p.low, p.high)
        elif self.limit == 'LOOP' and p.high > p.low:
            acc = p.low + np.mod(acc - p.low, p.high - p.low)
        st["acc"] = acc
        return src.replace(acc)


class LN_SlopeCHOP(_Filter, bpy.types.Node):
    """Rate of change per second"""
    bl_idname = "LN_SlopeCHOP"
    bl_label = "Slope CHOP"
    ln_params = False

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return src
        st = ctx.state
        prev = st.get("prev")
        st["prev"] = src.data.copy()
        if prev is None or prev.shape != src.data.shape:
            return src.replace(np.zeros_like(src.data))
        return src.replace((src.data - prev) / max(ctx.dt, 1e-6))


class LN_LimitCHOP(_Filter, bpy.types.Node):
    """Clamp, loop or fold values into a range; quantize to steps"""
    bl_idname = "LN_LimitCHOP"
    bl_label = "Limit CHOP"

    mode: EnumProperty(name="Mode", items=[('OFF', "Off", ""), ('CLAMP', "Clamp", ""), ('LOOP', "Loop", ""), ('ZIGZAG', "Zigzag", "")], default='CLAMP')
    low: FloatProperty(name="Min", default=0.0)
    high: FloatProperty(name="Max", default=1.0)
    step: FloatProperty(name="Quantize", default=0.0, min=0.0, description="Snap to multiples of this value (0 = off)")

    def ln_draw(self, context, layout):
        layout.prop(self, "mode", text="")
        row = layout.row(align=True)
        row.prop(self, "low", text="")
        row.prop(self, "high", text="")
        layout.prop(self, "step")

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return src
        p = ctx.p
        d = src.data
        span = p.high - p.low
        if self.mode == 'CLAMP':
            d = np.clip(d, p.low, p.high)
        elif self.mode == 'LOOP' and span > 0:
            d = p.low + np.mod(d - p.low, span)
        elif self.mode == 'ZIGZAG' and span > 0:
            d = p.low + span - np.abs(np.mod(d - p.low, span * 2) - span)
        if p.step > 0:
            d = np.round(d / p.step) * p.step
        return src.replace(d)


class LN_LogicCHOP(_Filter, bpy.types.Node):
    """Turns values into on/off: threshold, toggle, edge pulses, channel logic"""
    bl_idname = "LN_LogicCHOP"
    bl_label = "Logic CHOP"

    threshold: FloatProperty(name="Threshold", default=0.5)
    mode: EnumProperty(name="Mode", items=[('RAW', "While On", "1 while the input is above the threshold"),
                                           ('TOGGLE', "Toggle", "Flip on every rising edge"),
                                           ('RISE', "Rising Edge", "One-frame pulse when turning on"),
                                           ('FALL', "Falling Edge", "One-frame pulse when turning off"),
                                           ('CHANGE', "Any Change", "One-frame pulse on either edge")], default='RAW')
    combine: EnumProperty(name="Combine", items=[('NONE', "Off", ""), ('AND', "And", ""), ('OR', "Or", ""), ('XOR', "Xor", "")], default='NONE')
    invert: BoolProperty(name="Invert", default=False)

    def ln_draw(self, context, layout):
        layout.prop(self, "mode", text="")
        layout.prop(self, "threshold")
        layout.prop(self, "combine")
        layout.prop(self, "invert")

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return src
        st = ctx.state
        on = src.data[:, :1] > ctx.p.threshold
        prev = st.get("prev")
        if prev is None or prev.shape != on.shape:
            prev = on.copy()
            st["tog"] = np.zeros(on.shape, dtype=bool)
        st["prev"] = on
        mode = self.mode
        if mode == 'TOGGLE':
            st["tog"] = st["tog"] ^ (on & ~prev)
            out = st["tog"]
        elif mode == 'RISE':
            out = on & ~prev
        elif mode == 'FALL':
            out = ~on & prev
        elif mode == 'CHANGE':
            out = on ^ prev
        else:
            out = on
        names = src.names
        if self.combine != 'NONE' and len(out):
            fn = {'AND': np.logical_and, 'OR': np.logical_or, 'XOR': np.logical_xor}[self.combine]
            out = fn.reduce(out, axis=0).reshape(1, -1)
            names = names[:1]
        if self.invert:
            out = ~out
        return Channels(names, out.astype(np.float32), src.rate)


class LN_CountCHOP(_Filter, bpy.types.Node):
    """Counts rising edges"""
    bl_idname = "LN_CountCHOP"
    bl_label = "Count CHOP"

    threshold: FloatProperty(name="Threshold", default=0.5)
    loop_at: IntProperty(name="Loop At", default=0, min=0, description="Wrap back to zero at this count (0 = never)")

    def ln_init(self):
        self.add_in('CHOP', "In")
        self.add_in('CHOP', "Reset")
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "threshold")
        layout.prop(self, "loop_at")

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return src
        st = ctx.state
        on = src.data[:, 0] > ctx.p.threshold
        prev = st.get("prev")
        if prev is None or prev.shape != on.shape or inp.chop("Reset").first() > 0.5:
            st["count"] = np.zeros(on.shape, dtype=np.int64)
            prev = on
        st["count"] = st["count"] + (on & ~prev)
        if ctx.p.loop_at > 0:
            st["count"] %= ctx.p.loop_at
        st["prev"] = on
        return src.replace(st["count"].reshape(-1, 1))


class LN_HoldCHOP(_Filter, bpy.types.Node):
    """Sample and hold: passes the input while Gate is on, freezes it otherwise"""
    bl_idname = "LN_HoldCHOP"
    bl_label = "Hold CHOP"

    on_edge: BoolProperty(name="Sample On Edge", default=True, description="Sample only on the rising edge of the gate")

    def ln_init(self):
        self.add_in('CHOP', "In")
        self.add_in('CHOP', "Gate")
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "on_edge")

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return src
        st = ctx.state
        gate = inp.chop("Gate").first() > 0.5
        held = st.get("held")
        take = gate and not st.get("gate", False) if ctx.p.on_edge else gate
        st["gate"] = gate
        if held is None or held.shape != src.data.shape or take:
            held = st["held"] = src.data.copy()
        return src.replace(held)


class LN_DelayCHOP(_Filter, bpy.types.Node):
    """Delays channels by a time"""
    bl_idname = "LN_DelayCHOP"
    bl_label = "Delay CHOP"

    delay: FloatProperty(name="Delay", default=0.5, min=0.0, max=30.0, subtype='TIME_ABSOLUTE')

    def ln_draw(self, context, layout):
        layout.prop(self, "delay")

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return src
        st = ctx.state
        buf = st.setdefault("buf", [])
        buf.append((ctx.time, src.data.copy()))
        cutoff = ctx.time - ctx.p.delay
        while len(buf) > 1 and buf[1][0] <= cutoff:
            buf.pop(0)
        if len(buf) > 4096:
            del buf[:len(buf) - 4096]
        data = buf[0][1]
        if data.shape != src.data.shape:
            data = src.data
        return src.replace(data)


class LN_SelectCHOP(_Filter, bpy.types.Node):
    """Keeps channels by name pattern and optionally renames them"""
    bl_idname = "LN_SelectCHOP"
    bl_label = "Select CHOP"
    ln_params = False

    pattern: StringProperty(name="Channels", default="*", description="Space separated names, with * and ? wildcards")
    rename: StringProperty(name="Rename To", default="", description="New names in order; a trailing * numbers the rest (e.g. 'band*')")

    def ln_draw(self, context, layout):
        layout.prop(self, "pattern", text="")
        layout.prop(self, "rename", text="", icon='GREASEPENCIL')

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return src
        out = src.select(src.match(self.pattern))
        new = self.rename.split()
        if new:
            names = list(out.names)
            for i in range(len(names)):
                if i < len(new) and not new[i].endswith("*"):
                    names[i] = new[i]
                elif new[-1].endswith("*"):
                    names[i] = f"{new[-1][:-1]}{i - len(new) + 2}"
            out.names = unique_names(names)
        return out


class LN_MergeCHOP(_Filter, bpy.types.Node):
    """Joins the channels of all inputs"""
    bl_idname = "LN_MergeCHOP"
    bl_label = "Merge CHOP"
    ln_params = False

    def ln_init(self):
        self.add_in('CHOP', "In", multi=True)
        self.add_out('CHOP')

    def cook(self, ctx, inp):
        ins = [c for c in inp.all("In") if c.num_channels]
        if not ins:
            return Channels.empty()
        ns = max(c.num_samples for c in ins)
        names = []
        for c in ins:
            names.extend(c.names)
        return Channels(unique_names(names), np.concatenate([resample(c.data, ns) for c in ins]),
                        max(ins, key=lambda c: c.num_samples).rate)


class LN_SwitchCHOP(_Filter, bpy.types.Node):
    """Picks one of several inputs, with optional blending between neighbours"""
    bl_idname = "LN_SwitchCHOP"
    bl_label = "Switch CHOP"

    index: FloatProperty(name="Index", default=0.0, min=0.0)
    blend: BoolProperty(name="Blend", default=False, description="Crossfade between inputs for fractional indices")

    def ln_init(self):
        self.add_in('CHOP', "In", multi=True)
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "index")
        layout.prop(self, "blend")

    def cook(self, ctx, inp):
        ins = inp.all("In")
        if not ins:
            return Channels.empty()
        idx = min(max(ctx.p.index, 0.0), len(ins) - 1)
        lo = int(math.floor(idx))
        if not ctx.p.blend or lo >= len(ins) - 1:
            return ins[int(round(idx)) if not ctx.p.blend else lo]
        names, (a, b), rate = align([ins[lo], ins[lo + 1]])
        f = idx - lo
        return Channels(names, a * (1 - f) + b * f, rate)


class LN_NullCHOP(_Filter, bpy.types.Node):
    """Passes channels through: a stable place to connect from"""
    bl_idname = "LN_NullCHOP"
    bl_label = "Null CHOP"
    ln_params = False

    def cook(self, ctx, inp):
        return inp.chop()


class LN_ExpressionCHOP(_Filter, bpy.types.Node):
    """A Python expression evaluated per channel"""
    bl_idname = "LN_ExpressionCHOP"
    bl_label = "Expression CHOP"
    ln_params = False

    expr: StringProperty(name="Expression", default="v * 2", description=(
        "Variables: v (samples of this channel), i (channel index), n (channel name), t (seconds), "
        "dt, frame, ch (dict of all input values), np, math"))

    def ln_draw(self, context, layout):
        layout.prop(self, "expr", text="")

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return src
        st = ctx.state
        if st.get("src") != self.expr:
            st["code"] = compile(self.expr, "<expression>", "eval")
            st["src"] = self.expr
        env = {"np": np, "math": math, "t": ctx.time, "dt": ctx.dt, "frame": ctx.frame, "ch": src.to_dict(),
               "sin": np.sin, "cos": np.cos, "abs": np.abs, "min": np.minimum, "max": np.maximum, "pi": math.pi}
        out = np.empty_like(src.data)
        for i, (name, row) in enumerate(zip(src.names, src.data)):
            env.update(v=row, i=i, n=name)
            out[i] = eval(st["code"], env)
        return src.replace(out)


class LN_ResampleCHOP(_Filter, bpy.types.Node):
    """Changes the number of samples"""
    bl_idname = "LN_ResampleCHOP"
    bl_label = "Resample CHOP"

    samples: IntProperty(name="Samples", default=32, min=1, max=65536)

    def ln_draw(self, context, layout):
        layout.prop(self, "samples")

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return src
        n = max(ctx.p.samples, 1)
        return src.replace(resample(src.data, n), rate=src.rate * n / max(src.num_samples, 1))


class LN_AnalyzeCHOP(_Filter, bpy.types.Node):
    """Reduces many samples to one value per channel"""
    bl_idname = "LN_AnalyzeCHOP"
    bl_label = "Analyze CHOP"
    ln_params = False

    function: EnumProperty(name="Function", items=[('AVERAGE', "Average", ""), ('MIN', "Minimum", ""), ('MAX', "Maximum", ""),
                                                   ('RMS', "RMS Power", ""), ('SUM', "Sum", ""), ('RANGE', "Range", ""),
                                                   ('INDEX_MAX', "Index of Maximum", ""), ('FIRST', "First", ""), ('LAST', "Last", "")],
                           default='AVERAGE')

    def ln_draw(self, context, layout):
        layout.prop(self, "function", text="")

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return src
        d = src.data
        f = self.function
        if f == 'AVERAGE':
            r = d.mean(1)
        elif f == 'MIN':
            r = d.min(1)
        elif f == 'MAX':
            r = d.max(1)
        elif f == 'RMS':
            r = np.sqrt((d * d).mean(1))
        elif f == 'SUM':
            r = d.sum(1)
        elif f == 'RANGE':
            r = d.max(1) - d.min(1)
        elif f == 'INDEX_MAX':
            r = d.argmax(1)
        elif f == 'FIRST':
            r = d[:, 0]
        else:
            r = d[:, -1]
        return src.replace(np.asarray(r, dtype=np.float32).reshape(-1, 1), rate=60.0)


class LN_TrailCHOP(_Filter, bpy.types.Node):
    """Records the recent history of each channel as samples"""
    bl_idname = "LN_TrailCHOP"
    bl_label = "Trail CHOP"

    length: IntProperty(name="Length", default=120, min=2, max=8192, description="Frames of history")

    def ln_draw(self, context, layout):
        layout.prop(self, "length")

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return src
        n = max(ctx.p.length, 2)
        st = ctx.state
        buf = st.get("buf")
        if buf is None or buf.shape != (src.num_channels, n):
            buf = np.repeat(src.data[:, :1], n, axis=1)
        buf = np.roll(buf, -1, axis=1)
        buf[:, -1] = src.data[:, 0]
        st["buf"] = buf
        return src.replace(buf.copy(), rate=ctx.fps)


class LN_ShuffleCHOP(_Filter, bpy.types.Node):
    """Swaps channels and samples (e.g. a 32-sample spectrum into 32 channels)"""
    bl_idname = "LN_ShuffleCHOP"
    bl_label = "Shuffle CHOP"
    ln_params = False

    mode: EnumProperty(name="Mode", items=[('SPLIT', "Samples to Channels", "One channel per sample of the first channel"),
                                           ('JOIN', "Channels to Samples", "One channel whose samples are the channel values"),
                                           ('SWAP', "Transpose", "")], default='SPLIT')
    prefix: StringProperty(name="Prefix", default="chan")

    def ln_draw(self, context, layout):
        layout.prop(self, "mode", text="")
        layout.prop(self, "prefix")

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return src
        pre = self.prefix or "chan"
        if self.mode == 'SPLIT':
            row = src.data[0]
            return Channels([f"{pre}{i + 1}" for i in range(len(row))], row.reshape(-1, 1))
        if self.mode == 'JOIN':
            return Channels([pre], src.data[:, 0].reshape(1, -1), rate=src.num_channels)
        t = src.data.T
        return Channels([f"{pre}{i + 1}" for i in range(len(t))], t.copy())


class LN_FeedbackCHOP(LNNode, bpy.types.Node):
    """Outputs what another node produced on the previous frame, closing a loop"""
    bl_idname = "LN_FeedbackCHOP"
    bl_label = "Feedback CHOP"
    ln_category = "CHOP Filter"
    ln_params = False

    target: StringProperty(name="Target", description="Node whose previous output is returned")

    def ln_init(self):
        self.add_in('CHOP', "Initial")
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop_search(self, "target", self.id_data, "nodes", text="")

    def cook(self, ctx, inp):
        prev = ctx.output_of(self.target) if self.target else None
        return prev if isinstance(prev, Channels) else inp.chop("Initial")


classes = (LN_MathCHOP, LN_LagCHOP, LN_SpringCHOP, LN_SpeedCHOP, LN_SlopeCHOP, LN_LimitCHOP, LN_LogicCHOP,
           LN_CountCHOP, LN_HoldCHOP, LN_DelayCHOP, LN_SelectCHOP, LN_MergeCHOP, LN_SwitchCHOP, LN_NullCHOP,
           LN_ExpressionCHOP, LN_ResampleCHOP, LN_AnalyzeCHOP, LN_TrailCHOP, LN_ShuffleCHOP, LN_FeedbackCHOP)
