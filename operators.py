import bpy
import os
from bpy.types import Operator
from bpy.props import StringProperty, FloatProperty, BoolProperty, EnumProperty
from . import ai

class DEPTHMESH_OT_install_ai(Operator):
    bl_idname = "object.install_ai_dependencies"
    bl_label = "Install AI Dependencies"
    bl_description = "Installs onnxruntime and other required libraries in background"
    
    _timer = None
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            if ai.is_installing:
                context.workspace.status_text_set(f"AI Setup: {ai.status_message}")
            else:
                # Finished
                context.workspace.status_text_set(None) # Clear status
                self.report({'INFO'}, ai.status_message)
                
                # Force UI redraw to update panel button state
                for window in context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()
                            
                context.window_manager.event_timer_remove(self._timer)
                return {'FINISHED'}
                
        return {'PASS_THROUGH'}

    def execute(self, context):
        if ai.is_installing:
            self.report({'WARNING'}, "Installation already in progress")
            return {'CANCELLED'}
            
        ai.start_install_thread()
        self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

class DEPTHMESH_OT_download_model(Operator):
    bl_idname = "object.download_ai_model"
    bl_label = "Download AI Model"
    bl_description = "Downloads the Depth Anything ONNX model"
    
    _timer = None
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            if ai.is_downloading:
                context.workspace.status_text_set(f"AI Model: {ai.status_message}")
                # Force UI redraw to show progress bar in panel if we add one
                for window in context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()
            else:
                context.workspace.status_text_set(None)
                self.report({'INFO'}, ai.status_message)
                context.window_manager.event_timer_remove(self._timer)
                # Auto-trigger generation? No, let user decide.
                return {'FINISHED'}
        
        return {'PASS_THROUGH'}

    def execute(self, context):
        if ai.is_downloading:
            self.report({'WARNING'}, "Download already in progress")
            return {'CANCELLED'}
            
        ai.start_download_thread()
        self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

class DEPTHMESH_OT_generate_ai(Operator):
    bl_idname = "object.generate_ai_depth"
    bl_label = "Generate AI Depth"
    bl_description = "Generate depth map from image using AI and create mesh"
    
    filepath: StringProperty(
        name="Source Image", description="Image to process", subtype="FILE_PATH"
    )
    
    filter_glob: StringProperty(
        default="*.jpg;*.jpeg;*.png;*.tif;*.tiff;*.bmp",
        options={'HIDDEN'},
        maxlen=255,
    )
    
    def execute(self, context):
        # 1. Check Model
        if not ai.is_model_downloaded():
             self.report({'ERROR'}, "Model not found. Please download it first.")
             return {'CANCELLED'}

        # 2. Process Image
        if not self.filepath:
             self.report({'ERROR'}, "No image selected")
             return {'CANCELLED'}
             
        filepath = bpy.path.abspath(self.filepath)
        self.report({'INFO'}, f"Processing {filepath}...")
        
        # This part is still blocking, but inference is usually fast (seconds).
        # We could make this modal too, but let's stick to install/download first.
        depth_path = ai.process_image(filepath)
        
        if not depth_path:
            self.report({'ERROR'}, "AI Inference Failed. Check console.")
            return {'CANCELLED'}
            
        self.report({'INFO'}, f"Depth map saved to {depth_path}")
        
        # 3. Call the Mesh Generator
        bpy.ops.object.generate_depth_mesh(
            filepath=depth_path, 
            use_color_map=True, 
            use_alpha_mask=False,
            depth_strength=1.0
        )
        
        # Fix texture
        active_obj = context.active_object
        if active_obj and active_obj.name.startswith("DepthMesh"):
            if active_obj.data.materials:
                mat = active_obj.data.materials[0]
                if mat.use_nodes:
                    nodes = mat.node_tree.nodes
                    for node in nodes:
                        if node.type == 'TEX_IMAGE':
                            try:
                                orig_img = bpy.data.images.load(filepath)
                                node.image = orig_img
                            except:
                                pass
                            break

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

class DEPTHMESH_OT_generate(Operator):
    bl_idname = "object.generate_depth_mesh"
    bl_label = "Create Depth Mesh"
    bl_description = "Create a subdivided plane displaced by a depth map"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(
        name="Depth Map", description="Path to depth map image", subtype="FILE_PATH"
    )

    filter_glob: StringProperty(
        default="*.jpg;*.jpeg;*.png;*.tif;*.tiff;*.bmp;*.exr;*.hdr;*.tga",
        options={'HIDDEN'},
        maxlen=255,
    )

    use_color_map: BoolProperty(
        name="Use as Color",
        description="Apply the image as a Base Color material to the mesh",
        default=True
    )

    # Depth Controls
    depth_strength: FloatProperty(
        name="Strength",
        description="Displacement strength",
        default=0.5,
        min=-10.0,
        max=10.0
    )

    depth_midlevel: FloatProperty(
        name="Midlevel",
        description="Texture value treated as no displacement",
        default=0.5,
        min=0.0,
        max=1.0
    )

    invert_depth: BoolProperty(
        name="Invert Depth",
        description="Invert the depth map (dark becomes high)",
        default=False
    )

    use_clamp: BoolProperty(
        name="Clamp",
        description="Clamp texture values to 0-1 range (Clip Extension)",
        default=True
    )

    # 1. Silhouette Masking
    use_alpha_mask: BoolProperty(
        name="Use Alpha Mask",
        description="Use image alpha channel to mask displacement (Zero displacement in transparent areas)",
        default=True
    )

    # 2. Geometry Refinement
    refinement_method: EnumProperty(
        name="Refinement",
        description="Method to refine geometry after displacement",
        items=[
            ('SUBDIV', "Subdivision Only", "Standard subdivision (Fast)"),
            ('REMESH', "Voxel Remesh", "Rebuilds mesh with uniform voxels (Good for sculpting, destroys UVs)"),
        ],
        default='SUBDIV'
    )
    
    use_optimization: BoolProperty(
        name="Optimize Mesh",
        description="Reduce polygon count while preserving shape (Decimate)",
        default=False
    )

    optimization_ratio: FloatProperty(
        name="Optimization Ratio",
        description="Ratio of triangles to reduce to (0.1 = 10% of original count)",
        default=0.5,
        min=0.01,
        max=1.0,
        precision=2
    )
    
    remesh_voxel_size: FloatProperty(
        name="Voxel Size",
        description="Size of voxels for remeshing (Smaller = More Detail)",
        default=0.05,
        min=0.001,
        max=1.0,
        precision=3
    )

    # 3. Volume / Solidity
    use_solidify: BoolProperty(
        name="Add Thickness",
        description="Add a solid volume to the mesh",
        default=False
    )
    
    thickness_amount: FloatProperty(
        name="Thickness",
        description="Amount of thickness to add",
        default=0.1,
        min=0.0,
        max=10.0
    )

    def execute(self, context):
        if not self.filepath:
            self.report({"ERROR"}, "No image path provided")
            return {"CANCELLED"}

        # Ensure path is absolute
        filepath = bpy.path.abspath(self.filepath)

        if not os.path.exists(filepath):
             self.report({"ERROR"}, f"File not found: {filepath}")
             return {"CANCELLED"}

        # Load image
        try:
            img = bpy.data.images.load(filepath)
        except Exception as e:
            self.report({"ERROR"}, f"Failed to load image: {str(e)}")
            return {"CANCELLED"}

        # Create plane
        bpy.ops.mesh.primitive_plane_add(size=2)
        plane = context.active_object
        plane.name = "DepthMesh"

        # Create Texture
        tex = bpy.data.textures.new("DepthTexture", type="IMAGE")
        tex.image = img
        if self.use_clamp:
            tex.extension = 'CLIP'
        else:
            tex.extension = 'EXTEND'

        # 1. Silhouette Masking Logic
        # We create a Vertex Group and use a VertexWeightEdit modifier masked by texture to control it.
        # Then we feed this Vertex Group into the Displace modifier.
        displace_vg_name = None
        
        if self.use_alpha_mask:
            # Create Vertex Group
            displace_vg = plane.vertex_groups.new(name="DisplaceMask")
            displace_vg_name = displace_vg.name
            
            # Add all vertices to group with weight 0 initially
            verts = [v.index for v in plane.data.vertices]
            displace_vg.add(verts, 0.0, 'REPLACE')
            
            # Use VertexWeightEdit to map texture alpha to weight
            # Note: This is a tricky hack in standard modifiers. 
            # A cleaner way usually is "VertexWeightProximity" but we don't have a target.
            # "VertexWeightMix" requires a second group.
            # "VertexWeightEdit" with Texture Mask works:
            # It modifies existing weights based on texture.
            # Setting default weight to 0 and 'Add' or 'Replace' based on texture intensity.
            
            # However, modifier texture masks usually read Intensity (Value), not specifically Alpha.
            # If the image has premultiplied alpha or black background, Intensity works fine.
            # If transparent areas are white but 0 alpha, this might fail.
            # Assuming standard PNG where transparent = 0,0,0,0 or just Alpha=0.
            
            vw_mod = plane.modifiers.new("MaskWeights", "VERTEX_WEIGHT_EDIT")
            vw_mod.vertex_group = displace_vg_name
            vw_mod.default_weight = 0.0
            vw_mod.falloff_type = 'LINEAR'
            vw_mod.mask_texture = tex
            vw_mod.mask_tex_use_channel = 'INT' # Intensity. 
            # If simple alpha support is needed, we might rely on the user ensuring background is black.
            # Blender's modifier mask doesn't explicitly pick "Alpha" channel easily without nodes.
            # But usually (Alpha * Color) is read as intensity.
            
            # To ensure it adds weight:
            vw_mod.use_add = True 
            vw_mod.add_threshold = 0.0
            vw_mod.mask_tex_mapping = 'UV' # CRITICAL: Map mask using UVs

        # Subdivision
        sub = plane.modifiers.new("Subdivision", "SUBSURF")
        sub.levels = 6
        sub.render_levels = 6
        sub.subdivision_type = 'SIMPLE'

        # Displacement
        disp = plane.modifiers.new("Displace", "DISPLACE")
        
        # Apply Properties
        final_strength = -self.depth_strength if self.invert_depth else self.depth_strength
        disp.strength = final_strength
        disp.mid_level = self.depth_midlevel
        disp.texture = tex
        disp.texture_coords = 'UV' # CRITICAL: Ensure texture uses UV map
        
        if displace_vg_name:
            disp.vertex_group = displace_vg_name

        # 2. Geometry Refinement
        if self.refinement_method == 'REMESH':
            remesh = plane.modifiers.new("Remesh", "REMESH")
            remesh.mode = 'VOXEL'
            remesh.voxel_size = self.remesh_voxel_size
            remesh.adaptivity = 0.0
            remesh.use_smooth_shade = True

        # Optimization / Decimation
        if self.use_optimization:
            decimate = plane.modifiers.new("Optimize", "DECIMATE")
            decimate.decimate_type = 'COLLAPSE'
            decimate.ratio = self.optimization_ratio
            # If using Voxel Remesh, usually Triangulate is handled by it, but Decimate works on Tris.
            # No special extra settings needed for basic reduction.

        # 3. Volume / Solidity
        if self.use_solidify:
            solid = plane.modifiers.new("Solidify", "SOLIDIFY")
            solid.thickness = self.thickness_amount
            solid.offset = 0 # Center the solidify? Or -1. User usually expects inward/outward. Default -1.
            # To prevent "collapsing edges" (z-fighting/self intersection), we might want Even Thickness
            solid.use_even_offset = True

        # 4. Material / Color
        if self.use_color_map:
            mat = bpy.data.materials.new(name="DepthMaterial")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            
            # Clear default nodes to ensure clean state
            nodes.clear()
            
            # Create Principled BSDF
            shader = nodes.new(type='ShaderNodeBsdfPrincipled')
            shader.location = (0, 0)
            
            # Create Output
            output = nodes.new(type='ShaderNodeOutputMaterial')
            output.location = (300, 0)
            
            # Create Image Texture
            tex_node = nodes.new(type='ShaderNodeTexImage')
            tex_node.location = (-300, 0)
            tex_node.image = img
            
            # Link
            links.new(tex_node.outputs['Color'], shader.inputs['Base Color'])
            links.new(shader.outputs['BSDF'], output.inputs['Surface'])
            
            # Assign to plane
            if plane.data.materials:
                plane.data.materials[0] = mat
            else:
                plane.data.materials.append(mat)
            
            # Set viewport display to textured to see it immediately
            context.space_data.shading.type = 'MATERIAL'

        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
