# GameForge

Local-first Windows desktop application for creating **game voice lines and graphical assets**, designed for a laptop RTX 3060 (typically 6 GB VRAM).

## Features (initial working version)

- **Voice Studio:** Generate WAV voice dialogue using Kokoro, select voices, and save files for Godot.
- **Art Studio:** Generate PNG concept art, portraits, spritesheet references, backgrounds and UI artwork using a local Stable Diffusion model.
- **Asset Library:** Browse and open generated output files.
- Background workers keep the desktop UI responsive; progress and errors are shown in the app.
- Exports are local. No paid cloud API required. Models download on first use and occupy disk space.

## Windows installation

Install Python 3.11 (64-bit), Git, and current NVIDIA drivers. Open PowerShell in the cloned repository:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
# CUDA PyTorch wheels (adjust to supported CUDA version if necessary):
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126
pip install -r requirements.txt
python -m gameforge
```

If your environment lacks CUDA-enabled PyTorch, image generation will be extremely slow on CPU. The first voice generation may also need espeak-ng / phonemizer dependencies; consult Kokoro's platform setup instructions if prompted.

## Model selection and licensing

Kokoro's base model is Apache 2.0. GameForge defaults to `hexgrad/Kokoro-82M` through the Kokoro package. For images, the default model is `runwayml/stable-diffusion-v1-5` (a commonly used SD 1.5 checkpoint). Some model repositories require license acceptance, authentication, or may become unavailable: enter another compatible Diffusers model ID in the UI when needed. **Review each model, voice, and output license before commercial distribution.** Do not clone voices or reproduce copyrighted characters without permission.

The RTX 3060 laptop's VRAM varies; the app enables attention slicing and CPU offload for image generation to reduce memory usage, at the cost of speed. Start with 512x512 images.

## Godot workflow

Voice files export as 24 kHz WAV. PNG artwork exports into `outputs/art`. Import these files into your Godot project and attach dialogue WAVs to AudioStreamPlayer nodes. This initial version does not yet automate Godot imports, build animation-ready spritesheets, or guarantee transparent sprite backgrounds. Generated images are concept art/reference until cleaned up and cut into game-ready assets.

## Roadmap

Character voice presets and batch dialogue CSV, image-to-image/reference consistency, background removal, sprite slicing, asset tagging/search, per-project directories, and Windows packaging.
