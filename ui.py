import bpy
from bpy.types import Panel
from . import ai

class DEPTHMESH_PT_panel(Panel):
    bl_label = "Depth Mesh"
    bl_idname = "DEPTHMESH_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Depth Mesh"

    def draw(self, context):
        layout = self.layout
        
        # AI Section
        layout.label(text="AI Generation (Experimental)")
        box = layout.box()
        
        if ai.is_installing:
            box.label(text=ai.status_message, icon='TIME')
        elif ai.is_downloading:
            box.label(text=ai.status_message, icon='TIME')
            box.progress(factor=ai.download_progress)
        elif not ai.is_onnx_installed():
            box.label(text="AI Libraries Missing", icon='ERROR')
            box.operator("object.install_ai_dependencies", icon='IMPORT')
        elif not ai.is_model_downloaded():
            box.label(text="Model Missing", icon='INFO')
            box.operator("object.download_ai_model", text="Download Model", icon='IMPORT')
        else:
            box.operator("object.generate_ai_depth", text="Generate Depth & Mesh", icon='NODE')

        layout.separator()
        layout.label(text="Manual Generation")
        layout.operator("object.generate_depth_mesh")
