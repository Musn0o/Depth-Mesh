import os
import sys
import subprocess
import urllib.request
import threading
import bpy
import importlib.util
import site

# Global State for UI
is_installing = False
is_downloading = False
download_progress = 0.0 # 0.0 to 1.0
status_message = ""

# Dependency check
def is_onnx_installed():
    # Ensure user site-packages are in sys.path (needed for Snap/Flatpak)
    user_site = site.getusersitepackages()
    if user_site not in sys.path:
        sys.path.append(user_site)
        
    # Check if we can find the spec without full import
    if importlib.util.find_spec("onnxruntime") is not None:
        return True
    
    # Fallback to direct import test
    try:
        import onnxruntime
        return True
    except ImportError:
        return False

def _install_logic():
    global is_installing, status_message
    is_installing = True
    status_message = "Installing..."
    
    python_exe = sys.executable
    addon_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(addon_dir, "install_log.txt")
    
    try:
        with open(log_path, "w") as log_file:
            log_file.write(f"Starting installation using: {python_exe}\n")
            log_file.flush()
            
            # Using subprocess.run to capture output
            process = subprocess.run(
                [python_exe, "-m", "pip", "install", "onnxruntime", "numpy", "pillow"],
                capture_output=True,
                text=True
            )
            
            log_file.write("--- STDOUT ---\n")
            log_file.write(process.stdout)
            log_file.write("\n--- STDERR ---\n")
            log_file.write(process.stderr)
            
            if process.returncode == 0:
                status_message = "Installation Complete"
                importlib.invalidate_caches()
            else:
                status_message = f"Installation Failed (Code {process.returncode}). Check install_log.txt"
                
    except Exception as e:
        status_message = f"Error: {e}"
        with open(log_path, "a") as log_file:
            log_file.write(f"\nUnexpected Exception: {str(e)}\n")
    finally:
        is_installing = False

def start_install_thread():
    thread = threading.Thread(target=_install_logic)
    thread.start()

# Model Management
MODEL_URL = "https://huggingface.co/yuvraj108c/Depth-Anything-Onnx/resolve/main/depth_anything_vits14.onnx"
MODEL_NAME = "depth_anything_vits14.onnx"

def get_model_path():
    addon_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(addon_dir, "models")
    return os.path.join(models_dir, MODEL_NAME)

def is_model_downloaded():
    return os.path.exists(get_model_path())

def _download_logic():
    global is_downloading, download_progress, status_message
    is_downloading = True
    download_progress = 0.0
    status_message = "Starting Download..."
    
    url = MODEL_URL
    destination = get_model_path()
    models_dir = os.path.dirname(destination)
    
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)
    
    try:
        # Use curl for more robust download on Linux (handles redirects/LFS better)
        # -L to follow redirects
        # -o to specify output file
        # -s for silent, but we want progress for UI if possible.
        # However, capturing curl's progress bar in real-time is complex.
        # We'll use simple status for now.
        status_message = "Downloading (via curl)..."
        
        process = subprocess.run(
            ["curl", "-L", "-o", destination, url],
            capture_output=True,
            text=True
        )
        
        if process.returncode == 0:
            # Verify file size (should be ~100MB)
            file_size = os.path.getsize(destination)
            if file_size < 10 * 1024 * 1024: # Less than 10MB is definitely an error page
                status_message = "Download Failed: Data corrupted (likely error page)"
                print(f"File size too small: {file_size} bytes. Deleting.")
                os.remove(destination)
            else:
                status_message = "Download Complete"
        else:
            status_message = f"Download Failed (curl error {process.returncode})"
            print(f"Curl Error: {process.stderr}")
            if os.path.exists(destination):
                os.remove(destination)
        
    except Exception as e:
        status_message = f"Download Failed: {e}"
        print(status_message)
        if os.path.exists(destination):
            os.remove(destination)
    finally:
        is_downloading = False
        download_progress = 0.0

def start_download_thread():
    thread = threading.Thread(target=_download_logic)
    thread.start()

# Inference
def process_image(image_path):
    """
    Run depth estimation on the image at image_path.
    Returns the path to the saved depth map, or None if failed.
    """
    if not is_onnx_installed():
        print("ONNX Runtime not installed.")
        return None

    import onnxruntime as ort
    import numpy as np
    from PIL import Image

    model_path = get_model_path()
    if not os.path.exists(model_path):
        print("Model not found.")
        return None

    # Log file for inference
    addon_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(addon_dir, "inference_log.txt")
    
    try:
        with open(log_path, "w") as log:
            log.write(f"Inference started for: {image_path}\n")
            
            # Load session
            log.write(f"Loading model from: {model_path}\n")
            session = ort.InferenceSession(model_path)
            
            # Get input/output names
            inputs = session.get_inputs()
            input_name = inputs[0].name
            input_shape = inputs[0].shape
            log.write(f"Model Input name: {input_name}, Shape: {input_shape}\n")
            
            # Target size from model if possible, otherwise fallback
            # The yuvraj108c model often uses dynamic shapes or specific fixed ones.
            # Standard Depth Anything is 518.
            target_size = (518, 518)
            log.write(f"Processing image with target size: {target_size}\n")
            
            # Load and Preprocess Image
            orig_image = Image.open(image_path).convert('RGB')
            orig_width, orig_height = orig_image.size
            
            input_image = orig_image.resize(target_size, Image.BILINEAR)
            input_tensor = np.array(input_image) / 255.0 # 0-1
            
            # Normalize (Mean and Std for ImageNet)
            mean = np.array([0.485, 0.456, 0.406])
            std = np.array([0.229, 0.224, 0.225])
            input_tensor = (input_tensor - mean) / std
            
            # CHW format
            input_tensor = input_tensor.transpose(2, 0, 1)
            # Batch dimension
            input_tensor = input_tensor[None, :, :].astype(np.float32)
            
            log.write(f"Input tensor shape: {input_tensor.shape}\n")
            
            # Run Inference
            outputs = session.run(None, {input_name: input_tensor})
            depth = outputs[0] # (1, H, W) or (1, 1, H, W)
            log.write(f"Output shape: {depth.shape}\n")
            
            # Post-process
            if len(depth.shape) == 4:
                depth = depth[0, 0]
            elif len(depth.shape) == 3:
                depth = depth[0] # H, W
                
            # Normalize depth to 0-255
            depth_min = depth.min()
            depth_max = depth.max()
            depth_normalized = (depth - depth_min) / (depth_max - depth_min)
            depth_normalized = (depth_normalized * 255).astype(np.uint8)
            
            # Resize back to original size
            depth_image = Image.fromarray(depth_normalized)
            depth_image = depth_image.resize((orig_width, orig_height), Image.BICUBIC)
            
            # Save output
            directory = os.path.dirname(image_path)
            filename = os.path.basename(image_path)
            name, ext = os.path.splitext(filename)
            output_path = os.path.join(directory, f"{name}_depth.png")
            
            depth_image.save(output_path)
            log.write(f"Success! Saved to: {output_path}\n")
            return output_path

    except Exception as e:
        import traceback
        with open(log_path, "a") as log:
            log.write(f"\nInference Failed: {str(e)}\n")
            log.write(traceback.format_exc())
        print(f"Error during inference: {e}")
        return None
