import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty


class LN_Settings(bpy.types.PropertyGroup):
    fps: IntProperty(name="Target FPS", default=60, min=1, max=240, description="Cook rate of the engine")
    res_x: IntProperty(name="Width", default=1280, min=1, max=16384, description="Default resolution of texture generators")
    res_y: IntProperty(name="Height", default=720, min=1, max=16384)
    tex_format: EnumProperty(name="Precision", items=[
        ('RGBA8', "8-bit", "Least memory, banding on gradients and feedback"),
        ('RGBA16F', "16-bit float", "Good default: HDR values, smooth feedback"),
        ('RGBA32F', "32-bit float", "Maximum precision, for data textures")], default='RGBA16F')
    time_mode: EnumProperty(name="Clock", items=[
        ('REALTIME', "Real Time", "Cook continuously at the target FPS, independent of the timeline"),
        ('TIMELINE', "Timeline", "Cook once per timeline frame: deterministic, use it to render animations")],
        default='REALTIME')
    autostart: BoolProperty(name="Start on Load", default=False, description="Start the engine when this file is opened")
    redraw_viewports: BoolProperty(name="Redraw 3D Views", default=True, description="Redraw 3D views every frame so driven objects move smoothly")
    capture_input: BoolProperty(name="Capture Keyboard & Mouse", default=True, description="Feed Keyboard In and Mouse In nodes while running")
    show_previews: BoolProperty(name="Node Previews", default=True, description="Show texture thumbnails above TOP nodes")
    preview_size: IntProperty(name="Preview Size", default=160, min=32, max=1024)
    backdrop: BoolProperty(name="Backdrop", default=False, description="Show the Out TOP (or active TOP) behind the node editor")


classes = (LN_Settings,)


def register():
    bpy.types.Scene.livenodes = bpy.props.PointerProperty(type=LN_Settings)


def unregister():
    del bpy.types.Scene.livenodes
