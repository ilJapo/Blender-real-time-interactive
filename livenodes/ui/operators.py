import bpy
from bpy.props import BoolProperty, StringProperty

from ..core import deps, gpu_util
from ..core.engine import ENGINE
from ..core.tree import TREE_ID

# event type -> name used by the Mouse In node
_MOUSE_BUTTONS = {'LEFTMOUSE': "left", 'MIDDLEMOUSE': "middle", 'RIGHTMOUSE': "right"}


class LN_OT_start(bpy.types.Operator):
    """Start cooking all Live Node networks"""
    bl_idname = "livenodes.start"
    bl_label = "Start"

    def execute(self, context):
        ENGINE.start()
        if context.scene.livenodes.capture_input and context.window is not None:
            bpy.ops.livenodes.capture_input('INVOKE_DEFAULT')
        return {'FINISHED'}


class LN_OT_stop(bpy.types.Operator):
    """Stop the engine and close devices and network ports"""
    bl_idname = "livenodes.stop"
    bl_label = "Stop"

    def execute(self, context):
        ENGINE.stop()
        return {'FINISHED'}


class LN_OT_toggle(bpy.types.Operator):
    """Start or stop the Live Nodes engine"""
    bl_idname = "livenodes.toggle"
    bl_label = "Start / Stop Live Nodes"

    def execute(self, context):
        if ENGINE.running:
            return bpy.ops.livenodes.stop()
        return bpy.ops.livenodes.start()


class LN_OT_reset(bpy.types.Operator):
    """Rewind time and clear every node's memory (feedback, lags, counters, timers)"""
    bl_idname = "livenodes.reset"
    bl_label = "Reset"

    def execute(self, context):
        ENGINE.reset()
        return {'FINISHED'}


class LN_OT_step(bpy.types.Operator):
    """Cook a single frame (while stopped)"""
    bl_idname = "livenodes.step"
    bl_label = "Step"

    def execute(self, context):
        ENGINE.tick(context.scene)
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class LN_OT_capture_input(bpy.types.Operator):
    """Listens to keyboard and mouse for the Keyboard In / Mouse In nodes (passes every event on)"""
    bl_idname = "livenodes.capture_input"
    bl_label = "Capture Input"
    bl_options = {'INTERNAL'}

    _running = False

    def invoke(self, context, event):
        if LN_OT_capture_input._running:
            return {'CANCELLED'}
        LN_OT_capture_input._running = True
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not ENGINE.running or not context.scene.livenodes.capture_input:
            LN_OT_capture_input._running = False
            return {'FINISHED', 'PASS_THROUGH'}
        t = event.type
        win = context.window
        if t in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'} and win is not None:
            ENGINE.mouse["x"] = event.mouse_x / max(win.width, 1)
            ENGINE.mouse["y"] = event.mouse_y / max(win.height, 1)
        elif t in _MOUSE_BUTTONS:
            ENGINE.mouse[_MOUSE_BUTTONS[t]] = 1.0 if event.value == 'PRESS' else 0.0
        elif t == 'WHEELUPMOUSE':
            ENGINE.mouse["wheel"] += 1.0
        elif t == 'WHEELDOWNMOUSE':
            ENGINE.mouse["wheel"] -= 1.0
        elif event.value in {'PRESS', 'RELEASE'}:
            ENGINE.keys[t] = 1.0 if event.value == 'PRESS' else 0.0
        return {'PASS_THROUGH'}


def _out_nodes():
    for tree in bpy.data.node_groups:
        if tree.bl_idname == TREE_ID:
            for node in tree.nodes:
                if node.bl_idname == "LN_OutTOP":
                    yield tree, node


class LN_OT_output_window(bpy.types.Operator):
    """Open a window that shows this output (projector, LED wall, second screen)"""
    bl_idname = "livenodes.output_window"
    bl_label = "Open Output Window"

    tree: StringProperty()
    node: StringProperty()
    fullscreen: BoolProperty(name="Fullscreen", default=False)

    def execute(self, context):
        tree_name, node_name = self.tree, self.node
        if not tree_name:
            found = next(_out_nodes(), None)
            if found is None:
                self.report({'ERROR'}, "Add an Out TOP node first")
                return {'CANCELLED'}
            tree_name, node_name = found[0].name, found[1].name
        area = context.area or next(iter(context.screen.areas))
        before = {w.as_pointer() for w in context.window_manager.windows}
        region = next((r for r in area.regions if r.type == 'WINDOW'), area.regions[-1])
        with context.temp_override(area=area, region=region):
            bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
        new = [w for w in context.window_manager.windows if w.as_pointer() not in before]
        if not new:
            self.report({'ERROR'}, "Could not open a window")
            return {'CANCELLED'}
        win = new[0]
        out_area = win.screen.areas[0]
        out_area.type = 'IMAGE_EDITOR'
        space = out_area.spaces.active
        space.show_region_header = False
        space.show_region_toolbar = False
        space.show_region_ui = False
        space.show_region_tool_header = False
        space.image = None
        ENGINE.output_windows[win.as_pointer()] = (tree_name, node_name)
        if self.fullscreen:
            with context.temp_override(window=win, area=out_area):
                bpy.ops.wm.window_fullscreen_toggle()
        if not ENGINE.running:
            bpy.ops.livenodes.start()
        return {'FINISHED'}


class LN_OT_install_dep(bpy.types.Operator):
    """Download and install an optional Python module into Blender (needs internet)"""
    bl_idname = "livenodes.install_dep"
    bl_label = "Install"

    module: StringProperty()

    def execute(self, context):
        ok, log = deps.install(self.module)
        if ok:
            self.report({'INFO'}, f"Installed {deps.OPTIONAL[self.module][0]}")
            return {'FINISHED'}
        print(log)
        self.report({'ERROR'}, f"Install failed (see the system console): {log[-200:]}")
        return {'CANCELLED'}


class LN_OT_new_tree(bpy.types.Operator):
    """Create a Live Node network and show it in this editor"""
    bl_idname = "livenodes.new_tree"
    bl_label = "New Live Network"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        tree = bpy.data.node_groups.new("Live Network", TREE_ID)
        tree.use_fake_user = True
        space = context.space_data
        if space is not None and space.type == 'NODE_EDITOR':
            space.tree_type = TREE_ID
            space.node_tree = tree
        return {'FINISHED'}


class LN_OT_clear_cache(bpy.types.Operator):
    """Recompile shaders and rebuild every node (use after editing GLSL or scripts if needed)"""
    bl_idname = "livenodes.clear_cache"
    bl_label = "Reload Shaders"

    def execute(self, context):
        gpu_util.free_all()
        for st in ENGINE.states.values():
            st.pop("src", None)
            st.pop("key", None)
        ENGINE.errors.clear()
        ENGINE._reported.clear()
        return {'FINISHED'}


classes = (LN_OT_start, LN_OT_stop, LN_OT_toggle, LN_OT_reset, LN_OT_step, LN_OT_capture_input,
           LN_OT_output_window, LN_OT_install_dep, LN_OT_new_tree, LN_OT_clear_cache)
