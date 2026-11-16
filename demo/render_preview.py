"""Renders the PULSAR network to an MP4 with its soundtrack, frame by frame.

    blender -b demo/pulsar.blend --python demo/render_preview.py -- out.mp4 [width height fps seconds]
    python3 demo/render_preview.py demo/pulsar.blend out.mp4 1280 720 30   # with `pip install bpy`

Uses the Timeline clock, so the result is identical on every run and independent
of how fast this machine is. Needs ffmpeg on the PATH.
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bootstrap  # noqa: E402

import bpy  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
blend = args.pop(0) if args and args[0].endswith(".blend") else None
out = os.path.abspath(args[0] if args else "pulsar_preview.mp4")
width, height, fps = (int(args[1]), int(args[2]), int(args[3])) if len(args) >= 4 else (1280, 720, 30)
ln = _bootstrap.livenodes()
if blend:  # python3 demo/render_preview.py demo/pulsar.blend out.mp4 ...
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
from importlib import import_module  # noqa: E402

engine = import_module(ln.__name__ + ".core.engine").ENGINE
encode_rgba8 = import_module(ln.__name__ + ".nodes.top_io").encode_rgba8
pulsar_audio = import_module(ln.__name__ + ".demos.pulsar_audio")

tree = bpy.data.node_groups.get("PULSAR")
if tree is None:  # not opened from pulsar.blend: build it
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    tree = import_module(ln.__name__ + ".demos.pulsar").build(bpy.context)
seconds = float(args[4]) if len(args) >= 5 else pulsar_audio.LENGTH
scene = bpy.context.scene
s = scene.livenodes
s.time_mode = 'TIMELINE'
s.res_x, s.res_y = width, height
wav = bpy.path.abspath(tree.nodes["Pulsar Loop"].filepath)
final = tree.nodes.get("Overlay") or next(n for n in tree.nodes if n.bl_idname == "LN_OutTOP")

ffmpeg = subprocess.Popen(
    ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{width}x{height}",
     "-r", str(fps), "-i", "-", "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow",
     "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out],
    stdin=subprocess.PIPE)


class _Ctx:
    state = {}
    time = 0.0


engine.reset()
frames = int(round(seconds * fps))
t0 = time.perf_counter()
for f in range(frames):
    engine.tick(scene, now_time=f / fps, dt=1.0 / fps)
    tex = engine.outputs[f"{tree.name}\x00{final.name}"]["Out"]
    ffmpeg.stdin.write(encode_rgba8(_Ctx, tex, (width, height)).tobytes())
    if f % fps == 0:
        print(f"  {f / fps:5.1f}s / {seconds:.1f}s   ({(time.perf_counter() - t0) / (f + 1):.2f} s per frame)", flush=True)
if engine.errors:
    print("node errors:", engine.errors)
ffmpeg.stdin.close()
ffmpeg.wait()
engine.shutdown()
print(f"wrote {out}")
