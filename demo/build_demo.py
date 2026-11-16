"""Builds demo/pulsar.blend (+ pulsar_loop.wav next to it).

    blender -b --factory-startup --python demo/build_demo.py
    python3 demo/build_demo.py            # with `pip install bpy`
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bootstrap  # noqa: E402

import bpy  # noqa: E402

ln = _bootstrap.livenodes()
from importlib import import_module  # noqa: E402

pulsar = import_module(ln.__name__ + ".demos.pulsar")
pulsar_audio = import_module(ln.__name__ + ".demos.pulsar_audio")

BLEND = os.path.join(_bootstrap.DEMO, "pulsar.blend")
WAV = os.path.join(_bootstrap.DEMO, "pulsar_loop.wav")

# start from an empty scene
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)
pulsar_audio.write(WAV)
tree = pulsar.build(bpy.context)
tree.nodes["Pulsar Loop"].filepath = WAV
scene = bpy.context.scene
scene.name = "PULSAR"
scene.livenodes.time_mode = 'REALTIME'
scene.livenodes.autostart = False

# the 'PULSAR' workspace tab: 3D view through the camera (the Render TOP draws from it) above the network
wm = bpy.context.window_manager
win = wm.windows[0] if wm.windows else None
ws = bpy.data.workspaces.get("Geometry Nodes")
if win is not None and ws is not None:
    ws.name = "PULSAR"
    win.workspace = ws
    for area in ws.screens[0].areas:
        space = area.spaces.active
        if area.type == 'NODE_EDITOR':
            space.tree_type = tree.bl_idname
            space.node_tree = tree
            space.show_region_ui = True       # the Live sidebar: Start, Perform panel
        elif area.type == 'VIEW_3D':
            space.region_3d.view_perspective = 'CAMERA'
            space.shading.type = 'RENDERED'
            space.overlay.show_overlays = False


bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True, relative_remap=True)
tree.nodes["Pulsar Loop"].filepath = "//pulsar_loop.wav"
bpy.ops.wm.save_mainfile(filepath=BLEND, compress=True)
print(f"saved {BLEND} ({os.path.getsize(BLEND) // 1024} KB) and {WAV}")
