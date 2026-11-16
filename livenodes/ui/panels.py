import bpy

from ..core import deps
from ..core.engine import ENGINE
from ..core.tree import TREE_ID


def _is_live(context):
    space = context.space_data
    return space is not None and getattr(space, "tree_type", "") == TREE_ID


def draw_transport(layout, context):
    row = layout.row(align=True)
    row.scale_y = 1.4
    if ENGINE.running:
        row.operator("livenodes.stop", text="Stop", icon='PAUSE', depress=True)
    else:
        row.operator("livenodes.start", text="Start", icon='PLAY')
    row.operator("livenodes.reset", text="", icon='LOOP_BACK')
    row.operator("livenodes.step", text="", icon='FRAME_NEXT')
    s = context.scene.livenodes
    col = layout.column(align=True)
    if ENGINE.running:
        col.label(text=f"{ENGINE.fps_actual:5.1f} fps   cook {ENGINE.cook_total_ms:5.2f} ms", icon='TIME')
        col.label(text=f"time {ENGINE.time:7.2f} s   frame {ENGINE.frame}")
    errors = len(ENGINE.errors)
    if errors:
        col.alert = True
        col.label(text=f"{errors} node(s) with errors", icon='ERROR')
    return s


class LN_PT_engine(bpy.types.Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Live"
    bl_label = "Engine"

    @classmethod
    def poll(cls, context):
        return _is_live(context)

    def draw(self, context):
        layout = self.layout
        s = draw_transport(layout, context)
        layout.operator("livenodes.output_window", text="Output Window", icon='WINDOW')
        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(s, "fps")
        col.prop(s, "time_mode")
        sub = col.column(align=True)
        sub.prop(s, "res_x", text="Resolution X")
        sub.prop(s, "res_y", text="Y")
        col.prop(s, "tex_format")
        col.prop(s, "show_previews")
        if s.show_previews:
            col.prop(s, "preview_size")
        col.prop(s, "backdrop")
        col.prop(s, "redraw_viewports")
        col.prop(s, "capture_input")
        col.prop(s, "autostart")
        layout.operator("livenodes.clear_cache", icon='FILE_REFRESH')


class LN_PT_profiler(bpy.types.Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Live"
    bl_label = "Performance"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _is_live(context)

    def draw(self, context):
        col = self.layout.column(align=True)
        items = sorted(ENGINE.cook_ms.items(), key=lambda kv: -kv[1])[:12]
        if not items:
            col.label(text="Start the engine to measure")
        for key, ms in items:
            tree, _, node = key.partition("\x00")
            row = col.row()
            row.alert = key in ENGINE.errors
            row.label(text=node)
            row.label(text=f"{ms:6.2f} ms")


def draw_controls(layout):
    controls = []
    for tree in bpy.data.node_groups:
        if tree.bl_idname == TREE_ID:
            controls.extend(n for n in tree.nodes if n.bl_idname == "LN_ControlCHOP" and n.show_in_panel)
    if not controls:
        layout.label(text="Add Control CHOP nodes to build", icon='INFO')
        layout.label(text="a performance interface here.")
        return
    controls.sort(key=lambda n: (n.order, n.name))
    col = layout.column()
    for node in controls:
        node.draw_widget(col)


class LN_PT_perform(bpy.types.Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Live"
    bl_label = "Perform"

    @classmethod
    def poll(cls, context):
        return _is_live(context)

    def draw(self, context):
        draw_controls(self.layout)


class LN_PT_perform_view3d(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Live"
    bl_label = "Live Nodes"

    @classmethod
    def poll(cls, context):
        return any(t.bl_idname == TREE_ID for t in bpy.data.node_groups)

    def draw(self, context):
        draw_transport(self.layout, context)
        self.layout.operator("livenodes.output_window", text="Output Window", icon='WINDOW')
        box = self.layout.box()
        draw_controls(box)


class LN_PT_extras(bpy.types.Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Live"
    bl_label = "Modules & Examples"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _is_live(context)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Optional modules:")
        for mod, (pkg, what) in deps.OPTIONAL.items():
            row = col.row(align=True)
            ok = deps.load(mod) is not None
            row.label(text=what, icon='CHECKMARK' if ok else 'BLANK1')
            if not ok:
                row.operator("livenodes.install_dep", text="Install").module = mod
        layout.separator()
        col = layout.column(align=True)
        col.label(text="Example networks:")
        for key, label, _ in EXAMPLES_MENU:
            col.operator("livenodes.add_example", text=label).example = key


from ..examples import EXAMPLES as EXAMPLES_MENU  # noqa: E402

classes = (LN_PT_engine, LN_PT_perform, LN_PT_profiler, LN_PT_extras, LN_PT_perform_view3d)
