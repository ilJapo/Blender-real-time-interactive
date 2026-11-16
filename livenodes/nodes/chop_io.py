"""CHOP inputs: audio, MIDI, OSC, keyboard, mouse, DMX and Blender data."""
import math
import threading

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty

from ..core import deps, net, services
from ..core.data import Channels
from ..core.tree import LNNode


# -- audio ----------------------------------------------------------------
class _AudioStream:
    """Ring buffer fed by a sounddevice input stream."""

    def __init__(self, device, channels, rate):
        sd = deps.require("sounddevice")
        self.rate = rate
        self.buf = np.zeros((channels, rate * 2), dtype=np.float32)
        self.lock = threading.Lock()
        self.stream = sd.InputStream(device=device, channels=channels, samplerate=rate, callback=self._cb)
        self.stream.start()

    def _cb(self, indata, frames, time_info, status):
        with self.lock:
            n = min(frames, self.buf.shape[1])
            self.buf = np.roll(self.buf, -n, axis=1)
            self.buf[:, -n:] = indata[-n:].T

    def latest(self, n):
        with self.lock:
            return self.buf[:, -n:].copy()

    def close(self):
        self.stream.stop()
        self.stream.close()


class LN_AudioDeviceInCHOP(LNNode, bpy.types.Node):
    """Live audio from a microphone or line input"""
    bl_idname = "LN_AudioDeviceInCHOP"
    bl_label = "Audio Device In CHOP"
    ln_category = "CHOP Input"
    ln_params = False

    device: StringProperty(name="Device", default="", description="Device name (part of it is enough); empty = system default")
    channels: IntProperty(name="Channels", default=1, min=1, max=8)
    rate: IntProperty(name="Sample Rate", default=44100, min=8000, max=192000)
    window: IntProperty(name="Samples", default=1024, min=64, max=16384, description="Samples output each frame")
    show_values: BoolProperty(default=False, options={'HIDDEN'})

    def ln_init(self):
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "device", text="", icon='SPEAKER')
        layout.prop(self, "channels")

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "rate")
        layout.prop(self, "window")
        sd = deps.load("sounddevice")
        if sd is None:
            layout.label(text="Needs the 'sounddevice' module", icon='ERROR')
            return
        try:
            devs = [d["name"] for d in sd.query_devices() if d["max_input_channels"] > 0]
        except Exception:
            devs = []
        for name in devs[:12]:
            layout.label(text=name, icon='DOT')

    def cook(self, ctx, inp):
        key = (self.device, self.channels, self.rate)
        stream = services.get("audio_in", key, lambda: _AudioStream(self.device or None, self.channels, self.rate))
        data = stream.latest(self.window)
        return Channels([f"chan{i + 1}" for i in range(len(data))], data, rate=self.rate)


class LN_AudioFileInCHOP(LNNode, bpy.types.Node):
    """Plays an audio file and outputs the samples at the play position"""
    bl_idname = "LN_AudioFileInCHOP"
    bl_label = "Audio File In CHOP"
    ln_category = "CHOP Input"

    filepath: StringProperty(name="File", subtype='FILE_PATH')
    play: BoolProperty(name="Play", default=True)
    loop: BoolProperty(name="Loop", default=True)
    volume: FloatProperty(name="Volume", default=1.0, min=0.0, max=2.0, description="Speaker volume (the channels are not scaled)")
    mono: BoolProperty(name="Mono", default=True, description="Mix all channels down to one")
    window: IntProperty(name="Samples", default=1024, min=64, max=16384)
    show_values: BoolProperty(default=False, options={'HIDDEN'})

    def ln_init(self):
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "filepath", text="")
        row = layout.row(align=True)
        row.prop(self, "play", toggle=True, icon='PLAY')
        row.prop(self, "loop", toggle=True, icon='FILE_REFRESH', text="")
        layout.prop(self, "volume")

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "mono")
        layout.prop(self, "window")

    def cook(self, ctx, inp):
        import aud
        p = ctx.p
        st = ctx.state
        path = bpy.path.abspath(self.filepath)
        if st.get("path") != path:
            self._stop(st)
            st.clear()
            st["path"] = path
            if not path:
                return Channels.empty()
            sound = aud.Sound(path)
            st["data"] = np.ascontiguousarray(sound.data().T, dtype=np.float32)  # (channels, frames)
            st["rate"] = sound.specs[0]
            st["sound"] = sound
            st["pos"] = 0.0
        data = st.get("data")
        if data is None or not data.shape[1]:
            return Channels.empty()
        rate = st["rate"]
        length = data.shape[1] / rate
        handle = st.get("handle")
        if p.play and handle is None and "nodevice" not in st:
            try:
                dev = st["device"] = aud.Device()
                handle = st["handle"] = dev.play(st["sound"])
                handle.loop_count = -1 if p.loop else 0
            except Exception:
                st["nodevice"] = True  # no audio output: follow the engine clock instead
        if handle is not None:
            try:
                if p.play:
                    handle.resume()
                    handle.volume = p.volume
                    st["pos"] = handle.position % length if p.loop else handle.position
                else:
                    handle.pause()
            except Exception:
                st.pop("handle", None)
        elif p.play:
            st["pos"] += ctx.dt
            if st["pos"] >= length:
                st["pos"] = st["pos"] % length if p.loop else length
        n = min(self.window, data.shape[1])
        end = min(max(int(st["pos"] * rate), n), data.shape[1])
        chunk = data[:, end - n:end]
        playing = 1.0 if p.play and st["pos"] < length else 0.0
        if not playing:
            chunk = np.zeros_like(chunk)
        if p.mono:
            return Channels(["chan1"], chunk.mean(0, keepdims=True), rate=rate)
        return Channels([f"chan{i + 1}" for i in range(len(chunk))], chunk, rate=rate)

    @staticmethod
    def _stop(st):
        handle = st.get("handle")
        if handle is not None:
            try:
                handle.stop()
            except Exception:
                pass

    def free(self):
        from ..core.engine import ENGINE
        from ..core.tree import node_key
        self._stop(ENGINE.states.get(node_key(self), {}))
        super().free()


class LN_AudioSpectrumCHOP(LNNode, bpy.types.Node):
    """Frequency spectrum of an audio signal, as log-spaced bands"""
    bl_idname = "LN_AudioSpectrumCHOP"
    bl_label = "Audio Spectrum CHOP"
    ln_category = "CHOP Audio"

    bands: IntProperty(name="Bands", default=32, min=1, max=512)
    freq_low: FloatProperty(name="Low Hz", default=30.0, min=1.0)
    freq_high: FloatProperty(name="High Hz", default=16000.0, min=10.0)
    decibels: BoolProperty(name="Decibel Scale", default=True, description="Map -60..0 dB to 0..1 (closer to how we hear)")
    gain: FloatProperty(name="Gain", default=1.0, min=0.0)
    falloff: FloatProperty(name="Falloff", default=0.15, min=0.0, subtype='TIME_ABSOLUTE', description="How slowly bands drop")
    show_values: BoolProperty(default=False, options={'HIDDEN'})

    def ln_init(self):
        self.add_in('CHOP', "In")
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "bands")
        layout.prop(self, "gain")
        layout.prop(self, "falloff")

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "freq_low")
        layout.prop(self, "freq_high")
        layout.prop(self, "decibels")

    def cook(self, ctx, inp):
        src = inp.chop()
        p = ctx.p
        bands = max(p.bands, 1)
        if not src or src.num_samples < 16:
            return Channels(["spectrum"], np.zeros((1, bands), np.float32), rate=bands)
        x = src.data.mean(0)
        n = len(x)
        mag = np.abs(np.fft.rfft(x * np.hanning(n))) / (n * 0.25)
        freqs = np.fft.rfftfreq(n, 1.0 / src.rate)
        hi = min(p.freq_high, src.rate * 0.5)
        edges = np.geomspace(max(p.freq_low, 1.0), max(hi, p.freq_low + 1.0), bands + 1)
        idx = np.clip(np.searchsorted(freqs, edges), 1, len(mag) - 1)
        out = np.empty(bands, dtype=np.float32)
        for b in range(bands):
            lo, up = idx[b], max(idx[b + 1], idx[b] + 1)
            out[b] = mag[lo:up].max()
        out *= p.gain
        if p.decibels:
            out = np.clip((20.0 * np.log10(np.maximum(out, 1e-6)) + 60.0) / 60.0, 0.0, 1.0)
        st = ctx.state
        prev = st.get("prev")
        if prev is not None and prev.shape == out.shape and p.falloff > 0:
            out = np.maximum(out, prev * math.exp(-ctx.dt / p.falloff))
        st["prev"] = out
        return Channels(["spectrum"], out.reshape(1, bands), rate=bands)


class LN_AudioAnalysisCHOP(LNNode, bpy.types.Node):
    """Ready-made audio reactive signals: level, bass / mid / high, kick detection"""
    bl_idname = "LN_AudioAnalysisCHOP"
    bl_label = "Audio Analysis CHOP"
    ln_category = "CHOP Audio"

    gain: FloatProperty(name="Gain", default=1.0, min=0.0)
    auto_gain: BoolProperty(name="Auto Gain", default=True, description="Normalise each band against its recent maximum")
    smoothing: FloatProperty(name="Smoothing", default=0.08, min=0.0, subtype='TIME_ABSOLUTE')
    kick_sensitivity: FloatProperty(name="Kick Sensitivity", default=1.5, min=1.0, max=5.0,
                                    description="How far bass must jump above its average to count as a kick")

    def ln_init(self):
        self.add_in('CHOP', "In")
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "gain")
        layout.prop(self, "auto_gain")
        layout.prop(self, "smoothing")
        layout.prop(self, "kick_sensitivity")

    def cook(self, ctx, inp):
        src = inp.chop()
        names = ["level", "peak", "bass", "mid", "high", "kick"]
        if not src or src.num_samples < 16:
            return Channels(names, np.zeros((6, 1), np.float32))
        p = ctx.p
        st = ctx.state
        x = src.data.mean(0)
        n = len(x)
        mag = np.abs(np.fft.rfft(x * np.hanning(n))) / (n * 0.25)
        freqs = np.fft.rfftfreq(n, 1.0 / src.rate)

        def band(lo, hi):
            sel = mag[(freqs >= lo) & (freqs < hi)]
            return float(np.sqrt((sel * sel).mean())) if len(sel) else 0.0

        raw = np.array([float(np.sqrt((x * x).mean())), float(np.abs(x).max()),
                        band(20, 250), band(250, 4000), band(4000, 16000)]) * p.gain
        if p.auto_gain:
            ref = st.get("ref")
            if ref is None:
                ref = np.full(5, 1e-3)
            ref = np.maximum(ref * math.exp(-ctx.dt / 8.0), np.maximum(raw, 1e-4))
            st["ref"] = ref
            raw = raw / ref
        # kick: bass energy jumping above its running average
        avg = st.get("avg", raw[2])
        kick = 1.0 if raw[2] > avg * p.kick_sensitivity and raw[2] > 0.05 and not st.get("hold", 0) > 0 else 0.0
        st["avg"] = avg + (raw[2] - avg) * min(1.0, ctx.dt / 0.4)
        st["hold"] = 0.12 if kick else max(st.get("hold", 0) - ctx.dt, 0.0)
        sm = st.get("sm")
        if sm is None or p.smoothing <= 1e-6:
            sm = raw
        else:
            k = 1.0 - math.exp(-ctx.dt / p.smoothing)
            sm = np.where(raw > sm, raw, sm + (raw - sm) * k)  # instant attack, smooth release
        st["sm"] = sm
        return Channels(names, np.append(sm, kick).reshape(6, 1))


# -- MIDI -----------------------------------------------------------------
class _MidiIn:
    def __init__(self, port_hint):
        rtmidi = deps.require("rtmidi")
        self.midi = rtmidi.MidiIn()
        ports = self.midi.get_ports()
        idx = next((i for i, n in enumerate(ports) if port_hint.lower() in n.lower()), None)
        if idx is None:
            self.midi.delete()
            raise RuntimeError(f"no MIDI input matching '{port_hint}'" if port_hint else "no MIDI input found")
        self.name = ports[idx]
        self.lock = threading.Lock()
        self.values = {}
        self.midi.open_port(idx)
        self.midi.set_callback(self._cb)

    def _cb(self, event, data=None):
        self.handle(event[0])

    def handle(self, msg):
        if len(msg) < 2:
            return
        status, ch = msg[0] & 0xF0, (msg[0] & 0x0F) + 1
        with self.lock:
            if status == 0x90 and len(msg) > 2:
                self.values[f"ch{ch}n{msg[1]}"] = msg[2] / 127.0
            elif status == 0x80:
                self.values[f"ch{ch}n{msg[1]}"] = 0.0
            elif status == 0xB0 and len(msg) > 2:
                self.values[f"ch{ch}c{msg[1]}"] = msg[2] / 127.0
            elif status == 0xE0 and len(msg) > 2:
                self.values[f"ch{ch}pitch"] = ((msg[2] << 7 | msg[1]) - 8192) / 8192.0
            elif status == 0xD0:
                self.values[f"ch{ch}pressure"] = msg[1] / 127.0

    def snapshot(self):
        with self.lock:
            return dict(self.values)

    def close(self):
        self.midi.close_port()
        self.midi.delete()


class LN_MidiInCHOP(LNNode, bpy.types.Node):
    """Notes and controllers from a MIDI device (channels appear as they are touched)"""
    bl_idname = "LN_MidiInCHOP"
    bl_label = "MIDI In CHOP"
    ln_category = "CHOP Input"
    ln_params = False

    port: StringProperty(name="Port", default="", description="Part of the device name; empty = first device")
    pattern: StringProperty(name="Channels", default="*", description="Filter, e.g. 'ch1c*' for the controllers of MIDI channel 1")

    def ln_init(self):
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "port", text="", icon='PLUGIN')
        layout.prop(self, "pattern", text="")

    def ln_draw_ext(self, context, layout):
        rtmidi = deps.load("rtmidi")
        if rtmidi is None:
            layout.label(text="Needs the 'python-rtmidi' module", icon='ERROR')
            return
        try:
            probe = rtmidi.MidiIn()
            ports = probe.get_ports()
            probe.delete()
        except Exception:
            ports = []
        for name in ports[:12]:
            layout.label(text=name, icon='DOT')
        layout.label(text="Names: ch1n60 (note), ch1c7 (controller)")

    def cook(self, ctx, inp):
        dev = services.get("midi_in", self.port, lambda: _MidiIn(self.port))
        vals = dev.snapshot()
        ch = Channels.from_dict(dict(sorted(vals.items())))
        return ch.select(ch.match(self.pattern)) if self.pattern.strip() not in {"", "*"} else ch


# -- OSC ------------------------------------------------------------------
class LN_OscInCHOP(LNNode, bpy.types.Node):
    """Receives OSC messages over UDP; each address becomes a channel"""
    bl_idname = "LN_OscInCHOP"
    bl_label = "OSC In CHOP"
    ln_category = "CHOP Input"
    ln_params = False

    port: IntProperty(name="Port", default=9000, min=1, max=65535)
    pattern: StringProperty(name="Address Filter", default="*", description="Keep addresses matching this pattern, e.g. '/fader*'")

    def ln_init(self):
        self.add_out('CHOP')
        self.add_out('DAT', "Log")

    def ln_draw(self, context, layout):
        layout.prop(self, "port")
        layout.prop(self, "pattern", text="")

    def cook(self, ctx, inp):
        import fnmatch
        server = services.get("osc_in", self.port, lambda: net.OscServer(self.port))
        values, log, _count = server.snapshot()
        pat = self.pattern.strip() or "*"
        out = {}
        for address in sorted(values):
            if not fnmatch.fnmatchcase(address, pat):
                continue
            nums = [float(a) for a in values[address] if isinstance(a, (int, float, bool))]
            name = address.lstrip("/")
            if len(nums) == 1:
                out[name] = nums[0]
            else:
                for i, v in enumerate(nums):
                    out[f"{name}{i + 1}"] = v
        text = "\n".join(f"{addr} {' '.join(str(a) for a in args)}" for _t, addr, args in log[-32:])
        return {"Out": Channels.from_dict(out), "Log": text}


class LN_DmxInCHOP(LNNode, bpy.types.Node):
    """Receives DMX over Art-Net"""
    bl_idname = "LN_DmxInCHOP"
    bl_label = "DMX In CHOP"
    ln_category = "CHOP Input"
    ln_params = False

    universe: IntProperty(name="Universe", default=0, min=0, max=32767)
    count: IntProperty(name="Channels", default=16, min=1, max=512)
    port: IntProperty(name="Port", default=6454, min=1, max=65535)
    show_values: BoolProperty(default=False, options={'HIDDEN'})

    class _Server:
        def __init__(self, port):
            self.universes = {}
            self.udp = net.UdpServer(port, self._packet)

        def _packet(self, data, addr):
            parsed = net.artnet_parse(data)
            if parsed:
                self.universes[parsed[0]] = parsed[1]

        def close(self):
            self.udp.close()

    def ln_init(self):
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "universe")
        layout.prop(self, "count")

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "port")

    def cook(self, ctx, inp):
        server = services.get("artnet_in", self.port, lambda: self._Server(self.port))
        raw = server.universes.get(self.universe, b"")
        vals = np.zeros(self.count, dtype=np.float32)
        n = min(len(raw), self.count)
        vals[:n] = np.frombuffer(raw[:n], dtype=np.uint8) / 255.0
        return Channels([f"dmx{i + 1}" for i in range(self.count)], vals.reshape(-1, 1))


# -- keyboard / mouse -----------------------------------------------------
class LN_KeyboardInCHOP(LNNode, bpy.types.Node):
    """Key states as 0/1 channels (while the engine runs)"""
    bl_idname = "LN_KeyboardInCHOP"
    bl_label = "Keyboard In CHOP"
    ln_category = "CHOP Input"
    ln_params = False
    ln_live = True

    keys: StringProperty(name="Keys", default="SPACE A S D", description="Space separated Blender key names, e.g. SPACE A ONE LEFT_ARROW F1")

    def ln_init(self):
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "keys", text="")

    def cook(self, ctx, inp):
        state = ctx.engine.keys
        names = self.keys.upper().split()
        return Channels([n.lower() for n in names], [[state.get(n, 0.0)] for n in names])


class LN_MouseInCHOP(LNNode, bpy.types.Node):
    """Mouse position (0..1 across the window) and buttons"""
    bl_idname = "LN_MouseInCHOP"
    bl_label = "Mouse In CHOP"
    ln_category = "CHOP Input"
    ln_params = False
    ln_live = True

    def ln_init(self):
        self.add_out('CHOP')

    def cook(self, ctx, inp):
        m = ctx.engine.mouse
        st = ctx.state
        st["wheel"] = st.get("wheel", 0.0) + m["wheel"]
        return Channels.from_dict({"x": m["x"], "y": m["y"], "left": m["left"], "middle": m["middle"],
                                   "right": m["right"], "wheel": st["wheel"]})


# -- Blender data ---------------------------------------------------------
class LN_ObjectCHOP(LNNode, bpy.types.Node):
    """Transform of an object, optionally relative to a second one"""
    bl_idname = "LN_ObjectCHOP"
    bl_label = "Object CHOP"
    ln_category = "CHOP Input"
    ln_params = False

    target: PointerProperty(name="Object", type=bpy.types.Object)
    reference: PointerProperty(name="Relative To", type=bpy.types.Object)
    world: BoolProperty(name="World Space", default=True)

    def ln_init(self):
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "target", text="")
        layout.prop(self, "world")

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "reference")

    def cook(self, ctx, inp):
        ob = self.target
        if ob is None:
            return Channels.empty()
        mat = ob.matrix_world if self.world else ob.matrix_local
        d = {}
        if self.reference is not None:
            mat = self.reference.matrix_world.inverted_safe() @ ob.matrix_world
            d["distance"] = (ob.matrix_world.translation - self.reference.matrix_world.translation).length
        loc, rot, scale = mat.decompose()
        eul = rot.to_euler()
        out = {"tx": loc.x, "ty": loc.y, "tz": loc.z, "rx": eul.x, "ry": eul.y, "rz": eul.z,
               "sx": scale.x, "sy": scale.y, "sz": scale.z}
        out.update(d)
        return Channels.from_dict(out)


ID_KINDS = [('OBJECT', "Object", ""), ('MATERIAL', "Material", ""), ('WORLD', "World", ""), ('SCENE', "Scene", ""),
            ('NODE', "Live Node", "A property of a node in this tree")]


class _DataTarget:
    """Shared UI + lookup for nodes addressing a Blender property by data path."""

    kind: EnumProperty(name="Type", items=ID_KINDS, default='OBJECT')
    ob: PointerProperty(name="Object", type=bpy.types.Object)
    mat: PointerProperty(name="Material", type=bpy.types.Material)
    world: PointerProperty(name="World", type=bpy.types.World)
    scene: PointerProperty(name="Scene", type=bpy.types.Scene)
    node_name: StringProperty(name="Node")
    path: StringProperty(name="Path", default="location", description=(
        "Data path, as shown by 'Copy Data Path' in Blender, e.g. location, rotation_euler[2], "
        "data.energy, modifiers[\"Wave\"].height, [\"my_property\"]"))

    def draw_target(self, layout):
        layout.prop(self, "kind", text="")
        if self.kind == 'OBJECT':
            layout.prop(self, "ob", text="")
        elif self.kind == 'MATERIAL':
            layout.prop(self, "mat", text="")
        elif self.kind == 'WORLD':
            layout.prop(self, "world", text="")
        elif self.kind == 'SCENE':
            layout.prop(self, "scene", text="")
        else:
            layout.prop_search(self, "node_name", self.id_data, "nodes", text="")
        layout.prop(self, "path", text="", icon='RNA')

    def owner(self):
        k = self.kind
        if k == 'OBJECT':
            return self.ob
        if k == 'MATERIAL':
            return self.mat
        if k == 'WORLD':
            return self.world
        if k == 'SCENE':
            return self.scene
        return self.id_data.nodes.get(self.node_name)


class LN_PropertyInCHOP(_DataTarget, LNNode, bpy.types.Node):
    """Reads any Blender property as channels"""
    bl_idname = "LN_PropertyInCHOP"
    bl_label = "Property In CHOP"
    ln_category = "CHOP Input"
    ln_params = False

    channel: StringProperty(name="Channel", default="value")

    def ln_init(self):
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        self.draw_target(layout)

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "channel")

    def cook(self, ctx, inp):
        owner = self.owner()
        if owner is None or not self.path:
            return Channels.empty()
        val = owner.path_resolve(self.path)
        name = self.channel or "value"
        if isinstance(val, (int, float, bool)):
            return Channels([name], [[float(val)]])
        vals = [float(v) for v in val]
        suffix = "xyzw" if len(vals) <= 4 else None
        return Channels([f"{name}{suffix[i] if suffix else i}" for i in range(len(vals))], [[v] for v in vals])


classes = (LN_AudioDeviceInCHOP, LN_AudioFileInCHOP, LN_AudioSpectrumCHOP, LN_AudioAnalysisCHOP, LN_MidiInCHOP,
           LN_OscInCHOP, LN_DmxInCHOP, LN_KeyboardInCHOP, LN_MouseInCHOP, LN_ObjectCHOP, LN_PropertyInCHOP)
