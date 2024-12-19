# Scene Exporter for NeRF with Viewport Rendering

This Blender add-on exports camera poses and corresponding viewport-rendered images for use in NeRF (Neural Radiance Fields) training pipelines. It generates a structured dataset that includes camera intrinsics, extrinsics, and rendered frames suitable for tools like COLMAP or NeRF training frameworks.

## Features

- **Camera Pose Export:**  
  Extracts camera world transformations and converts from Blender’s Z-up to a Y-up coordinate system (common in NeRF/Colmap pipelines).
  
- **Intrinsics Computation:**  
  Automatically calculates focal length and principal points from Blender’s camera settings. Supports adding distortion coefficients (k1, k2, p1, p2).
  
- **Viewport Rendering:**  
  Renders images directly from the Blender viewport using the active camera in a specified shading mode (`RENDERED` by default).
  
- **Transforms File:**  
  Generates `transforms.json` containing per-frame camera transforms and intrinsics, commonly used as input to NeRF training scripts.
  
- **Organized Folder Structure:**  
  Saves rendered images into an `images/` folder, camera poses into a `poses/` folder, and a `transforms.json` file in the root export directory.

## Requirements

- Blender 3.6 or newer.
- A scene with at least one camera.
- A visible 3D Viewport area if using viewport rendering (headless mode not supported for OpenGL viewport renders).

## Installation

1. Download the Python script.
2. In Blender, go to **Edit > Preferences > Add-ons**.
3. Click **Install...**, select the downloaded `.py` file, and install it.
4. Enable the add-on by checking the box next to *"Scene Exporter for NeRF with Viewport Rendering"*.

## Usage

1. Prepare your Blender scene with at least one camera.
2. Go to **File > Export > Export as NeRF Dataset**.
3. In the export dialog:
   - Set the **Directory** where you want the dataset saved.
   - Adjust intrinsic parameters or distortion coefficients (k1, k2, p1, p2) if necessary.
   - Set `AABB Scale` as needed (useful for NeRF bounding boxes).
   
4. Click **Export**.

After the export:
- The chosen directory will contain:
  - `images/` folder with `frame_00000.png`, `frame_00001.png`, etc.
  - `poses/` folder with camera model and image pose data (via `write_model`).
  - `transforms.json` with all intrinsic and extrinsic parameters.

## Customization

- **Model Name-Based Directories:**  
  Modify the `execute()` method to append a model name:
  ```python
  model_name = "my_model_name"
  dirpath = Path(self.directory) / model_name
