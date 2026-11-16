"""PULSAR - the showcase network.

  01 AUDIO     loop playback, analysis, spectrum, kick envelope
  02 PERFORM   sliders and buttons in the Perform panel, keyboard shortcuts
  03 BRAIN     a Script node packing everything into named channels
  04 ECLIPSE   GLSL black sun with a spectrum corona
  05 FEEDBACK  zooming, swirling, colour-drifting trails
  06 3D        spectrum ring instanced by Geometry Nodes, rendered live
  07 POST      bloom, chromatic split, mosaic, tone mapping, grain
  08 OUTPUT    HUD typography, Out TOP, Stream Out (NDI / Spout / Syphon)

Keys while running: SPACE = glitch, F = flash.
"""
import math
import os

import bpy

from ..core.tree import TREE_ID
from . import pulsar_audio, pulsar_shaders

TITLE = "PULSAR"

# frame colours: muted versions of the palette, readable in the dark node editor
FRAMES = {
    "01 · AUDIO": (0.13, 0.17, 0.30),
    "02 · PERFORM": (0.30, 0.20, 0.12),
    "03 · BRAIN": (0.22, 0.14, 0.26),
    "04 · ECLIPSE": (0.18, 0.13, 0.33),
    "05 · FEEDBACK": (0.15, 0.20, 0.30),
    "06 · 3D": (0.12, 0.24, 0.22),
    "07 · POST": (0.30, 0.15, 0.15),
    "08 · OUTPUT": (0.24, 0.24, 0.24),
}


def _hex(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb) + (1.0,)


VIOLET, CORAL, WHITE = _hex("#7B5CFF"), _hex("#FF5A36"), _hex("#FFF4E6")


# -- assets ---------------------------------------------------------------
def audio_path():
    """The loop lives next to the .blend when saved, else in Blender's user data folder."""
    if bpy.data.filepath:
        folder = os.path.dirname(bpy.data.filepath)
    else:
        folder = bpy.utils.user_resource('DATAFILES', path="livenodes", create=True)
    path = os.path.join(folder, "pulsar_loop.wav")
    if not os.path.exists(path):
        pulsar_audio.write(path)
    return path


def _text(name, body):
    txt = bpy.data.texts.get(name) or bpy.data.texts.new(name)
    txt.clear()
    txt.write(body)
    return txt


def _emission_material(name, color=None, attr=None):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)
    em = nt.nodes.new("ShaderNodeEmission")
    em.name = "Emission"
    em.location = (150, 0)
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    if attr:
        at = nt.nodes.new("ShaderNodeAttribute")
        at.attribute_type = 'INSTANCER'
        at.attribute_name = attr
        at.location = (-450, 0)
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.location = (-200, 0)
        els = ramp.color_ramp.elements
        els[0].position, els[0].color = 0.0, VIOLET
        els[1].position, els[1].color = 0.6, CORAL
        e = els.new(1.0)
        e.color = WHITE
        nt.links.new(at.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
        em.inputs["Strength"].default_value = 4.0
    else:
        em.inputs["Color"].default_value = color or (0, 0, 0, 1)
        em.inputs["Strength"].default_value = 0.0 if color is None else 1.0
    return mat


def _ring_nodes(material):
    ng = bpy.data.node_groups.get("Pulsar Ring") or bpy.data.node_groups.new("Pulsar Ring", 'GeometryNodeTree')
    ng.nodes.clear()
    ng.interface.clear()
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    n, l = ng.nodes, ng.links

    def add(idname, x, y):
        node = n.new(idname)
        node.location = (x, y)
        return node

    gin, gout = add("NodeGroupInput", -800, 0), add("NodeGroupOutput", 500, 0)
    cube = add("GeometryNodeMeshCube", -500, -120)
    cube.inputs["Size"].default_value = (1.0, 1.0, 1.0)
    setmat = add("GeometryNodeSetMaterial", -300, -120)
    setmat.inputs["Material"].default_value = material
    inst = add("GeometryNodeInstanceOnPoints", 250, 0)
    sx = add("GeometryNodeInputNamedAttribute", -600, -360)
    sx.data_type = 'FLOAT'
    sx.inputs["Name"].default_value = "sx"
    rz = add("GeometryNodeInputNamedAttribute", -600, -560)
    rz.data_type = 'FLOAT'
    rz.inputs["Name"].default_value = "rz"
    scale = add("ShaderNodeCombineXYZ", -300, -360)
    scale.inputs["Y"].default_value = 0.028
    scale.inputs["Z"].default_value = 0.028
    rot = add("ShaderNodeCombineXYZ", -300, -560)
    l.new(gin.outputs[0], inst.inputs["Points"])
    l.new(cube.outputs["Mesh"], setmat.inputs["Geometry"])
    l.new(setmat.outputs["Geometry"], inst.inputs["Instance"])
    l.new(sx.outputs["Attribute"], scale.inputs["X"])
    l.new(rz.outputs["Attribute"], rot.inputs["Z"])
    l.new(scale.outputs[0], inst.inputs["Scale"])
    l.new(rot.outputs[0], inst.inputs["Rotation"])
    l.new(inst.outputs["Instances"], gout.inputs[0])
    return ng


def build_scene(context):
    scene = context.scene
    col = bpy.data.collections.get("PULSAR")
    if col is None:
        col = bpy.data.collections.new("PULSAR")
        scene.collection.children.link(col)

    def obj(name, data):
        ob = bpy.data.objects.get(name)
        if ob is None:
            ob = bpy.data.objects.new(name, data)
            col.objects.link(ob)
        return ob

    # world: pure black, the light comes from emission and the post chain
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = next((nd for nd in world.node_tree.nodes if nd.type == 'BACKGROUND'), None)
    if bg is not None:
        bg.inputs["Color"].default_value = (0, 0, 0, 1)
        bg.inputs["Strength"].default_value = 0.0

    # the black core, the same apparent size as the 2D eclipse disc
    if "Pulsar Core" not in bpy.data.meshes:
        import bmesh
        me = bpy.data.meshes.new("Pulsar Core")
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=0.9)
        bm.to_mesh(me)
        bm.free()
        for poly in me.polygons:
            poly.use_smooth = True
    core = obj("Pulsar Core", bpy.data.meshes["Pulsar Core"])
    core.data.materials.clear()
    core.data.materials.append(_emission_material("Pulsar Black"))

    # the ring: points written by CHOP to Mesh, bars made by Geometry Nodes
    ring_me = bpy.data.meshes.get("Pulsar Ring") or bpy.data.meshes.new("Pulsar Ring")
    ring = obj("Pulsar Ring", ring_me)
    ring.rotation_mode = 'ZXY'           # spin around its own axis, then tilt
    ring.rotation_euler = (math.radians(22.0), 0.0, 0.0)   # a Saturn-like ellipse
    mod = ring.modifiers.get("Ring") or ring.modifiers.new("Ring", 'NODES')
    mod.node_group = _ring_nodes(_emission_material("Pulsar Bars", attr="s"))

    # orthographic camera on a rig, so the core always matches the 2D disc
    rig = obj("Camera Rig", None)
    cam_data = bpy.data.cameras.get("Pulsar Camera") or bpy.data.cameras.new("Pulsar Camera")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 8.0
    cam_data.clip_end = 100.0
    cam = obj("Pulsar Camera", cam_data)
    cam.parent = rig
    cam.location = (0.0, -12.0, 0.0)
    cam.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    scene.camera = cam

    r = scene.render
    r.resolution_x, r.resolution_y = 1280, 720
    r.fps = 30
    scene.frame_start = 1
    scene.frame_end = int(pulsar_audio.LENGTH * 30)
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 8
        scene.eevee.taa_samples = 4
    scene.view_settings.view_transform = 'Standard'
    return {"core": core, "ring": ring, "rig": rig, "cam": cam, "bars": bpy.data.materials["Pulsar Bars"]}


# -- network --------------------------------------------------------------
class _Builder:
    def __init__(self, tree):
        self.t = tree
        self.frames = {}

    def frame(self, label):
        fr = self.t.nodes.new("NodeFrame")
        fr.label = label
        fr.name = label
        fr.label_size = 18
        fr.use_custom_color = True
        fr.color = FRAMES[label]
        fr.shrink = True
        self.frames[label] = fr
        return fr

    def node(self, idname, frame, x, y, name=None, **props):
        nd = self.t.nodes.new(idname)
        if name:
            nd.name = nd.label = name
        nd.parent = self.frames[frame]
        if hasattr(nd, "location_absolute"):
            nd.location_absolute = (x, y)
        else:
            nd.location = (x, y)
        for k, v in props.items():
            setattr(nd, k, v)
        return nd

    def link(self, a, b, out=0, inp=0):
        self.t.links.new(a.outputs[out], b.inputs[inp])


def build(context):
    scene = context.scene
    objs = build_scene(context)
    old = bpy.data.node_groups.get(TITLE)
    if old is not None:
        bpy.data.node_groups.remove(old)
    tree = bpy.data.node_groups.new(TITLE, TREE_ID)
    tree.use_fake_user = True
    b = _Builder(tree)
    for label in FRAMES:
        b.frame(label)

    s = scene.livenodes
    s.res_x, s.res_y, s.fps = 1280, 720, 60
    s.tex_format = 'RGBA16F'
    s.show_previews = True
    s.capture_input = True

    brain_txt = _text("pulsar_brain.py", pulsar_shaders.BRAIN)
    ring_txt = _text("pulsar_ring.py", pulsar_shaders.RING)
    eclipse_txt = _text("pulsar_eclipse.glsl", pulsar_shaders.ECLIPSE)
    finish_txt = _text("pulsar_finish.glsl", pulsar_shaders.FINISH)

    # 01 AUDIO --------------------------------------------------------------
    F = "01 · AUDIO"
    audio = b.node("LN_AudioFileInCHOP", F, -2600, 700, "Pulsar Loop", filepath=audio_path(), window=2048, volume=0.8)
    ana = b.node("LN_AudioAnalysisCHOP", F, -2300, 820, "Analysis", smoothing=0.06, kick_sensitivity=1.4)
    spec = b.node("LN_AudioSpectrumCHOP", F, -2300, 520, "Spectrum", bands=64, falloff=0.18, gain=1.6)
    kick_sel = b.node("LN_SelectCHOP", F, -2000, 900, "Kick", pattern="kick", rename="kick_env")
    kick_env = b.node("LN_TriggerCHOP", F, -1780, 900, "Kick Envelope", attack=0.0, decay=0.32, sustain=0.0, release=0.05)
    b.link(audio, ana)
    b.link(audio, spec)
    b.link(ana, kick_sel)
    b.link(kick_sel, kick_env)

    # 02 PERFORM ------------------------------------------------------------
    F = "02 · PERFORM"
    controls = []
    for i, (label, kind, chan, val) in enumerate([
            ("Intensity", 'SLIDER', "intensity", 0.7), ("Trails", 'SLIDER', "opacity", 0.82),
            ("Hue Shift", 'SLIDER', "hue", 0.0), ("3D Ring", 'SLIDER', "opacity", 1.0),
            ("Glitch  [Space]", 'BUTTON', "glitch", 0.0), ("Flash  [F]", 'BUTTON', "flash", 0.0)]):
        nd = b.node("LN_ControlCHOP", F, -2600, 200 - i * 170, label, kind=kind, channel=chan, value=val, order=i)
        controls.append(nd)
    c_int, c_trails, c_hue, c_ring, c_glitch, c_flash = controls
    keys = b.node("LN_KeyboardInCHOP", F, -2300, -560, "Keys", keys="SPACE F")
    key_glitch = b.node("LN_SelectCHOP", F, -2050, -500, "Space", pattern="space", rename="glitch")
    key_flash = b.node("LN_SelectCHOP", F, -2050, -680, "F Key", pattern="f", rename="flash")
    b.link(keys, key_glitch)
    b.link(keys, key_flash)
    glitch_or = b.node("LN_MathCHOP", F, -1800, -440, "Glitch Or", combine_chops='MAX')
    flash_or = b.node("LN_MathCHOP", F, -1800, -660, "Flash Or", combine_chops='MAX')
    b.link(c_glitch, glitch_or)
    b.link(key_glitch, glitch_or)
    b.link(c_flash, flash_or)
    b.link(key_flash, flash_or)
    glitch_env = b.node("LN_TriggerCHOP", F, -1560, -440, "Glitch Envelope", attack=0.0, decay=0.6, sustain=0.0)
    flash_env = b.node("LN_TriggerCHOP", F, -1560, -660, "Flash Envelope", attack=0.0, decay=0.22, sustain=0.0)
    b.link(glitch_or, glitch_env)
    b.link(flash_or, flash_env)

    # 03 BRAIN --------------------------------------------------------------
    F = "03 · BRAIN"
    pos = b.node("LN_SelectCHOP", F, -1500, 650, "Position", pattern="position")
    b.link(audio, pos, out="Info")
    gather = b.node("LN_MergeCHOP", F, -1250, 300, "Gather")
    for src in (ana, kick_env, pos, c_int, c_hue, glitch_env, flash_env):
        b.link(src, gather)
    brain = b.node("LN_ScriptNode", F, -1000, 300, "Brain", script=brain_txt)
    b.link(gather, brain)
    uniforms = b.node("LN_NullCHOP", F, -700, 300, "Uniforms")
    b.link(brain, uniforms)

    # 04 ECLIPSE ------------------------------------------------------------
    F = "04 · ECLIPSE"
    spec_tex = b.node("LN_ChopToTOP", F, -1000, 760, "Spectrum Texture")
    b.link(spec, spec_tex)
    eclipse = b.node("LN_GlslTOP", F, -700, 760, "Eclipse", source=eclipse_txt, res_mode='SCENE')
    b.link(spec_tex, eclipse, 0, "In 0")
    b.link(uniforms, eclipse, 0, "Uniforms")

    # 05 FEEDBACK -----------------------------------------------------------
    F = "05 · FEEDBACK"
    fb = b.node("LN_FeedbackTOP", F, -700, 1250, "Feedback")
    swirl = b.node("LN_TransformTOP", F, -450, 1250, "Swirl", uniform_scale=1.012, extend='ZERO')
    fade = b.node("LN_LevelTOP", F, -200, 1250, "Fade", hue=0.0025, brightness=0.985)
    soften = b.node("LN_BlurTOP", F, 50, 1250, "Soften", radius=1.2)
    mix = b.node("LN_CompositeTOP", F, 300, 1000, "Mix", operation='OVER')
    fb.target_node = mix.name
    b.link(fb, swirl)
    b.link(uniforms, swirl, 0, "Params")
    b.link(swirl, fade)
    b.link(c_trails, fade, 0, "Params")
    b.link(fade, soften)
    b.link(soften, mix, 0, "Base")
    b.link(eclipse, mix, 0, "Layers")

    # 06 3D -----------------------------------------------------------------
    F = "06 · 3D"
    ring_layout = b.node("LN_ScriptNode", F, -1000, -150, "Ring Layout", script=ring_txt)
    b.link(spec, ring_layout)
    to_mesh = b.node("LN_ChopToMeshCHOP", F, -700, -150, "Ring Points", target=objs["ring"], layout_mode='CHANNELS')
    b.link(ring_layout, to_mesh)
    core_exp = b.node("LN_ExportCHOP", F, -700, -400, "Core Pulse", ob=objs["core"], path="scale", channel="core_scale")
    spin_exp = b.node("LN_ExportCHOP", F, -700, -620, "Ring Spin", ob=objs["ring"], path="rotation_euler[2]", channel="spin")
    glow_exp = b.node("LN_ExportCHOP", F, -700, -840, "Bar Glow", kind='MATERIAL', mat=objs["bars"],
                      path='node_tree.nodes["Emission"].inputs["Strength"].default_value', channel="energy")
    for e in (core_exp, spin_exp, glow_exp):
        b.link(uniforms, e)
    sway = b.node("LN_LfoCHOP", F, -1000, -1060, "Camera Sway", channel="sway", frequency=0.045,
                  amplitude=math.radians(16.0), wave='SINE')
    sway_exp = b.node("LN_ExportCHOP", F, -700, -1060, "Camera Rig", ob=objs["rig"], path="rotation_euler[0]")
    b.link(sway, sway_exp)
    render = b.node("LN_RenderTOP", F, -300, -400, "3D Scene", camera=objs["cam"], shading='RENDERED')

    # 07 POST ---------------------------------------------------------------
    F = "07 · POST"
    scene_mix = b.node("LN_CompositeTOP", F, 650, 600, "Scene Mix", operation='ADD')
    b.link(mix, scene_mix, 0, "Base")
    b.link(render, scene_mix, 0, "Layers")
    b.link(c_ring, scene_mix, 0, "Params")
    bloom = b.node("LN_BloomTOP", F, 900, 600, "Bloom", threshold=0.7, radius=14.0, intensity=0.55)
    split = b.node("LN_RgbSplitTOP", F, 1150, 600, "Chroma", radial=True)
    mosaic = b.node("LN_PixelateTOP", F, 1400, 600, "Mosaic")
    finish = b.node("LN_GlslTOP", F, 1650, 600, "Finish", source=finish_txt)
    b.link(scene_mix, bloom)
    b.link(bloom, split)
    b.link(uniforms, split, 0, "Params")
    b.link(split, mosaic)
    b.link(uniforms, mosaic, 0, "Params")
    b.link(mosaic, finish, 0, "In 0")
    b.link(uniforms, finish, 0, "Uniforms")

    # 08 OUTPUT -------------------------------------------------------------
    F = "08 · OUTPUT"
    title = b.node("LN_TextTOP", F, 1650, 1100, "Wordmark", text="PULSAR", size=0.034, align='LEFT',
                   font='MONO', tracking=0.9, position=(0.045, 0.92), font_color=(1.0, 0.905, 0.791, 0.92))
    hud_fmt = b.node("LN_FormatDAT", F, 1400, 1350, "HUD Text",
                     template="124 BPM   /   BAR {bar_num:.0f} . {beat_num:.0f}   /   LIVE NODES")
    b.link(uniforms, hud_fmt)
    hud = b.node("LN_TextTOP", F, 1650, 1350, "HUD", size=0.022, align='LEFT', font='MONO', tracking=0.25,
                 position=(0.045, 0.07), font_color=(1.0, 0.905, 0.791, 0.6))
    b.link(hud_fmt, hud, 0, "Text")
    overlay = b.node("LN_CompositeTOP", F, 1950, 800, "Overlay", operation='OVER')
    b.link(finish, overlay, 0, "Base")
    b.link(title, overlay, 0, "Layers")
    b.link(hud, overlay, 0, "Layers")
    out = b.node("LN_OutTOP", F, 2200, 900, "Out")
    b.link(overlay, out)
    stream = b.node("LN_StreamOutTOP", F, 2200, 650, "Stream Out", sender_name="PULSAR", active=False)
    b.link(overlay, stream)
    b.node("LN_NullTOP", F, 2200, 1150, "Preview")
    b.link(overlay, tree.nodes["Preview"])
    tree.nodes.active = out
    return tree
