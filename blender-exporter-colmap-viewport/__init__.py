import numpy as np
from pathlib import Path
import mathutils
from .ext.read_write_model import write_model, Camera, Image  # Corrected import
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, FloatProperty
import bpy
import json
import math
import os
import subprocess

bl_info = {
    "name": "Scene Exporter for NeRF with Viewport Rendering",
    "description": "Generates a dataset by exporting Blender camera poses and capturing viewport images.",
    "author": "Assistant",
    "version": (0, 2, 0),
    "blender": (3, 6, 0),
    "location": "File > Export",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Import-Export"
}

def get_coord_conversion_matrix():
    """
    Defines the coordinate system conversion matrix.
    Rotates -90 degrees around the X-axis to convert Blender's Z-up to COLMAP/NeRF's Y-up.
    """
    rot = mathutils.Euler((-math.pi / 2, 0, 0), 'XYZ').to_matrix().to_4x4()
    return rot

class BlenderExporterForNeRF(bpy.types.Operator, ExportHelper):
    bl_idname = "export_scene.nerf_dataset"
    bl_label = "Export as NeRF Dataset"
    bl_options = {"PRESET", "REGISTER"}

    filename_ext = ""
    directory: StringProperty(subtype="DIR_PATH")
    filter_folder = True

    # Adding properties for distortion coefficients
    k1: FloatProperty(name="K1", default=0.0)
    k2: FloatProperty(name="K2", default=0.0)
    p1: FloatProperty(name="P1", default=0.0)
    p2: FloatProperty(name="P2", default=0.0)
    aabb_scale: FloatProperty(name="AABB Scale", default=16.0)

    def execute(self, context):
        dirpath = Path(self.directory)
        format = '.json'  # Changed to JSON format

        # Initialize the export process
        try:
            for progress in self.export_dataset(context, dirpath, format):
                # Update progress if needed (optional)
                pass
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {e}")
            return {'CANCELLED'}

        self.report({'INFO'}, "Export completed successfully.")
        return {'FINISHED'}

    def export_dataset(self, context, dirpath: Path, format: str):
        scene = context.scene
        scene_cameras = [i for i in scene.objects if i.type == "CAMERA"]

        output_dir = dirpath
        images_dir = output_dir / 'images'
        poses_dir = output_dir / 'poses'

        # Create directories
        output_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)
        poses_dir.mkdir(parents=True, exist_ok=True)

        cameras = {}
        images = {}

        # Collect intrinsic parameters from the first camera (assuming all cameras have the same intrinsics)
        if not scene_cameras:
            self.report({'ERROR'}, "No cameras found in the scene.")
            return {'CANCELLED'}

        cam = scene_cameras[0]
        width = scene.render.resolution_x
        height = scene.render.resolution_y
        focal_length = cam.data.lens
        sensor_width = cam.data.sensor_width
        sensor_height = cam.data.sensor_height
        fx = focal_length * width / sensor_width
        fy = focal_length * height / sensor_height
        cx = width / 2
        cy = height / 2

        # Distortion coefficients (can be set via properties)
        k1 = self.k1
        k2 = self.k2
        p1 = self.p1
        p2 = self.p2

        # Prepare transforms.json structure
        transforms = {
            "fl_x": fx,
            "fl_y": fy,
            "k1": k1,
            "k2": k2,
            "p1": p1,
            "p2": p2,
            "cx": cx,
            "cy": cy,
            "w": width,
            "h": height,
            "aabb_scale": self.aabb_scale,
            "frames": []
        }

        # Define coordinate conversion matrix
        coord_conv = get_coord_conversion_matrix()

        # Proceed with exporting each camera/frame
        for idx, cam in enumerate(sorted(scene_cameras, key=lambda x: x.name_full)):
            filename = f'frame_{idx:05d}.png'
            file_path = images_dir / filename

            image_id = idx + 1

            # Extract camera's world matrix
            cam_matrix = cam.matrix_world.copy()

            # Apply coordinate conversion
            transformed_matrix = coord_conv @ cam_matrix

            # Extract rotation and translation from the transformed matrix
            rotation_euler = transformed_matrix.to_euler('XYZ')
            rotation_matrix = rotation_euler.to_matrix()
            translation = transformed_matrix.to_translation()

            # Convert rotation matrix to quaternion
            cam_rot = rotation_matrix.to_quaternion()
            qw, qx, qy, qz = cam_rot.w, cam_rot.x, cam_rot.y, cam_rot.z

            # Translation vector
            T1 = translation

            # Add camera to model
            cameras[image_id] = Camera(
                id=image_id,
                model='OPENCV',  # Can be changed if needed
                width=width,
                height=height,
                params=[fx, fy, cx, cy, k1, k2, p1, p2]
            )

            images[image_id] = Image(
                id=image_id,
                qvec=np.array([qw, qx, qy, qz]),
                tvec=np.array([T1[0], T1[1], T1[2]]),
                camera_id=image_id,
                name=filename,
                xys=[],
                point3D_ids=[]
            )

            # Set the scene camera
            scene.camera = cam

            # Set the render filepath
            scene.render.filepath = str(file_path)

            # Find the VIEW_3D area and region once
            view3d_area = None
            view3d_region = None
            view3d_space = None
            window = None
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        view3d_area = area
                        for region in area.regions:
                            if region.type == 'WINDOW':
                                view3d_region = region
                                break
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                view3d_space = space
                                break
                        break
                if view3d_area and view3d_region and view3d_space:
                    break

            if not (view3d_area and view3d_region and view3d_space):
                self.report({'ERROR'}, "No 3D Viewport area found")
                return {'CANCELLED'}

            # Set up the context override
            override = {
                'window': window,
                'screen': window.screen,
                'area': view3d_area,
                'region': view3d_region,
                'scene': scene,
            }

            with bpy.context.temp_override(**override):
                # Set the viewport's camera to the current camera
                view3d_space.camera = cam
                view3d_space.region_3d.view_perspective = 'CAMERA'

                # Refresh the context to update the viewport
                bpy.context.view_layer.update()

                # Optionally set viewport shading to 'RENDERED' for better visuals
                view3d_space.shading.type = 'RENDERED'

                # Render the viewport and save the image
                bpy.ops.render.opengl(write_still=True)

            # Append frame information for transforms.json
            frame = {
                "file_path": f"./images/{filename}",
                "transform_matrix": [
                    [
                        rotation_matrix[0][0], rotation_matrix[0][1], rotation_matrix[0][2], T1[0]
                    ],
                    [
                        rotation_matrix[1][0], rotation_matrix[1][1], rotation_matrix[1][2], T1[1]
                    ],
                    [
                        rotation_matrix[2][0], rotation_matrix[2][1], rotation_matrix[2][2], T1[2]
                    ],
                    [0, 0, 0, 1]
                ]
            }
            transforms["frames"].append(frame)

            yield 100.0 * (idx + 1) / len(scene_cameras)

        # Write camera poses to JSON
        write_model(cameras, images, {}, str(poses_dir), format)

        # Write transforms.json with the desired structure
        transforms_path = output_dir / 'transforms.json'
        with transforms_path.open('w') as f:
            json.dump(transforms, f, indent=4)

        return {'FINISHED'}

def menu_func_export(self, context):
    self.layout.operator(BlenderExporterForNeRF.bl_idname, text="Export as NeRF Dataset")

def register():
    bpy.utils.register_class(BlenderExporterForNeRF)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(BlenderExporterForNeRF)

if __name__ == "__main__":
    register()
