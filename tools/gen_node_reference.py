"""Generates docs/NODES.md from the node classes themselves.

    python3 tools/gen_node_reference.py          # needs `pip install bpy`
    blender -b --factory-startup --python tools/gen_node_reference.py

Every node is instantiated in a scratch tree to read its sockets and properties,
and cooked once (devices excluded) to list the channels it produces.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

if bpy.app.background:
    import gpu
    try:
        gpu.init()
    except Exception:
        pass

import livenodes  # noqa: E402

if not hasattr(bpy.types.Scene, "livenodes"):
    livenodes.register()

from livenodes.core.data import Channels  # noqa: E402
from livenodes.core.engine import ENGINE  # noqa: E402
from livenodes.ui.menus import CATEGORY_ORDER  # noqa: E402

OUT = os.path.join(ROOT, "docs", "NODES.md")
FAMILY = {"LNSocketCHOP": "CHOP", "LNSocketTOP": "TOP", "LNSocketDAT": "DAT"}
COMMON_TOP = {"res_mode", "res_x", "res_y"}
# nodes that need hardware, a network port or a user file to produce output
NO_COOK = {"LN_AudioDeviceInCHOP", "LN_MidiInCHOP", "LN_MidiOutCHOP", "LN_VideoDeviceTOP", "LN_RenderTOP",
           "LN_OscInCHOP", "LN_DmxInCHOP", "LN_UdpInDAT", "LN_GlslTOP", "LN_StreamOutTOP", "LN_ScriptNode"}
REQUIRES = {
    "LN_AudioDeviceInCHOP": "`sounddevice`",
    "LN_MidiInCHOP": "`python-rtmidi`",
    "LN_MidiOutCHOP": "`python-rtmidi`",
    "LN_VideoDeviceTOP": "`opencv-python-headless`",
    "LN_MovieFileTOP": "`opencv-python-headless`",
    "LN_MovieFileOutTOP": "`opencv-python-headless` (MP4 only)",
    "LN_StreamOutTOP": "`ndi-python` (NDI), `SpoutGL` (Spout, Windows) or `syphon-python` (Syphon, macOS)",
}
# channels of nodes whose output only exists with a file, device, port or input
CHANNELS = {
    "LN_AudioFileInCHOP": "Out: `chan1` (mono) or `chan1`, `chan2`… — the last *Samples* audio samples at the play "
                          "position · Info: `position`, `length`, `fraction`, `playing`",
    "LN_AudioDeviceInCHOP": "`chan1`, `chan2`… — the last *Samples* samples of each input channel",
    "LN_AudioSpectrumCHOP": "`spectrum` — one sample per band, low to high",
    "LN_MidiInCHOP": "created as controls are touched: `ch1n60` (note velocity 0–1), `ch1c7` (controller 0–1), "
                     "`ch1pitch` (−1–1), `ch1pressure` (0–1)",
    "LN_OscInCHOP": "Out: one channel per address, without the leading `/` (`fader/1`); messages with several "
                    "numbers give `address1`, `address2`… · Log (DAT): the last 32 messages",
    "LN_DmxInCHOP": "`dmx1` … `dmxN` (0–1)",
    "LN_ObjectCHOP": "`tx` `ty` `tz` `rx` `ry` `rz` `sx` `sy` `sz` (+ `distance` with *Relative To*)",
    "LN_PropertyInCHOP": "`value` for a single number; `valuex` `valuey`… for vectors (the name is set by *Channel*)",
    "LN_TopToCHOP": "`r` `g` `b` `a` (one sample, or *Samples* samples in Row mode)",
    "LN_MovieFileTOP": "Out: the frame · Info: `index`, `fraction`, `length`, `fps`",
    "LN_StreamOutTOP": "Info: `active`, `receivers`, `sent`, `width`, `height`",
    "LN_ScriptNode": "whatever `cook()` returns: a dict becomes channels, a string or rows become data, "
                     "a GPU texture becomes the Texture output",
    "LN_DatToCHOP": "named after the table (first column, or first row in *Columns* layout)",
}
EXTRA_NOTES = {
    "LN_StreamOutTOP": "the default protocol is the native one of the operating system (Spout on Windows, "
                       "Syphon on macOS, NDI elsewhere)",
    "LN_RenderTOP": "Viewport method needs a 3D View open in some window; without a window it falls back to "
                    "Final Render",
    "LN_GlslTOP": "see the manual's GLSL chapter for the variables and helpers available to the shader",
}
TYPE_NAMES = {"BOOLEAN": "on/off", "INT": "integer", "FLOAT": "number", "STRING": "text", "ENUM": "choice",
              "POINTER": "data-block"}


def anchor(text):
    keep = "".join(ch.lower() if ch.isalnum() else ("-" if ch in " -" else "") for ch in text)
    return keep.strip("-")


def fmt_num(v):
    if isinstance(v, bool):
        return "on" if v else "off"
    if isinstance(v, int):
        return str(v)
    if math.isinf(v) or abs(v) >= 1e30:
        return "∞" if v > 0 else "-∞"
    if v == int(v) and abs(v) < 1e6:
        return f"{v:.1f}"
    return f"{v:.4g}"


def fmt_default(prop):
    t = prop.type
    if t in {"FLOAT", "INT", "BOOLEAN"} and getattr(prop, "array_length", 0):
        return "(" + ", ".join(fmt_num(v) for v in prop.default_array) + ")"
    if t in {"FLOAT", "INT", "BOOLEAN"}:
        return fmt_num(prop.default)
    if t == "STRING":
        return f"`{prop.default}`" if prop.default else "—"
    if t == "ENUM":
        return f"`{prop.default}`"
    if t == "POINTER":
        return "none"
    return ""


def fmt_notes(prop):
    notes = []
    if prop.description:
        notes.append(prop.description.rstrip(".") + ".")
    if prop.type == "ENUM":
        items = []
        for it in prop.enum_items:
            d = f" — {it.description}" if it.description else ""
            items.append(f"`{it.identifier}` {it.name}{d}")
        notes.append("Options: " + "; ".join(items) + ".")
    if prop.type in {"FLOAT", "INT"}:
        lo, hi = prop.soft_min, prop.soft_max
        if prop.type == "FLOAT" and prop.subtype == "COLOR":
            pass
        elif not (abs(lo) > 1e8 and abs(hi) > 1e8):
            unit = " (radians)" if prop.subtype == "ANGLE" else (" s" if prop.subtype == "TIME_ABSOLUTE" else "")
            notes.append(f"Range {fmt_num(lo)} – {fmt_num(hi)}{unit}.")
        elif prop.subtype == "ANGLE":
            notes.append("In radians (shown in degrees).")
    if prop.type == "POINTER":
        notes.append(f"A Blender {prop.fixed_type.bl_rna.name}.")
    if prop.type == "STRING" and prop.subtype == "FILE_PATH":
        notes.append("File path (`//` = relative to the .blend).")
    return " ".join(notes).replace("|", "\\|")


def socket_list(sockets):
    return ", ".join(f"{s.name} ({FAMILY.get(s.bl_idname, '?')}{', multi' if getattr(s, 'is_multi_input', False) else ''})"
                     for s in sockets) or "—"


def main():
    for tree in [t for t in bpy.data.node_groups if t.bl_idname == "LiveNodeTree"]:
        bpy.data.node_groups.remove(tree)
    tree = bpy.data.node_groups.new("Reference", "LiveNodeTree")
    base = set(bpy.types.Node.bl_rna.properties.keys())
    scene = bpy.context.scene
    scene.livenodes.res_x, scene.livenodes.res_y = 64, 36
    classes = livenodes.node_classes()
    nodes = {cls.bl_idname: tree.nodes.new(cls.bl_idname) for cls in classes}
    for idname, node in nodes.items():
        if idname in NO_COOK:
            node.mute = True
    ENGINE.reset()
    for i in range(3):
        ENGINE.tick(scene, now_time=(i + 1) / 30, dt=1 / 30)
    ENGINE.stop()

    by_cat = {}
    for cls in classes:
        by_cat.setdefault(cls.ln_category, []).append(cls)
    cats = [c for c in CATEGORY_ORDER if c in by_cat] + sorted(set(by_cat) - set(CATEGORY_ORDER))

    lines = ["# Live Nodes — node reference", "",
             f"Generated from the add-on's code by `tools/gen_node_reference.py` — {len(classes)} nodes. "
             "See the [manual](MANUAL.md) for concepts and workflows.", "",
             "Conventions:", "",
             "- **Params**: ✓ means the parameter can be driven by a channel of the same name on the node's "
             "*Params* input (vector parameters by component: `name.x`, `name.r`, `name0`…).",
             "- Every TOP also has the common resolution settings described in "
             "[TOP resolution](#top-resolution-common-to-every-top).",
             "- **Output channels** are the names a node produces with its default settings; filters "
             "generally keep the names of their input.", "",
             "## Contents", ""]
    for cat in cats:
        lines.append(f"- **{cat}** — " + ", ".join(f"[{c.bl_label}](#{anchor(c.bl_label)})"
                                                   for c in sorted(by_cat[cat], key=lambda c: c.bl_label)))
    lines += ["", "## TOP resolution (common to every TOP)", "",
              "| Parameter | Identifier | Type | Default | Notes |", "|---|---|---|---|---|"]
    some_top = nodes["LN_LevelTOP"]
    for ident in ("res_mode", "res_x", "res_y"):
        prop = some_top.bl_rna.properties[ident]
        lines.append(f"| {prop.name} | `{ident}` | {TYPE_NAMES[prop.type]} | {fmt_default(prop)} | {fmt_notes(prop)} |")
    lines.append("")

    for cat in cats:
        lines += [f"## {cat}", ""]
        for cls in sorted(by_cat[cat], key=lambda c: c.bl_label):
            node = nodes[cls.bl_idname]
            doc = (cls.__doc__ or "").strip().split("\n")[0]
            lines += [f"### {cls.bl_label}", "", f"`{cls.bl_idname}` · family **{cls.ln_family}**", "", doc + ".", ""]
            rows = [("Inputs", socket_list(node.inputs)), ("Outputs", socket_list(node.outputs))]
            outs = ENGINE.outputs.get(f"{tree.name}\x00{node.name}", {})
            chans = []
            for sock, val in outs.items():
                if isinstance(val, Channels) and val.num_channels:
                    names = ", ".join(f"`{n}`" for n in val.names[:12]) + (" …" if val.num_channels > 12 else "")
                    samples = f" ({val.num_samples} samples)" if val.num_samples > 1 else ""
                    chans.append(f"{sock}: {names}{samples}" if len(node.outputs) > 1 else names + samples)
            if cls.bl_idname in CHANNELS:
                rows.append(("Output channels", CHANNELS[cls.bl_idname]))
            elif chans:
                rows.append(("Output channels", " · ".join(chans)))
            if cls.bl_idname in REQUIRES:
                rows.append(("Requires", REQUIRES[cls.bl_idname]))
            flags = []
            if getattr(cls, "ln_live", False):
                flags.append("reads the keyboard/mouse while the engine runs (Capture Keyboard & Mouse)")
            if getattr(cls, "ln_writes_scene", False):
                flags.append("writes Blender data — cooked before nodes that read the scene")
            if getattr(cls, "ln_reads_scene", False):
                flags.append("reads Blender data — cooked after nodes that write it")
            if cls.bl_idname in EXTRA_NOTES:
                flags.append(EXTRA_NOTES[cls.bl_idname])
            if flags:
                rows.append(("Notes", "; ".join(flags)))
            lines += ["| | |", "|---|---|"] + [f"| {k} | {v} |" for k, v in rows] + [""]
            props = [p for p in node.bl_rna.properties
                     if p.identifier not in base and p.identifier not in COMMON_TOP
                     and not p.is_hidden and p.identifier != "rna_type"]
            if props:
                drivable = getattr(cls, "ln_params", True)
                lines += ["| Parameter | Identifier | Type | Default | Params | Notes |", "|---|---|---|---|---|---|"]
                for p in props:
                    tname = TYPE_NAMES.get(p.type, p.type.lower())
                    if p.type in {"FLOAT", "INT", "BOOLEAN"} and getattr(p, "array_length", 0):
                        tname = "colour" if p.subtype == "COLOR" else f"{p.array_length} × {tname}"
                    ok = "✓" if drivable and p.type in {"FLOAT", "INT", "BOOLEAN"} else ""
                    lines.append(f"| {p.name} | `{p.identifier}` | {tname} | {fmt_default(p)} | {ok} | {fmt_notes(p)} |")
                lines.append("")
    bpy.data.node_groups.remove(tree)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines).rstrip() + "\n")
    print(f"wrote {OUT}: {len(classes)} nodes")


main()
