"""Headless test-suite: python3 tests/run_tests.py  (needs the `bpy` wheel).

Registers the add-on in a fresh Blender, builds networks and cooks them with a
fixed clock, checking channel values, GPU textures and Blender side effects.
"""
import math
import os
import socket
import sys
import tempfile
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import gpu  # noqa: E402
import numpy as np  # noqa: E402

gpu.init()

import livenodes  # noqa: E402
from livenodes.core import gpu_util, net  # noqa: E402
from livenodes.core.engine import ENGINE  # noqa: E402

livenodes.register()

SCENE = bpy.context.scene
SCENE.livenodes.res_x = 64
SCENE.livenodes.res_y = 36

RESULTS = []


def test(fn):
    RESULTS.append(fn)
    return fn


def new_tree():
    for t in [t for t in bpy.data.node_groups if t.bl_idname == "LiveNodeTree"]:
        bpy.data.node_groups.remove(t)
    ENGINE.reset()
    return bpy.data.node_groups.new("Test", "LiveNodeTree")


def node(tree, idname, **props):
    n = tree.nodes.new(idname)
    for k, v in props.items():
        setattr(n, k, v)
    return n


def link(tree, a, b, out=0, inp=0):
    tree.links.new(a.outputs[out], b.inputs[inp])


def cook(frames=1, dt=1 / 60):
    for _ in range(frames):
        ENGINE.tick(SCENE, now_time=ENGINE.time + dt, dt=dt)


def out(tree, n, sock=None):
    o = ENGINE.outputs.get(f"{tree.name}\x00{n.name}", {})
    return o.get(sock) if sock else next(iter(o.values()), None)


def no_errors():
    assert not ENGINE.errors, ENGINE.errors


def pixels(tex):
    return gpu_util.read_pixels(tex)


# -- CHOP ----------------------------------------------------------------
@test
def every_node_cooks_unconnected():
    t = new_tree()
    for cls in livenodes.node_classes():
        if cls.bl_idname in {"LN_AudioDeviceInCHOP", "LN_MidiInCHOP", "LN_MidiOutCHOP", "LN_VideoDeviceTOP", "LN_StreamOutTOP",
                             "LN_RenderTOP", "LN_OscInCHOP", "LN_DmxInCHOP", "LN_UdpInDAT", "LN_GlslTOP"}:
            continue  # need devices, a window, ports or a shader text
        node(t, cls.bl_idname)
    cook(3)
    no_errors()


@test
def lfo_and_math():
    t = new_tree()
    lfo = node(t, "LN_LfoCHOP", frequency=1.0)
    m = node(t, "LN_MathCHOP", multiply=2.0, post_add=1.0)
    link(t, lfo, m)
    cook(15)  # a quarter cycle at 60 fps
    v = out(t, m).get("lfo")
    assert abs(v - 3.0) < 1e-3, v
    m.use_range = True
    m.from_low, m.from_high, m.to_low, m.to_high = 1.0, 3.0, 0.0, 10.0
    cook(1)
    assert 9.0 < out(t, m).get("lfo") <= 10.0
    no_errors()


@test
def math_combines_inputs():
    t = new_tree()
    a = node(t, "LN_ConstantCHOP", names="a b", values=(1, 2, 0, 0, 0, 0, 0, 0))
    b = node(t, "LN_ConstantCHOP", names="x y", values=(10, 20, 0, 0, 0, 0, 0, 0))
    m = node(t, "LN_MathCHOP", combine_chops='MULTIPLY')
    link(t, a, m)
    link(t, b, m)
    cook()
    assert out(t, m).to_dict() == {"a": 10.0, "b": 40.0}, out(t, m).to_dict()
    m.combine_channels = 'ADD'
    cook()
    assert out(t, m).to_dict() == {"a": 50.0}


@test
def params_override_properties():
    t = new_tree()
    c = node(t, "LN_ConstantCHOP", names="frequency amplitude", values=(0.0, 5.0, 0, 0, 0, 0, 0, 0))
    lfo = node(t, "LN_LfoCHOP", wave='SINE', phase=0.25)
    link(t, c, lfo, 0, "Params")
    cook(10)
    assert abs(out(t, lfo).first() - 5.0) < 1e-4, out(t, lfo).first()


@test
def lag_spring_speed():
    t = new_tree()
    c = node(t, "LN_ConstantCHOP", values=(0.0,) * 8)
    lag = node(t, "LN_LagCHOP", lag_up=0.1, lag_down=0.1)
    spring = node(t, "LN_SpringCHOP")
    speed = node(t, "LN_SpeedCHOP")
    for dst in (lag, spring, speed):
        link(t, c, dst)
    cook(2)
    c.values[0] = 1.0
    cook(6)  # 0.1 s
    v = out(t, lag).first()
    assert 0.55 < v < 0.7, v  # 1 - e^-1
    cook(54)
    assert abs(out(t, speed).first() - 1.0) < 0.05, out(t, speed).first()
    cook(240)
    assert abs(out(t, spring).first() - 1.0) < 0.01


@test
def logic_count_trigger():
    t = new_tree()
    c = node(t, "LN_ConstantCHOP", values=(0.0,) * 8)
    logic = node(t, "LN_LogicCHOP", mode='TOGGLE')
    cnt = node(t, "LN_CountCHOP")
    trig = node(t, "LN_TriggerCHOP", attack=0.0, decay=0.1, sustain=0.0)
    for dst in (logic, cnt, trig):
        link(t, c, dst)
    cook()
    for _ in range(3):
        c.values[0] = 1.0
        cook()
        c.values[0] = 0.0
        cook()
    assert out(t, logic).first() == 1.0
    assert out(t, cnt).first() == 3.0
    c.values[0] = 1.0
    cook(2)
    assert out(t, trig).first() > 0.7
    cook(30)
    assert out(t, trig).first() == 0.0


@test
def select_merge_shuffle_trail():
    t = new_tree()
    c = node(t, "LN_ConstantCHOP", names="tx ty tz", values=(1, 2, 3, 0, 0, 0, 0, 0))
    sel = node(t, "LN_SelectCHOP", pattern="t[xz]", rename="a b")
    link(t, c, sel)
    merge = node(t, "LN_MergeCHOP")
    link(t, sel, merge)
    link(t, c, merge)
    trail = node(t, "LN_TrailCHOP", length=10)
    link(t, c, trail)
    shuffle = node(t, "LN_ShuffleCHOP", mode='JOIN')
    link(t, c, shuffle)
    cook(3)
    assert out(t, sel).to_dict() == {"a": 1.0, "b": 3.0}
    assert out(t, merge).names == ["a", "b", "tx", "ty", "tz"]
    assert out(t, trail).data.shape == (3, 10)
    assert list(out(t, shuffle).data[0]) == [1, 2, 3]


@test
def feedback_chop_loop():
    t = new_tree()
    one = node(t, "LN_ConstantCHOP", names="v", values=(1.0,) + (0,) * 7)
    fb = node(t, "LN_FeedbackCHOP")
    add = node(t, "LN_MathCHOP", combine_chops='ADD')
    fb.target = add.name
    link(t, one, fb, 0, "Initial")
    link(t, fb, add)
    link(t, one, add)
    cook(5)
    assert out(t, add).first() == 6.0, out(t, add).first()


@test
def expression_and_script():
    t = new_tree()
    c = node(t, "LN_ConstantCHOP", names="a b", values=(2, 3, 0, 0, 0, 0, 0, 0))
    e = node(t, "LN_ExpressionCHOP", expr="v * v + i")
    link(t, c, e)
    s = node(t, "LN_ScriptNode")
    txt = bpy.data.texts.new("s.py")
    txt.write("def cook(ctx, inputs):\n    ctx.state['n'] = ctx.state.get('n', 0) + 1\n"
              "    return {'n': ctx.state['n'], 'sum': sum(inputs.chop('In').to_dict().values())}\n")
    s.script = txt
    link(t, c, s)
    cook(4)
    assert out(t, e).to_dict() == {"a": 4.0, "b": 10.0}
    assert out(t, s, "Channels").to_dict() == {"n": 4.0, "sum": 5.0}
    no_errors()


@test
def errors_are_reported_per_node():
    t = new_tree()
    e = node(t, "LN_ExpressionCHOP", expr="v +* 2")
    c = node(t, "LN_ConstantCHOP")
    link(t, c, e)
    cook()
    assert any("SyntaxError" in m for m in ENGINE.errors.values())
    e.expr = "v"
    cook()
    no_errors()


@test
def mute_passes_through():
    t = new_tree()
    c = node(t, "LN_ConstantCHOP", values=(4.0,) + (0,) * 7)
    m = node(t, "LN_MathCHOP", multiply=10.0)
    n = node(t, "LN_NullCHOP")
    link(t, c, m)
    link(t, m, n)
    m.mute = True
    cook()
    assert out(t, n).first() == 4.0


@test
def export_to_blender():
    t = new_tree()
    ob = bpy.data.objects.new("Target", bpy.data.meshes.new("m"))
    SCENE.collection.objects.link(ob)
    ob["custom"] = 0.0
    c = node(t, "LN_ConstantCHOP", names="x y z", values=(1, 2, 3, 0, 0, 0, 0, 0))
    e1 = node(t, "LN_ExportCHOP", ob=ob, path="location")
    e2 = node(t, "LN_ExportCHOP", ob=ob, path="rotation_euler[2]", channel="z")
    e3 = node(t, "LN_ExportCHOP", ob=ob, path='["custom"]', channel="y", multiply=0.5)
    for e in (e1, e2, e3):
        link(t, c, e)
    cook()
    no_errors()
    assert tuple(ob.location) == (1.0, 2.0, 3.0)
    assert abs(ob.rotation_euler[2] - 3.0) < 1e-6
    assert ob["custom"] == 1.0


@test
def export_geometry_nodes_input():
    t = new_tree()
    ob = bpy.data.objects.new("GN", bpy.data.meshes.new("gm"))
    SCENE.collection.objects.link(ob)
    ng = bpy.data.node_groups.new("GNTest", 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Amount", in_out='INPUT', socket_type='NodeSocketFloat')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    mod = ob.modifiers.new("GeoNodes", 'NODES')
    mod.node_group = ng
    c = node(t, "LN_ConstantCHOP", values=(0.75,) + (0,) * 7)
    e = node(t, "LN_ExportCHOP", ob=ob, gn_modifier="GeoNodes", path="Amount")
    link(t, c, e)
    cook()
    no_errors()
    ident = next(i.identifier for i in ng.interface.items_tree if i.name == "Amount")
    value = getattr(mod.properties.inputs, ident).value if hasattr(mod, "properties") else mod[ident]
    assert abs(value - 0.75) < 1e-6, value


@test
def chop_to_mesh_attributes():
    t = new_tree()
    me = bpy.data.meshes.new("pts")
    ob = bpy.data.objects.new("Pts", me)
    p = node(t, "LN_PatternCHOP", samples=20, shape='RAMP')
    m = node(t, "LN_ChopToMeshCHOP", target=ob, layout_mode='LINE', lift=2.0)
    link(t, p, m)
    cook()
    no_errors()
    assert len(me.vertices) == 20
    vals = np.zeros(20, np.float32)
    me.attributes["pattern"].data.foreach_get("value", vals)
    assert abs(vals[10] - 0.5) < 1e-6
    assert abs(me.vertices[10].co.z - 1.0) < 1e-5


@test
def property_in_and_object_chop():
    t = new_tree()
    ob = bpy.data.objects.new("Src", None)
    SCENE.collection.objects.link(ob)
    ob.location = (1, 2, 3)
    bpy.context.view_layer.update()
    p = node(t, "LN_PropertyInCHOP", ob=ob, path="location", channel="loc")
    o = node(t, "LN_ObjectCHOP", target=ob)
    cook()
    assert out(t, p).to_dict() == {"locx": 1.0, "locy": 2.0, "locz": 3.0}
    assert abs(out(t, o).get("ty") - 2.0) < 1e-6


@test
def timer_and_beat():
    t = new_tree()
    tm = node(t, "LN_TimerCHOP", length=0.5, mode='LOOP')
    beat = node(t, "LN_BeatCHOP", bpm=120.0)
    cook(45)  # 0.75 s
    assert out(t, tm).get("cycles") == 1.0
    assert abs(out(t, tm).get("fraction") - 0.5) < 0.05
    assert out(t, beat).get("count") == 1.0


@test
def audio_file_spectrum_analysis():
    import aud
    path = os.path.join(tempfile.gettempdir(), "ln_test_tone.wav")
    aud.Sound.sine(440.0, 44100).limit(0, 2.0).write(path, rate=44100, channels=1)
    t = new_tree()
    a = node(t, "LN_AudioFileInCHOP", filepath=path, window=2048)
    sp = node(t, "LN_AudioSpectrumCHOP", bands=24, decibels=False)
    an = node(t, "LN_AudioAnalysisCHOP")
    link(t, a, sp)
    link(t, a, an)
    cook(20)
    no_errors()
    assert out(t, a).num_samples == 2048
    spec = out(t, sp).data[0]
    edges = np.geomspace(30.0, 16000.0, 25)
    peak_band = int(np.argmax(spec))
    assert edges[peak_band] <= 440.0 <= edges[peak_band + 1] * 1.05, (peak_band, edges[peak_band:peak_band + 2])
    assert out(t, an).get("mid") > out(t, an).get("high")


@test
def osc_roundtrip():
    msg = net.osc_message("/fader/1", 0.25, 3, "hi", True)
    assert net.osc_parse(msg) == [("/fader/1", [0.25, 3, "hi", True])]
    bundle = b"#bundle\x00" + b"\x00" * 8 + len(msg).to_bytes(4, "big") + msg
    assert net.osc_parse(bundle)[0][0] == "/fader/1"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    t = new_tree()
    osc = node(t, "LN_OscInCHOP", port=port)
    cook()
    sender = net.UdpSender()
    sender.send(net.osc_message("/fader/1", 0.25), "127.0.0.1", port)
    sender.send(net.osc_message("/xy", 0.1, 0.9), "127.0.0.1", port)
    time.sleep(0.3)
    cook()
    vals = out(t, osc).to_dict()
    assert abs(vals["fader/1"] - 0.25) < 1e-6 and abs(vals["xy2"] - 0.9) < 1e-6, vals
    assert "/xy" in out(t, osc, "Log")
    # OSC Out -> OSC In through the network
    c = node(t, "LN_ConstantCHOP", names="level", values=(0.5,) + (0,) * 7)
    o = node(t, "LN_OscOutCHOP", port=port, prefix="/out")
    link(t, c, o)
    cook()
    time.sleep(0.3)
    cook()
    assert abs(out(t, osc).get("out/level") - 0.5) < 1e-6
    sender.close()
    ENGINE.stop()


@test
def artnet_roundtrip():
    pkt = net.artnet_dmx(3, bytes([0, 128, 255]))
    uni, data = net.artnet_parse(pkt)
    assert uni == 3 and data[:3] == bytes([0, 128, 255])
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    t = new_tree()
    dmx_in = node(t, "LN_DmxInCHOP", port=port, universe=1, count=4)
    c = node(t, "LN_ConstantCHOP", names="a b", values=(1.0, 0.5, 0, 0, 0, 0, 0, 0))
    dmx_out = node(t, "LN_DmxOutCHOP", host="127.0.0.1", port=port, universe=1, start=2)
    link(t, c, dmx_out)
    cook()
    time.sleep(0.3)
    cook()
    vals = out(t, dmx_in).data[:, 0]
    assert vals[0] == 0.0 and vals[1] == 1.0 and abs(vals[2] - 128 / 255) < 1e-6, vals
    ENGINE.stop()


@test
def midi_message_encoding():
    from livenodes.nodes.chop_io import _MidiIn
    from livenodes.nodes.chop_out import midi_messages
    msgs = midi_messages(["ch1c7", "ch2n60", "other"], [1.0, 0.5], {})
    assert msgs == [[0xB0, 7, 127], [0x91, 60, 64]], msgs
    fake = _MidiIn.__new__(_MidiIn)
    import threading
    fake.lock = threading.Lock()
    fake.values = {}
    fake.handle([0x90, 60, 127])
    fake.handle([0xB1, 1, 64])
    fake.handle([0xE0, 0, 64])
    assert fake.values == {"ch1n60": 1.0, "ch2c1": 64 / 127, "ch1pitch": 0.0}, fake.values


@test
def dat_nodes():
    t = new_tree()
    txt = bpy.data.texts.new("table.csv")
    txt.write("speed,2.5\nsize,4\n")
    table = node(t, "LN_TableDAT", text=txt)
    d2c = node(t, "LN_DatToCHOP")
    link(t, table, d2c)
    c2d = node(t, "LN_ChopToDAT", digits=1)
    link(t, d2c, c2d)
    fmt = node(t, "LN_FormatDAT", template="{speed:.1f}/{size:.0f}/{missing}")
    link(t, d2c, fmt)
    cook()
    no_errors()
    assert out(t, d2c).to_dict() == {"speed": 2.5, "size": 4.0}
    assert out(t, c2d) == [["speed", "2.5"], ["size", "4.0"]]
    assert out(t, fmt) == "2.5/4/0.0"


@test
def execute_dat_fires_on_rise():
    t = new_tree()
    c = node(t, "LN_ConstantCHOP", names="go", values=(0.0,) * 8)
    ex = node(t, "LN_ExecuteDAT", code="scene['fired'] = scene.get('fired', 0) + 1")
    link(t, c, ex)
    cook(2)
    c.values[0] = 1.0
    cook(3)
    assert SCENE.get("fired") == 1


@test
def control_chop():
    t = new_tree()
    s = node(t, "LN_ControlCHOP", kind='SLIDER', channel="amt", value=0.4)
    b = node(t, "LN_ControlCHOP", kind='BUTTON', channel="go")
    cook()
    assert abs(out(t, s).get("amt") - 0.4) < 1e-6
    bpy.ops.livenodes.control_press(tree=t.name, node=b.name)
    cook()
    assert out(t, b).first() == 1.0
    cook()
    assert out(t, b).first() == 0.0


# -- TOP -----------------------------------------------------------------
@test
def constant_and_level():
    t = new_tree()
    c = node(t, "LN_ConstantTOP", rgba=(0.5, 0.25, 1.0, 1.0))
    lvl = node(t, "LN_LevelTOP", brightness=2.0)
    link(t, c, lvl)
    cook()
    no_errors()
    px = pixels(out(t, lvl))
    assert px.shape == (36, 64, 4)
    assert np.allclose(px[10, 10], [1.0, 0.5, 2.0, 1.0], atol=1e-2), px[10, 10]


@test
def every_top_filter_renders():
    t = new_tree()
    src = node(t, "LN_NoiseTOP")
    ramp = node(t, "LN_RampTOP")
    shape = node(t, "LN_ShapeTOP")
    names = ["LN_LevelTOP", "LN_BlurTOP", "LN_CornerPinTOP", "LN_TransformTOP", "LN_EdgeTOP", "LN_KeyTOP", "LN_MirrorTOP",
             "LN_PixelateTOP", "LN_RgbSplitTOP", "LN_BloomTOP", "LN_NormalMapTOP", "LN_ResolutionTOP", "LN_NullTOP"]
    nodes = []
    for n in names:
        f = node(t, n)
        link(t, src, f)
        nodes.append(f)
    for idname, ins in (("LN_CompositeTOP", ("Base", "Layers")), ("LN_CrossTOP", ("A", "B")),
                        ("LN_DisplaceTOP", ("In", "Map")), ("LN_LookupTOP", ("In", "Ramp"))):
        f = node(t, idname)
        link(t, src, f, 0, ins[0])
        link(t, ramp, f, 0, ins[1])
        nodes.append(f)
    sw = node(t, "LN_SwitchTOP", index=0.5, blend=True)
    link(t, src, sw)
    link(t, shape, sw)
    nodes.append(sw)
    for kind in ('SMOOTH', 'CELL', 'RANDOM'):
        nodes.append(node(t, "LN_NoiseTOP", kind=kind))
    cook(2)
    no_errors()
    for n in nodes:
        tex = out(t, n)
        assert tex is not None, n.name
        px = pixels(tex)
        assert np.isfinite(px).all(), n.name
        assert px.std() > 1e-4 or n.bl_idname in {"LN_NullTOP"}, (n.name, px.std())


@test
def composite_ops():
    t = new_tree()
    a = node(t, "LN_ConstantTOP", rgba=(0.2, 0.2, 0.2, 1.0))
    b = node(t, "LN_ConstantTOP", rgba=(0.5, 0.0, 0.0, 1.0))
    b2 = node(t, "LN_ConstantTOP", rgba=(0.5, 0.0, 0.0, 1.0))
    comp = node(t, "LN_CompositeTOP", operation='ADD')
    link(t, a, comp, 0, "Base")
    link(t, b, comp, 0, "Layers")
    link(t, b2, comp, 0, "Layers")
    cook()
    assert np.allclose(pixels(out(t, comp))[0, 0, :3], [1.2, 0.2, 0.2], atol=1e-2)
    comp.operation = 'MULTIPLY'
    cook()
    no_errors()


@test
def resolution_and_transform():
    t = new_tree()
    s = node(t, "LN_ShapeTOP", kind='RECT', radius=0.2)
    s.res_mode = 'CUSTOM'
    s.res_x, s.res_y = 100, 100
    x = node(t, "LN_TransformTOP", translate=(0.25, 0.0))
    link(t, s, x)
    cook()
    px = pixels(out(t, x))
    assert px.shape[:2] == (100, 100)
    # the 0.3..0.7 square moves to 0.55..0.95
    assert px[50, 60, 3] > 0.9 and px[50, 90, 3] > 0.9 and px[50, 40, 3] < 0.1 and px[50, 97, 3] < 0.1


@test
def corner_pin_maps_corners():
    t = new_tree()
    s = node(t, "LN_ConstantTOP", rgba=(1.0, 1.0, 1.0, 1.0))
    cp = node(t, "LN_CornerPinTOP", bottom_left=(0.5, 0.0), bottom_right=(1.0, 0.0), top_right=(1.0, 1.0), top_left=(0.5, 1.0))
    link(t, s, cp)
    cook()
    no_errors()
    px = pixels(out(t, cp))  # 64 wide: left half empty, right half filled
    assert px[18, 10, 3] < 0.01 and px[18, 50, 3] > 0.99, (px[18, 10], px[18, 50])


@test
def feedback_top_accumulates():
    t = new_tree()
    c = node(t, "LN_ConstantTOP", rgba=(0.1, 0.1, 0.1, 1.0))
    fb = node(t, "LN_FeedbackTOP")
    comp = node(t, "LN_CompositeTOP", operation='ADD')
    fb.target_node = comp.name
    link(t, fb, comp, 0, "Base")
    link(t, c, comp, 0, "Layers")
    cook(5)
    no_errors()
    v = pixels(out(t, comp))[5, 5, 0]
    assert abs(v - 0.5) < 0.02, v


@test
def glsl_and_shadertoy():
    t = new_tree()
    g = node(t, "LN_GlslTOP")
    txt = bpy.data.texts.new("s.glsl")
    txt.write("void main(){ fragColor = vec4(vUV.x, uP0.x, ln_noise(vec3(vUV*4.0, uTime))*0.0, 1.0); }")
    g.source = txt
    c = node(t, "LN_ConstantCHOP", values=(0.75,) + (0,) * 7)
    link(t, c, g, 0, "Uniforms")
    cook()
    no_errors()
    px = pixels(out(t, g))
    assert abs(px[0, -1, 0] - 1.0) < 0.05 and abs(px[0, 0, 1] - 0.75) < 1e-2
    st = bpy.data.texts.new("toy.glsl")
    st.write("void mainImage(out vec4 o, in vec2 f){ o = vec4(f / iResolution.xy, 0.5 + 0.5 * sin(iTime), 1.0); }")
    g.source = st
    cook()
    no_errors()
    txt.clear()
    txt.write("void main(){ fragColor = oops; }")
    g.source = txt
    cook()
    assert "GLSL" in next(iter(ENGINE.errors.values()))


@test
def text_top_draws():
    t = new_tree()
    tx = node(t, "LN_TextTOP", text="HELLO", size=0.5)
    cook()
    no_errors()
    assert pixels(out(t, tx))[..., 3].max() > 0.5


@test
def top_chop_conversions():
    t = new_tree()
    r = node(t, "LN_RampTOP")
    tc = node(t, "LN_TopToCHOP", mode='ROW', samples=8)
    link(t, r, tc)
    p = node(t, "LN_PatternCHOP", samples=16, shape='RAMP')
    ct = node(t, "LN_ChopToTOP")
    link(t, p, ct)
    cook()
    no_errors()
    row = out(t, tc).chan("r")
    assert len(row) == 8 and row[0] < row[-1]
    assert out(t, ct).width == 16 and out(t, ct).height == 1


@test
def image_in_and_out():
    t = new_tree()
    img = bpy.data.images.new("src", 8, 4, float_buffer=True)
    img.pixels.foreach_set(np.full(8 * 4 * 4, 0.5, np.float32))
    i = node(t, "LN_ImageTOP", image=img)
    dst = bpy.data.images.new("dst", 2, 2, float_buffer=True)
    o = node(t, "LN_TopToImage", image=dst)
    link(t, i, o)
    cook()
    no_errors()
    assert tuple(dst.size) == (8, 4)
    assert abs(dst.pixels[0] - 0.5) < 1e-2


@test
def record_png_sequence():
    t = new_tree()
    d = tempfile.mkdtemp()
    c = node(t, "LN_NoiseTOP")
    r = node(t, "LN_MovieFileOutTOP", filepath=os.path.join(d, "rec"), fmt='PNG', record=True)
    link(t, c, r)
    cook(3)
    no_errors()
    assert sorted(os.listdir(d)) == ["rec_00001.png", "rec_00002.png", "rec_00003.png"], os.listdir(d)


class _FakeSpoutSender:
    calls = []

    def setSenderName(self, name):
        self.calls.append(("name", name))

    def createOpenGL(self):
        self.calls.append(("createOpenGL",))
        return True

    def sendImage(self, buf, width, height, fmt, invert, fbo):
        self.calls.append(("send", np.array(buf, copy=True), width, height, fmt, invert, fbo))
        return True

    def setFrameSync(self, name):
        self.calls.append(("sync", name))

    def releaseSender(self):
        self.calls.append(("release",))

    def closeOpenGL(self):
        self.calls.append(("closeOpenGL",))


def _fake_modules(platform):
    """Stand-ins with the exact call signatures of SpoutGL 0.1.1 and syphon-python 0.2.0."""
    import types
    spout = types.ModuleType("SpoutGL")
    spout.SpoutSender = _FakeSpoutSender
    enums = types.ModuleType("SpoutGL.enums")
    enums.GL_RGBA = 0x1908
    spout.enums = enums
    syphon = types.ModuleType("syphon")
    published = []

    class Server:
        def __init__(self, name):
            self.name = name
            self.device = "metal-device"
            self.has_clients = True

        def publish_frame_texture(self, texture):
            published.append(np.array(texture["data"], copy=True))

        def stop(self):
            published.append("stopped")

    syphon.SyphonMetalServer = Server
    raw = types.ModuleType("syphon.utils.raw")
    raw.create_mtl_texture = lambda device, w, h: {"device": device, "size": (w, h), "data": None}
    npu = types.ModuleType("syphon.utils.numpy")

    def copy(image, texture):
        assert image.shape == (texture["size"][1], texture["size"][0], 4) and image.dtype == np.uint8
        texture["data"] = image
    npu.copy_image_to_mtl_texture = copy
    mods = {"SpoutGL": spout, "SpoutGL.enums": enums, "syphon": syphon, "syphon.utils": types.ModuleType("syphon.utils"),
            "syphon.utils.raw": raw, "syphon.utils.numpy": npu}
    return mods, published


def _with_platform(platform, fn):
    from livenodes.core import deps
    mods, published = _fake_modules(platform)
    saved_platform, saved_mods = sys.platform, {k: sys.modules.get(k) for k in mods}
    sys.modules.update(mods)
    deps._cache.pop("SpoutGL", None)
    deps._cache.pop("syphon", None)
    sys.platform = platform
    try:
        return fn(published)
    finally:
        sys.platform = saved_platform
        for k, v in saved_mods.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        deps._cache.pop("SpoutGL", None)
        deps._cache.pop("syphon", None)


def _stream_tree(protocol, rgba=(1.0, 0.0, 0.0, 0.5)):
    t = new_tree()
    ramp = node(t, "LN_RampTOP", angle=math.pi / 2)  # black at the bottom, white at the top
    c = node(t, "LN_ConstantTOP", rgba=rgba)
    comp = node(t, "LN_CompositeTOP", operation='MULTIPLY')
    link(t, ramp, comp, 0, "Base")
    link(t, c, comp, 0, "Layers")
    s = node(t, "LN_StreamOutTOP", protocol=protocol, sender_name="LN Test", max_fps=0.0)
    link(t, ramp, s)
    return t, s, c


@test
def stream_encode_orientation_srgb_alpha():
    from livenodes.nodes.top_io import encode_rgba8
    t = new_tree()
    ramp = node(t, "LN_RampTOP", angle=math.pi / 2)
    half = node(t, "LN_ConstantTOP", rgba=(0.5, 0.5, 0.5, 1.0))
    red = node(t, "LN_ConstantTOP", rgba=(1.0, 0.0, 0.0, 0.5))
    cook()

    class Ctx:
        state = {}
        time = 0.0
    img = encode_rgba8(Ctx, out(t, ramp), (64, 36))
    assert img.shape == (36, 64, 4) and img.dtype == np.uint8
    # row 0 is the top; the last row of the ramp is 0.014 linear = ~31 in sRGB
    assert img[0, 10, 0] > 250 and img[-1, 10, 0] < 40, (img[0, 10], img[-1, 10])
    img = encode_rgba8(Ctx, out(t, half), (8, 8))
    assert abs(int(img[4, 4, 0]) - 188) <= 1, img[4, 4]  # linear 0.5 -> sRGB 188
    img = encode_rgba8(Ctx, out(t, red), (8, 8))
    assert tuple(img[4, 4]) in {(255, 0, 0, 127), (255, 0, 0, 128)}, img[4, 4]  # un-premultiplied
    img = encode_rgba8(Ctx, out(t, red), (8, 8), srgb=False, alpha=False)
    assert img[4, 4, 3] == 255


@test
def stream_out_spout():
    def run(_published):
        _FakeSpoutSender.calls.clear()
        t, s, _ = _stream_tree('SPOUT')
        cook(2)
        no_errors()
        sends = [c for c in _FakeSpoutSender.calls if c[0] == "send"]
        assert len(sends) == 2, _FakeSpoutSender.calls
        _, img, w, h, fmt, invert, fbo = sends[0]
        assert (w, h, fmt, invert, fbo) == (64, 36, 0x1908, False, 0)
        assert img.shape == (36, 64, 4) and img[0, 0, 0] > 250 and img[-1, 0, 0] < 40
        assert ("name", "LN Test") in _FakeSpoutSender.calls and ("sync", "LN Test") in _FakeSpoutSender.calls
        # Blender draws with Vulkan here, so Spout must bring its own OpenGL context
        assert (("createOpenGL",) in _FakeSpoutSender.calls) == (gpu.platform.backend_type_get() != 'OPENGL')
        assert out(t, s).get("sent") == 2.0
        ENGINE.stop()
        assert ("release",) in _FakeSpoutSender.calls
    _with_platform("win32", run)


@test
def stream_out_syphon():
    def run(published):
        t, s, _ = _stream_tree('SYPHON')
        s.res_mode = 'CUSTOM'
        s.res_x, s.res_y = 32, 16
        cook(3)
        no_errors()
        assert len(published) == 3 and published[0].shape == (16, 32, 4)
        assert published[0][0, 0, 0] > 250 and published[0][-1, 0, 0] < 60
        assert out(t, s).get("receivers") == 1.0 and out(t, s).get("width") == 32.0
        ENGINE.stop()
        assert published[-1] == "stopped"
    _with_platform("darwin", run)


@test
def stream_out_wrong_platform_is_reported():
    t, s, _ = _stream_tree('SYPHON' if sys.platform != "darwin" else 'SPOUT')
    cook()
    assert "only available on" in ENGINE.errors.get(f"{t.name}\x00{s.name}", ""), ENGINE.errors


@test
def stream_out_ndi_loopback():
    try:
        import NDIlib as ndi
    except ImportError:
        print("    (skipped: ndi-python not installed)")
        return
    t, s, _ = _stream_tree('NDI')
    s.only_connected = True
    cook()
    no_errors()
    assert out(t, s).get("receivers") == 0.0 and out(t, s).get("sent") == 0.0  # nobody watching: no readback
    find_settings = ndi.FindCreate()
    find_settings.show_local_sources = True
    find_settings.extra_ips = "127.0.0.1"
    finder = ndi.find_create_v2(find_settings)
    src = None
    for _ in range(50):
        ndi.find_wait_for_sources(finder, 100)
        src = next((x for x in ndi.find_get_current_sources(finder) if "LN Test" in x.ndi_name), None)
        if src is not None:
            break
    assert src is not None, "NDI source not found"
    rc = ndi.RecvCreateV3()
    rc.color_format = ndi.RECV_COLOR_FORMAT_RGBX_RGBA
    recv = ndi.recv_create_v3(rc)
    ndi.recv_connect(recv, src)
    got = None
    for _ in range(100):
        cook()
        kind, video, _a, _m = ndi.recv_capture_v2(recv, 50)
        if kind == ndi.FRAME_TYPE_VIDEO:
            got = np.copy(video.data)
            ndi.recv_free_video_v2(recv, video)
            break
    ndi.recv_destroy(recv)
    ndi.find_destroy(finder)
    assert got is not None, "no NDI frame received"
    assert got.shape == (36, 64, 4), got.shape
    # top white, bottom dark (NDI compression softens the values a little)
    assert got[1, 5, 0] > 230 and got[-2, 5, 0] < 80, (got[1, 5], got[-2, 5])
    assert out(t, s).get("receivers") == 1.0 and out(t, s).get("sent") >= 1.0
    ENGINE.stop()


@test
def text_top_font_and_tracking():
    t = new_tree()
    plain = node(t, "LN_TextTOP", text="WIDE", size=0.3, font='MONO', align='LEFT', position=(0.05, 0.5))
    spaced = node(t, "LN_TextTOP", text="WIDE", size=0.3, font='MONO', align='LEFT', position=(0.05, 0.5), tracking=0.5)
    cook()
    no_errors()

    def right_edge(n):
        cols = np.where(pixels(out(t, n))[..., 3].max(0) > 0.2)[0]
        return cols.max()
    assert right_edge(spaced) > right_edge(plain) + 5, (right_edge(plain), right_edge(spaced))


@test
def text_top_redraws_only_on_change():
    t = new_tree()
    txt = node(t, "LN_TextDAT", value="ONE")
    tx = node(t, "LN_TextTOP", size=0.4)
    link(t, txt, tx, 0, "Text")
    cook()
    key = ENGINE.states[f"{t.name}\x00{tx.name}"]["drawn"]
    first = pixels(out(t, tx)).copy()
    cook(3)
    assert ENGINE.states[f"{t.name}\x00{tx.name}"]["drawn"] is key  # untouched: no redraw
    txt.value = "TWO LINES\nOF TEXT"
    cook()
    assert not np.array_equal(first, pixels(out(t, tx)))


@test
def scene_resolution_mode():
    t = new_tree()
    p = node(t, "LN_PatternCHOP", samples=16)
    data = node(t, "LN_ChopToTOP")
    link(t, p, data)
    g = node(t, "LN_GlslTOP", res_mode='SCENE')
    txt = bpy.data.texts.new("res.glsl")
    txt.write("void main(){ fragColor = texture(uIn0, vUV); }")
    g.source = txt
    link(t, data, g, 0, "In 0")
    cook()
    no_errors()
    assert (out(t, g).width, out(t, g).height) == (64, 36)
    g.res_mode = 'AUTO'
    cook()
    assert (out(t, g).width, out(t, g).height) == (16, 1)


@test
def scene_writers_cook_before_readers():
    t = new_tree()
    ob = bpy.data.objects.new("Order", None)
    SCENE.collection.objects.link(ob)
    reader = node(t, "LN_PropertyInCHOP", ob=ob, path="location", channel="loc")  # created first on purpose
    c = node(t, "LN_ConstantCHOP", names="x y z", values=(5, 6, 7, 0, 0, 0, 0, 0))
    e = node(t, "LN_ExportCHOP", ob=ob, path="location")
    link(t, c, e)
    cook()  # one frame: the reader must already see what the export wrote
    assert out(t, reader).get("locx") == 5.0, out(t, reader).to_dict()


@test
def audio_file_info_and_timeline_sync():
    import aud
    path = os.path.join(tempfile.gettempdir(), "ln_test_tone2.wav")
    aud.Sound.sine(220.0, 44100).limit(0, 1.0).write(path, rate=44100, channels=1)
    t = new_tree()
    a = node(t, "LN_AudioFileInCHOP", filepath=path)
    SCENE.livenodes.time_mode = 'TIMELINE'
    try:
        ENGINE.tick(SCENE, now_time=1.25, dt=1 / 30)  # loops after 1 s
        info = out(t, a, "Info")
        length = info.get("length")  # the encoder pads the file by a few samples
        assert abs(length - 1.0) < 0.01 and abs(info.get("position") - 1.25 % length) < 1e-5, info.to_dict()
    finally:
        SCENE.livenodes.time_mode = 'REALTIME'


@test
def display_respects_srgb_framebuffers():
    """What reaches the screen must not depend on whether Blender draws into an sRGB
    framebuffer (Metal/EDR and others) or a plain one: no double gamma."""
    from mathutils import Matrix
    tex = gpu_util.texture_from_array(np.full((4, 4, 4), [0.5, 0.5, 0.5, 1.0], np.float32))
    stored = {}
    for fmt in ('RGBA8', 'SRGB8_A8'):
        target = gpu.types.GPUTexture((8, 8), format=fmt)
        fb = gpu.types.GPUFrameBuffer(color_slots=(target,))
        with fb.bind(), gpu.matrix.push_pop(), gpu.matrix.push_pop_projection():
            gpu.matrix.load_identity()
            gpu.matrix.load_projection_matrix(Matrix(((2 / 8, 0, 0, -1), (0, 2 / 8, 0, -1), (0, 0, -1, 0), (0, 0, 0, 1))))
            gpu_util.draw_texture(tex, 0, 0, 8, 8)
            stored[fmt] = np.asarray(fb.read_color(0, 0, 8, 8, 4, 0, 'FLOAT')).reshape(8, 8, 4)[4, 4, 0]
    # linear 0.5 is shown as sRGB 0.735 either way
    assert abs(stored['RGBA8'] - 0.735) < 0.01 and abs(stored['SRGB8_A8'] - 0.735) < 0.01, stored


@test
def pulsar_feedback_is_frame_rate_independent():
    from livenodes.demos import pulsar
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    new_tree()
    tree = pulsar.build(bpy.context)
    tree.nodes["3D Scene"].mute = True
    SCENE.livenodes.res_x, SCENE.livenodes.res_y = 96, 54
    SCENE.livenodes.time_mode = 'TIMELINE'
    means = {}
    try:
        for fps in (30, 60):
            ENGINE.reset()
            for f in range(1, int(2.0 * fps) + 1):
                ENGINE.tick(SCENE, now_time=f / fps, dt=1.0 / fps)
            means[fps] = float(pixels(out(tree, tree.nodes["Trail Loop"]))[..., :3].mean())
    finally:
        SCENE.livenodes.time_mode = 'REALTIME'
        SCENE.livenodes.res_x, SCENE.livenodes.res_y = 64, 36
        bpy.data.node_groups.remove(tree)
    assert means[30] > 0.005, means
    assert abs(means[60] / means[30] - 1.0) < 0.15, means


@test
def mp4_recording_is_finalised_on_stop_and_plays_back():
    try:
        import cv2
    except ImportError:
        print("    (skipped: opencv not installed)")
        return
    t = new_tree()
    d = tempfile.mkdtemp()
    ramp = node(t, "LN_RampTOP", angle=math.pi / 2)
    rec = node(t, "LN_MovieFileOutTOP", filepath=os.path.join(d, "clip"), fmt='MP4', record=True, fps=30.0)
    link(t, ramp, rec)
    cook(12)
    no_errors()
    ENGINE.stop()  # must finalise the file while the node is still "recording"
    path = os.path.join(d, "clip.mp4")
    cap = cv2.VideoCapture(path)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    assert frames == 12, frames
    # and Movie File In plays it back, right side up
    t2 = new_tree()
    mov = node(t2, "LN_MovieFileTOP", filepath=path)
    cook(2)
    no_errors()
    px = pixels(out(t2, mov, "Out"))
    assert px.shape[:2] == (36, 64) and px[-2, 32, 0] > px[1, 32, 0] + 0.3, (px[-2, 32], px[1, 32])  # white on top
    assert out(t2, mov, "Info").get("length") == 12.0
    ENGINE.stop()


@test
def timeline_mode_is_deterministic():
    t = new_tree()
    lfo = node(t, "LN_LfoCHOP", frequency=0.5)
    vals = []
    for _ in range(2):
        ENGINE.reset()
        for f in range(1, 31):
            ENGINE.tick(SCENE, now_time=f / 30, dt=1 / 30)
        vals.append(out(t, lfo).first())
    assert vals[0] == vals[1]


@test
def examples_build_and_cook():
    new_tree()
    for key in ('FEEDBACK', 'AUDIO', 'INSTANCES', 'CONTROL', 'PULSAR'):
        assert bpy.ops.livenodes.add_example(example=key) == {'FINISHED'}
    cook(5)
    pulsar = bpy.data.node_groups["PULSAR"]
    assert out(pulsar, pulsar.nodes["Overlay"]).width == 1280  # the showcase sets its own resolution
    SCENE.livenodes.res_x, SCENE.livenodes.res_y = 64, 36
    errs = {k: v for k, v in ENGINE.errors.items() if "OSC" not in k}
    assert not errs, errs
    pts = bpy.data.objects["Live Points"]
    assert len(pts.data.vertices) == 64
    cube = bpy.data.objects["Live Cube"]
    assert cube.scale[0] == cube.scale[1] == cube.scale[2] >= 1.0
    ENGINE.stop()


@test
def rename_and_delete_nodes():
    t = new_tree()
    c = node(t, "LN_ConstantCHOP", values=(2.0,) + (0,) * 7)
    m = node(t, "LN_MathCHOP")
    link(t, c, m)
    cook()
    c.name = "Renamed"
    cook()
    assert out(t, m).first() == 2.0
    t.nodes.remove(c)
    cook()
    assert out(t, m).num_channels == 0
    no_errors()


@test
def performance_budget():
    t = new_tree()
    SCENE.livenodes.res_x, SCENE.livenodes.res_y = 64, 36
    prev = node(t, "LN_LfoCHOP")
    for i in range(60):  # a long chain of cheap CHOPs
        m = node(t, "LN_MathCHOP", multiply=1.0)
        link(t, prev, m)
        prev = m
    cook(5)
    t0 = time.perf_counter()
    cook(50)
    ms = (time.perf_counter() - t0) / 50 * 1000
    print(f"    61-node CHOP chain: {ms:.2f} ms / frame")
    assert ms < 16.0, ms


def main():
    failed = 0
    for fn in RESULTS:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL  {fn.__name__}")
            traceback.print_exc()
    ENGINE.shutdown()
    livenodes.unregister()
    print(f"\n{len(RESULTS) - failed}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
