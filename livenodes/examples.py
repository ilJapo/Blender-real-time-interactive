"""Ready-made networks that show how the pieces fit together."""
import bpy
from bpy.props import StringProperty

from .core.tree import TREE_ID

EXAMPLES = [
    ('PULSAR', "PULSAR  (showcase)", "Audio-reactive eclipse: GLSL, feedback, Geometry Nodes, 3D render, post, HUD"),
    ('FEEDBACK', "Feedback Visuals", "Generative texture loop with bloom, sent to an Out TOP"),
    ('AUDIO', "Audio Reactive Object", "Beat clock and audio analysis drive an object's scale and a light"),
    ('INSTANCES', "Channels to Geometry", "A trail of an LFO becomes points instanced by Geometry Nodes"),
    ('CONTROL', "Controls, Text & OSC", "Perform-panel sliders, live text overlay and OSC input"),
]


def _tree(name):
    tree = bpy.data.node_groups.new(name, TREE_ID)
    tree.use_fake_user = True
    return tree


def _node(tree, idname, x, y, **props):
    node = tree.nodes.new(idname)
    node.location = (x, y)
    for key, value in props.items():
        setattr(node, key, value)
    return node


def _link(tree, a, b, out=0, inp=0):
    tree.links.new(a.outputs[out], b.inputs[inp])


def _object(context, name, prim):
    ob = bpy.data.objects.get(name)
    if ob is None:
        prim()
        ob = context.active_object
        ob.name = name
    return ob


def build_feedback(context):
    t = _tree("Feedback Visuals")
    lfo = _node(t, "LN_LfoCHOP", -900, 300, channel="radius", frequency=0.25, amplitude=0.12, offset=0.22)
    shape = _node(t, "LN_ShapeTOP", -650, 300, kind='POLYGON', sides=5, border=0.01, softness=0.004)
    shape.fill = (1.0, 0.35, 0.1, 1.0)
    _link(t, lfo, shape, 0, "Params")
    fb = _node(t, "LN_FeedbackTOP", -900, -50)
    xf = _node(t, "LN_TransformTOP", -650, -50, uniform_scale=1.015, rotate=0.012, extend='ZERO')
    lvl = _node(t, "LN_LevelTOP", -400, -50, opacity=0.96, hue=0.004)
    comp = _node(t, "LN_CompositeTOP", -150, 100, operation='ADD')
    fb.target_node = comp.name
    _link(t, fb, xf)
    _link(t, xf, lvl)
    _link(t, lvl, comp, 0, "Base")
    _link(t, shape, comp, 0, "Layers")
    bloom = _node(t, "LN_BloomTOP", 100, 100, threshold=0.4, radius=12.0)
    _link(t, comp, bloom)
    out = _node(t, "LN_OutTOP", 350, 100)
    _link(t, bloom, out)
    return t


def build_audio(context):
    t = _tree("Audio Reactive")
    ob = _object(context, "Live Cube", lambda: bpy.ops.mesh.primitive_cube_add(size=1.0))
    beat = _node(t, "LN_BeatCHOP", -900, 300, bpm=120.0)
    sel = _node(t, "LN_SelectCHOP", -650, 300, pattern="pulse")
    trig = _node(t, "LN_TriggerCHOP", -400, 300, attack=0.01, decay=0.25, sustain=0.0, release=0.1)
    math_ = _node(t, "LN_MathCHOP", -150, 300, multiply=0.6, post_add=1.0)
    exp = _node(t, "LN_ExportCHOP", 350, 300, kind='OBJECT', ob=ob, path="scale")
    for a, b in ((beat, sel), (sel, trig), (trig, math_)):
        _link(t, a, b)
    _link(t, math_, exp)  # one channel sets x, y and z of the scale
    audio = _node(t, "LN_AudioFileInCHOP", -900, -100, label="Audio File In (pick a file)")
    ana = _node(t, "LN_AudioAnalysisCHOP", -650, -100)
    rot = _node(t, "LN_SelectCHOP", -400, -100, pattern="bass")
    spd = _node(t, "LN_SpeedCHOP", -150, -100)
    rexp = _node(t, "LN_ExportCHOP", 100, -100, kind='OBJECT', ob=ob, path="rotation_euler[2]")
    for a, b in ((audio, ana), (ana, rot), (rot, spd), (spd, rexp)):
        _link(t, a, b)
    return t


def _instancer_group():
    ng = bpy.data.node_groups.get("Live Instancer")
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new("Live Instancer", 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    n = ng.nodes
    gin = n.new("NodeGroupInput")
    gin.location = (-600, 0)
    gout = n.new("NodeGroupOutput")
    gout.location = (400, 0)
    inst = n.new("GeometryNodeInstanceOnPoints")
    inst.location = (100, 0)
    cube = n.new("GeometryNodeMeshCube")
    cube.location = (-200, -150)
    cube.inputs["Size"].default_value = (0.12, 0.12, 0.12)
    attr = n.new("GeometryNodeInputNamedAttribute")
    attr.location = (-400, -350)
    attr.data_type = 'FLOAT'
    attr.inputs["Name"].default_value = "lfo"
    comb = n.new("ShaderNodeCombineXYZ")
    comb.location = (-200, -350)
    comb.inputs["X"].default_value = 1.0
    comb.inputs["Y"].default_value = 1.0
    l = ng.links
    l.new(gin.outputs[0], inst.inputs["Points"])
    l.new(cube.outputs["Mesh"], inst.inputs["Instance"])
    l.new(attr.outputs["Attribute"], comb.inputs["Z"])
    l.new(comb.outputs[0], inst.inputs["Scale"])
    l.new(inst.outputs["Instances"], gout.inputs[0])
    return ng


def build_instances(context):
    t = _tree("Channels to Geometry")
    mesh = bpy.data.meshes.get("Live Points") or bpy.data.meshes.new("Live Points")
    ob = bpy.data.objects.get("Live Points")
    if ob is None:
        ob = bpy.data.objects.new("Live Points", mesh)
        context.scene.collection.objects.link(ob)
    if not any(m.type == 'NODES' for m in ob.modifiers):
        mod = ob.modifiers.new("Live Instancer", 'NODES')
        mod.node_group = _instancer_group()
    lfo = _node(t, "LN_LfoCHOP", -650, 200, channel="lfo", frequency=0.7, amplitude=4.0, offset=4.5)
    noise = _node(t, "LN_NoiseCHOP", -650, -50, names="lfo", speed=1.5, amplitude=2.0)
    m = _node(t, "LN_MathCHOP", -400, 100)
    _link(t, lfo, m)
    _link(t, noise, m)
    trail = _node(t, "LN_TrailCHOP", -150, 100, length=64)
    _link(t, m, trail)
    out = _node(t, "LN_ChopToMeshCHOP", 100, 100, target=ob, layout_mode='LINE', spread=8.0, lift=0.0)
    _link(t, trail, out)
    return t


def build_control(context):
    t = _tree("Controls Text OSC")
    hue = _node(t, "LN_ControlCHOP", -900, 300, kind='SLIDER', channel="hue", label="Hue", value=0.0, order=0)
    speed = _node(t, "LN_ControlCHOP", -900, 100, kind='SLIDER', channel="speed", label="Noise Speed", value=0.3, order=1)
    flash = _node(t, "LN_ControlCHOP", -900, -100, kind='BUTTON', channel="flash", label="Flash", order=2)
    noise = _node(t, "LN_NoiseTOP", -600, 200, kind='FRACTAL', mono=False)
    _link(t, speed, noise, 0, "Params")
    lvl = _node(t, "LN_LevelTOP", -350, 200)
    _link(t, noise, lvl)
    _link(t, hue, lvl, 0, "Params")
    trig = _node(t, "LN_TriggerCHOP", -600, -100, attack=0.0, decay=0.4)
    _link(t, flash, trig)
    sel = _node(t, "LN_SelectCHOP", -350, -100, rename="brightness")
    _link(t, trig, sel)
    bright = _node(t, "LN_MathCHOP", -150, -100, multiply=3.0, post_add=1.0)
    _link(t, sel, bright)
    lvl2 = _node(t, "LN_LevelTOP", -100, 200)
    _link(t, lvl, lvl2)
    _link(t, bright, lvl2, 0, "Params")
    clock = _node(t, "LN_TimeCHOP", -600, -350)
    osc = _node(t, "LN_OscInCHOP", -600, -550, port=9000)
    merge = _node(t, "LN_MergeCHOP", -350, -400)
    _link(t, clock, merge)
    _link(t, osc, merge)
    fmt = _node(t, "LN_FormatDAT", -150, -400, template="t = {seconds:.1f} s   fps {fps:.0f}")
    _link(t, merge, fmt)
    text = _node(t, "LN_TextTOP", 100, -300, size=0.08)
    text.position = (0.5, 0.1)
    _link(t, fmt, text, 0, "Text")
    comp = _node(t, "LN_CompositeTOP", 350, 100, operation='OVER')
    _link(t, lvl2, comp, 0, "Base")
    _link(t, text, comp, 0, "Layers")
    out = _node(t, "LN_OutTOP", 600, 100)
    _link(t, comp, out)
    return t


def build_pulsar(context):
    from .demos import pulsar
    return pulsar.build(context)


BUILDERS = {'PULSAR': build_pulsar, 'FEEDBACK': build_feedback, 'AUDIO': build_audio, 'INSTANCES': build_instances, 'CONTROL': build_control}


class LN_OT_add_example(bpy.types.Operator):
    """Build an example network"""
    bl_idname = "livenodes.add_example"
    bl_label = "Add Example"
    bl_options = {'REGISTER', 'UNDO'}

    example: StringProperty()

    def execute(self, context):
        tree = BUILDERS[self.example](context)
        space = context.space_data
        if space is not None and space.type == 'NODE_EDITOR':
            space.tree_type = TREE_ID
            space.node_tree = tree
        return {'FINISHED'}


classes = (LN_OT_add_example,)
