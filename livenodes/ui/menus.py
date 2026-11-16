"""Shift+A menu for Live networks, grouped by node category."""
import bpy

from ..core.tree import TREE_ID

CATEGORY_ORDER = ["CHOP Generate", "CHOP Input", "CHOP Audio", "CHOP Filter", "CHOP Output",
                  "TOP Generate", "TOP Input", "TOP Filter", "TOP Composite", "TOP Convert", "TOP Output", "DAT"]
_menus = []


def _menu_draw(items):
    def draw(self, context):
        for cls in items:
            op = self.layout.operator("node.add_node", text=cls.bl_label)
            op.type = cls.bl_idname
            op.use_transform = True
    return draw


def build(node_classes):
    by_cat = {}
    for cls in node_classes:
        by_cat.setdefault(cls.ln_category, []).append(cls)
    cats = [c for c in CATEGORY_ORDER if c in by_cat] + sorted(set(by_cat) - set(CATEGORY_ORDER))
    menus = []
    for cat in cats:
        items = sorted(by_cat[cat], key=lambda c: c.bl_label)
        ident = "LN_MT_add_" + cat.lower().replace(" ", "_")

        menus.append(type(ident, (bpy.types.Menu,), {"bl_idname": ident, "bl_label": cat, "draw": _menu_draw(items)}))
    _menus[:] = menus
    return menus


def draw_add_menu(self, context):
    space = context.space_data
    if space is None or getattr(space, "tree_type", "") != TREE_ID:
        return
    layout = self.layout
    last_family = None
    for menu in _menus:
        family = menu.bl_label.split()[0]
        if last_family is not None and family != last_family:
            layout.separator()
        last_family = family
        layout.menu(menu.bl_idname)
    layout.separator()
    op = layout.operator("node.add_node", text="Frame")
    op.type = "NodeFrame"
    op.use_transform = True
    op = layout.operator("node.add_node", text="Reroute")
    op.type = "NodeReroute"
    op.use_transform = True


def draw_header(self, context):
    space = context.space_data
    if space is None or getattr(space, "tree_type", "") != TREE_ID:
        return
    from ..core.engine import ENGINE
    layout = self.layout
    if space.node_tree is None:
        layout.operator("livenodes.new_tree", icon='ADD')
    if ENGINE.running:
        layout.operator("livenodes.stop", text="", icon='PAUSE', depress=True)
        layout.label(text=f"{ENGINE.fps_actual:.0f} fps")
    else:
        layout.operator("livenodes.start", text="", icon='PLAY')


def register():
    bpy.types.NODE_MT_add.append(draw_add_menu)
    bpy.types.NODE_HT_header.append(draw_header)


def unregister():
    bpy.types.NODE_MT_add.remove(draw_add_menu)
    bpy.types.NODE_HT_header.remove(draw_header)
