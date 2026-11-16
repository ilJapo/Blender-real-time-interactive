"""The cook loop: orders the network, evaluates it every frame and owns all
runtime state (outputs, per-node state, errors, timings)."""
import time
import traceback

import bpy
from bpy.app.handlers import persistent

from . import services, tree as tree_mod
from .data import Channels
from .tree import TREE_ID, node_key


class Inputs:
    """Data arriving at a node, by input socket name."""

    __slots__ = ("_d",)

    def __init__(self, d):
        self._d = d

    def get(self, name, default=None):
        vals = self._d.get(name)
        return vals[0] if vals else default

    def all(self, name):
        return self._d.get(name, ())

    def chop(self, name="In"):
        v = self.get(name)
        return v if isinstance(v, Channels) else Channels.empty()


class ParamView:
    """Node properties, with values overridden by same-named channels on the
    Params input (`speed`, or `color.r` / `offset.x` / `size0` for components)."""

    __slots__ = ("_node", "_over")
    _COMP = {"x": 0, "y": 1, "z": 2, "w": 3, "r": 0, "g": 1, "b": 2, "a": 3,
             "0": 0, "1": 1, "2": 2, "3": 3}

    def __init__(self, node, over):
        self._node = node
        self._over = over

    def __getattr__(self, name):
        val = getattr(self._node, name)
        over = self._over
        if not over:
            return val
        if isinstance(val, bool):
            return over[name] > 0.5 if name in over else val
        if isinstance(val, int):
            return int(round(over[name])) if name in over else val
        if isinstance(val, float):
            return over.get(name, val)
        if isinstance(val, str) or not hasattr(val, "__len__"):
            return val
        out = None
        for key, v in over.items():
            if key.startswith(name) and len(key) > len(name):
                suffix = key[len(name):].lstrip("._")
                idx = self._COMP.get(suffix)
                if idx is not None and idx < len(val):
                    if out is None:
                        out = list(val)
                    out[idx] = v
        return out if out is not None else val


class Context:
    """Everything a node may need while cooking."""

    __slots__ = ("engine", "tree", "scene", "time", "dt", "frame", "fps",
                 "default_res", "tex_format", "key", "node", "p")

    @property
    def state(self):
        return self.engine.states.setdefault(self.key, {})

    def output_of(self, node_name, socket=None):
        """Latest output of another node in this tree (previous frame if it
        has not cooked yet): the basis of feedback loops."""
        outs = self.engine.outputs.get(f"{self.tree.name}\x00{node_name}")
        if not outs:
            return None
        if socket is None:
            return next(iter(outs.values()), None)
        return outs.get(socket)


class Engine:
    def __init__(self):
        self.running = False
        self.time = 0.0
        self.dt = 1.0 / 60.0
        self.frame = 0
        self.fps_actual = 0.0
        self.cook_total_ms = 0.0
        self._t_start = 0.0
        self._t_last = 0.0
        self._deadline = 0.0
        self._last_ui = 0.0
        self.plans = {}
        self.outputs = {}
        self.states = {}
        self.errors = {}
        self.cook_ms = {}
        self._reported = set()
        # shared input state filled by the capture operator
        self.keys = {}
        self.mouse = {"x": 0.5, "y": 0.5, "left": 0.0, "middle": 0.0, "right": 0.0, "wheel": 0.0}
        self.output_windows = {}  # window pointer -> (tree name, node name)

    # -- lifecycle --------------------------------------------------------
    def start(self):
        if self.running:
            return
        self.running = True
        now = time.perf_counter()
        self._t_start = now - self.time
        self._t_last = now
        self._deadline = now
        tree_mod.mark_all_dirty()
        if not bpy.app.timers.is_registered(_timer):
            bpy.app.timers.register(_timer, first_interval=0.0, persistent=True)

    def stop(self):
        self.running = False
        if bpy.app.timers.is_registered(_timer):
            bpy.app.timers.unregister(_timer)
        services.shutdown_all()

    def reset(self):
        """Rewind time and drop all runtime state."""
        self.time = 0.0
        self.frame = 0
        self._t_start = time.perf_counter()
        self._t_last = self._t_start
        self.free_states()
        self.outputs.clear()
        self.errors.clear()
        self._reported.clear()
        tree_mod.mark_all_dirty()

    def free_states(self):
        for st in self.states.values():
            _free_state(st)
        self.states.clear()

    def release(self, key):
        _free_state(self.states.pop(key, None))
        self.outputs.pop(key, None)
        self.errors.pop(key, None)
        self.cook_ms.pop(key, None)

    def shutdown(self):
        self.stop()
        self.free_states()
        self.outputs.clear()
        self.plans.clear()
        self.errors.clear()

    # -- planning ---------------------------------------------------------
    def _build_plan(self, tree):
        nodes = {n.name: n for n in tree.nodes}
        incoming = {}
        for link in tree.links:
            incoming.setdefault((link.to_node.name, link.to_socket.identifier), []).append(
                (link.multi_input_sort_id, link.from_node.name, link.from_socket.identifier,
                 link.from_socket.bl_idname))

        def source(node_name, sock_ident, depth=0):
            """Follow reroutes back to a real output."""
            node = nodes.get(node_name)
            if node is None or depth > 64:
                return None
            if node.bl_idname != 'NodeReroute':
                return node_name, sock_ident, None
            up = incoming.get((node_name, node.inputs[0].identifier))
            if not up:
                return None
            return source(up[0][1], up[0][2], depth + 1)

        plan = []
        deps = {}
        for name, node in nodes.items():
            if not hasattr(node, "cook") or not hasattr(node, "ln_family"):
                continue
            ins = []
            dep = set()
            for sock in node.inputs:
                srcs = []
                for _sort, fname, fident, _ in sorted(incoming.get((name, sock.identifier), ())):
                    src = source(fname, fident)
                    if src is None or src[0] == name:
                        continue
                    src_node = nodes[src[0]]
                    src_sock = next((s for s in src_node.outputs if s.identifier == src[1]), None)
                    if src_sock is None or src_sock.bl_idname != sock.bl_idname:
                        continue  # mismatched families do not connect
                    srcs.append((f"{tree.name}\x00{src[0]}", src[1]))
                    dep.add(src[0])
                ins.append((sock.identifier, sock.bl_idname, tuple(srcs)))
            outs = tuple((s.identifier, s.bl_idname) for s in node.outputs)
            plan.append((name, f"{tree.name}\x00{name}", tuple(ins), outs))
            deps[name] = dep

        # Nodes that read the scene wait for the nodes that write it (unless
        # the writer is downstream of the reader), so renders see this frame's state.
        writers = [n for n in deps if getattr(nodes[n], "ln_writes_scene", False)]
        readers = [n for n in deps if getattr(nodes[n], "ln_reads_scene", False)]
        if writers and readers:
            def ancestors(name, seen=None):
                seen = set() if seen is None else seen
                for d in deps[name]:
                    if d not in seen:
                        seen.add(d)
                        ancestors(d, seen)
                return seen
            for w in writers:
                up = ancestors(w)
                for r in readers:
                    if r not in up and r != w:
                        deps[r].add(w)

        # Kahn topological order; members of a cycle keep reading last frame.
        order, done, pending = [], set(), list(plan)
        while pending:
            ready = [e for e in pending if deps[e[0]] <= done]
            if not ready:
                ready = pending[:1]
            for e in ready:
                order.append(e)
                done.add(e[0])
            pending = [e for e in pending if e[0] not in done]

        live = {e[1] for e in order}
        prefix = tree.name + "\x00"
        for key in [k for k in self.states if k.startswith(prefix) and k not in live]:
            self.release(key)
        for key in [k for k in self.outputs if k.startswith(prefix) and k not in live]:
            self.outputs.pop(key, None)
        return order, (len(tree.nodes), len(tree.links))

    # -- cooking ----------------------------------------------------------
    def tick(self, scene=None, now_time=None, dt=None):
        """Advance one frame. `now_time`/`dt` override the wall clock
        (timeline sync and tests)."""
        t0 = time.perf_counter()
        if scene is None:
            scene = _active_scene()
        if scene is None:
            return
        settings = scene.livenodes
        if now_time is None:
            self.time = t0 - self._t_start
            self.dt = min(max(t0 - self._t_last, 1e-6), 0.25)
        else:
            self.dt = dt if dt is not None else max(now_time - self.time, 1e-6)
            self.time = now_time
        if t0 > self._t_last:
            inst = 1.0 / (t0 - self._t_last)
            self.fps_actual += (inst - self.fps_actual) * 0.1
        self._t_last = t0
        self.frame += 1

        ctx = Context()
        ctx.engine = self
        ctx.scene = scene
        ctx.time = self.time
        ctx.dt = self.dt
        ctx.frame = self.frame
        ctx.fps = settings.fps
        ctx.default_res = (settings.res_x, settings.res_y)
        ctx.tex_format = settings.tex_format

        for tree in bpy.data.node_groups:
            if tree.bl_idname == TREE_ID:
                ctx.tree = tree
                self._cook_tree(tree, ctx)
        self.mouse["wheel"] = 0.0
        self.cook_total_ms = (time.perf_counter() - t0) * 1000.0

    def _cook_tree(self, tree, ctx):
        name = tree.name
        cached = self.plans.get(name)
        if cached is None or tree_mod.is_dirty(name) or cached[1] != (len(tree.nodes), len(tree.links)):
            tree_mod.clear_dirty(name)
            cached = self.plans[name] = self._build_plan(tree)
        nodes = tree.nodes
        outputs = self.outputs
        for node_name, key, ins, outs in cached[0]:
            node = nodes.get(node_name)
            if node is None:
                tree_mod._dirty.add(name)
                continue
            data = {}
            over = None
            for ident, _idname, srcs in ins:
                vals = []
                for src_key, src_ident in srcs:
                    v = outputs.get(src_key)
                    if v is not None:
                        v = v.get(src_ident)
                        if v is not None:
                            vals.append(v)
                if vals:
                    data[ident] = vals
                    if ident == "Params" and node.ln_params:
                        over = vals[0].to_dict()
            if node.mute:
                outputs[key] = _passthrough(ins, outs, data)
                continue
            ctx.key = key
            ctx.node = node
            ctx.p = ParamView(node, over)
            t0 = time.perf_counter()
            try:
                res = node.cook(ctx, Inputs(data))
            except Exception as exc:
                msg = f"{type(exc).__name__}: {exc}"
                self.errors[key] = msg
                if (key, msg) not in self._reported:
                    self._reported.add((key, msg))
                    print(f"[LiveNodes] {tree.name} / {node_name}: {msg}")
                    if not isinstance(exc, (RuntimeError, ValueError)):
                        traceback.print_exc()
            else:
                self.errors.pop(key, None)
                if isinstance(res, dict):
                    outputs[key] = res
                elif res is not None and outs:
                    outputs[key] = {outs[0][0]: res}
                else:
                    outputs[key] = {}
            self.cook_ms[key] = (time.perf_counter() - t0) * 1000.0

    # -- UI helpers -------------------------------------------------------
    def draw_status(self, node, layout, full=False):
        key = node_key(node)
        err = self.errors.get(key)
        if err:
            col = layout.column(align=True)
            col.alert = True
            for i in range(0, min(len(err), 160 if full else 80), 40):
                col.label(text=err[i:i + 40], icon='ERROR' if i == 0 else 'BLANK1')
        if not self.running and not full:
            return
        outs = self.outputs.get(key)
        if outs and getattr(node, "show_values", True):
            for val in outs.values():
                if isinstance(val, Channels) and val.num_channels:
                    col = layout.column(align=True)
                    limit = 32 if full else 4
                    for cname, row in list(zip(val.names, val.data))[:limit]:
                        txt = f"{cname}: {row[0]:.3f}"
                        if len(row) > 1:
                            txt += f"  [{len(row)}]"
                        col.label(text=txt)
                    if val.num_channels > limit:
                        col.label(text=f"... {val.num_channels} channels")
                    break
        if full:
            ms = self.cook_ms.get(key)
            if ms is not None:
                layout.label(text=f"Cook: {ms:.2f} ms")

    def tag_redraw(self, settings):
        wm = bpy.context.window_manager
        if wm is None:
            return
        now = time.perf_counter()
        ui = now - self._last_ui > 0.05
        if ui:
            self._last_ui = now
        for window in wm.windows:
            is_out = window.as_pointer() in self.output_windows
            for area in window.screen.areas:
                if is_out:
                    area.tag_redraw()
                elif area.type == 'VIEW_3D':
                    if settings.redraw_viewports:
                        area.tag_redraw()
                elif ui and area.type == 'NODE_EDITOR':
                    space = area.spaces.active
                    if getattr(space, "tree_type", "") == TREE_ID:
                        area.tag_redraw()


def _passthrough(ins, outs, data):
    """Muted node: each output forwards the first input of the same family."""
    res = {}
    for out_ident, out_idname in outs:
        for ident, idname, _ in ins:
            if idname == out_idname and ident != "Params" and ident in data:
                res[out_ident] = data[ident][0]
                break
    return res


def _free_state(st):
    if not st:
        return
    for val in st.values():
        free = getattr(val, "free", None)
        if callable(free):
            try:
                free()
            except Exception:
                pass


def _active_scene():
    win = bpy.context.window
    if win is not None:
        return win.scene
    wm = bpy.context.window_manager
    if wm is not None and wm.windows:
        return wm.windows[0].scene
    return bpy.context.scene or (bpy.data.scenes[0] if bpy.data.scenes else None)


ENGINE = Engine()


def _timer():
    eng = ENGINE
    if not eng.running:
        return None
    scene = _active_scene()
    if scene is None:
        return 0.1
    settings = scene.livenodes
    if settings.time_mode == 'REALTIME':
        try:
            eng.tick(scene)
        except Exception:
            traceback.print_exc()
    try:
        eng.tag_redraw(settings)
    except Exception:
        pass
    now = time.perf_counter()
    eng._deadline = max(eng._deadline + 1.0 / max(settings.fps, 1), now - 0.1)
    return max(0.0, eng._deadline - now)


@persistent
def _on_frame_change(scene, depsgraph=None):
    """Timeline sync: one cook per frame, so animations render deterministically."""
    eng = ENGINE
    if not eng.running or scene.livenodes.time_mode != 'TIMELINE':
        return
    fps = scene.render.fps / scene.render.fps_base
    try:
        eng.tick(scene, now_time=(scene.frame_current - scene.frame_start) / fps, dt=1.0 / fps)
    except Exception:
        traceback.print_exc()


@persistent
def _on_load_pre(*_args):
    ENGINE.shutdown()
    ENGINE.time = 0.0
    ENGINE.frame = 0


@persistent
def _on_load_post(*_args):
    tree_mod.mark_all_dirty()
    for scene in bpy.data.scenes:
        if scene.livenodes.autostart:
            ENGINE.start()
            break


@persistent
def _on_undo(*_args):
    tree_mod.mark_all_dirty()


def register():
    bpy.app.handlers.frame_change_post.append(_on_frame_change)
    bpy.app.handlers.load_pre.append(_on_load_pre)
    bpy.app.handlers.load_post.append(_on_load_post)
    bpy.app.handlers.undo_post.append(_on_undo)
    bpy.app.handlers.redo_post.append(_on_undo)


def unregister():
    ENGINE.shutdown()
    for lst, fn in ((bpy.app.handlers.frame_change_post, _on_frame_change),
                    (bpy.app.handlers.load_pre, _on_load_pre),
                    (bpy.app.handlers.load_post, _on_load_post),
                    (bpy.app.handlers.undo_post, _on_undo),
                    (bpy.app.handlers.redo_post, _on_undo)):
        if fn in lst:
            lst.remove(fn)
