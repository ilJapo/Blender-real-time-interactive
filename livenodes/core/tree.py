"""Node tree, sockets and the base class shared by every Live node."""
import bpy
from bpy.props import EnumProperty, IntProperty

TREE_ID = "LiveNodeTree"

FAMILY_COLORS = {
    'CHOP': (0.20, 0.42, 0.24),
    'TOP': (0.36, 0.26, 0.52),
    'DAT': (0.50, 0.26, 0.42),
    'OUT': (0.50, 0.36, 0.16),
}

_dirty = set()


def is_dirty(tree_name):
    return tree_name in _dirty


def clear_dirty(tree_name):
    _dirty.discard(tree_name)


def mark_all_dirty():
    for tree in bpy.data.node_groups:
        if tree.bl_idname == TREE_ID:
            _dirty.add(tree.name)


class LNTree(bpy.types.NodeTree):
    """Real-time operator network: channels, textures and data"""
    bl_idname = TREE_ID
    bl_label = "Live Nodes"
    bl_icon = 'FORCE_HARMONIC'

    def update(self):
        _dirty.add(self.name)


class _LNSocket:
    ln_color = (0.5, 0.5, 0.5, 1.0)

    def draw(self, context, layout, node, text):
        layout.label(text=text)

    def draw_color(self, context, node):
        return self.ln_color

    @classmethod
    def draw_color_simple(cls):
        return cls.ln_color


class LNSocketCHOP(_LNSocket, bpy.types.NodeSocket):
    """Channels: named streams of numbers"""
    bl_idname = "LNSocketCHOP"
    bl_label = "Channels"
    ln_color = (0.35, 0.85, 0.40, 1.0)


class LNSocketTOP(_LNSocket, bpy.types.NodeSocket):
    """Texture: a GPU image"""
    bl_idname = "LNSocketTOP"
    bl_label = "Texture"
    ln_color = (0.62, 0.42, 0.95, 1.0)


class LNSocketDAT(_LNSocket, bpy.types.NodeSocket):
    """Data: text or a table"""
    bl_idname = "LNSocketDAT"
    bl_label = "Data"
    ln_color = (0.95, 0.45, 0.75, 1.0)


SOCKETS = {'CHOP': "LNSocketCHOP", 'TOP': "LNSocketTOP", 'DAT': "LNSocketDAT"}


def node_key(node):
    return f"{node.id_data.name}\x00{node.name}"


class LNNode:
    """Mixin for all Live nodes. Runtime state never lives on `self`:
    Blender recreates the Python wrapper at will, so state is kept by the
    engine under the node's key."""

    ln_family = 'CHOP'
    ln_category = "Misc"
    ln_params = True      # adds a "Params" CHOP input that overrides properties by name
    ln_live = False       # needs the interactive capture operator (keyboard / mouse)
    ln_writes_scene = False  # changes Blender data (exports): cooked before nodes that read the scene
    ln_reads_scene = False   # reads Blender data (render, object transforms)

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == TREE_ID

    # -- construction -----------------------------------------------------
    def init(self, context):
        self.use_custom_color = True
        self.color = FAMILY_COLORS.get(self.ln_family, (0.3, 0.3, 0.3))
        self.ln_init()
        if self.ln_params:
            self.inputs.new("LNSocketCHOP", "Params")

    def ln_init(self):
        pass

    def add_in(self, family, name, multi=False):
        return self.inputs.new(SOCKETS[family], name, use_multi_input=multi)

    def add_out(self, family, name="Out"):
        return self.outputs.new(SOCKETS[family], name)

    def free(self):
        from .engine import ENGINE
        ENGINE.release(node_key(self))

    # -- UI ---------------------------------------------------------------
    def draw_buttons(self, context, layout):
        self.ln_draw(context, layout)
        from .engine import ENGINE
        ENGINE.draw_status(self, layout)

    def draw_buttons_ext(self, context, layout):
        self.ln_draw(context, layout)
        self.ln_draw_ext(context, layout)
        from .engine import ENGINE
        ENGINE.draw_status(self, layout, full=True)

    def ln_draw(self, context, layout):
        pass

    def ln_draw_ext(self, context, layout):
        pass

    # -- evaluation -------------------------------------------------------
    def cook(self, ctx, inp):
        """Return data for the first output, or a dict {socket: data}."""
        return None


class LNTopNode(LNNode):
    """Base for texture nodes: owns render targets and resolution settings."""
    ln_family = 'TOP'

    res_mode: EnumProperty(
        name="Resolution",
        items=[('AUTO', "Auto", "Use the input resolution, or the scene default for generators"),
               ('SCENE', "Scene", "Always use the default resolution of the Live Nodes settings"),
               ('CUSTOM', "Custom", "Use the resolution set on this node")],
        default='AUTO')
    res_x: IntProperty(name="Width", default=1280, min=1, max=16384)
    res_y: IntProperty(name="Height", default=720, min=1, max=16384)

    def ln_draw_ext(self, context, layout):
        col = layout.column(align=True)
        col.prop(self, "res_mode")
        if self.res_mode == 'CUSTOM':
            col.prop(self, "res_x")
            col.prop(self, "res_y")

    def out_size(self, ctx, src=None):
        if self.res_mode == 'CUSTOM':
            return (self.res_x, self.res_y)
        if src is not None and self.res_mode == 'AUTO':
            return (src.width, src.height)
        return ctx.default_res

    def target(self, ctx, size, slot=0):
        from . import gpu_util
        st = ctx.state
        tgt = st.get(("target", slot))
        if tgt is None:
            tgt = st[("target", slot)] = gpu_util.Target()
        return tgt.ensure(size[0], size[1], ctx.tex_format)

    def run(self, ctx, frag, uniforms=None, textures=(), size=None, slot=0, decl=(), common=True):
        """Render one full-screen pass and return the resulting texture."""
        from . import gpu_util
        if size is None:
            size = self.out_size(ctx, textures[0] if textures else None)
        compiled = gpu_util.shader(frag, tuple(decl), len(textures), common)
        return gpu_util.draw(self.target(ctx, size, slot), compiled, uniforms or {}, textures, ctx.time)


classes = (LNTree, LNSocketCHOP, LNSocketTOP, LNSocketDAT)
