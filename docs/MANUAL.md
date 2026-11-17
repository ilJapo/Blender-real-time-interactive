# Live Nodes — User Manual

Version 0.1 · Blender 4.2 or newer (tested on 5.3)

Live Nodes turns Blender into a real-time, interactive visuals tool. You build a
network of small operators in a node editor; the network is evaluated
(*cooked*) continuously, many times per second, independently of Blender's
timeline. It listens to audio, MIDI, OSC, DMX, keyboard and mouse, generates and
processes images on the GPU, drives any property of your Blender scene and sends
the result to a screen, a projector, a video file or another application.

If you know TouchDesigner, most of this will feel familiar: the same families of
operators (CHOP, TOP, DAT), the same idea of a network that is always running, the
same habits (Null nodes as stable connection points, feedback loops, exports).

The complete list of nodes, with every parameter, is in the
**[node reference](NODES.md)**. This manual explains how things fit together.

---

## Contents

1. [Installation](#1-installation)
2. [Quick start: your first network](#2-quick-start-your-first-network)
3. [The interface](#3-the-interface)
4. [The engine](#4-the-engine)
5. [Data families: CHOP, TOP, DAT](#5-data-families-chop-top-dat)
6. [Parameters and the Params input](#6-parameters-and-the-params-input)
7. [Feedback](#7-feedback)
8. [Working with the Blender scene](#8-working-with-the-blender-scene)
9. [Audio](#9-audio)
10. [Control: MIDI, OSC, DMX, keyboard, mouse, Perform panel](#10-control-midi-osc-dmx-keyboard-mouse-perform-panel)
11. [Video in](#11-video-in)
12. [Writing shaders (GLSL TOP)](#12-writing-shaders-glsl-top)
13. [Python scripting](#13-python-scripting)
14. [Output: screens, projectors, streams and files](#14-output-screens-projectors-streams-and-files)
15. [Performance](#15-performance)
16. [The PULSAR demo](#16-the-pulsar-demo)
17. [Writing your own nodes](#17-writing-your-own-nodes)
18. [Troubleshooting](#18-troubleshooting)
19. [Reference tables](#19-reference-tables)

---

## 1. Installation

### Requirements

- Blender **4.2 or newer**. Development and testing happen on Blender 5.3. The demo
  file `demo/pulsar.blend` was saved with 5.3; on older versions rebuild the demo
  from the *Examples* panel instead of opening the file.
- Any GPU Blender supports (OpenGL, Vulkan or Metal).

### Installing the add-on

1. Get `dist/livenodes.zip` from the repository (on GitHub open the file and press
   **Download raw file**), or build it yourself:
   ```bash
   cd livenodes && zip -r ../dist/livenodes.zip . -x '*__pycache__*'
   ```
   The zip must contain `blender_manifest.toml` at its top level, not inside a folder.
2. In Blender: **Edit › Preferences › Get Extensions**, open the **⌄** menu at the
   top right, choose **Install from Disk…** and pick the zip.
3. Make sure *Live Nodes* is enabled in the list.

To update, install the new zip the same way. To remove it, use the extension's
menu in the same preferences page.

### Optional modules

Everything works out of the box except the nodes that talk to hardware or to other
applications. They need a Python module that Blender does not ship. Install them
with one click from **Live sidebar › Modules & Examples** (it downloads from PyPI,
so it needs internet; the panel only lists the modules that make sense on your
operating system):

| Module | Enables |
|---|---|
| `python-rtmidi` | MIDI In, MIDI Out |
| `sounddevice` | Audio Device In (microphone, line in, audio interfaces) |
| `opencv-python-headless` | Video Device In (webcams, capture cards), Movie File In, MP4 recording |
| `ndi-python` | Stream Out over NDI (the NDI runtime is included) |
| `SpoutGL` | Stream Out over Spout (Windows) |
| `syphon-python` | Stream Out over Syphon (macOS) |

The modules are installed into Blender's user `scripts/modules` folder and are
available immediately, without restarting.

On macOS the first use of a microphone or camera triggers the system permission
prompt for Blender; allow it, then press **Stop** and **Start** again.

---

## 2. Quick start: your first network

This takes five minutes and touches the main ideas.

1. Open a **Node Editor** (any area: change its editor type) and pick the
   **Live Nodes** tree type in its header. Press **New Live Network**.
2. Press `N` to open the sidebar and select the **Live** tab. Press **Start**.
   The header now shows the measured frame rate.
3. **A moving value.** `Shift+A › CHOP Generate › LFO CHOP`. Its body shows the
   current value of its channel `lfo`, swinging between −1 and 1.
4. **Drive the scene.** Add `CHOP Output › Export CHOP`, connect the LFO to it.
   In the Export node choose *Object*, pick the default cube and type
   `rotation_euler[2]` as path. The cube spins back and forth.
5. **An image.** Add `TOP Generate › Noise TOP`, then `TOP Filter › Level TOP`,
   then `TOP Output › Out TOP`, and connect them in a chain. A thumbnail of each
   texture appears above the nodes.
6. **Connect control to image.** Connect the LFO to the *Params* input of the
   Level TOP and rename the LFO's channel (sidebar, *Node* tab, or the node's
   extended settings) to `brightness`. The image now pulses with the LFO: any
   channel whose name matches a parameter overrides it.
7. **Show it.** Press **Fullscreen** on the Out TOP (or *Output Window* in the
   sidebar). Close the window, or toggle fullscreen off, to get back.

Two more things worth trying straight away: the **Examples** buttons in
*Modules & Examples* build complete networks you can take apart, and **PULSAR**
(chapter 16) shows everything working together.

---

## 3. The interface

### The node editor

- **Tree type.** Live networks are node trees of type *Live Nodes*. A file can hold
  any number of them; all of them cook while the engine runs.
- **Add menu** (`Shift+A`): nodes are grouped by family and role — *CHOP Generate,
  CHOP Input, CHOP Audio, CHOP Filter, CHOP Output, TOP Generate, TOP Input, TOP
  Filter, TOP Composite, TOP Convert, TOP Output, DAT* — plus Blender's *Frame* and
  *Reroute*. Frames are just for layout; reroutes are followed transparently.
- **Socket colours**: green = CHOP (channels), purple = TOP (textures),
  pink = DAT (text/tables). A link between different families is ignored.
- **Multi-input sockets** (drawn as a pill, e.g. *Math CHOP › In*, *Merge CHOP*,
  *Composite TOP › Layers*) accept several links. Their order is the order you made
  the links. Blender does not allow the same output twice into one multi-input.
- **Node colours** tell the family: green CHOP, purple TOP, magenta DAT, amber for
  output nodes that act on the outside world.
- **Node body** shows the main parameters and, while running, the first four
  channel values of CHOP outputs (`name: value [samples]`).
- **Node sidebar** (`N › Node`): the extended settings of the active node —
  resolution for TOPs, secondary parameters, up to 32 channel values, the full
  error message and the cook time.
- **Mute** (`M`) bypasses a node: each output passes on the first input of the
  same family.
- **Errors** turn the node's text red with the message; the first occurrence of
  each message is also printed to Blender's system console (with the traceback
  for unexpected errors).

### Texture previews and backdrop

While the engine runs, every TOP shows a thumbnail of its output above the node.
Turn them off or change their size in **Engine › Node Previews / Preview Size**.
**Backdrop** draws the Out TOP — or the active TOP node, if one is selected —
behind the whole network.

### The Live sidebar (Node Editor, `N › Live`)

| Panel | Contents |
|---|---|
| **Engine** | Start/Stop, Reset (`⟲`), Step (one frame), measured fps and cook time, error count, Output Window, and the settings described in [chapter 4](#4-the-engine) |
| **Perform** | the controls created by *Control CHOP* nodes |
| **Performance** | the slowest nodes and their cook time in ms |
| **Modules & Examples** | optional modules with install buttons, example networks |

The **3D View sidebar** has a *Live* tab too, with Start/Stop, Output Window and
the Perform controls, so you can perform from the 3D view.

The node editor header shows a Play/Pause button and the frame rate.
**`Ctrl+Shift+Space`** in the node editor toggles the engine.

---

## 4. The engine

### Starting and stopping

**Start** begins cooking every Live network in the file. **Stop** halts cooking and
closes everything the nodes opened: network ports, MIDI ports, audio streams,
cameras, NDI/Spout/Syphon senders. **Reset** rewinds the engine clock to zero and
clears the memory of every node (feedback buffers, lags, counters, timers).
**Step** cooks a single frame, which is handy while stopped.

If **Start on Load** is enabled, the engine starts by itself when the file is
opened. Keyboard and mouse capture start only when you press Start (or use the
shortcut), so press it once if you rely on them.

### Settings (Engine panel)

| Setting | Meaning |
|---|---|
| **Target FPS** | how many times per second the networks cook (1–240, default 60). The actual rate is shown next to Start; if the network is too heavy it will be lower. |
| **Clock** | *Real Time*: cook continuously, time follows the wall clock. *Timeline*: cook once per timeline frame change, time = (frame − start) / scene fps. |
| **Resolution X / Y** | the default size of generated textures. |
| **Precision** | texture format: 8-bit (least memory, visible banding in gradients and feedback), **16-bit float** (default: HDR values, smooth feedback), 32-bit float (data textures). |
| **Node Previews / Preview Size** | thumbnails above TOP nodes. |
| **Backdrop** | output behind the network. |
| **Redraw 3D Views** | repaint 3D views every frame so objects driven by the network move smoothly on screen. Turn it off when the 3D view is only a source for a Render TOP. |
| **Capture Keyboard & Mouse** | feed the Keyboard In and Mouse In nodes. Every event is passed on to Blender as usual. |
| **Start on Load** | start the engine when the file opens. |
| **Reload Shaders** | recompile GLSL and re-read scripts; normally not needed, edits are picked up automatically. |

### Real Time and Timeline clocks

Use **Real Time** for performances, installations and anything interactive.

Use **Timeline** when you need the exact same result every time, for example to
record an animation: with the engine started, each change of the current frame
(playback, scrubbing, frame stepping) cooks the network once with a time that
depends only on the frame number. In Timeline mode Audio File In follows the
timeline instead of playing through the speakers. For frame-by-frame recording set
the timeline's playback *Sync* to **Play Every Frame**. Rendering an animation with
`Ctrl+F12` while the engine runs has not been tested; for offline exports prefer the
approach in [chapter 14](#offline-rendering-without-a-window).

### Evaluation order

Every frame the engine cooks each network in dependency order: a node cooks after
the nodes connected to its inputs. A few rules complete the picture:

- **Nodes that change the scene cook before nodes that read it.** Export CHOP and
  CHOP to Mesh write Blender data; Render TOP, Object CHOP and Property In CHOP read
  it. Unless the reader is upstream of the writer, the reader waits, so a render
  always shows the current frame's state.
- **Cycles** are allowed only through Feedback nodes (chapter 7). A direct loop is
  broken arbitrarily and the node at the break reads the previous frame.
- Renaming, adding or deleting nodes and links is picked up immediately; the
  running state of untouched nodes is kept.

### Where state lives

Node parameters are saved with the .blend. What nodes remember while running
(feedback buffers, filter memories, open devices) lives in the engine only and
disappears on Reset, Stop, or reopening the file.

---

## 5. Data families: CHOP, TOP, DAT

### CHOP — channels

A CHOP carries an ordered set of **named channels**. All channels in one CHOP have
the same number of **samples**:

- A control signal has **one sample** per channel: an LFO, a slider, a MIDI
  controller, an object's position.
- Audio, spectra, trails and patterns have **many samples**: Audio File In gives the
  last 1024 samples of the sound, Audio Spectrum gives one sample per band, Trail
  CHOP gives the last N frames of history.

Each CHOP also has a sample **rate** (samples per second), used by audio nodes.

Nodes that read a single value per channel (Export, OSC Out, MIDI Out, Logic,
Params…) use the **first sample**.

When a node combines several CHOPs (Math with several inputs, Switch with blending)
they are aligned: the input with the most channels sets the names, inputs with
fewer channels are reused cyclically, a single sample is repeated, other sample
counts are resampled.

**Names matter.** Channel names are how you address things: Select CHOP picks
channels by name (wildcards `*` and `?`, several patterns separated by spaces),
Export CHOP picks the channel to export, Params matches names to parameters, and
OSC/MIDI outputs build addresses and messages from names. Merge CHOP makes clashing
names unique by appending numbers (`lfo`, `lfo1`).

### TOP — textures

A TOP carries a **GPU texture**. Every TOP renders into its own buffer each
frame. Two conventions apply everywhere:

- **Linear colour.** Values are scene-linear, like Blender's renders: 0.5 is
  mid-grey in light, which displays as about 0.735 on screen. Conversion to the
  display happens at the very end (previews, output windows, streams, files).
  Values above 1.0 are allowed with float precision and are useful for glow.
- **Premultiplied alpha.** Colour is stored already multiplied by alpha. A pixel
  with alpha 0 and non-zero colour is valid: it is *additive light* (glow that adds
  to whatever is below without hiding it). Composite TOP's *Over* handles both kinds
  correctly. Level TOP works on un-premultiplied colour, so it removes additive
  light; if you need to adjust glow, do it in a GLSL TOP or before the alpha is set.

**Resolution** (node sidebar of every TOP):

| Mode | Size |
|---|---|
| **Auto** | the size of the first connected texture input; generators use the default resolution |
| **Scene** | always the default resolution of the Engine settings (useful for a GLSL TOP whose first input is a small data texture) |
| **Custom** | the Width × Height set on the node |

### DAT — text and tables

A DAT carries either **text** (a string) or a **table** (a list of rows of
strings). Text containing commas or tabs is read as CSV/TSV where a table is
needed. DATs connect the network to Python, to files and to text on screen (Text
TOP accepts a DAT input).

---

## 6. Parameters and the Params input

Almost every node has a **Params** input (CHOP). For every channel on it whose name
matches one of the node's parameters, the channel's first sample replaces the
parameter's value for that frame. The parameter shown in the UI does not change;
it simply loses to the channel while the link is there.

| Parameter type | How the channel is applied |
|---|---|
| number | used as is |
| integer | rounded |
| on/off | on when the value is above 0.5 |
| vector or colour | by component: `name.x` `name.y` `name.z` `name.w`, `name.r` `name.g` `name.b` `name.a`, or `name0` `name1`…; `name_x` and `namex` work too |
| text, choice, data-block | cannot be driven |

The identifier of each parameter is listed in the [node reference](NODES.md)
(and shown in Blender's tooltip with Python tooltips enabled). Examples:

- LFO → Select CHOP (rename to `radius`) → *Params* of a Shape TOP: a breathing circle.
- Control CHOP with channel `hue` → *Params* of Level TOP: a hue knob.
- Constant CHOP with names `translate.x translate.y` → *Params* of Transform TOP.

A common pattern is a **"brain" node** — an Expression CHOP or Script node — that
computes many named channels, then a single link from it to the Params of several
nodes; each node takes only the names it knows.

---

## 7. Feedback

Feedback means using a node's previous frame as input. It produces trails, echoes,
smoke, reaction-diffusion and every kind of accumulation.

- **Feedback TOP**: pick a *Target* TOP. Each frame it outputs what the target
  produced on the previous frame (a copy). Put the target **downstream**: Feedback
  TOP → processing → … → target, and the target is fed back next frame. The
  *Initial* input is used on the first frame and while **Reset** is held.
- **Feedback CHOP**: the same for channels (accumulators, iterative systems).

A classic texture loop:

```
Feedback TOP ──► Transform TOP (scale 1.01, rotate 0.01) ──► Level TOP (opacity 0.9) ──► Composite TOP (Over) ──► …
      ▲                                                                                   ▲ Layers: new content
      └────────────────────────────── target ──────────────────────────────────────────────┘
```

### Make feedback independent of the frame rate

Feedback operations happen **per frame**. If the network runs at 60 fps instead of
30, a zoom of 1% per frame becomes twice as fast, and new content is added twice as
often (so the trails get brighter). If the frame rate changes during a show, the
look changes with it. To keep the same look at any frame rate, express each step
per unit of time and scale it by the frame time — `ctx.dt` in a Script node:

| Per-frame operation | Scaled by `k = dt × 30` (1.0 at 30 fps, 0.5 at 60 fps) |
|---|---|
| zoom by `z` | zoom by `z ** k` |
| rotate by `a` | rotate by `a * k` |
| keep `d` of the old image | keep `d ** k` |
| blur radius `r` | radius `r * sqrt(k)` |
| add new light `L` | add `L * k` |

The PULSAR demo does exactly this in its *Trail Loop* shader (chapter 16).

---

## 8. Working with the Blender scene

### Driving properties: Export CHOP

Export CHOP writes channel values into **any Blender property**:

1. Choose the kind of owner — Object, Material, World, Scene or a node of this
   Live network — and pick it.
2. Type the **path**, as given by Blender's *Copy Data Path* (right-click a
   property): `location`, `rotation_euler[2]`, `scale`, `data.energy` (a light),
   `data.lens` (a camera), `modifiers["Wave"].height`, `["my_property"]` (a custom
   property), `node_tree.nodes["Emission"].inputs["Strength"].default_value`
   (a material node input).
3. **Channel** chooses which channel(s) to export, by name or pattern; empty = all
   channels in order. A vector property takes one channel per component; **a
   single channel sets every component** (handy for uniform scale).
4. **Multiply** and **Add** rescale the value.

**Geometry Nodes inputs**: for an object with a Geometry Nodes modifier, pick the
modifier in the extra field that appears and type the **input's name** (as shown
in the modifier) as path. This works on Blender 4.x and on the new modifier
interface of Blender 5.

Export only writes when the value changes, and Blender re-evaluates what depends on
it. Exporting to many objects every frame has a cost on Blender's side (depsgraph
updates), not in Live Nodes.

### Reading the scene

- **Object CHOP**: position (`tx ty tz`), rotation (`rx ry rz`, radians) and scale
  (`sx sy sz`) of an object, in world or local space, optionally relative to a
  second object (adds `distance`).
- **Property In CHOP**: any property by path, like Export CHOP in reverse.

### Geometry from channels: CHOP to Mesh + Geometry Nodes

CHOP to Mesh turns samples into **points of a mesh object** and every channel into
a **float point attribute** of the same name. Geometry Nodes then does the rest
(instancing, curves, volumes…).

- With multi-sample channels you get one point per sample; with single-sample
  channels, one point per channel.
- *Positions*: **From tx / ty / tz** uses those channels as coordinates;
  **Line + Height** spreads points along X and lifts them by the first channel;
  **Leave Unchanged** only writes attributes (the vertex count must already match).

Recipe — audio bars: Audio File In → Audio Spectrum → CHOP to Mesh (*Line + Height*)
on an empty mesh object; in its Geometry Nodes modifier, *Instance on Points* with
a cube and a *Named Attribute* `spectrum` driving the instance scale. In a material,
an *Attribute* node of type **Instancer** reads the same attribute for colour.

### Textures into materials: TOP to Image

TOP to Image copies a texture into a Blender **Image** every frame (the `+` button
creates a float image). Use that image in an *Image Texture* node of any material,
in the compositor, or in the image editor. The copy goes through the CPU, so use
*Every Nth Frame* or moderate resolutions for big textures.

### The scene as a texture: Render TOP

Render TOP renders the scene through a camera every frame, as a texture you can
process and composite.

- **Viewport** method (real time): draws like the 3D viewport with the chosen
  shading — *Rendered* gives EEVEE — without overlays (grid, gizmos). It needs a
  **3D View open** somewhere (it can be small, and in any shading mode).
- **Final Render** method: runs the scene's render engine. Slow; meant for
  Timeline-clock exports. Also used automatically when Blender runs without a window.
- *Transparent* leaves the world out (premultiplied alpha), ready for compositing.

The world colour of your scene appears behind the render unless *Transparent* is
on. With an **orthographic camera** it is easy to align 3D objects with 2D content,
as in PULSAR.

---

## 9. Audio

### Sources

- **Audio File In CHOP** plays a file (WAV, FLAC, MP3, OGG… anything Blender reads)
  through the speakers and outputs the samples at the play position: `chan1`
  (mono, the default) or one channel per audio channel. *Samples* sets how many
  samples you get each frame (1024 ≈ 23 ms at 44.1 kHz). The **Info** output gives
  `position`, `length`, `fraction` and `playing`, useful to keep visuals in time
  with the music (see PULSAR's beat counter).
- **Audio Device In CHOP** captures a microphone or interface input (needs
  `sounddevice`). Type part of the device name, or leave it empty for the system
  default; the node's sidebar lists the available inputs.

### Analysis

- **Audio Spectrum CHOP** — the frequency content as *Bands* logarithmically spaced
  between *Low Hz* and *High Hz*, in one channel `spectrum` with one sample per band.
  *Decibel Scale* maps −60…0 dB to 0…1 (closer to how we hear); *Falloff* makes
  peaks decay smoothly; *Gain* boosts quiet sources.
- **Audio Analysis CHOP** — ready-made signals: `level` (RMS), `peak`, `bass`
  (20–250 Hz), `mid` (250–4000 Hz), `high` (4–16 kHz) and `kick` (1 for one frame
  when the bass jumps above its recent average). *Auto Gain* normalises each band
  against its recent maximum, so the values use the whole 0–1 range whatever the
  volume. *Smoothing* has instant attack and a smooth release.
- Turn the kick pulse into a shape with **Trigger CHOP** (attack/decay/sustain/
  release), and keep tempo with **Beat CHOP** (BPM, tap tempo, ramps and counters).

Spectrum and Analysis work on any multi-sample CHOP, not only on audio.

---

## 10. Control: MIDI, OSC, DMX, keyboard, mouse, Perform panel

### Perform panel and Control CHOP

**Control CHOP** creates a control in the **Perform** panel (Node Editor and 3D View
sidebars): **Slider**, **Toggle**, **Momentary** button (1 for one frame when
pressed) or **XY Pad** (two sliders: `namex`, `namey`). The node's *label* (or its
channel name) is the text shown; *Panel Order* sorts the controls. Connect it
wherever a channel is needed — often to Params.

### MIDI

**MIDI In CHOP** (needs `python-rtmidi`): *Port* is part of the device name (empty =
first device; the sidebar lists the devices). Channels appear as they are used:

| Message | Channel | Value |
|---|---|---|
| note on/off | `ch1n60` (MIDI channel 1, note 60) | velocity 0–1, 0 on release |
| control change | `ch1c7` | 0–1 |
| pitch bend | `ch1pitch` | −1–1 |
| channel pressure | `ch1pressure` | 0–1 |

Use *Channels* (a pattern such as `ch1c*`) to keep only some of them.

**MIDI Out CHOP** sends channels with the same naming (`ch1c7` → controller 7 on
MIDI channel 1, `ch2n60` → note 60 on channel 2, velocity = value), only when the
value changes. Values are clamped to 0–1.

### OSC

**OSC In CHOP** listens on a UDP **Port** (default 9000). Each OSC address becomes a
channel named like the address without the leading slash (`/fader/1` → `fader/1`);
messages with several numbers give `address1`, `address2`…; *Address Filter*
keeps matching addresses (e.g. `/fader*`). The **Log** output (DAT) holds the last
32 messages — connect a Text TOP to see what arrives. Bundles are supported.
Several OSC In nodes on the same port share one socket.

**OSC Out CHOP** sends every channel as `/<prefix>/<channel name>` with one float to
*Host*:*Port* (default 127.0.0.1:9001), by default only when the value changes.

### DMX (Art-Net)

**DMX Out CHOP** sends channels as one DMX universe over Art-Net (UDP 6454). Channel
order is the DMX address order, starting at *Start Address*; values 0–1 become
0–255. *Host* is the node's IP or the broadcast address; *Rate* caps the packets per
second (DMX hardware usually expects ≤ 44 Hz). A single channel with many samples
(for example from a Pattern or TOP to CHOP) is sent sample by sample — handy for
LED strips.

**DMX In CHOP** receives one universe: channels `dmx1`… with values 0–1.

### Keyboard and mouse

With **Capture Keyboard & Mouse** on (Engine settings) and the engine started:

- **Keyboard In CHOP**: list keys by their Blender names, separated by spaces —
  `SPACE A S D`, `ONE TWO`, `LEFT_ARROW`, `F1`, `NUMPAD_1`… Each key gives a 0/1
  channel with the name in lower case (`space`, `a`).
- **Mouse In CHOP**: `x` and `y` from 0 to 1 across the Blender window (origin at
  the bottom left), `left`, `middle`, `right` buttons, and `wheel` (accumulated
  steps).

Events keep reaching Blender as usual: keys you use for the show still trigger
Blender shortcuts where the mouse is.

---

## 11. Video in

- **Image TOP** — any image of the file or opened from disk (sequences and movies:
  use Movie File In).
- **Movie File In TOP** (needs OpenCV) — plays a movie in step with the engine
  clock: *Play*, *Loop*, *Speed*, and *Position* to cue (0–1) while paused. The
  **Info** output gives `index`, `fraction`, `length` (frames) and `fps`.
- **Video Device In TOP** (needs OpenCV) — a webcam or capture card by index (0 is
  the first camera). The requested width and height are a hint; the camera may
  choose another size.

Frames from video are converted from sRGB to linear (approximately) on the way in.

---

## 12. Writing shaders (GLSL TOP)

GLSL TOP runs your own fragment shader. Press `+` on the node to create a text
block with a starter shader, or pick an existing one. Edit it in Blender's text
editor: the node recompiles automatically when the text changes.

### What the shader sees

| Name | Type | Meaning |
|---|---|---|
| `vUV` | `vec2` | pixel position, 0–1, origin at the bottom left |
| `uRes` | `vec2` | output size in pixels |
| `uTime` | `float` | engine time in seconds |
| `uMouse` | `vec4` | mouse `x`, `y` (0–1), left button, right button |
| `uP0` … `uP3` | `vec4` | the first 16 channels of the **Uniforms** input, four per vector, in order |
| `uIn0` … `uIn3` | `sampler2D` | the textures on inputs *In 0* … *In 3* (black when unconnected) |
| `fragColor` | `vec4` out | the result: linear, premultiplied RGBA |

Read textures with `texture(uIn0, vUV)`. Write normal GLSL functions above
`main()`. The code is cross-compiled by Blender for OpenGL, Vulkan and Metal, so use
the modern syntax (`texture`, `fragColor`) and no `#version` line.

### Helper functions (always available)

| Function | Returns |
|---|---|
| `ln_noise(vec3 p)` | smooth gradient noise, about −1…1 |
| `ln_fbm(vec3 p, int octaves, float roughness)` | fractal noise (up to 8 octaves) |
| `ln_cell(vec3 p)` | distance to the nearest scattered point (cellular noise) |
| `ln_hash3(vec3 p)` | three pseudo-random values 0–1 |
| `ln_luma(vec3 c)` | luminance |
| `ln_rgb2hsv(vec3)`, `ln_hsv2rgb(vec3)` | colour conversions |
| `ln_wrap(vec2 uv, int mode)` | 0 clamp, 1 repeat, 2 mirror |
| `ln_inside(vec2 uv)` | 1 inside 0–1, 0 outside |

### Shadertoy code

If the text defines `mainImage(out vec4 fragColor, in vec2 fragCoord)`, it runs as
Shadertoy code: `iTime`, `iResolution`, `iChannel0`…`iChannel3` (= *In 0*…*In 3*)
and `iMouse` (mouse position in pixels and buttons) are provided, and `fragCoord`
is in pixels. Paste a shader and it usually just works. Multi-pass shaders need one
GLSL TOP per pass, and a Feedback TOP for buffers that read themselves.

### Uniforms in practice

Feed the Uniforms input with a CHOP whose channel **order** is known: a Merge of a
few nodes, or better a Script node that returns a dict in the exact order you want
(PULSAR's *Brain*). Then name them in the shader:

```glsl
#define BASS uP0.x
#define KICK uP0.w
```

### Errors

A compile error shows *GLSL compile error* on the node; the details (line and
message) are in Blender's **system console** (*Window › Toggle System Console* on
Windows; start Blender from a terminal on macOS/Linux). Fix the text and the node
recovers by itself.

If the output has the wrong size, check the resolution mode: in *Auto* the size
comes from *In 0*; use **Scene** or **Custom** when *In 0* is a small data texture
(for example a spectrum from CHOP to TOP).

---

## 13. Python scripting

### Script node

The **Script** node runs a function of yours every frame — anything Blender's
Python can do. Press `+` for a starter text. The text must define:

```python
def cook(ctx, inputs):
    ...
    return {...}
```

**Inputs**: *In* (CHOP), *In 1* (TOP), *In 2* (DAT). **Outputs**: *Channels*,
*Texture*, *Data* — what you return decides which one is filled:

| Return value | Goes to |
|---|---|
| a dict `{name: number or list/array}` | Channels (a list gives several samples) |
| a `Channels` object | Channels |
| a string, or a list of rows | Data |
| a GPU texture | Texture |
| `None` | nothing |

**`ctx`** — the cook context:

| Attribute | Meaning |
|---|---|
| `ctx.time`, `ctx.dt`, `ctx.frame` | engine time (s), time since the last cook (s), frame counter |
| `ctx.fps` | target frame rate |
| `ctx.state` | a dict that persists between frames (private to this node; reset when the text changes or on Reset) |
| `ctx.scene`, `ctx.tree` | the Blender scene and the Live network |
| `ctx.default_res`, `ctx.tex_format` | default resolution and texture precision |
| `ctx.output_of("Node", socket=None)` | the latest output of another node of the network |

**`inputs`**:

| Call | Returns |
|---|---|
| `inputs.chop("In")` | the CHOP on that input (empty if unconnected) |
| `inputs.get("In 1")` | the first value on that input, or `None` |
| `inputs.all("In")` | every value on a multi-input |

**`Channels`** (also available as a global in scripts):

| Member | Meaning |
|---|---|
| `.names`, `.data`, `.rate` | channel names, a NumPy array (channels × samples), sample rate |
| `.num_channels`, `.num_samples` | sizes |
| `.to_dict()` | `{name: first sample}` |
| `.get(name, default)`, `.first()` | one value |
| `.chan(name)` | all samples of a channel (NumPy row) or `None` |
| `.match("t* level")` | indices of matching channels |
| `Channels.from_dict({...})` | build a CHOP from a dict |

The module is executed again whenever you edit the text. Globals available without
importing: `bpy`, `np` (NumPy), `math`, `Channels`.

Example — a smoothed, normalised mouse distance from the centre:

```python
import math

def cook(ctx, inputs):
    m = inputs.chop("In").to_dict()            # connect a Mouse In CHOP
    d = math.hypot(m.get("x", .5) - .5, m.get("y", .5) - .5)
    s = ctx.state.get("s", 0.0)
    s += (d - s) * min(1.0, ctx.dt * 8.0)       # frame-rate independent smoothing
    ctx.state["s"] = s
    return {"distance": s}
```

### Expression CHOP

A one-line Python expression evaluated for each channel of the input. Variables:
`v` (the channel's samples as a NumPy array), `i` (channel index), `n` (name),
`t`, `dt`, `frame`, `ch` (dict of all first values), `np`, `math`, `sin`, `cos`,
`abs`, `min`, `max`, `pi`. Example: `v * 2 + sin(t)`.

### Execute DAT

Runs Python when channels change: **Off to On** (rising above 0.5), **On to Off**,
or **Value Change**. The code — a line in the node, or a whole text block — sees
`name`, `value`, `prev`, `ctx`, `scene`, `bpy`, `np`, `math`. Use it to switch
scenes or cameras, toggle visibility, start renders, run operators:

```python
bpy.context.scene.camera = bpy.data.objects["Cam B"] if value > 0.5 else bpy.data.objects["Cam A"]
```

### Text and tables

**Text DAT** (a text block or a typed string), **Table DAT** (CSV/TSV), **File In
DAT** (re-read when the file changes on disk — edit it in any program), **UDP In DAT**
(text lines from the network), **DAT to CHOP** (numbers in a table become channels:
*Name | Value*, *Columns* or *Rows*), **CHOP to DAT** (channels as a table),
**Format DAT** (Python format string such as `BPM {bpm:.0f}`; unknown names give 0).

---

## 14. Output: screens, projectors, streams and files

### Out TOP and output windows

**Out TOP** marks the final image. Its **Window** button opens a separate window
showing it; **Fullscreen** opens it fullscreen (on macOS this is a native
fullscreen space). *Output Window* in the sidebar does the same for the first Out
TOP it finds. Move the window to the projector or second screen before making it
fullscreen. The image is fitted to the window with black bars where the aspect
ratios differ. Close the window as any Blender window.

Several Out TOPs can drive several windows at once.

### Projection mapping

**Corner Pin TOP** pins the four corners of the image anywhere in the output
(coordinates 0–1). Drive the corners from Params (`top_left.x`, …) — for example
from XY-pad Control CHOPs — to line the image up with a physical surface from the
Perform panel. Combine several Corner Pins with Composite TOP for several surfaces.

### Stream Out: NDI, Spout, Syphon

**Stream Out TOP** shares the image live with other applications — OBS, vMix,
Resolume, MadMapper, Millumin, TouchDesigner…

| Protocol | System | Notes |
|---|---|---|
| NDI | any | video over the local network; receivers find it by name (*Name*). Discovery uses mDNS — receivers must be on the same network, and firewalls must allow NDI. |
| Spout | Windows | shared GPU texture with apps on the same PC. If Blender draws with Vulkan, Spout creates its own OpenGL context. |
| Syphon | macOS | shared Metal texture with apps on the same Mac. |

*Alpha* sends transparency, *sRGB* encodes like a normal video image (turn it off to
send raw linear values), *Max FPS* limits the send rate, and **Only When Connected**
skips the work while no receiver is connected (NDI and Syphon can tell). The **Info**
output reports `active`, `receivers`, `sent`, `width` and `height`.

Sending costs one GPU → CPU copy per frame (Blender does not let add-ons share its
GPU textures directly), so prefer moderate resolutions or a lower *Max FPS* when
streaming at 4K.

### Recording: Movie File Out TOP

Records its input while **Record** is on (or while the *Record* CHOP input is above
0.5): a **PNG** or **EXR** sequence (`name_00001.png`…), or an **MP4** (needs
OpenCV). Paths starting with `//` are relative to the .blend.

In Real Time mode every cooked frame is written, so the result follows the real
frame rate. For a perfect, fixed-rate recording use the **Timeline** clock and play
the timeline with *Play Every Frame*, or render offline as PULSAR's
`demo/render_preview.py` does (a template for your own exports: Timeline clock,
one cook per frame, frames piped to ffmpeg).

### Offline rendering without a window

Blender running without a window (`blender -b`, or the `bpy` Python module) never
finishes a GPU frame, so GPU memory is not recycled and very long runs eventually
crash. `render_preview.py` therefore renders in segments of 120 frames, each in a
fresh process with 1.5 s of pre-roll to rebuild trails and envelopes. Use the same
approach for your own headless exports.

---

## 15. Performance

Where the time goes:

- **CHOPs** cost Python time on the CPU: roughly 10–15 µs per node for control
  signals (a chain of 61 Math nodes cooks in under 1 ms). Hundreds of CHOPs are
  fine; thousands are not.
- **TOPs** are GPU passes. Cost grows with resolution and with the number of texture
  reads in a shader (blurs, blooms). 16-bit float is the sweet spot; 32-bit costs
  twice the memory bandwidth.
- **GPU → CPU copies** are the expensive operations: TOP to CHOP, TOP to Image,
  Movie File Out, Stream Out. Keep their resolution reasonable and use *Every Nth
  Frame* / *Max FPS* where available.
- **Render TOP** costs one viewport render of the scene per frame.
- **Exports** cost what Blender needs to re-evaluate the objects you change.

What to do:

1. Watch the **Performance** panel: it lists the slowest nodes.
2. Lower the **Resolution** (Engine settings) while designing; raise it for the show.
3. Turn off **Redraw 3D Views** when the 3D view is only a Render TOP source, and
   keep that 3D view in *Solid* shading — the Render TOP renders with EEVEE anyway.
4. Turn off **Node Previews** during a show, or close the node editor.
5. Make feedback frame-rate independent (chapter 7) so a drop in fps does not
   change the look.

---

## 16. The PULSAR demo

PULSAR is a complete audio-reactive piece built only from Live Nodes: a black sun
whose corona is the audio spectrum, feedback trails, a 3D ring of bars instanced
by Geometry Nodes and rendered live, bloom, chromatic aberration on the kicks, tone
mapping, grain and a typographic HUD. Its soundtrack (124 BPM, 8 bars) is
synthesised by code.

**Open it**: `demo/pulsar.blend` (with `pulsar_loop.wav` next to it), click the
**PULSAR** workspace tab, **Start**. Or build it in any file: *Modules & Examples ›
PULSAR*. **Play it** from the Perform panel: Intensity, Trails, Hue Shift, 3D Ring,
**Glitch** (`Space`) and **Flash** (`F`).

The network is laid out in eight numbered frames, left to right:

1. **AUDIO** — the loop, its analysis and a 64-band spectrum; the kick becomes an envelope.
2. **PERFORM** — the controls and keys.
3. **BRAIN** — a Script node (`pulsar_brain.py`) that turns everything into named
   channels: the first 16 are shader uniforms, the rest drive parameters by name.
   It also computes the frame-rate factor for the feedback.
4. **ECLIPSE** — `pulsar_eclipse.glsl`, reading the spectrum as a texture.
5. **FEEDBACK** — Feedback TOP + `pulsar_trails.glsl` (*Trail Loop*): zoom, swirl,
   fade, blur and colour drift in one frame-rate independent pass, then *Mix*
   puts the eclipse on top.
6. **3D** — `pulsar_ring.py` lays the spectrum out as 96 points → CHOP to Mesh →
   Geometry Nodes bars; Export CHOPs drive the core, the spin, the bar glow and the
   camera; Render TOP draws it. The camera is orthographic so the 3D core always
   matches the 2D disc.
7. **POST** — bloom, chromatic split, mosaic, and `pulsar_finish.glsl` (ACES tone
   mapping, flash, vignette, scanlines, grain, glitch tearing).
8. **OUTPUT** — HUD text (Format DAT + Text TOP), Out TOP, Stream Out (off).

**Make it yours**: point *Pulsar Loop* to your own track and change `BPM` at the
top of `pulsar_brain.py`; edit the palette in `pulsar_eclipse.glsl`; switch on
*Stream Out* to send it to OBS or Resolume.

**Offline video**: `blender -b demo/pulsar.blend --python demo/render_preview.py --
out.mp4 1280 720 30` (needs ffmpeg).

---

## 17. Writing your own nodes

Every node is a Python class. Add it to the `classes` tuple of a module in
`livenodes/nodes/` (or a new module listed in `livenodes/__init__.py`) and it
appears in the Add menu under its category.

```python
import bpy
from bpy.props import FloatProperty
from ..core.data import Channels
from ..core.tree import LNNode


class LN_GainCHOP(LNNode, bpy.types.Node):
    """Multiplies every channel"""            # tooltip and reference text
    bl_idname = "LN_GainCHOP"
    bl_label = "Gain CHOP"
    ln_category = "CHOP Filter"               # Add menu group
    gain: FloatProperty(name="Gain", default=2.0)

    def ln_init(self):                         # create sockets (Params is added for you)
        self.add_in('CHOP', "In")
        self.add_out('CHOP')

    def ln_draw(self, context, layout):        # node body
        layout.prop(self, "gain")

    def cook(self, ctx, inp):
        src = inp.chop()                       # Channels on "In"
        return src.replace(src.data * ctx.p.gain)   # ctx.p = parameters with Params applied
```

**Class attributes**

| Attribute | Meaning |
|---|---|
| `ln_family` | `'CHOP'`, `'TOP'`, `'DAT'` or `'OUT'` (node colour) |
| `ln_category` | Add menu group |
| `ln_params` | add the Params input (default `True`) |
| `ln_live` | needs keyboard/mouse capture |
| `ln_writes_scene` / `ln_reads_scene` | ordering relative to the scene (chapter 4) |

**Methods**

| Method | Purpose |
|---|---|
| `ln_init()` | create sockets with `add_in(family, name, multi=False)` and `add_out(family, name="Out")` |
| `ln_draw(context, layout)` / `ln_draw_ext(...)` | node body / sidebar UI |
| `cook(ctx, inp)` | return the value of the first output, or a dict `{socket name: value}` |

Never keep runtime state on `self` — Blender recreates node objects freely. Use
`ctx.state`: a dict per node that survives between frames and across Stop/Start;
it is cleared on Reset, when the node is deleted and when another file is opened
(objects in it with a `free()` method are freed then).

**Texture nodes** derive from `LNTopNode`, which adds the resolution settings and
`self.run(ctx, frag, uniforms, textures, size=None, slot=0, decl=())`: it renders a
full-screen pass with your fragment shader (`decl` lists push constants as
`('FLOAT', 'uAmount')` — keep them under 128 bytes) into a buffer owned by the node
and returns the texture. `slot` gives you several buffers for multi-pass effects.

**Background resources** (sockets, devices) go through
`core.services.get(kind, key, factory)`: the first call creates the object, later
calls reuse it, and Stop closes it (`close()`).

Run the test suite after changes (`python3 tests/run_tests.py`) and regenerate the
reference with `python3 tools/gen_node_reference.py`.

---

## 18. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Nothing moves | The engine is stopped (press Start), or the Clock is *Timeline* and the timeline is not playing. |
| A node is red | Read the message on the node or in the node sidebar; the system console has the traceback. |
| *needs 'python-rtmidi' / 'sounddevice' / …* | Install the module from *Modules & Examples*. |
| *needs a 3D Viewport open in some window* | Render TOP (Viewport method): open a 3D View anywhere, or switch to Final Render. |
| *no camera* | Set a camera on the Render TOP or in the scene. |
| *GLSL compile error* | The details are in the system console. Fix the text; the node recovers. |
| A GLSL TOP comes out tiny | Its first input is a small data texture: set Resolution to **Scene** or **Custom**. |
| OSC In shows nothing | Check the sender's target port and IP, the firewall, and that no other program uses the port. Connect the Log output to a Text TOP. |
| MIDI device not found | Check the sidebar list of ports; part of the name is enough (case-insensitive). Stop/Start after plugging a device in. |
| Keyboard In does not react | Turn on *Capture Keyboard & Mouse* and press Start again (the capture starts with Start). |
| No sound from Audio File In | Check *Play* and *Volume*. In Timeline mode it is silent by design. |
| Webcam/microphone silent on macOS | Allow Blender in *System Settings › Privacy & Security*, then Stop/Start. |
| The look changes with the frame rate | Per-frame feedback: scale it by `dt` (chapter 7). |
| Low frame rate | See chapter 15: Performance panel, resolution, previews, readbacks, Redraw 3D Views. |
| Colours look washed out in previews/output (macOS) | Older versions applied the display gamma twice on sRGB/EDR framebuffers (Metal); this release follows Blender's own rule. If the output still differs from a recording, please report it with a screenshot. |
| Stream Out: receivers do not see NDI | Same network and subnet, firewall rules for NDI, mDNS allowed. |
| Spout/Syphon unavailable | They exist only on Windows / macOS respectively; use NDI elsewhere. |
| Headless render crashes after a few hundred frames | Render in segments (chapter 14). |

---

## 19. Reference tables

### TouchDesigner → Live Nodes

| TouchDesigner | Live Nodes |
|---|---|
| CHOP / TOP / DAT | same families |
| Parameter references, CHOP exports to parameters | the **Params** input; Export CHOP for Blender properties |
| Null CHOP/TOP | Null CHOP / Null TOP |
| Feedback TOP | Feedback TOP (pick the target) |
| Script CHOP/DAT/TOP | Script node (one node, three outputs) |
| Execute DAT | Execute DAT |
| GLSL TOP | GLSL TOP (+ Shadertoy compatibility) |
| Render TOP + SOPs | Render TOP + the Blender scene and Geometry Nodes |
| Window COMP, Perform mode | Output Window (fullscreen) + Perform panel |
| Panel COMPs, custom parameters | Control CHOP + Perform panel |
| Movie File In/Out, Video Device In | same names |
| NDI Out, Spout/Syphon Out | Stream Out TOP |
| COMP containers | not available: use Frames to organise, several networks per file |

### Files in the repository

| Path | Contents |
|---|---|
| `livenodes/` | the add-on: `core/` (engine, data types, GPU, network, streaming), `nodes/`, `ui/`, `demos/` |
| `dist/livenodes.zip` | ready-to-install add-on |
| `demo/` | `pulsar.blend`, its soundtrack, build and offline-render scripts |
| `docs/` | this manual and the generated node reference |
| `tests/run_tests.py` | headless test suite (`pip install bpy`, then run it) |
| `tools/gen_node_reference.py` | regenerates `docs/NODES.md` |

### Keyboard

| Keys | Where | Action |
|---|---|---|
| `Ctrl+Shift+Space` | Node Editor | Start / Stop |
| `Shift+A` | Node Editor | add a node |
| `M` | Node Editor | mute (bypass) the selected nodes |
| `N` | any editor | sidebar (*Live* tab) |
