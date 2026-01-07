bl_info = {
    "name": "Depth Mesh Generator",
    "author": "Scar",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Depth Mesh",
    "description": "Generate a displaced mesh from a depth map image",
    "category": "Object",
}

import bpy
from .operators import DEPTHMESH_OT_generate, DEPTHMESH_OT_install_ai, DEPTHMESH_OT_generate_ai, DEPTHMESH_OT_download_model
from .ui import DEPTHMESH_PT_panel

def register():
    bpy.utils.register_class(DEPTHMESH_OT_install_ai)
    bpy.utils.register_class(DEPTHMESH_OT_download_model)
    bpy.utils.register_class(DEPTHMESH_OT_generate_ai)
    bpy.utils.register_class(DEPTHMESH_OT_generate)
    bpy.utils.register_class(DEPTHMESH_PT_panel)

def unregister():
    bpy.utils.unregister_class(DEPTHMESH_PT_panel)
    bpy.utils.unregister_class(DEPTHMESH_OT_generate)
    bpy.utils.unregister_class(DEPTHMESH_OT_generate_ai)
    bpy.utils.unregister_class(DEPTHMESH_OT_download_model)
    bpy.utils.unregister_class(DEPTHMESH_OT_install_ai)

if __name__ == "__main__":
    register()
