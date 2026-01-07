# Depth Mesh Generator

Depth Mesh Generator is a Blender add-on that uses AI to transform images into 3D models by generating a depth map and applying it as a displacement to a subdivided plane.

## Features
- **AI-Powered Depth Generation**: Uses the "Depth Anything" ONNX model for high-quality depth estimation.
- **Automated Geometry Creation**: Automatically creates a subdivided plane and applies a displacement modifier.
- **Snap/Linux Compatibility**: Handles Python path issues commonly found in Snap-installed Blender.
- **Robust Dependency Installer**: Built-in installer for required AI libraries (`onnxruntime`, `numpy`, `pillow`).
- **UV Mapping Support**: Ensures standard image textures are correctly mapped to the generated mesh.

## Installation
1.  Download the latest release zip file.
2.  Open Blender and go to **Edit > Preferences > Get Extensions**.
3.  Click the arrow icon in the top right and select **Install from Disk...**.
4.  Select the `depth_mesh_generator.zip` file.
5.  Enable the extension.

## Usage
1.  Open the **3D Viewport** and find the **Depth Mesh** tab in the Sidebar (N-panel).
2.  **Install Dependencies**: Click this button first to install the required AI libraries.
3.  **Download Model**: Click this to download the ~100MB depth estimation model.
4.  **Generate Depth & Mesh**: Pick an image file and click this button to generate your 3D model.

## Troubleshooting
If you encounter issues during installation or inference, check the following log files in the add-on directory:
- `install_log.txt`: Logs from the dependency installation process.
- `inference_log.txt`: Logs from the AI image processing.

## License
GPL-2.0-or-later
