"""CHOP outputs: drive Blender, send OSC / MIDI / DMX, build geometry."""
import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty

from ..core import deps, net, services
from ..core.tree import LNNode
from .chop_io import _DataTarget


def split_path(path):
    """'a.b[2]' -> ('a', 'b', 2); '["x"]' -> ('', '["x"]', None)."""
    path = path.strip()
    index = None
    if path.endswith("]") and not path.endswith('"]') and not path.endswith("']"):
        head, _, tail = path.rpartition("[")
        try:
            index = int(tail[:-1])
            path = head
        except ValueError:
            pass
    if path.endswith('"]') or path.endswith("']"):
        cut = path.rfind("[")
        return path[:cut].rstrip("."), path[cut:], index
    parent, _, attr = path.rpartition(".")
    return parent, attr, index


def write_property(owner, path, values, last=None, eps=1e-7):
    """Assign channel values to `owner.path`. Scalars take values[0];
    vectors take as many components as there are values. Returns the tuple
    written, so callers can skip unchanged frames."""
    parent_path, attr, index = split_path(path)
    parent = owner.path_resolve(parent_path) if parent_path else owner
    custom = attr.startswith("[")
    key = attr[2:-2] if custom else attr
    cur = parent[key] if custom else getattr(parent, key)
    if index is not None or not hasattr(cur, "__len__") or isinstance(cur, str):
        new = (values[0],)
    elif len(values) == 1:
        new = (values[0],) * len(cur)  # one channel drives every component (uniform scale)
    else:
        new = tuple(values[:len(cur)])
    if last is not None and len(last) == len(new) and all(abs(a - b) <= eps for a, b in zip(last, new)):
        return last
    if index is not None:
        cur[index] = type(cur[index])(new[0]) if isinstance(cur[index], (bool, int)) else new[0]
    elif len(new) == 1 and (not hasattr(cur, "__len__") or isinstance(cur, str)):
        v = new[0]
        if isinstance(cur, bool):
            v = v > 0.5
        elif isinstance(cur, int):
            v = int(round(v))
        if custom:
            parent[key] = v
        else:
            setattr(parent, key, v)
    else:
        merged = list(cur)
        merged[:len(new)] = new
        if custom:
            parent[key] = merged
        else:
            setattr(parent, key, merged)
    return new


class LN_ExportCHOP(_DataTarget, LNNode, bpy.types.Node):
    """Drives any Blender property with a channel: objects, lights, cameras, materials, modifiers, Geometry Nodes inputs"""
    bl_idname = "LN_ExportCHOP"
    bl_label = "Export CHOP"
    ln_category = "CHOP Output"
    ln_family = 'OUT'

    channel: StringProperty(name="Channel", default="", description=(
        "Channel(s) to export: empty = all in order. A vector property takes one channel per component; "
        "a single channel sets every component"))
    multiply: FloatProperty(name="Multiply", default=1.0)
    add: FloatProperty(name="Add", default=0.0)
    gn_modifier: StringProperty(name="Modifier", default="", description="Geometry Nodes modifier: Path is then the name of one of its inputs")

    def ln_init(self):
        self.add_in('CHOP', "In")

    def ln_draw(self, context, layout):
        self.draw_target(layout)
        if self.kind == 'OBJECT' and self.ob is not None and any(m.type == 'NODES' for m in self.ob.modifiers):
            layout.prop_search(self, "gn_modifier", self.ob, "modifiers", text="", icon='GEOMETRY_NODES')
        layout.prop(self, "channel", text="", icon='IPO_SINE')
        row = layout.row(align=True)
        row.prop(self, "multiply", text="×")
        row.prop(self, "add", text="+")

    def cook(self, ctx, inp):
        src = inp.chop()
        owner = self.owner()
        if not src or owner is None or not self.path:
            return None
        p = ctx.p
        sel = src.match(self.channel) if self.channel.strip() else range(src.num_channels)
        vals = [float(src.data[i, 0]) * p.multiply + p.add for i in sel]
        if not vals:
            raise ValueError(f"no channel named '{self.channel}'")
        st = ctx.state
        path = self.path
        if self.gn_modifier and self.kind == 'OBJECT':
            path = self._gn_path(owner)
        new = write_property(owner, path, vals, st.get("last"))
        if new is not st.get("last"):
            st["last"] = new
            if self.kind == 'OBJECT' and ("[" in path or ".properties." in path):
                owner.update_tag()  # custom properties and modifier inputs need a nudge
        return None

    def _gn_path(self, ob):
        mod = ob.modifiers.get(self.gn_modifier)
        if mod is None or mod.type != 'NODES' or mod.node_group is None:
            raise ValueError("pick a Geometry Nodes modifier")
        for item in mod.node_group.interface.items_tree:
            if item.item_type == 'SOCKET' and item.in_out == 'INPUT' and item.name == self.path:
                if hasattr(mod, "properties"):  # Blender 5.x: typed modifier interface
                    return f'modifiers["{mod.name}"].properties.inputs.{item.identifier}.value'
                return f'modifiers["{mod.name}"]["{item.identifier}"]'
        raise ValueError(f"modifier has no input named '{self.path}'")


class LN_OscOutCHOP(LNNode, bpy.types.Node):
    """Sends each channel as an OSC message"""
    bl_idname = "LN_OscOutCHOP"
    bl_label = "OSC Out CHOP"
    ln_category = "CHOP Output"
    ln_family = 'OUT'
    ln_params = False

    host: StringProperty(name="Host", default="127.0.0.1")
    port: IntProperty(name="Port", default=9001, min=1, max=65535)
    prefix: StringProperty(name="Prefix", default="/", description="Address prefix; the channel name is appended")
    on_change: BoolProperty(name="Only On Change", default=True)

    def ln_init(self):
        self.add_in('CHOP', "In")

    def ln_draw(self, context, layout):
        row = layout.row(align=True)
        row.prop(self, "host", text="")
        row.prop(self, "port", text="")
        layout.prop(self, "prefix", text="")
        layout.prop(self, "on_change")

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return None
        sender = services.get("udp_out", "plain", lambda: net.UdpSender())
        st = ctx.state
        last = st.setdefault("last", {})
        prefix = "/" + self.prefix.strip("/")
        if not prefix.endswith("/"):
            prefix += "/"
        for name, row in zip(src.names, src.data):
            v = float(row[0])
            if self.on_change and last.get(name) == v:
                continue
            last[name] = v
            sender.send(net.osc_message(prefix + name, v), self.host, self.port)
        return None


class _MidiOut:
    def __init__(self, port_hint):
        rtmidi = deps.require("rtmidi")
        self.midi = rtmidi.MidiOut()
        ports = self.midi.get_ports()
        idx = next((i for i, n in enumerate(ports) if port_hint.lower() in n.lower()), None)
        if idx is None:
            self.midi.delete()
            raise RuntimeError(f"no MIDI output matching '{port_hint}'" if port_hint else "no MIDI output found")
        self.midi.open_port(idx)

    def send(self, msg):
        self.midi.send_message(msg)

    def close(self):
        self.midi.close_port()
        self.midi.delete()


def midi_messages(names, values, last):
    """Channels named ch<N>c<CC> / ch<N>n<NOTE> -> raw MIDI messages for the values that changed."""
    import re
    out = []
    for name, v in zip(names, values):
        m = re.fullmatch(r"ch(\d+)([cn])(\d+)", name)
        if not m:
            continue
        val = int(round(min(max(v, 0.0), 1.0) * 127))
        if last.get(name) == val:
            continue
        last[name] = val
        ch = (int(m.group(1)) - 1) & 0x0F
        num = int(m.group(3)) & 0x7F
        if m.group(2) == "c":
            out.append([0xB0 | ch, num, val])
        else:
            out.append([0x90 | ch, num, val] if val else [0x80 | ch, num, 0])
    return out


class LN_MidiOutCHOP(LNNode, bpy.types.Node):
    """Sends controllers and notes from channels named ch1c7 / ch1n60"""
    bl_idname = "LN_MidiOutCHOP"
    bl_label = "MIDI Out CHOP"
    ln_category = "CHOP Output"
    ln_family = 'OUT'
    ln_params = False

    port: StringProperty(name="Port", default="", description="Part of the device name; empty = first device")

    def ln_init(self):
        self.add_in('CHOP', "In")

    def ln_draw(self, context, layout):
        layout.prop(self, "port", text="", icon='PLUGIN')

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return None
        dev = services.get("midi_out", self.port, lambda: _MidiOut(self.port))
        for msg in midi_messages(src.names, src.data[:, 0], ctx.state.setdefault("last", {})):
            dev.send(msg)
        return None


class LN_DmxOutCHOP(LNNode, bpy.types.Node):
    """Sends channels (0..1) as DMX over Art-Net; channel order = DMX address"""
    bl_idname = "LN_DmxOutCHOP"
    bl_label = "DMX Out CHOP"
    ln_category = "CHOP Output"
    ln_family = 'OUT'
    ln_params = False

    host: StringProperty(name="Host", default="255.255.255.255", description="Node IP, or the broadcast address")
    universe: IntProperty(name="Universe", default=0, min=0, max=32767)
    start: IntProperty(name="Start Address", default=1, min=1, max=512)
    port: IntProperty(name="Port", default=6454, min=1, max=65535)
    rate: FloatProperty(name="Rate", default=40.0, min=1.0, max=44.0, description="Packets per second")

    def ln_init(self):
        self.add_in('CHOP', "In")

    def ln_draw(self, context, layout):
        layout.prop(self, "host", text="")
        layout.prop(self, "universe")
        layout.prop(self, "start")

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "port")
        layout.prop(self, "rate")

    def cook(self, ctx, inp):
        src = inp.chop()
        if not src:
            return None
        st = ctx.state
        if ctx.time - st.get("sent", -1e9) < 1.0 / self.rate and ctx.time >= st.get("sent", 0):
            return None
        st["sent"] = ctx.time
        st["seq"] = st.get("seq", 0) % 255 + 1
        vals = src.data[:, 0] if src.num_samples == 1 or src.num_channels > 1 else src.data[0]
        frame = np.zeros(512, dtype=np.uint8)
        start = self.start - 1
        n = max(0, min(len(vals), 512 - start))
        frame[start:start + n] = np.clip(np.nan_to_num(vals[:n]) * 255.0 + 0.5, 0, 255).astype(np.uint8)
        sender = services.get("udp_out", "broadcast", lambda: net.UdpSender(broadcast=True))
        sender.send(net.artnet_dmx(self.universe, frame[:start + n].tobytes(), st["seq"]), self.host, self.port)
        return None


class LN_ChopToMeshCHOP(LNNode, bpy.types.Node):
    """Writes samples into a mesh as points and attributes, ready for Geometry Nodes"""
    bl_idname = "LN_ChopToMeshCHOP"
    bl_label = "CHOP to Mesh"
    ln_category = "CHOP Output"
    ln_family = 'OUT'
    ln_params = False

    target: PointerProperty(name="Mesh Object", type=bpy.types.Object, poll=lambda self, ob: ob.type == 'MESH',
                            description="Its vertices are replaced: one point per sample")
    layout_mode: EnumProperty(name="Positions", items=[
        ('CHANNELS', "From tx / ty / tz", "Use channels named tx, ty, tz (missing ones are zero)"),
        ('LINE', "Line + Height", "Spread points along X and lift them by the first channel"),
        ('KEEP', "Leave Unchanged", "Only write attributes")], default='LINE')
    spread: FloatProperty(name="Spread", default=4.0, description="Length of the line along X")
    lift: FloatProperty(name="Lift", default=1.0, description="Height multiplier for the first channel")

    def ln_init(self):
        self.add_in('CHOP', "In")

    def ln_draw(self, context, layout):
        layout.prop(self, "target", text="")
        layout.prop(self, "layout_mode", text="")
        if self.layout_mode == 'LINE':
            row = layout.row(align=True)
            row.prop(self, "spread")
            row.prop(self, "lift")

    def cook(self, ctx, inp):
        src = inp.chop()
        ob = self.target
        if not src or ob is None or ob.type != 'MESH':
            return None
        mesh = ob.data
        # one point per sample, or per channel when everything is single-sample
        per_channel = src.num_samples == 1
        n = src.num_channels if per_channel else src.num_samples
        if len(mesh.vertices) != n:
            if self.layout_mode == 'KEEP':
                raise ValueError(f"mesh has {len(mesh.vertices)} vertices, input has {n} samples")
            mesh.clear_geometry()
            mesh.vertices.add(n)
        mode = self.layout_mode
        if mode != 'KEEP':
            co = np.zeros((n, 3), dtype=np.float32)
            if mode == 'LINE':
                co[:, 0] = np.linspace(-0.5, 0.5, n) * self.spread if n > 1 else 0.0
                co[:, 2] = (src.data[:, 0] if per_channel else src.data[0]) * self.lift
            elif not per_channel:
                for axis, cname in enumerate(("tx", "ty", "tz")):
                    row = src.chan(cname)
                    if row is not None:
                        co[:, axis] = row
            mesh.vertices.foreach_set("co", co.ravel())
        if per_channel:
            attrs = {"value": src.data[:, 0]}
        else:
            attrs = {name: row for name, row in zip(src.names, src.data)
                     if not (mode == 'CHANNELS' and name in {"tx", "ty", "tz"})}
        for name, row in attrs.items():
            attr = mesh.attributes.get(name)
            if attr is None or attr.domain != 'POINT' or attr.data_type != 'FLOAT':
                if attr is not None:
                    mesh.attributes.remove(attr)
                attr = mesh.attributes.new(name, 'FLOAT', 'POINT')
            attr.data.foreach_set("value", np.ascontiguousarray(row, dtype=np.float32))
        mesh.update()
        return None


classes = (LN_ExportCHOP, LN_OscOutCHOP, LN_MidiOutCHOP, LN_DmxOutCHOP, LN_ChopToMeshCHOP)
