# Live Nodes — real-time / interactive visuals in Blender

An add-on for Blender (4.2+, tested on **Blender 5.3**) that adds a "live" node
editor modelled on TouchDesigner: a network of operators that is *cooked*
continuously at a fixed frame rate, independently of the timeline, and drives
Blender, the GPU and external devices in real time.

| Family | Socket colour | What it carries |
|---|---|---|
| **CHOP** | green | named numeric channels (controls, audio, MIDI, OSC, DMX) |
| **TOP**  | purple | GPU textures (GLSL shaders, compositing, feedback, video) |
| **DAT**  | pink  | text, tables, Python scripts |

## Installation

Download [`dist/livenodes.zip`](dist/livenodes.zip) (on GitHub: open the file, then **Download raw file**).
In Blender: *Edit › Preferences › Get Extensions › ⌄ › Install from Disk…* → `livenodes.zip`.

To rebuild the zip after changing the code:

```bash
cd livenodes && zip -r ../dist/livenodes.zip . -x '*__pycache__*' && cd ..
```

Then open a **Node Editor**, choose the **Live Nodes** tree type, press
**New Live Network** (or create an example from the sidebar, `N › Live › Modules & Examples`)
and press **Start** (`Ctrl+Shift+Space`).

Optional modules (one-click install from the *Modules & Examples* panel, which
only lists the ones that apply to your operating system):
`python-rtmidi` (MIDI), `sounddevice` (microphone / line in), `opencv-python-headless`
(webcam, movie files, MP4 recording), `ndi-python` (NDI, ships the NDI runtime),
`SpoutGL` (Spout, Windows), `syphon-python` (Syphon, macOS). Everything else — OSC,
Art-Net/DMX, UDP, audio files, shaders, compositing — works with no external dependencies.

## Demo: PULSAR

![PULSAR](demo/pulsar_poster.jpg)

A complete audio-reactive piece: a black sun whose corona is the audio spectrum,
feedback trails, a ring of 3D bars (Geometry Nodes) rendered live and composited
on top, bloom, chromatic aberration on the kicks, tone mapping, film grain and a
typographic HUD. The soundtrack (124 BPM, an 8-bar loop) is synthesised in code:
no external files.

**Open it:** install the add-on, open `demo/pulsar.blend`, click the **PULSAR**
workspace tab at the top, then **Start** in the *Live* sidebar (`N`). Or, from any
file: *Live › Modules & Examples › PULSAR*.

**Play it** (the *Perform* panel, also in the 3D View sidebar):

| Control | Effect |
|---|---|
| Intensity | size and energy of the corona |
| Trails | how long the feedback trails persist |
| Hue Shift | rotates the palette |
| 3D Ring | amount of the 3D layer |
| Glitch · `Space` | mosaic, horizontal tearing, RGB split |
| Flash · `F` | white flash |

**How it is built** — 57 nodes in 8 numbered frames, to be read left to right:

1. **AUDIO** — loop → analysis (level / bass / mid / high / kick) and a 64-band spectrum; the kick becomes an envelope.
2. **PERFORM** — the controls above, keyboard included.
3. **BRAIN** — a *Script* node (`pulsar_brain.py`) that packs everything into named channels: the first 16 are the shader uniforms, the rest drive node parameters by name (`rotate`, `amount`, `block`, `core_scale`…).
4. **ECLIPSE** — a GLSL shader (`pulsar_eclipse.glsl`) that reads the spectrum as a texture.
5. **FEEDBACK** — zoom, swirl and colour drift: the corona leaves expanding trails.
6. **3D** — the spectrum becomes 96 points (`pulsar_ring.py` → CHOP to Mesh), instanced as bars by Geometry Nodes; the core, spin, material glow and camera are driven by Export CHOPs; *Render TOP* draws it every frame. The camera is orthographic, so the 3D core always matches the 2D disc.
7. **POST** — bloom, RGB split, mosaic and a finishing shader (`pulsar_finish.glsl`: ACES, vignette, scanlines, grain).
8. **OUTPUT** — HUD (*Format DAT* + monospaced *Text TOP*), *Out TOP*, *Stream Out* (off: switch it on to send the image to OBS/Resolume over NDI/Spout/Syphon).

Palette: indigo `#1B1440`, electric violet `#7B5CFF`, coral `#FF5A36`, warm white `#FFF4E6` on black.

**Offline video** (Timeline clock, deterministic, with sound; needs ffmpeg). The video
is made in segments, each in a fresh process with a 1.5 s pre-roll: Blender without
a window never ends a GPU frame, and over long sequences it runs out of video memory.

```bash
blender -b demo/pulsar.blend --python demo/render_preview.py -- pulsar.mp4 1280 720 30
python3 demo/build_demo.py      # regenerates pulsar.blend and pulsar_loop.wav
```

## Concepts

- **Engine**: a timer cooks every network at the *Target FPS* (default 60). The
  *Timeline* clock cooks once per timeline frame, deterministically, for rendering animations.
- **Params**: every node has a *Params* input; a channel with the same name as a
  property overrides it (`speed`, `radius`, or components such as `color.r`, `offset.x`).
  This is the equivalent of TouchDesigner's parameter references / exports.
- **Feedback**: *Feedback CHOP/TOP* read another node's output from the previous
  frame — trails, echoes, accumulation, reaction systems.
- **Mute** (`M`) on a node = bypass. Errors appear in red on the node, and the
  *Performance* panel shows the cook time of each node in ms.
- **Texture previews** above every TOP node, an output **backdrop**, and an
  **Output Window** (fullscreen too, for a second screen / projector).
- **Perform panel**: *Control CHOP* nodes (sliders, toggles, buttons, XY pads) become
  a control surface in the Node Editor and 3D View sidebars.

## Nodes (89)

**CHOP Generate** — Constant, LFO (sine/tri/ramp/square/pulse/random), Noise, Time,
Timer, Beat (BPM, tap tempo), Pattern, Trigger (ADSR), Control.

**CHOP Filter** — Math (ranges, combining inputs/channels, functions), Lag, Spring,
Speed, Slope, Limit, Logic (toggle, edges), Count, Hold, Delay, Select (wildcards,
renaming), Merge, Switch (with blending), Null, Expression (Python per channel),
Resample, Analyze, Trail, Shuffle, Feedback.

**CHOP Input / Audio** — Audio File In (plays and analyses), Audio Device In,
Audio Spectrum (log bands, dB), Audio Analysis (level, bass/mid/high, *kick*),
MIDI In, OSC In (+ log), DMX In (Art-Net), Keyboard In, Mouse In, Object,
Property In (any Blender property).

**CHOP Output** — Export (any property: objects, lights, cameras, materials,
modifiers, **Geometry Nodes inputs**), OSC Out, MIDI Out, DMX Out (Art-Net),
CHOP to Mesh (points + attributes for Geometry Nodes → instancing).

**TOP** — Constant, Noise (smooth/fractal/cellular/random), Ramp, Shape, Text,
**GLSL** (your own shaders, compatible with *Shadertoy* code), CHOP to TOP,
Feedback, Image, Movie File In, Video Device In, **Render** (the 3D scene through a
camera, every frame), Level, Blur, Transform, **Corner Pin** (projection
mapping), Composite (12 modes), Cross, Switch, Displace, Edge, Key (luma/chroma),
Mirror/Kaleidoscope, Pixelate, RGB Split, Lookup, Bloom, Normal Map, Resolution,
Null, TOP to CHOP, TOP to Image (live textures in materials), Out, Movie File Out
(PNG/EXR/MP4), **Stream Out** (NDI / Spout / Syphon).

**DAT** — Text, Table, File In (automatic reload), UDP In, DAT to CHOP,
CHOP to DAT, Format, **Script** (Python `cook(ctx, inputs)` → channels/text/texture),
**Execute** (Python on events: rising/falling edges, value changes).

## Included examples

1. **PULSAR (showcase)** — the demo described above.
2. **Feedback Visuals** — a generative feedback loop with bloom → Out TOP.
3. **Audio Reactive Object** — a BPM clock and audio analysis driving an object's
   scale and rotation.
4. **Channels to Geometry** — an LFO trail → points → Geometry Nodes instancing.
5. **Controls, Text & OSC** — Perform-panel sliders, live text overlay, OSC input.

## Stream Out: NDI, Spout, Syphon

The **Stream Out TOP** node shares a live image with other applications
(OBS, vMix, Resolume, MadMapper, TouchDesigner, Millumin…):

| Protocol | System | How it works |
|---|---|---|
| NDI | all | compressed video over the local network; with *Only When Connected* it costs nothing until someone receives |
| Spout | Windows | shared DirectX texture; if Blender runs on Vulkan, Spout creates its own OpenGL context |
| Syphon | macOS | shared Metal texture |

On the GPU the node converts to 8-bit sRGB, un-premultiplies the alpha and flips
the image, then reads the pixels back. The GPU → CPU readback remains the main
cost (Blender does not expose the native handle of its textures). Lower *Max FPS*
or the node's resolution if needed. The *Info* output reports receivers, frames
sent and resolution.

## Tests

```bash
pip install bpy==5.3.0            # Blender as a Python module
python3 tests/run_tests.py        # 48 tests, headless (a software GPU is fine)
pip install ndi-python            # optional: enables the real NDI loopback test
```

The tests cook real networks with a fixed clock and check channel values, GPU
texture pixels, effects on Blender (properties, meshes, Geometry Nodes inputs,
recorded files) and OSC and Art-Net network round trips on localhost.

## An honest comparison with TouchDesigner

Covered: the CHOP/TOP/DAT operator architecture, real-time cooking, feedback,
GLSL, compositing, audio reactivity, MIDI/OSC/DMX, video/webcam, per-frame and
event-driven Python scripting, fullscreen output, four-corner projection mapping,
and control over all of Blender (which stands in for SOPs/POPs through Geometry
Nodes, and for the Render TOP through EEVEE).

Not covered (yet), because of real limits more than lack of time:

- **Performance**: every node is Python; cooking a CHOP costs ~10 µs per node
  (61 nodes ≈ 0.8 ms), while TOPs are GPU shaders and scale well. TOP → material goes
  through the CPU (readback) — use *Every Nth Frame* or moderate resolutions.
- **Render TOP** in real time uses viewport drawing (overlays excluded) and needs
  an open 3D View; in *Final Render* mode it uses the render engine (slow, for
  offline exports with the Timeline clock).
- **COMPs / custom UI panels, Kinect/Leap/sensors, WebSocket/Web Server DAT,
  cue-based timelines, multi-threaded cooking**: not available. They can be written
  as *Script* nodes or as new nodes (every node is a class with a `cook` method).
- The interface (previews, output window, panels) is not covered by the headless
  automated tests: it needs to be tried in Blender with a window.

## Writing a node

```python
class LN_MyCHOP(LNNode, bpy.types.Node):
    bl_idname = "LN_MyCHOP"
    bl_label = "My CHOP"
    ln_category = "CHOP Filter"
    gain: FloatProperty(default=2.0)

    def ln_init(self):
        self.add_in('CHOP', "In")
        self.add_out('CHOP')

    def cook(self, ctx, inp):          # ctx.time, ctx.dt, ctx.state, ctx.p (parameters)
        src = inp.chop()
        return src.replace(src.data * ctx.p.gain)
```

Add it to the module's `classes` tuple and it will appear in the `Shift+A` menu.
