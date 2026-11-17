# Live Nodes — node reference

Generated from the add-on's code by `tools/gen_node_reference.py` — 89 nodes. See the [manual](MANUAL.md) for concepts and workflows.

Conventions:

- **Params**: ✓ means the parameter can be driven by a channel of the same name on the node's *Params* input (vector parameters by component: `name.x`, `name.r`, `name0`…).
- Every TOP also has the common resolution settings described in [TOP resolution](#top-resolution-common-to-every-top).
- **Output channels** are the names a node produces with its default settings; filters generally keep the names of their input.

## Contents

- **CHOP Generate** — [Beat CHOP](#beat-chop), [Constant CHOP](#constant-chop), [Control CHOP](#control-chop), [LFO CHOP](#lfo-chop), [Noise CHOP](#noise-chop), [Pattern CHOP](#pattern-chop), [Time CHOP](#time-chop), [Timer CHOP](#timer-chop), [Trigger CHOP](#trigger-chop)
- **CHOP Input** — [Audio Device In CHOP](#audio-device-in-chop), [Audio File In CHOP](#audio-file-in-chop), [DMX In CHOP](#dmx-in-chop), [Keyboard In CHOP](#keyboard-in-chop), [MIDI In CHOP](#midi-in-chop), [Mouse In CHOP](#mouse-in-chop), [OSC In CHOP](#osc-in-chop), [Object CHOP](#object-chop), [Property In CHOP](#property-in-chop)
- **CHOP Audio** — [Audio Analysis CHOP](#audio-analysis-chop), [Audio Spectrum CHOP](#audio-spectrum-chop)
- **CHOP Filter** — [Analyze CHOP](#analyze-chop), [Count CHOP](#count-chop), [Delay CHOP](#delay-chop), [Expression CHOP](#expression-chop), [Feedback CHOP](#feedback-chop), [Hold CHOP](#hold-chop), [Lag CHOP](#lag-chop), [Limit CHOP](#limit-chop), [Logic CHOP](#logic-chop), [Math CHOP](#math-chop), [Merge CHOP](#merge-chop), [Null CHOP](#null-chop), [Resample CHOP](#resample-chop), [Select CHOP](#select-chop), [Shuffle CHOP](#shuffle-chop), [Slope CHOP](#slope-chop), [Speed CHOP](#speed-chop), [Spring CHOP](#spring-chop), [Switch CHOP](#switch-chop), [Trail CHOP](#trail-chop)
- **CHOP Output** — [CHOP to Mesh](#chop-to-mesh), [DMX Out CHOP](#dmx-out-chop), [Export CHOP](#export-chop), [MIDI Out CHOP](#midi-out-chop), [OSC Out CHOP](#osc-out-chop)
- **TOP Generate** — [CHOP to TOP](#chop-to-top), [Constant TOP](#constant-top), [Feedback TOP](#feedback-top), [GLSL TOP](#glsl-top), [Noise TOP](#noise-top), [Ramp TOP](#ramp-top), [Shape TOP](#shape-top), [Text TOP](#text-top)
- **TOP Input** — [Image TOP](#image-top), [Movie File In TOP](#movie-file-in-top), [Render TOP](#render-top), [Video Device In TOP](#video-device-in-top)
- **TOP Filter** — [Bloom TOP](#bloom-top), [Blur TOP](#blur-top), [Corner Pin TOP](#corner-pin-top), [Displace TOP](#displace-top), [Edge TOP](#edge-top), [Key TOP](#key-top), [Level TOP](#level-top), [Lookup TOP](#lookup-top), [Mirror TOP](#mirror-top), [Normal Map TOP](#normal-map-top), [Null TOP](#null-top), [Pixelate TOP](#pixelate-top), [RGB Split TOP](#rgb-split-top), [Resolution TOP](#resolution-top), [Transform TOP](#transform-top)
- **TOP Composite** — [Composite TOP](#composite-top), [Cross TOP](#cross-top), [Switch TOP](#switch-top)
- **TOP Convert** — [TOP to CHOP](#top-to-chop)
- **TOP Output** — [Movie File Out TOP](#movie-file-out-top), [Out TOP](#out-top), [Stream Out TOP](#stream-out-top), [TOP to Image](#top-to-image)
- **DAT** — [CHOP to DAT](#chop-to-dat), [DAT to CHOP](#dat-to-chop), [Execute DAT](#execute-dat), [File In DAT](#file-in-dat), [Format DAT](#format-dat), [Script](#script), [Table DAT](#table-dat), [Text DAT](#text-dat), [UDP In DAT](#udp-in-dat)

## TOP resolution (common to every TOP)

| Parameter | Identifier | Type | Default | Notes |
|---|---|---|---|---|
| Resolution | `res_mode` | choice | `AUTO` | Options: `AUTO` Auto — Use the input resolution, or the scene default for generators; `SCENE` Scene — Always use the default resolution of the Live Nodes settings; `CUSTOM` Custom — Use the resolution set on this node. |
| Width | `res_x` | integer | 1280 | Range 1 – 16384. |
| Height | `res_y` | integer | 720 | Range 1 – 16384. |

## CHOP Generate

### Beat CHOP

`LN_BeatCHOP` · family **CHOP**

Tempo clock: beat ramps, pulses and counters, with tap tempo.

| | |
|---|---|
| Inputs | Params (CHOP) |
| Outputs | Out (CHOP) |
| Output channels | `ramp`, `pulse`, `sine`, `beat`, `bar`, `bar_ramp`, `count` |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| BPM | `bpm` | number | 120.0 | ✓ | Range 1.0 – 999.0. |
| Beats / Bar | `beats_per_bar` | integer | 4 | ✓ | Range 1 – 32. |
| Multiplier | `multiplier` | number | 1.0 | ✓ | Speed up or slow down the ramp (0.5 = half time). Range 0.0625 – 16.0. |

### Constant CHOP

`LN_ConstantCHOP` · family **CHOP**

Fixed values, one per named channel.

| | |
|---|---|
| Inputs | Params (CHOP) |
| Outputs | Out (CHOP) |
| Output channels | `chan1` |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Names | `names` | text | `chan1` |  | Space separated channel names (up to 8). |
| Values | `values` | 8 × number | (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0) | ✓ |  |

### Control CHOP

`LN_ControlCHOP` · family **CHOP**

A slider, button or toggle shown in the Perform panel (3D View and Node Editor sidebar).

| | |
|---|---|
| Inputs | — |
| Outputs | Out (CHOP) |
| Output channels | `slider` |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Type | `kind` | choice | `SLIDER` |  | Options: `SLIDER` Slider; `TOGGLE` Toggle; `BUTTON` Momentary — On for a short moment when pressed; `XY` XY Pad — Two sliders. |
| Channel | `channel` | text | `slider` |  |  |
| Value | `value` | number | 0.0 |  | Range 0.0 – 1.0. |
| Y | `value_y` | number | 0.0 |  | Range 0.0 – 1.0. |
| On | `toggle` | on/off | off |  |  |
| Show in Perform Panel | `show_in_panel` | on/off | on |  |  |
| Panel Order | `order` | integer | 0 |  |  |

### LFO CHOP

`LN_LfoCHOP` · family **CHOP**

Low frequency oscillator.

| | |
|---|---|
| Inputs | Params (CHOP) |
| Outputs | Out (CHOP) |
| Output channels | `lfo` |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Channel | `channel` | text | `lfo` |  |  |
| Wave | `wave` | choice | `SINE` |  | Options: `SINE` Sine; `TRIANGLE` Triangle; `RAMP` Ramp — Sawtooth 0..1; `SQUARE` Square; `PULSE` Pulse — Single-frame pulse each cycle; `RANDOM` Random — New random value each cycle; `SMOOTH` Smooth Random — Interpolated random. |
| Frequency | `frequency` | number | 1.0 | ✓ | Cycles per second. |
| Amplitude | `amplitude` | number | 1.0 | ✓ |  |
| Offset | `offset` | number | 0.0 | ✓ |  |
| Phase | `phase` | number | 0.0 | ✓ | Phase offset in cycles. |
| Bias | `bias` | number | 0.5 | ✓ | Duty cycle of square and triangle. Range 0.0 – 1.0. |
| 0..1 | `unipolar` | on/off | off | ✓ | Output 0..1 instead of -1..1. |
| Seed | `seed` | integer | 0 | ✓ |  |

### Noise CHOP

`LN_NoiseCHOP` · family **CHOP**

Smooth or random noise per channel.

| | |
|---|---|
| Inputs | Params (CHOP) |
| Outputs | Out (CHOP) |
| Output channels | `noise` |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Names | `names` | text | `noise` |  | Space separated channel names. |
| Type | `kind` | choice | `SMOOTH` |  | Options: `SMOOTH` Smooth — Perlin noise; `FRACTAL` Fractal — Layered Perlin noise; `RANDOM` Random — White noise; `BROWNIAN` Brownian — Random walk. |
| Speed | `speed` | number | 1.0 | ✓ | How fast the noise evolves. |
| Amplitude | `amplitude` | number | 1.0 | ✓ |  |
| Offset | `offset` | number | 0.0 | ✓ |  |
| Roughness | `roughness` | number | 0.5 | ✓ | Range 0.0 – 1.0. |
| Seed | `seed` | integer | 0 | ✓ |  |

### Pattern CHOP

`LN_PatternCHOP` · family **CHOP**

A multi-sample shape: lookup curves, tables for instancing.

| | |
|---|---|
| Inputs | Params (CHOP) |
| Outputs | Out (CHOP) |
| Output channels | `pattern` (64 samples) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Channel | `channel` | text | `pattern` |  |  |
| Shape | `shape` | choice | `SINE` |  | Options: `SINE` Sine; `RAMP` Ramp; `TRIANGLE` Triangle; `SQUARE` Square; `GAUSSIAN` Gaussian; `RANDOM` Random. |
| Samples | `samples` | integer | 64 | ✓ | Range 1 – 65536. |
| Cycles | `cycles` | number | 1.0 | ✓ |  |
| Phase | `phase` | number | 0.0 | ✓ |  |
| Amplitude | `amplitude` | number | 1.0 | ✓ |  |
| Offset | `offset` | number | 0.0 | ✓ |  |
| Seed | `seed` | integer | 0 | ✓ |  |

### Time CHOP

`LN_TimeCHOP` · family **CHOP**

Engine clock: seconds, frame, delta and frame rate.

| | |
|---|---|
| Inputs | — |
| Outputs | Out (CHOP) |
| Output channels | `seconds`, `frame`, `delta`, `fps` |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Wall Clock | `wall_clock` | on/off | off |  | Also output the time of day. |

### Timer CHOP

`LN_TimerCHOP` · family **CHOP**

Countdown / stopwatch with start, pause and looping.

| | |
|---|---|
| Inputs | Trigger (CHOP), Params (CHOP) |
| Outputs | Out (CHOP) |
| Output channels | `fraction`, `seconds`, `done`, `cycles`, `running` |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Length | `length` | number | 4.0 | ✓ | Seconds. Range 0.001 – ∞. |
| On Done | `mode` | choice | `ONCE` |  | Options: `ONCE` Once; `LOOP` Loop; `PINGPONG` Ping Pong. |
| Autostart | `autostart` | on/off | on | ✓ |  |

### Trigger CHOP

`LN_TriggerCHOP` · family **CHOP**

Attack / decay / sustain / release envelope fired by a rising input.

| | |
|---|---|
| Inputs | In (CHOP), Params (CHOP) |
| Outputs | Out (CHOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Threshold | `threshold` | number | 0.5 | ✓ |  |
| Attack | `attack` | number | 0.05 | ✓ | Range 0.0 – ∞ s. |
| Decay | `decay` | number | 0.2 | ✓ | Range 0.0 – ∞ s. |
| Sustain | `sustain` | number | 0.0 | ✓ | Range 0.0 – 1.0. |
| Release | `release` | number | 0.3 | ✓ | Range 0.0 – ∞ s. |
| Peak | `peak` | number | 1.0 | ✓ |  |

## CHOP Input

### Audio Device In CHOP

`LN_AudioDeviceInCHOP` · family **CHOP**

Live audio from a microphone or line input.

| | |
|---|---|
| Inputs | — |
| Outputs | Out (CHOP) |
| Output channels | `chan1`, `chan2`… — the last *Samples* samples of each input channel |
| Requires | `sounddevice` |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Device | `device` | text | — |  | Device name (part of it is enough); empty = system default. |
| Channels | `channels` | integer | 1 |  | Range 1 – 8. |
| Sample Rate | `rate` | integer | 44100 |  | Range 8000 – 192000. |
| Samples | `window` | integer | 1024 |  | Samples output each frame. Range 64 – 16384. |

### Audio File In CHOP

`LN_AudioFileInCHOP` · family **CHOP**

Plays an audio file and outputs the samples at the play position.

| | |
|---|---|
| Inputs | Params (CHOP) |
| Outputs | Out (CHOP), Info (CHOP) |
| Output channels | Out: `chan1` (mono) or `chan1`, `chan2`… — the last *Samples* audio samples at the play position · Info: `position`, `length`, `fraction`, `playing` |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| File | `filepath` | text | — |  | File path (`//` = relative to the .blend). |
| Play | `play` | on/off | on | ✓ |  |
| Loop | `loop` | on/off | on | ✓ |  |
| Volume | `volume` | number | 1.0 | ✓ | Speaker volume (the channels are not scaled). Range 0.0 – 2.0. |
| Mono | `mono` | on/off | on | ✓ | Mix all channels down to one. |
| Samples | `window` | integer | 1024 | ✓ | Range 64 – 16384. |

### DMX In CHOP

`LN_DmxInCHOP` · family **CHOP**

Receives DMX over Art-Net.

| | |
|---|---|
| Inputs | — |
| Outputs | Out (CHOP) |
| Output channels | `dmx1` … `dmxN` (0–1) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Universe | `universe` | integer | 0 |  | Range 0 – 32767. |
| Channels | `count` | integer | 16 |  | Range 1 – 512. |
| Port | `port` | integer | 6454 |  | Range 1 – 65535. |

### Keyboard In CHOP

`LN_KeyboardInCHOP` · family **CHOP**

Key states as 0/1 channels (while the engine runs).

| | |
|---|---|
| Inputs | — |
| Outputs | Out (CHOP) |
| Output channels | `space`, `a`, `s`, `d` |
| Notes | reads the keyboard/mouse while the engine runs (Capture Keyboard & Mouse) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Keys | `keys` | text | `SPACE A S D` |  | Space separated Blender key names, e.g. SPACE A ONE LEFT_ARROW F1. |

### MIDI In CHOP

`LN_MidiInCHOP` · family **CHOP**

Notes and controllers from a MIDI device (channels appear as they are touched).

| | |
|---|---|
| Inputs | — |
| Outputs | Out (CHOP) |
| Output channels | created as controls are touched: `ch1n60` (note velocity 0–1), `ch1c7` (controller 0–1), `ch1pitch` (−1–1), `ch1pressure` (0–1) |
| Requires | `python-rtmidi` |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Port | `port` | text | — |  | Part of the device name; empty = first device. |
| Channels | `pattern` | text | `*` |  | Filter, e.g. 'ch1c*' for the controllers of MIDI channel 1. |

### Mouse In CHOP

`LN_MouseInCHOP` · family **CHOP**

Mouse position (0..1 across the window) and buttons.

| | |
|---|---|
| Inputs | — |
| Outputs | Out (CHOP) |
| Output channels | `x`, `y`, `left`, `middle`, `right`, `wheel` |
| Notes | reads the keyboard/mouse while the engine runs (Capture Keyboard & Mouse) |

### OSC In CHOP

`LN_OscInCHOP` · family **CHOP**

Receives OSC messages over UDP; each address becomes a channel.

| | |
|---|---|
| Inputs | — |
| Outputs | Out (CHOP), Log (DAT) |
| Output channels | Out: one channel per address, without the leading `/` (`fader/1`); messages with several numbers give `address1`, `address2`… · Log (DAT): the last 32 messages |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Port | `port` | integer | 9000 |  | Range 1 – 65535. |
| Address Filter | `pattern` | text | `*` |  | Keep addresses matching this pattern, e.g. '/fader*'. |

### Object CHOP

`LN_ObjectCHOP` · family **CHOP**

Transform of an object, optionally relative to a second one.

| | |
|---|---|
| Inputs | — |
| Outputs | Out (CHOP) |
| Output channels | `tx` `ty` `tz` `rx` `ry` `rz` `sx` `sy` `sz` (+ `distance` with *Relative To*) |
| Notes | reads Blender data — cooked after nodes that write it |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Object | `target` | data-block | none |  | A Blender Object. |
| Relative To | `reference` | data-block | none |  | A Blender Object. |
| World Space | `world` | on/off | on |  |  |

### Property In CHOP

`LN_PropertyInCHOP` · family **CHOP**

Reads any Blender property as channels.

| | |
|---|---|
| Inputs | — |
| Outputs | Out (CHOP) |
| Output channels | `value` for a single number; `valuex` `valuey`… for vectors (the name is set by *Channel*) |
| Notes | reads Blender data — cooked after nodes that write it |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Type | `kind` | choice | `OBJECT` |  | Options: `OBJECT` Object; `MATERIAL` Material; `WORLD` World; `SCENE` Scene; `NODE` Live Node — A property of a node in this tree. |
| Object | `ob` | data-block | none |  | A Blender Object. |
| Material | `mat` | data-block | none |  | A Blender Material. |
| World | `world` | data-block | none |  | A Blender World. |
| Scene | `scene` | data-block | none |  | A Blender Scene. |
| Node | `node_name` | text | — |  |  |
| Path | `path` | text | `location` |  | Data path, as shown by 'Copy Data Path' in Blender, e.g. location, rotation_euler[2], data.energy, modifiers["Wave"].height, ["my_property"]. |
| Channel | `channel` | text | `value` |  |  |

## CHOP Audio

### Audio Analysis CHOP

`LN_AudioAnalysisCHOP` · family **CHOP**

Ready-made audio reactive signals: level, bass / mid / high, kick detection.

| | |
|---|---|
| Inputs | In (CHOP), Params (CHOP) |
| Outputs | Out (CHOP) |
| Output channels | `level`, `peak`, `bass`, `mid`, `high`, `kick` |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Gain | `gain` | number | 1.0 | ✓ | Range 0.0 – ∞. |
| Auto Gain | `auto_gain` | on/off | on | ✓ | Normalise each band against its recent maximum. |
| Smoothing | `smoothing` | number | 0.08 | ✓ | Range 0.0 – ∞ s. |
| Kick Sensitivity | `kick_sensitivity` | number | 1.5 | ✓ | How far bass must jump above its average to count as a kick. Range 1.0 – 5.0. |

### Audio Spectrum CHOP

`LN_AudioSpectrumCHOP` · family **CHOP**

Frequency spectrum of an audio signal, as log-spaced bands.

| | |
|---|---|
| Inputs | In (CHOP), Params (CHOP) |
| Outputs | Out (CHOP) |
| Output channels | `spectrum` — one sample per band, low to high |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Bands | `bands` | integer | 32 | ✓ | Range 1 – 512. |
| Low Hz | `freq_low` | number | 30.0 | ✓ | Range 1.0 – ∞. |
| High Hz | `freq_high` | number | 16000.0 | ✓ | Range 10.0 – ∞. |
| Decibel Scale | `decibels` | on/off | on | ✓ | Map -60..0 dB to 0..1 (closer to how we hear). |
| Gain | `gain` | number | 1.0 | ✓ | Range 0.0 – ∞. |
| Falloff | `falloff` | number | 0.15 | ✓ | How slowly bands drop. Range 0.0 – ∞ s. |

## CHOP Filter

### Analyze CHOP

`LN_AnalyzeCHOP` · family **CHOP**

Reduces many samples to one value per channel.

| | |
|---|---|
| Inputs | In (CHOP) |
| Outputs | Out (CHOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Function | `function` | choice | `AVERAGE` |  | Options: `AVERAGE` Average; `MIN` Minimum; `MAX` Maximum; `RMS` RMS Power; `SUM` Sum; `RANGE` Range; `INDEX_MAX` Index of Maximum; `FIRST` First; `LAST` Last. |

### Count CHOP

`LN_CountCHOP` · family **CHOP**

Counts rising edges.

| | |
|---|---|
| Inputs | In (CHOP), Reset (CHOP), Params (CHOP) |
| Outputs | Out (CHOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Threshold | `threshold` | number | 0.5 | ✓ |  |
| Loop At | `loop_at` | integer | 0 | ✓ | Wrap back to zero at this count (0 = never). Range 0 – 2147483647. |

### Delay CHOP

`LN_DelayCHOP` · family **CHOP**

Delays channels by a time.

| | |
|---|---|
| Inputs | In (CHOP), Params (CHOP) |
| Outputs | Out (CHOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Delay | `delay` | number | 0.5 | ✓ | Range 0.0 – 30.0 s. |

### Expression CHOP

`LN_ExpressionCHOP` · family **CHOP**

A Python expression evaluated per channel.

| | |
|---|---|
| Inputs | In (CHOP) |
| Outputs | Out (CHOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Expression | `expr` | text | `v * 2` |  | Variables: v (samples of this channel), i (channel index), n (channel name), t (seconds), dt, frame, ch (dict of all input values), np, math. |

### Feedback CHOP

`LN_FeedbackCHOP` · family **CHOP**

Outputs what another node produced on the previous frame, closing a loop.

| | |
|---|---|
| Inputs | Initial (CHOP) |
| Outputs | Out (CHOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Target | `target` | text | — |  | Node whose previous output is returned. |

### Hold CHOP

`LN_HoldCHOP` · family **CHOP**

Sample and hold: passes the input while Gate is on, freezes it otherwise.

| | |
|---|---|
| Inputs | In (CHOP), Gate (CHOP), Params (CHOP) |
| Outputs | Out (CHOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Sample On Edge | `on_edge` | on/off | on | ✓ | Sample only on the rising edge of the gate. |

### Lag CHOP

`LN_LagCHOP` · family **CHOP**

Smooths changes, with separate rise and fall times.

| | |
|---|---|
| Inputs | In (CHOP), Params (CHOP) |
| Outputs | Out (CHOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Lag Up | `lag_up` | number | 0.2 | ✓ | Range 0.0 – ∞ s. |
| Lag Down | `lag_down` | number | 0.2 | ✓ | Range 0.0 – ∞ s. |

### Limit CHOP

`LN_LimitCHOP` · family **CHOP**

Clamp, loop or fold values into a range; quantize to steps.

| | |
|---|---|
| Inputs | In (CHOP), Params (CHOP) |
| Outputs | Out (CHOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Mode | `mode` | choice | `CLAMP` |  | Options: `OFF` Off; `CLAMP` Clamp; `LOOP` Loop; `ZIGZAG` Zigzag. |
| Min | `low` | number | 0.0 | ✓ |  |
| Max | `high` | number | 1.0 | ✓ |  |
| Quantize | `step` | number | 0.0 | ✓ | Snap to multiples of this value (0 = off). Range 0.0 – ∞. |

### Logic CHOP

`LN_LogicCHOP` · family **CHOP**

Turns values into on/off: threshold, toggle, edge pulses, channel logic.

| | |
|---|---|
| Inputs | In (CHOP), Params (CHOP) |
| Outputs | Out (CHOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Threshold | `threshold` | number | 0.5 | ✓ |  |
| Mode | `mode` | choice | `RAW` |  | Options: `RAW` While On — 1 while the input is above the threshold; `TOGGLE` Toggle — Flip on every rising edge; `RISE` Rising Edge — One-frame pulse when turning on; `FALL` Falling Edge — One-frame pulse when turning off; `CHANGE` Any Change — One-frame pulse on either edge. |
| Combine | `combine` | choice | `NONE` |  | Options: `NONE` Off; `AND` And; `OR` Or; `XOR` Xor. |
| Invert | `invert` | on/off | off | ✓ |  |

### Math CHOP

`LN_MathCHOP` · family **CHOP**

Arithmetic on channels: scale, remap ranges, combine inputs or channels.

| | |
|---|---|
| Inputs | In (CHOP, multi), Params (CHOP) |
| Outputs | Out (CHOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Function | `unary` | choice | `NONE` |  | Options: `NONE` Off; `ABS` Absolute; `NEGATE` Negate; `SQRT` Square Root; `SQUARE` Square; `INVERSE` 1 / x; `SIGN` Sign; `ROUND` Round; `FLOOR` Floor; `CEIL` Ceiling; `SIN` Sine; `COS` Cosine; `LOG` Log 10; `EXP` Exp. |
| Combine Inputs | `combine_chops` | choice | `ADD` |  | How several connected inputs are merged, channel by channel. Options: `NONE` Off; `ADD` Add; `SUBTRACT` Subtract; `MULTIPLY` Multiply; `DIVIDE` Divide; `AVERAGE` Average; `MIN` Minimum; `MAX` Maximum; `LENGTH` Length. |
| Combine Channels | `combine_channels` | choice | `NONE` |  | Collapse all channels into one. Options: `NONE` Off; `ADD` Add; `SUBTRACT` Subtract; `MULTIPLY` Multiply; `DIVIDE` Divide; `AVERAGE` Average; `MIN` Minimum; `MAX` Maximum; `LENGTH` Length. |
| Pre-Add | `pre_add` | number | 0.0 | ✓ |  |
| Multiply | `multiply` | number | 1.0 | ✓ |  |
| Post-Add | `post_add` | number | 0.0 | ✓ |  |
| Range | `use_range` | on/off | off | ✓ | Remap From range to To range. |
| From Low | `from_low` | number | 0.0 | ✓ |  |
| From High | `from_high` | number | 1.0 | ✓ |  |
| To Low | `to_low` | number | 0.0 | ✓ |  |
| To High | `to_high` | number | 1.0 | ✓ |  |
| Clamp | `clamp` | on/off | off | ✓ | Clamp the result to the To range. |

### Merge CHOP

`LN_MergeCHOP` · family **CHOP**

Joins the channels of all inputs.

| | |
|---|---|
| Inputs | In (CHOP, multi) |
| Outputs | Out (CHOP) |

### Null CHOP

`LN_NullCHOP` · family **CHOP**

Passes channels through: a stable place to connect from.

| | |
|---|---|
| Inputs | In (CHOP) |
| Outputs | Out (CHOP) |

### Resample CHOP

`LN_ResampleCHOP` · family **CHOP**

Changes the number of samples.

| | |
|---|---|
| Inputs | In (CHOP), Params (CHOP) |
| Outputs | Out (CHOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Samples | `samples` | integer | 32 | ✓ | Range 1 – 65536. |

### Select CHOP

`LN_SelectCHOP` · family **CHOP**

Keeps channels by name pattern and optionally renames them.

| | |
|---|---|
| Inputs | In (CHOP) |
| Outputs | Out (CHOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Channels | `pattern` | text | `*` |  | Space separated names, with * and ? wildcards. |
| Rename To | `rename` | text | — |  | New names in order; a trailing * numbers the rest (e.g. 'band*'). |

### Shuffle CHOP

`LN_ShuffleCHOP` · family **CHOP**

Swaps channels and samples (e.g. a 32-sample spectrum into 32 channels).

| | |
|---|---|
| Inputs | In (CHOP) |
| Outputs | Out (CHOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Mode | `mode` | choice | `SPLIT` |  | Options: `SPLIT` Samples to Channels — One channel per sample of the first channel; `JOIN` Channels to Samples — One channel whose samples are the channel values; `SWAP` Transpose. |
| Prefix | `prefix` | text | `chan` |  |  |

### Slope CHOP

`LN_SlopeCHOP` · family **CHOP**

Rate of change per second.

| | |
|---|---|
| Inputs | In (CHOP) |
| Outputs | Out (CHOP) |

### Speed CHOP

`LN_SpeedCHOP` · family **CHOP**

Integrates the input over time (value = speed).

| | |
|---|---|
| Inputs | In (CHOP), Reset (CHOP), Params (CHOP) |
| Outputs | Out (CHOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Limit | `limit` | choice | `OFF` |  | Options: `OFF` Off; `CLAMP` Clamp; `LOOP` Loop. |
| Min | `low` | number | 0.0 | ✓ |  |
| Max | `high` | number | 1.0 | ✓ |  |

### Spring CHOP

`LN_SpringCHOP` · family **CHOP**

Follows the input like a mass on a spring: overshoot and wobble.

| | |
|---|---|
| Inputs | In (CHOP), Params (CHOP) |
| Outputs | Out (CHOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Stiffness | `stiffness` | number | 120.0 | ✓ | Range 0.0 – ∞. |
| Damping | `damping` | number | 8.0 | ✓ | Range 0.0 – ∞. |
| Mass | `mass` | number | 1.0 | ✓ | Range 0.001 – ∞. |

### Switch CHOP

`LN_SwitchCHOP` · family **CHOP**

Picks one of several inputs, with optional blending between neighbours.

| | |
|---|---|
| Inputs | In (CHOP, multi), Params (CHOP) |
| Outputs | Out (CHOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Index | `index` | number | 0.0 | ✓ | Range 0.0 – ∞. |
| Blend | `blend` | on/off | off | ✓ | Crossfade between inputs for fractional indices. |

### Trail CHOP

`LN_TrailCHOP` · family **CHOP**

Records the recent history of each channel as samples.

| | |
|---|---|
| Inputs | In (CHOP), Params (CHOP) |
| Outputs | Out (CHOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Length | `length` | integer | 120 | ✓ | Frames of history. Range 2 – 8192. |

## CHOP Output

### CHOP to Mesh

`LN_ChopToMeshCHOP` · family **OUT**

Writes samples into a mesh as points and attributes, ready for Geometry Nodes.

| | |
|---|---|
| Inputs | In (CHOP) |
| Outputs | — |
| Notes | writes Blender data — cooked before nodes that read the scene |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Mesh Object | `target` | data-block | none |  | Its vertices are replaced: one point per sample. A Blender Object. |
| Positions | `layout_mode` | choice | `LINE` |  | Options: `CHANNELS` From tx / ty / tz — Use channels named tx, ty, tz (missing ones are zero); `LINE` Line + Height — Spread points along X and lift them by the first channel; `KEEP` Leave Unchanged — Only write attributes. |
| Spread | `spread` | number | 4.0 |  | Length of the line along X. |
| Lift | `lift` | number | 1.0 |  | Height multiplier for the first channel. |

### DMX Out CHOP

`LN_DmxOutCHOP` · family **OUT**

Sends channels (0..1) as DMX over Art-Net; channel order = DMX address.

| | |
|---|---|
| Inputs | In (CHOP) |
| Outputs | — |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Host | `host` | text | `255.255.255.255` |  | Node IP, or the broadcast address. |
| Universe | `universe` | integer | 0 |  | Range 0 – 32767. |
| Start Address | `start` | integer | 1 |  | Range 1 – 512. |
| Port | `port` | integer | 6454 |  | Range 1 – 65535. |
| Rate | `rate` | number | 40.0 |  | Packets per second. Range 1.0 – 44.0. |

### Export CHOP

`LN_ExportCHOP` · family **OUT**

Drives any Blender property with a channel: objects, lights, cameras, materials, modifiers, Geometry Nodes inputs.

| | |
|---|---|
| Inputs | In (CHOP), Params (CHOP) |
| Outputs | — |
| Notes | writes Blender data — cooked before nodes that read the scene |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Type | `kind` | choice | `OBJECT` |  | Options: `OBJECT` Object; `MATERIAL` Material; `WORLD` World; `SCENE` Scene; `NODE` Live Node — A property of a node in this tree. |
| Object | `ob` | data-block | none |  | A Blender Object. |
| Material | `mat` | data-block | none |  | A Blender Material. |
| World | `world` | data-block | none |  | A Blender World. |
| Scene | `scene` | data-block | none |  | A Blender Scene. |
| Node | `node_name` | text | — |  |  |
| Path | `path` | text | `location` |  | Data path, as shown by 'Copy Data Path' in Blender, e.g. location, rotation_euler[2], data.energy, modifiers["Wave"].height, ["my_property"]. |
| Channel | `channel` | text | — |  | Channel(s) to export: empty = all in order. A vector property takes one channel per component; a single channel sets every component. |
| Multiply | `multiply` | number | 1.0 | ✓ |  |
| Add | `add` | number | 0.0 | ✓ |  |
| Modifier | `gn_modifier` | text | — |  | Geometry Nodes modifier: Path is then the name of one of its inputs. |

### MIDI Out CHOP

`LN_MidiOutCHOP` · family **OUT**

Sends controllers and notes from channels named ch1c7 / ch1n60.

| | |
|---|---|
| Inputs | In (CHOP) |
| Outputs | — |
| Requires | `python-rtmidi` |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Port | `port` | text | — |  | Part of the device name; empty = first device. |

### OSC Out CHOP

`LN_OscOutCHOP` · family **OUT**

Sends each channel as an OSC message.

| | |
|---|---|
| Inputs | In (CHOP) |
| Outputs | — |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Host | `host` | text | `127.0.0.1` |  |  |
| Port | `port` | integer | 9001 |  | Range 1 – 65535. |
| Prefix | `prefix` | text | `/` |  | Address prefix; the channel name is appended. |
| Only On Change | `on_change` | on/off | on |  |  |

## TOP Generate

### CHOP to TOP

`LN_ChopToTOP` · family **TOP**

Turns channels into a texture: one row per channel, one pixel per sample.

| | |
|---|---|
| Inputs | In (CHOP) |
| Outputs | Out (TOP) |

### Constant TOP

`LN_ConstantTOP` · family **TOP**

A solid colour.

| | |
|---|---|
| Inputs | Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Color | `rgba` | colour | (1.0, 1.0, 1.0, 1.0) | ✓ |  |

### Feedback TOP

`LN_FeedbackTOP` · family **TOP**

Outputs what another TOP rendered on the previous frame: trails, echoes, reaction loops.

| | |
|---|---|
| Inputs | Initial (TOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Target | `target_node` | text | — |  | TOP whose previous frame is returned (place it downstream of this node). |
| Reset | `reset` | on/off | off |  | Hold to restart the loop from the Initial input. |

### GLSL TOP

`LN_GlslTOP` · family **TOP**

Your own fragment shader, with textures and channels as inputs.

| | |
|---|---|
| Inputs | In 0 (TOP), In 1 (TOP), In 2 (TOP), In 3 (TOP), Uniforms (CHOP) |
| Outputs | Out (TOP) |
| Notes | see the manual's GLSL chapter for the variables and helpers available to the shader |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Shader | `source` | data-block | none |  | A Blender Text. |

### Noise TOP

`LN_NoiseTOP` · family **TOP**

Animated procedural noise.

| | |
|---|---|
| Inputs | Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Type | `kind` | choice | `FRACTAL` |  | Options: `SMOOTH` Smooth — Gradient noise; `FRACTAL` Fractal — Layered gradient noise; `CELL` Cellular — Distance to scattered points; `RANDOM` Random — Per-pixel white noise. |
| Scale | `scale` | number | 4.0 | ✓ |  |
| Octaves | `octaves` | integer | 4 | ✓ | Range 1 – 8. |
| Roughness | `roughness` | number | 0.5 | ✓ | Range 0.0 – 1.0. |
| Speed | `speed` | number | 0.25 | ✓ | How fast the pattern evolves. |
| Offset | `offset` | 2 × number | (0.0, 0.0) | ✓ |  |
| Amplitude | `amplitude` | number | 0.5 | ✓ |  |
| Offset Value | `base` | number | 0.5 | ✓ |  |
| Monochrome | `mono` | on/off | on | ✓ |  |

### Ramp TOP

`LN_RampTOP` · family **TOP**

Linear, radial or angular gradient between two colours.

| | |
|---|---|
| Inputs | Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Type | `kind` | choice | `LINEAR` |  | Options: `LINEAR` Linear; `RADIAL` Radial; `ANGULAR` Angular. |
| Start | `color_a` | colour | (0.0, 0.0, 0.0, 1.0) | ✓ |  |
| End | `color_b` | colour | (1.0, 1.0, 1.0, 1.0) | ✓ |  |
| Angle | `angle` | number | 0.0 | ✓ | In radians (shown in degrees). |
| Cycles | `cycles` | number | 1.0 | ✓ |  |
| Phase | `phase` | number | 0.0 | ✓ |  |
| Repeat | `repeat` | choice | `CLAMP` |  | Options: `CLAMP` Clamp; `REPEAT` Repeat; `MIRROR` Mirror. |

### Shape TOP

`LN_ShapeTOP` · family **TOP**

Circle, rectangle or polygon with soft edges or an outline.

| | |
|---|---|
| Inputs | Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Shape | `kind` | choice | `CIRCLE` |  | Options: `CIRCLE` Circle; `RECT` Rectangle; `POLYGON` Polygon. |
| Radius | `radius` | number | 0.25 | ✓ | Range 0.0 – ∞. |
| Size | `size` | 2 × number | (1.0, 1.0) | ✓ |  |
| Center | `center` | 2 × number | (0.0, 0.0) | ✓ |  |
| Rotation | `rotation` | number | 0.0 | ✓ | In radians (shown in degrees). |
| Sides | `sides` | integer | 6 | ✓ | Range 3 – 64. |
| Softness | `softness` | number | 0.0 | ✓ | Range 0.0 – 0.5. |
| Outline | `border` | number | 0.0 | ✓ | Outline width (0 = filled). Range 0.0 – ∞. |
| Fill | `fill` | colour | (1.0, 1.0, 1.0, 1.0) | ✓ |  |
| Background | `background` | colour | (0.0, 0.0, 0.0, 0.0) | ✓ |  |

### Text TOP

`LN_TextTOP` · family **TOP**

Renders text; connect a DAT to show live data.

| | |
|---|---|
| Inputs | Text (DAT), Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Text | `text` | text | `LIVE` |  |  |
| Size | `size` | number | 0.2 | ✓ | Line height as a fraction of the image height. Range 0.001 – ∞. |
| Position | `position` | 2 × number | (0.5, 0.5) | ✓ | Anchor in the image (0..1). |
| Align | `align` | choice | `CENTER` |  | Options: `LEFT` Left; `CENTER` Center; `RIGHT` Right. |
| Color | `font_color` | colour | (1.0, 1.0, 1.0, 1.0) | ✓ |  |
| Background | `background` | colour | (0.0, 0.0, 0.0, 0.0) | ✓ |  |
| Font | `font` | choice | `DEFAULT` |  | Options: `DEFAULT` Interface — Blender's interface font; `MONO` Monospace — Blender's bundled DejaVu Sans Mono; `FILE` File — A .ttf / .otf / .woff2 font file. |
| Font File | `font_file` | text | — |  | File path (`//` = relative to the .blend). |
| Letter Spacing | `tracking` | number | 0.0 | ✓ | Extra space between letters, as a fraction of the size. Range -0.2 – 1.0. |

## TOP Input

### Image TOP

`LN_ImageTOP` · family **TOP**

An image from the blend file or from disk.

| | |
|---|---|
| Inputs | — |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Image | `image` | data-block | none |  | A Blender Image. |

### Movie File In TOP

`LN_MovieFileTOP` · family **TOP**

Plays a movie file, in sync with the engine clock.

| | |
|---|---|
| Inputs | Params (CHOP) |
| Outputs | Out (TOP), Info (CHOP) |
| Output channels | Out: the frame · Info: `index`, `fraction`, `length`, `fps` |
| Requires | `opencv-python-headless` |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| File | `filepath` | text | — |  | File path (`//` = relative to the .blend). |
| Play | `play` | on/off | on | ✓ |  |
| Loop | `loop` | on/off | on | ✓ |  |
| Speed | `speed` | number | 1.0 | ✓ |  |
| Position | `cue` | number | 0.0 | ✓ | Jump here (0..1) while Play is off. Range 0.0 – 1.0. |

### Render TOP

`LN_RenderTOP` · family **TOP**

Renders the 3D scene through a camera every frame: fast viewport drawing, or a full offline render.

| | |
|---|---|
| Inputs | — |
| Outputs | Out (TOP) |
| Notes | reads Blender data — cooked after nodes that write it; Viewport method needs a 3D View open in some window; without a window it falls back to Final Render |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Camera | `camera` | data-block | none |  | A Blender Object. |
| Shading | `shading` | choice | `RENDERED` |  | Options: `VIEWPORT` As Viewport — Use the shading of the 3D view used for drawing; `RENDERED` Rendered — Force rendered (EEVEE) shading; `MATERIAL` Material Preview; `SOLID` Solid. |
| Transparent | `transparent` | on/off | off |  | Leave the world background out. |
| Method | `method` | choice | `VIEWPORT` |  | Options: `VIEWPORT` Viewport (real time) — Draw like the 3D viewport; needs a 3D View open somewhere; `FINAL` Final Render (offline) — Full render with the scene's render engine: slow, for Timeline-clock exports; also used automatically when Blender runs without a window. |

### Video Device In TOP

`LN_VideoDeviceTOP` · family **TOP**

Live camera input (webcam, capture card).

| | |
|---|---|
| Inputs | — |
| Outputs | Out (TOP) |
| Requires | `opencv-python-headless` |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Device | `device` | integer | 0 |  | Range 0 – 16. |
| Request Width | `capture_w` | integer | 1280 |  | Range 0 – 2147483647. |
| Request Height | `capture_h` | integer | 720 |  | Range 0 – 2147483647. |

## TOP Filter

### Bloom TOP

`LN_BloomTOP` · family **TOP**

Glow around bright areas.

| | |
|---|---|
| Inputs | In (TOP), Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Threshold | `threshold` | number | 0.6 | ✓ | Range 0.0 – ∞. |
| Radius | `radius` | number | 16.0 | ✓ | Range 0.0 – ∞. |
| Intensity | `intensity` | number | 1.0 | ✓ | Range 0.0 – ∞. |

### Blur TOP

`LN_BlurTOP` · family **TOP**

Gaussian blur.

| | |
|---|---|
| Inputs | In (TOP), Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Radius | `radius` | number | 8.0 | ✓ | In pixels. Range 0.0 – ∞. |
| Horizontal | `horizontal` | number | 1.0 | ✓ | Range 0.0 – ∞. |
| Vertical | `vertical` | number | 1.0 | ✓ | Range 0.0 – ∞. |

### Corner Pin TOP

`LN_CornerPinTOP` · family **TOP**

Projection mapping: pins the four image corners anywhere in the output.

| | |
|---|---|
| Inputs | In (TOP), Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Bottom Left | `bottom_left` | 2 × number | (0.0, 0.0) | ✓ |  |
| Bottom Right | `bottom_right` | 2 × number | (1.0, 0.0) | ✓ |  |
| Top Right | `top_right` | 2 × number | (1.0, 1.0) | ✓ |  |
| Top Left | `top_left` | 2 × number | (0.0, 1.0) | ✓ |  |

### Displace TOP

`LN_DisplaceTOP` · family **TOP**

Warps an image using the red and green of a second one.

| | |
|---|---|
| Inputs | In (TOP), Map (TOP), Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Weight | `weight` | 2 × number | (0.1, 0.1) | ✓ |  |
| Midpoint | `midpoint` | number | 0.5 | ✓ | Map value that means 'no displacement'. |
| Extend | `extend` | choice | `HOLD` |  | Options: `HOLD` Hold — Repeat the edge pixels; `REPEAT` Repeat — Tile; `MIRROR` Mirror — Tile, flipping every other copy; `ZERO` Zero — Transparent outside. |

### Edge TOP

`LN_EdgeTOP` · family **TOP**

Finds outlines.

| | |
|---|---|
| Inputs | In (TOP), Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Strength | `strength` | number | 2.0 | ✓ | Range 0.0 – ∞. |
| Width | `distance` | number | 1.0 | ✓ | Sample distance in pixels. Range 0.25 – ∞. |
| Edge Color | `edge_color` | colour | (1.0, 1.0, 1.0, 1.0) | ✓ |  |
| Over Source | `over` | on/off | off | ✓ | Draw the edges on top of the input. |

### Key TOP

`LN_KeyTOP` · family **TOP**

Threshold by brightness (luma key) or remove a colour (chroma key).

| | |
|---|---|
| Inputs | In (TOP), Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Mode | `mode` | choice | `LUMA` |  | Options: `LUMA` Luma — Keep pixels brighter than the threshold; `CHROMA` Chroma — Remove pixels close to the key colour. |
| Key Color | `key` | colour | (0.0, 1.0, 0.0, 1.0) | ✓ |  |
| Threshold | `threshold` | number | 0.5 | ✓ | Range 0.0 – ∞. |
| Softness | `softness` | number | 0.05 | ✓ | Range 0.0 – ∞. |
| Invert | `invert` | on/off | off | ✓ |  |
| Output Matte | `matte` | on/off | off | ✓ | Output the black and white mask. |

### Level TOP

`LN_LevelTOP` · family **TOP**

Brightness, contrast, gamma, hue, saturation, invert and opacity.

| | |
|---|---|
| Inputs | In (TOP), Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Brightness | `brightness` | number | 1.0 | ✓ | Range 0.0 – ∞. |
| Contrast | `contrast` | number | 1.0 | ✓ | Range 0.0 – ∞. |
| Gamma | `gamma` | number | 1.0 | ✓ | Range 0.01 – ∞. |
| Hue Shift | `hue` | number | 0.0 | ✓ | In turns: 1.0 is a full rotation. |
| Saturation | `saturation` | number | 1.0 | ✓ | Range 0.0 – ∞. |
| Opacity | `opacity` | number | 1.0 | ✓ | Range 0.0 – 1.0. |
| Invert | `invert` | number | 0.0 | ✓ | Range 0.0 – 1.0. |
| Black Level | `black` | number | 0.0 | ✓ |  |
| White Level | `white` | number | 1.0 | ✓ |  |
| Clamp | `clamp` | on/off | off | ✓ | Clamp colours to 0..1. |

### Lookup TOP

`LN_LookupTOP` · family **TOP**

Recolours an image by brightness, through two colours or a ramp texture.

| | |
|---|---|
| Inputs | In (TOP), Ramp (TOP), Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Dark | `color_a` | colour | (0.02, 0.0, 0.1, 1.0) | ✓ |  |
| Bright | `color_b` | colour | (1.0, 0.6, 0.1, 1.0) | ✓ |  |

### Mirror TOP

`LN_MirrorTOP` · family **TOP**

Kaleidoscope, mirror and flip.

| | |
|---|---|
| Inputs | In (TOP), Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Mode | `mode` | choice | `KALEIDO` |  | Options: `KALEIDO` Kaleidoscope; `MIRROR_X` Mirror X; `MIRROR_Y` Mirror Y; `MIRROR_XY` Mirror Both; `FLIP_X` Flip X; `FLIP_Y` Flip Y. |
| Segments | `segments` | number | 6.0 | ✓ | Range 1.0 – 64.0. |
| Rotation | `rotation` | number | 0.0 | ✓ | In radians (shown in degrees). |
| Source Spin | `spin` | number | 0.0 | ✓ | Rotates what is seen inside each segment. In radians (shown in degrees). |
| Center | `center` | 2 × number | (0.0, 0.0) | ✓ |  |

### Normal Map TOP

`LN_NormalMapTOP` · family **TOP**

Turns brightness into a tangent-space normal map for materials.

| | |
|---|---|
| Inputs | In (TOP), Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Strength | `strength` | number | 4.0 | ✓ |  |

### Null TOP

`LN_NullTOP` · family **TOP**

Passes the image through: a stable place to connect from.

| | |
|---|---|
| Inputs | In (TOP) |
| Outputs | Out (TOP) |

### Pixelate TOP

`LN_PixelateTOP` · family **TOP**

Mosaic blocks and colour posterising.

| | |
|---|---|
| Inputs | In (TOP), Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Block Size | `block` | number | 16.0 | ✓ | In pixels. Range 1.0 – ∞. |
| Color Levels | `levels` | integer | 0 | ✓ | Posterise to this many levels (0 = off). Range 0 – 256. |

### RGB Split TOP

`LN_RgbSplitTOP` · family **TOP**

Offsets red and blue for a chromatic aberration look.

| | |
|---|---|
| Inputs | In (TOP), Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Amount | `amount` | number | 0.01 | ✓ |  |
| Angle | `angle` | number | 0.0 | ✓ | In radians (shown in degrees). |
| Radial | `radial` | on/off | off | ✓ | Grow the offset away from the centre. |

### Resolution TOP

`LN_ResolutionTOP` · family **TOP**

Resamples the image to another resolution.

| | |
|---|---|
| Inputs | In (TOP) |
| Outputs | Out (TOP) |

### Transform TOP

`LN_TransformTOP` · family **TOP**

Move, rotate, scale and tile an image.

| | |
|---|---|
| Inputs | In (TOP), Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Translate | `translate` | 2 × number | (0.0, 0.0) | ✓ |  |
| Rotate | `rotate` | number | 0.0 | ✓ | In radians (shown in degrees). |
| Scale | `scale` | 2 × number | (1.0, 1.0) | ✓ |  |
| Uniform Scale | `uniform_scale` | number | 1.0 | ✓ |  |
| Pivot | `pivot` | 2 × number | (0.5, 0.5) | ✓ |  |
| Extend | `extend` | choice | `ZERO` |  | Options: `HOLD` Hold — Repeat the edge pixels; `REPEAT` Repeat — Tile; `MIRROR` Mirror — Tile, flipping every other copy; `ZERO` Zero — Transparent outside. |
| Background | `background` | colour | (0.0, 0.0, 0.0, 0.0) | ✓ |  |

## TOP Composite

### Composite TOP

`LN_CompositeTOP` · family **TOP**

Blends layers onto a base image.

| | |
|---|---|
| Inputs | Base (TOP), Layers (TOP, multi), Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Operation | `operation` | choice | `OVER` |  | Options: `OVER` Over — Layer on top, using its alpha; `ADD` Add; `SUBTRACT` Subtract; `MULTIPLY` Multiply; `SCREEN` Screen; `DIFFERENCE` Difference; `LIGHTEN` Lighten — Maximum; `DARKEN` Darken — Minimum; `INSIDE` Inside — Keep the base where the layer is opaque; `OUTSIDE` Outside — Keep the base where the layer is transparent; `UNDER` Under — Layer behind the base; `AVERAGE` Average. |
| Layer Opacity | `opacity` | number | 1.0 | ✓ | Range 0.0 – 1.0. |

### Cross TOP

`LN_CrossTOP` · family **TOP**

Crossfades between two images.

| | |
|---|---|
| Inputs | A (TOP), B (TOP), Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Cross | `factor` | number | 0.5 | ✓ | Range 0.0 – 1.0. |

### Switch TOP

`LN_SwitchTOP` · family **TOP**

Picks one of several images by index, optionally blending neighbours.

| | |
|---|---|
| Inputs | In (TOP, multi), Params (CHOP) |
| Outputs | Out (TOP) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Index | `index` | number | 0.0 | ✓ | Range 0.0 – ∞. |
| Blend | `blend` | on/off | off | ✓ |  |

## TOP Convert

### TOP to CHOP

`LN_TopToCHOP` · family **CHOP**

Samples an image into channels: average colour, or a row of pixels.

| | |
|---|---|
| Inputs | In (TOP) |
| Outputs | Out (CHOP) |
| Output channels | `r` `g` `b` `a` (one sample, or *Samples* samples in Row mode) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Mode | `mode` | choice | `AVERAGE` |  | Options: `AVERAGE` Average — Mean colour of the whole image; `ROW` Row — Pixels of one row as samples; `POINT` Point — The colour at one position. |
| Samples | `samples` | integer | 64 |  | Range 1 – 4096. |
| Position | `position` | 2 × number | (0.5, 0.5) |  | Range 0.0 – 1.0. |

## TOP Output

### Movie File Out TOP

`LN_MovieFileOutTOP` · family **OUT**

Records the input to an MP4 (OpenCV) or a PNG / EXR sequence.

| | |
|---|---|
| Inputs | In (TOP), Record (CHOP) |
| Outputs | — |
| Requires | `opencv-python-headless` (MP4 only) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Output | `filepath` | text | `//live_recording` |  | File path (`//` = relative to the .blend). |
| Format | `fmt` | choice | `PNG` |  | Options: `MP4` MP4 Movie — Needs OpenCV; `PNG` PNG Sequence; `EXR` EXR Sequence — Float, lossless. |
| Record | `record` | on/off | off |  |  |
| FPS | `fps` | number | 30.0 |  | Range 1.0 – ∞. |

### Out TOP

`LN_OutTOP` · family **OUT**

Final output: shown in output windows, the node editor backdrop and recordings.

| | |
|---|---|
| Inputs | In (TOP) |
| Outputs | — |

### Stream Out TOP

`LN_StreamOutTOP` · family **OUT**

Shares the image live with other apps: NDI (network, any OS), Spout (Windows), Syphon (macOS).

| | |
|---|---|
| Inputs | In (TOP) |
| Outputs | Info (CHOP) |
| Output channels | Info: `active`, `receivers`, `sent`, `width`, `height` |
| Requires | `ndi-python` (NDI), `SpoutGL` (Spout, Windows) or `syphon-python` (Syphon, macOS) |
| Notes | the default protocol is the native one of the operating system (Spout on Windows, Syphon on macOS, NDI elsewhere) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Protocol | `protocol` | choice | `NDI` |  | Options: `NDI` NDI — Video over the network to any NDI receiver (OBS, vMix, Resolume, TouchDesigner...); `SPOUT` Spout — Texture sharing with apps on this Windows PC; `SYPHON` Syphon — Texture sharing with apps on this Mac. |
| Name | `sender_name` | text | `Blender Live` |  | How the stream appears in receiving apps. |
| Active | `active` | on/off | on |  |  |
| Alpha | `alpha` | on/off | on |  | Send transparency (otherwise the image is opaque). |
| sRGB | `srgb` | on/off | on |  | Encode to sRGB like a normal video/display image (off = raw linear values). |
| Max FPS | `max_fps` | number | 60.0 |  | Upper limit on frames sent per second (0 = every cook). Range 0.0 – ∞. |
| Only When Connected | `only_connected` | on/off | on |  | Skip the GPU readback while no receiver is connected (NDI and Syphon). |

### TOP to Image

`LN_TopToImage` · family **OUT**

Copies a texture into a Blender image: use it in materials, the compositor or the image editor.

| | |
|---|---|
| Inputs | In (TOP) |
| Outputs | — |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Image | `image` | data-block | none |  | A Blender Image. |
| Every Nth Frame | `every` | integer | 1 |  | Copying costs a GPU readback: skip frames to save time. Range 1 – 60. |

## DAT

### CHOP to DAT

`LN_ChopToDAT` · family **DAT**

Channels as a name | value table.

| | |
|---|---|
| Inputs | In (CHOP) |
| Outputs | Out (DAT) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Digits | `digits` | integer | 3 |  | Range 0 – 9. |

### DAT to CHOP

`LN_DatToCHOP` · family **CHOP**

Numbers in a table become channels.

| | |
|---|---|
| Inputs | In (DAT) |
| Outputs | Out (CHOP) |
| Output channels | named after the table (first column, or first row in *Columns* layout) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Layout | `layout_mode` | choice | `NAME_VALUE` |  | Options: `NAME_VALUE` Name \| Value — First column names, second column values; `COLUMNS` Columns — First row names, each column a channel (rows become samples); `ROWS` Rows — First column names, each row a channel (columns become samples). |

### Execute DAT

`LN_ExecuteDAT` · family **DAT**

Runs Python when channels change: switch scenes, fire operators, trigger anything.

| | |
|---|---|
| Inputs | In (CHOP) |
| Outputs | — |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Run On | `on` | choice | `RISE` |  | Options: `RISE` Off to On — When a channel rises above 0.5; `FALL` On to Off — When a channel drops below 0.5; `CHANGE` Value Change — Whenever a value changes. |
| Code | `code` | text | `print(name, value)` |  | Python run per event. Variables: name, value, prev, ctx, bpy, scene. |
| Script | `script` | data-block | none |  | Optional: runs the whole text block instead of Code. A Blender Text. |

### File In DAT

`LN_FileInDAT` · family **DAT**

Reads a text / CSV / JSON file from disk, reloading when it changes.

| | |
|---|---|
| Inputs | — |
| Outputs | Out (DAT) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| File | `filepath` | text | — |  | File path (`//` = relative to the .blend). |
| Parse as Table | `as_table_` | on/off | off |  |  |

### Format DAT

`LN_FormatDAT` · family **DAT**

Builds text from channels with Python formatting, e.g. 'BPM {bpm:.0f}'.

| | |
|---|---|
| Inputs | In (CHOP) |
| Outputs | Out (DAT) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Template | `template` | text | `{seconds:.1f}` |  | Python format string; {name} is replaced by that channel's value. |

### Script

`LN_ScriptNode` · family **DAT**

Runs your Python every frame: anything Blender's Python can do.

| | |
|---|---|
| Inputs | In (CHOP), In 1 (TOP), In 2 (DAT) |
| Outputs | Channels (CHOP), Texture (TOP), Data (DAT) |
| Output channels | whatever `cook()` returns: a dict becomes channels, a string or rows become data, a GPU texture becomes the Texture output |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Script | `script` | data-block | none |  | A Blender Text. |

### Table DAT

`LN_TableDAT` · family **DAT**

A table (CSV or tab separated) from a text block; pick cells by row and column.

| | |
|---|---|
| Inputs | In (DAT) |
| Outputs | Out (DAT) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Text Block | `text` | data-block | none |  | A Blender Text. |

### Text DAT

`LN_TextDAT` · family **DAT**

Text from a Blender text block or typed in.

| | |
|---|---|
| Inputs | — |
| Outputs | Out (DAT) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Text Block | `text` | data-block | none |  | A Blender Text. |
| Text | `value` | text | — |  |  |

### UDP In DAT

`LN_UdpInDAT` · family **DAT**

Lines of text received over UDP.

| | |
|---|---|
| Inputs | — |
| Outputs | Out (DAT) |

| Parameter | Identifier | Type | Default | Params | Notes |
|---|---|---|---|---|---|
| Port | `port` | integer | 7000 |  | Range 1 – 65535. |
| Keep Lines | `keep` | integer | 10 |  | Range 1 – 256. |
