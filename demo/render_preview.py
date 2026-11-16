"""Renders the PULSAR network to an MP4 with its soundtrack, frame by frame.

    blender -b demo/pulsar.blend --python demo/render_preview.py -- out.mp4 [width height fps seconds]
    python3 demo/render_preview.py demo/pulsar.blend out.mp4 1280 720 30   # with `pip install bpy`

Uses the Timeline clock, so the result does not depend on how fast the machine is.
The video is made in segments, each in a fresh process with a short pre-roll that
rebuilds trails and envelopes: headless Blender never ends a GPU frame, so a long
single run slowly exhausts GPU memory. Needs ffmpeg on the PATH.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bootstrap  # noqa: E402

import bpy  # noqa: E402

SEGMENT = 120      # frames per process
PREROLL = 1.5      # seconds simulated before each segment

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
child = None
if argv and argv[0] == "--segment":            # internal: --segment START END PATH
    child = (int(argv[1]), int(argv[2]), argv[3])
    argv = argv[4:]
args = list(argv)
blend = args.pop(0) if args and args[0].endswith(".blend") else None
out = os.path.abspath(args[0] if args else "pulsar_preview.mp4")
width, height, fps = (int(args[1]), int(args[2]), int(args[3])) if len(args) >= 4 else (1280, 720, 30)

ln = _bootstrap.livenodes()
if blend:
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
frames = int(round(seconds * fps))
wav = bpy.path.abspath(tree.nodes["Pulsar Loop"].filepath)


def render_segment(start, end, path):
    scene = bpy.context.scene
    s = scene.livenodes
    s.time_mode = 'TIMELINE'
    s.res_x, s.res_y = width, height
    final = tree.nodes.get("Overlay") or next(n for n in tree.nodes if n.bl_idname == "LN_OutTOP")
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
                            "-s", f"{width}x{height}", "-r", str(fps), "-i", "-", "-c:v", "libx264",
                            "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)

    class Ctx:
        state = {}
        time = 0.0

    engine.reset()
    first = max(0, start - int(PREROLL * fps))
    t0 = time.perf_counter()
    for f in range(first, end):
        engine.tick(scene, now_time=f / fps, dt=1.0 / fps)
        if f >= start:
            tex = engine.outputs[f"{tree.name}\x00{final.name}"]["Out"]
            enc.stdin.write(encode_rgba8(Ctx, tex, (width, height)).tobytes())
    enc.stdin.close()
    enc.wait()
    if engine.errors:
        print("node errors:", engine.errors)
    engine.shutdown()
    print(f"  frames {start}-{end - 1}: {(time.perf_counter() - t0) / (end - first):.2f} s per frame", flush=True)
    return enc.returncode == 0


if child is not None:
    sys.exit(0 if render_segment(*child) else 1)

# parent: one process per segment, then join and add the soundtrack
work = tempfile.mkdtemp(prefix="pulsar_")
blend_path = os.path.abspath(blend) if blend else bpy.data.filepath
if not blend_path:
    blend_path = os.path.join(work, "pulsar.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path, copy=True)
script = os.path.abspath(__file__)
binary = bpy.app.binary_path
use_blender = bool(binary) and "python" not in os.path.basename(binary).lower() and os.path.basename(binary) != ""
segments = []
for start in range(0, frames, SEGMENT):
    end = min(start + SEGMENT, frames)
    seg = os.path.join(work, f"seg_{start:05d}.mp4")
    tail = ["--segment", str(start), str(end), seg, out, str(width), str(height), str(fps), str(seconds)]
    if use_blender:
        cmd = [binary, "-b", blend_path, "--python", script, "--"] + tail
    else:
        cmd = [sys.executable, script] + tail[:4] + [blend_path] + tail[4:]
    if subprocess.run(cmd).returncode != 0 or not os.path.exists(seg):
        sys.exit(f"segment {start}-{end} failed")
    segments.append(seg)
listing = os.path.join(work, "segments.txt")
with open(listing, "w") as fh:
    fh.writelines(f"file '{p}'\n" for p in segments)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing, "-i", wav,
                "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                "-movflags", "+faststart", out], check=True)
shutil.rmtree(work, ignore_errors=True)
print(f"wrote {out}")
