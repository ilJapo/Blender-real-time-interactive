"""Drawing textures in the UI: node previews, backdrop and output windows."""
import bpy

from ..core import gpu_util
from ..core.engine import ENGINE
from ..core.tree import TREE_ID

_handles = []


def _texture_of(tree_name, node_name):
    outs = ENGINE.outputs.get(f"{tree_name}\x00{node_name}")
    if outs:
        for val in outs.values():
            if hasattr(val, "width") and hasattr(val, "height"):
                return val
    st = ENGINE.states.get(f"{tree_name}\x00{node_name}")
    if st:
        tex = st.get("tex")
        if tex is not None and hasattr(tex, "width"):
            return tex
    return None


def texture_for_node(node):
    return _texture_of(node.id_data.name, node.name)


def fit(tex_w, tex_h, w, h):
    """Aspect-correct rectangle of a texture inside w x h."""
    s = min(w / max(tex_w, 1), h / max(tex_h, 1))
    dw, dh = tex_w * s, tex_h * s
    return (w - dw) * 0.5, (h - dh) * 0.5, dw, dh


def _dpi():
    return bpy.context.preferences.system.dpi / 72.0


def draw_node_previews():
    context = bpy.context
    space = context.space_data
    if space is None or getattr(space, "tree_type", "") != TREE_ID:
        return
    tree = space.edit_tree
    scene = context.scene
    if tree is None or scene is None or not ENGINE.outputs:
        return
    settings = scene.livenodes
    region = context.region
    v2d = region.view2d
    dpi = _dpi()

    if settings.backdrop:
        node = next((n for n in tree.nodes if n.bl_idname == "LN_OutTOP"), None)
        active = tree.nodes.active
        if active is not None and getattr(active, "ln_family", "") == 'TOP':
            node = active
        tex = texture_for_node(node) if node is not None else None
        if tex is not None:
            x, y, w, h = fit(tex.width, tex.height, region.width, region.height)
            gpu_util.draw_texture(tex, x, y, w, h)

    if not settings.show_previews:
        return
    # zoom: region pixels per view unit
    x0, _ = v2d.view_to_region(0.0, 0.0, clip=False)
    x1, _ = v2d.view_to_region(100.0, 0.0, clip=False)
    zoom = (x1 - x0) / 100.0
    for node in tree.nodes:
        if getattr(node, "ln_family", None) not in {'TOP', 'OUT'} or node.hide:
            continue
        tex = texture_for_node(node)
        if tex is None:
            continue
        loc = node.location_absolute if hasattr(node, "location_absolute") else node.location
        x, y = v2d.view_to_region(loc.x * dpi, loc.y * dpi, clip=False)
        width = max(node.dimensions.x, settings.preview_size * dpi) * zoom
        h = width * tex.height / max(tex.width, 1)
        if x + width < 0 or x > region.width or y + h < 0 or y - 20 > region.height:
            continue
        gpu_util.draw_texture(tex, x, y + 4 * zoom, width, h, use_alpha=True)


def draw_output_window():
    context = bpy.context
    win = context.window
    if win is None:
        return
    entry = ENGINE.output_windows.get(win.as_pointer())
    if entry is None:
        return
    region = context.region
    # paint the region black instead of clearing: a clear can reach past this region
    gpu_util.draw_rect(0, 0, region.width, region.height)
    tex = _texture_of(*entry)
    if tex is None:
        return
    x, y, w, h = fit(tex.width, tex.height, region.width, region.height)
    gpu_util.draw_texture(tex, x, y, w, h)


def register():
    _handles.append((bpy.types.SpaceNodeEditor, bpy.types.SpaceNodeEditor.draw_handler_add(
        draw_node_previews, (), 'WINDOW', 'POST_PIXEL')))
    _handles.append((bpy.types.SpaceImageEditor, bpy.types.SpaceImageEditor.draw_handler_add(
        draw_output_window, (), 'WINDOW', 'POST_PIXEL')))


def unregister():
    for space, handle in _handles:
        try:
            space.draw_handler_remove(handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
    _handles.clear()
