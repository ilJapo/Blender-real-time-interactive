"""DAT nodes: text, tables and Python scripting."""
import csv
import io
import math
import os

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty

from ..core import net, services
from ..core.data import Channels
from ..core.tree import LNNode


def as_table(value):
    """DAT value -> list of rows (lists of strings)."""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip("\n")
        if not text:
            return []
        dialect = "excel-tab" if "\t" in text.split("\n", 1)[0] else "excel"
        return [row for row in csv.reader(io.StringIO(text), dialect=dialect)]
    return [[str(c) for c in row] for row in value]


def as_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return "\n".join("\t".join(str(c) for c in row) for row in value)


class _Dat(LNNode):
    ln_family = 'DAT'
    ln_category = "DAT"
    ln_params = False


class LN_TextDAT(_Dat, bpy.types.Node):
    """Text from a Blender text block or typed in"""
    bl_idname = "LN_TextDAT"
    bl_label = "Text DAT"

    text: PointerProperty(name="Text Block", type=bpy.types.Text)
    value: StringProperty(name="Text", default="")

    def ln_init(self):
        self.add_out('DAT')

    def ln_draw(self, context, layout):
        layout.prop(self, "text", text="")
        if self.text is None:
            layout.prop(self, "value", text="")

    def cook(self, ctx, inp):
        return self.text.as_string() if self.text is not None else self.value


class LN_TableDAT(_Dat, bpy.types.Node):
    """A table (CSV or tab separated) from a text block; pick cells by row and column"""
    bl_idname = "LN_TableDAT"
    bl_label = "Table DAT"

    text: PointerProperty(name="Text Block", type=bpy.types.Text)

    def ln_init(self):
        self.add_in('DAT', "In")
        self.add_out('DAT')

    def ln_draw(self, context, layout):
        layout.prop(self, "text", text="")

    def cook(self, ctx, inp):
        src = inp.get("In")
        if src is None and self.text is not None:
            src = self.text.as_string()
        return as_table(src)


class LN_FileInDAT(_Dat, bpy.types.Node):
    """Reads a text / CSV / JSON file from disk, reloading when it changes"""
    bl_idname = "LN_FileInDAT"
    bl_label = "File In DAT"

    filepath: StringProperty(name="File", subtype='FILE_PATH')
    as_table_: BoolProperty(name="Parse as Table", default=False)

    def ln_init(self):
        self.add_out('DAT')

    def ln_draw(self, context, layout):
        layout.prop(self, "filepath", text="")
        layout.prop(self, "as_table_")

    def cook(self, ctx, inp):
        path = bpy.path.abspath(self.filepath)
        if not path:
            return ""
        st = ctx.state
        if ctx.time - st.get("checked", -1.0) > 0.5 or "data" not in st:
            st["checked"] = ctx.time
            mtime = os.path.getmtime(path)
            if mtime != st.get("mtime"):
                with open(path, encoding="utf-8", errors="replace") as fh:
                    st["data"] = fh.read()
                st["mtime"] = mtime
        return as_table(st["data"]) if self.as_table_ else st["data"]


class LN_UdpInDAT(_Dat, bpy.types.Node):
    """Lines of text received over UDP"""
    bl_idname = "LN_UdpInDAT"
    bl_label = "UDP In DAT"

    port: IntProperty(name="Port", default=7000, min=1, max=65535)
    keep: IntProperty(name="Keep Lines", default=10, min=1, max=256)

    def ln_init(self):
        self.add_out('DAT')

    def ln_draw(self, context, layout):
        layout.prop(self, "port")
        layout.prop(self, "keep")

    def cook(self, ctx, inp):
        server = services.get("udp_lines", self.port, lambda: net.LineServer(self.port))
        return "\n".join(list(server.lines)[-self.keep:])


class LN_DatToCHOP(LNNode, bpy.types.Node):
    """Numbers in a table become channels"""
    bl_idname = "LN_DatToCHOP"
    bl_label = "DAT to CHOP"
    ln_category = "DAT"
    ln_params = False

    layout_mode: EnumProperty(name="Layout", items=[
        ('NAME_VALUE', "Name | Value", "First column names, second column values"),
        ('COLUMNS', "Columns", "First row names, each column a channel (rows become samples)"),
        ('ROWS', "Rows", "First column names, each row a channel (columns become samples)")], default='NAME_VALUE')

    def ln_init(self):
        self.add_in('DAT', "In")
        self.add_out('CHOP')

    def ln_draw(self, context, layout):
        layout.prop(self, "layout_mode", text="")

    def cook(self, ctx, inp):
        rows = as_table(inp.get("In"))
        if not rows:
            return Channels.empty()

        def num(s):
            try:
                return float(s)
            except (TypeError, ValueError):
                return 0.0

        if self.layout_mode == 'NAME_VALUE':
            return Channels.from_dict({r[0]: num(r[1]) if len(r) > 1 else 0.0 for r in rows if r})
        if self.layout_mode == 'ROWS':
            return Channels.from_dict({r[0]: [num(c) for c in r[1:]] or [0.0] for r in rows if r})
        head, body = rows[0], rows[1:]
        return Channels.from_dict({name: [num(r[i]) if i < len(r) else 0.0 for r in body] or [0.0]
                                   for i, name in enumerate(head)})


class LN_ChopToDAT(_Dat, bpy.types.Node):
    """Channels as a name | value table"""
    bl_idname = "LN_ChopToDAT"
    bl_label = "CHOP to DAT"

    digits: IntProperty(name="Digits", default=3, min=0, max=9)

    def ln_init(self):
        self.add_in('CHOP', "In")
        self.add_out('DAT')

    def ln_draw(self, context, layout):
        layout.prop(self, "digits")

    def cook(self, ctx, inp):
        src = inp.chop()
        return [[n, f"{row[0]:.{self.digits}f}"] for n, row in zip(src.names, src.data)]


class LN_FormatDAT(_Dat, bpy.types.Node):
    """Builds text from channels with Python formatting, e.g. 'BPM {bpm:.0f}'"""
    bl_idname = "LN_FormatDAT"
    bl_label = "Format DAT"

    template: StringProperty(name="Template", default="{seconds:.1f}",
                             description="Python format string; {name} is replaced by that channel's value")

    def ln_init(self):
        self.add_in('CHOP', "In")
        self.add_out('DAT')

    def ln_draw(self, context, layout):
        layout.prop(self, "template", text="")

    def cook(self, ctx, inp):
        values = inp.chop().to_dict()
        values.update(time=ctx.time, frame=ctx.frame)
        return self.template.format_map(_Missing(values))


class _Missing(dict):
    def __missing__(self, key):
        return 0.0


# -- scripting ------------------------------------------------------------
SCRIPT_TEMPLATE = '''"""Live Nodes script.

cook(ctx, inputs) runs every frame. Return:
  * a dict {name: value or list}  -> channels (CHOP)
  * a str or list of rows         -> data (DAT)
  * a GPU texture                 -> texture (TOP)

ctx.time, ctx.dt, ctx.frame, ctx.state (dict kept between frames),
ctx.output_of("Node Name"), ctx.scene.
inputs.chop("In").to_dict() / .data (numpy), inputs.get("In 1") ...
"""
import math


def cook(ctx, inputs):
    chans = inputs.chop("In").to_dict()
    ctx.state["count"] = ctx.state.get("count", 0) + 1
    return {
        "wave": math.sin(ctx.time * 2.0),
        "count": ctx.state["count"],
        "sum": sum(chans.values()),
    }
'''


class LN_OT_new_script(bpy.types.Operator):
    """Create a text block with a starter script and assign it to this node"""
    bl_idname = "livenodes.new_script"
    bl_label = "New Script"
    bl_options = {'INTERNAL', 'UNDO'}

    tree: StringProperty()
    node: StringProperty()

    def execute(self, context):
        tree = bpy.data.node_groups.get(self.tree)
        node = tree.nodes.get(self.node) if tree else None
        if node is None:
            return {'CANCELLED'}
        text = bpy.data.texts.new("live_script.py")
        text.write(SCRIPT_TEMPLATE)
        node.script = text
        return {'FINISHED'}


class LN_ScriptNode(LNNode, bpy.types.Node):
    """Runs your Python every frame: anything Blender's Python can do"""
    bl_idname = "LN_ScriptNode"
    bl_label = "Script"
    ln_category = "DAT"
    ln_family = 'DAT'
    ln_params = False

    script: PointerProperty(name="Script", type=bpy.types.Text)

    def ln_init(self):
        self.add_in('CHOP', "In")
        self.add_in('TOP', "In 1")
        self.add_in('DAT', "In 2")
        self.add_out('CHOP', "Channels")
        self.add_out('TOP', "Texture")
        self.add_out('DAT', "Data")

    def ln_draw(self, context, layout):
        row = layout.row(align=True)
        row.prop(self, "script", text="")
        if self.script is None:
            op = row.operator("livenodes.new_script", text="", icon='ADD')
            op.tree = self.id_data.name
            op.node = self.name

    def cook(self, ctx, inp):
        if self.script is None:
            return {}
        st = ctx.state
        src = self.script.as_string()
        if st.get("src") != src:
            env = {"__name__": f"livenodes_script_{self.name}", "bpy": bpy, "np": np, "math": math, "Channels": Channels}
            exec(compile(src, self.script.name, "exec"), env)
            if not callable(env.get("cook")):
                raise ValueError("script must define cook(ctx, inputs)")
            st["fn"] = env["cook"]
            st["src"] = src
            st["user"] = {}
        result = st["fn"](_ScriptContext(ctx, st["user"]), inp)
        if result is None:
            return {}
        if isinstance(result, Channels):
            return {"Channels": result}
        if isinstance(result, dict):
            return {"Channels": Channels.from_dict(result)}
        if isinstance(result, (str, list, tuple)):
            return {"Data": result}
        if hasattr(result, "width") and hasattr(result, "height"):
            return {"Texture": result}
        raise TypeError(f"cook() returned an unsupported {type(result).__name__}")


class _ScriptContext:
    """What scripts see: the cook context with a private `state` dict."""

    def __init__(self, ctx, user_state):
        self._ctx = ctx
        self.state = user_state

    def __getattr__(self, name):
        return getattr(self._ctx, name)

    def output_of(self, node_name, socket=None):
        return self._ctx.output_of(node_name, socket)


class LN_ExecuteDAT(LNNode, bpy.types.Node):
    """Runs Python when channels change: switch scenes, fire operators, trigger anything"""
    bl_idname = "LN_ExecuteDAT"
    bl_label = "Execute DAT"
    ln_category = "DAT"
    ln_family = 'DAT'
    ln_params = False

    on: EnumProperty(name="Run On", items=[('RISE', "Off to On", "When a channel rises above 0.5"),
                                           ('FALL', "On to Off", "When a channel drops below 0.5"),
                                           ('CHANGE', "Value Change", "Whenever a value changes")], default='RISE')
    code: StringProperty(name="Code", default="print(name, value)",
                         description="Python run per event. Variables: name, value, prev, ctx, bpy, scene")
    script: PointerProperty(name="Script", type=bpy.types.Text, description="Optional: runs the whole text block instead of Code")

    def ln_init(self):
        self.add_in('CHOP', "In")

    def ln_draw(self, context, layout):
        layout.prop(self, "on", text="")
        layout.prop(self, "code", text="")
        layout.prop(self, "script", text="")

    def cook(self, ctx, inp):
        src = inp.chop()
        st = ctx.state
        prev = st.get("prev", {})
        cur = src.to_dict()
        st["prev"] = cur
        if not prev:
            return None
        events = []
        for name, value in cur.items():
            old = prev.get(name)
            if old is None:
                continue
            if self.on == 'RISE' and old <= 0.5 < value:
                events.append((name, value, old))
            elif self.on == 'FALL' and old > 0.5 >= value:
                events.append((name, value, old))
            elif self.on == 'CHANGE' and old != value:
                events.append((name, value, old))
        if not events:
            return None
        code = self.script.as_string() if self.script is not None else self.code
        key = ("code", code)
        if st.get("key") != key:
            st["compiled"] = compile(code, self.script.name if self.script else "<execute>", "exec")
            st["key"] = key
        for name, value, old in events:
            exec(st["compiled"], {"bpy": bpy, "np": np, "math": math, "ctx": ctx, "scene": ctx.scene,
                                  "name": name, "value": value, "prev": old})
        return None


# -- controls -------------------------------------------------------------
class LN_ControlCHOP(LNNode, bpy.types.Node):
    """A slider, button or toggle shown in the Perform panel (3D View and Node Editor sidebar)"""
    bl_idname = "LN_ControlCHOP"
    bl_label = "Control CHOP"
    ln_category = "CHOP Generate"
    ln_params = False

    kind: EnumProperty(name="Type", items=[('SLIDER', "Slider", ""), ('TOGGLE', "Toggle", ""),
                                           ('BUTTON', "Momentary", "On for a short moment when pressed"),
                                           ('XY', "XY Pad", "Two sliders")], default='SLIDER')
    channel: StringProperty(name="Channel", default="slider")
    value: FloatProperty(name="Value", default=0.0, soft_min=0.0, soft_max=1.0)
    value_y: FloatProperty(name="Y", default=0.0, soft_min=0.0, soft_max=1.0)
    toggle: BoolProperty(name="On", default=False)
    pressed_at: FloatProperty(default=-1.0, options={'HIDDEN', 'SKIP_SAVE'})
    show_in_panel: BoolProperty(name="Show in Perform Panel", default=True)
    order: IntProperty(name="Panel Order", default=0)

    def ln_init(self):
        self.add_out('CHOP')

    def draw_widget(self, layout, label=True):
        text = (self.label or self.channel) if label else ""
        if self.kind == 'SLIDER':
            layout.prop(self, "value", text=text, slider=True)
        elif self.kind == 'XY':
            col = layout.column(align=True)
            col.prop(self, "value", text=f"{text} X" if text else "X", slider=True)
            col.prop(self, "value_y", text=f"{text} Y" if text else "Y", slider=True)
        elif self.kind == 'TOGGLE':
            layout.prop(self, "toggle", text=text, toggle=True)
        else:
            op = layout.operator("livenodes.control_press", text=text or "Press")
            op.tree = self.id_data.name
            op.node = self.name

    def ln_draw(self, context, layout):
        layout.prop(self, "kind", text="")
        layout.prop(self, "channel", text="")
        self.draw_widget(layout, label=False)

    def ln_draw_ext(self, context, layout):
        layout.prop(self, "show_in_panel")
        layout.prop(self, "order")

    def cook(self, ctx, inp):
        name = self.channel or "value"
        if self.kind == 'SLIDER':
            return Channels([name], [[self.value]])
        if self.kind == 'XY':
            return Channels([f"{name}x", f"{name}y"], [[self.value], [self.value_y]])
        if self.kind == 'TOGGLE':
            return Channels([name], [[1.0 if self.toggle else 0.0]])
        st = ctx.state
        pressed = st.pop("press", False)
        return Channels([name], [[1.0 if pressed else 0.0]])


class LN_OT_control_press(bpy.types.Operator):
    """Fire this momentary button"""
    bl_idname = "livenodes.control_press"
    bl_label = "Press"
    bl_options = {'INTERNAL'}

    tree: StringProperty()
    node: StringProperty()

    def execute(self, context):
        from ..core.engine import ENGINE
        ENGINE.states.setdefault(f"{self.tree}\x00{self.node}", {})["press"] = True
        return {'FINISHED'}


classes = (LN_OT_new_script, LN_OT_control_press, LN_TextDAT, LN_TableDAT, LN_FileInDAT, LN_UdpInDAT,
           LN_DatToCHOP, LN_ChopToDAT, LN_FormatDAT, LN_ScriptNode, LN_ExecuteDAT, LN_ControlCHOP)
