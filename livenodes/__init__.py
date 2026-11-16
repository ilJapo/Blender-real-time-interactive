"""Live Nodes: a real-time node engine for Blender.

Operator families like a real-time visual programming environment:
  CHOP - channels (control signals, audio, MIDI, OSC, DMX)
  TOP  - GPU textures (GLSL shaders, compositing, feedback, video)
  DAT  - text, tables and Python scripts
"""

bl_info = {
    "name": "Live Nodes",
    "author": "Live Nodes contributors",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "Node Editor > Live Nodes tree type, sidebar > Live",
    "description": "Real-time interactive visuals: channels, GPU textures, audio, MIDI, OSC, DMX, video and scripting",
    "category": "Node",
}

import bpy

from .core import engine, tree
from .nodes import chop_filter, chop_gen, chop_io, chop_out, dat, top_filter, top_gen, top_io
from .ui import display, menus, operators, settings
from . import examples

NODE_MODULES = (chop_gen, chop_filter, chop_io, chop_out, top_gen, top_filter, top_io, dat)
_registered = []
_keymaps = []


def node_classes():
    out = []
    for mod in NODE_MODULES:
        out.extend(c for c in mod.classes if issubclass(c, bpy.types.Node))
    return out


def _all_classes():
    classes = list(settings.classes) + list(tree.classes)
    for mod in NODE_MODULES:
        classes.extend(mod.classes)
    classes += list(operators.classes) + list(examples.classes)
    classes += menus.build(node_classes())
    from .ui import panels
    classes += list(panels.classes)
    return classes


def register():
    for cls in _all_classes():
        bpy.utils.register_class(cls)
        _registered.append(cls)
    settings.register()
    engine.register()
    menus.register()
    display.register()
    kc = bpy.context.window_manager.keyconfigs.addon if bpy.context.window_manager else None
    if kc is not None:
        km = kc.keymaps.new(name="Node Editor", space_type='NODE_EDITOR')
        kmi = km.keymap_items.new("livenodes.toggle", 'SPACE', 'PRESS', ctrl=True, shift=True)
        _keymaps.append((km, kmi))


def unregister():
    for km, kmi in _keymaps:
        km.keymap_items.remove(kmi)
    _keymaps.clear()
    display.unregister()
    menus.unregister()
    engine.unregister()
    from .core import gpu_util
    gpu_util.free_all()
    settings.unregister()
    for cls in reversed(_registered):
        bpy.utils.unregister_class(cls)
    _registered.clear()
