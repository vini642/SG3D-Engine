# Getting started

## Requirements

**Editor:** Python 3.9+ with Tkinter; Pillow (`python -m pip install -r requirements.txt`). Works as a local desktop app, no network service or account required.

**Exporter:** ARM build toolchain: `devkitARM` (preferred) or compatible Clang, LLD and `llvm-objcopy`. GBA development is easiest with devkitPro's GBA toolchain. The source includes its own minimal runtime/linker; it does **not** require a Super Mario Galaxy ISO.

**Emulator:** mGBA recommended. For hardware testing, use an actual compatible console or hardware-based GBA mode.

## Start the editor

Windows: `RUN_EDITOR.bat` from an extracted project folder. Alternatively:

```sh
python -m pip install -r requirements.txt
python editor/visual_editor.py
```

Import OBJ models with UVs, save the scene to `.sg3d.json`, and use **Export GBA** for a native ROM. Never modify a generated C file as your primary project file; it gets regenerated.

## Samples

- `examples/collectathon_v12.sg3d.json` — 3D platform/HUD/collision sample.
- `examples/orbit_sky_demo.sg3d.json` — orbit camera, camera-relative movement, panoramic sky.
- `examples/racing_controller_demo.sg3d.json` — basic racing movement and checkpoint logic.
- `examples/two_worlds_v10.sg3d.json` — scene switching and node variables.

## Export from the command line

```sh
python tools/project_check.py examples/collectathon_v12.sg3d.json
python tools/project_export.py examples/collectathon_v12.sg3d.json
python build.py --main generated/main.c --output build/collectathon.gba
```

For a clean rebuild:

```sh
python build.py --clean --main generated/main.c --output build/collectathon.gba
```

## Common problems

- **Missing Pillow:** `python -m pip install Pillow`.
- **Missing `arm-none-eabi-gcc` and `llvm-objcopy`:** install devkitARM or compatible LLVM tools, then reopen the terminal.
- **No HUD text or icons:** build the current native UI runtime, not an older v0.12 ZIP; check OAM/sprite usage.
- **Scene looks different from PC:** the preview is approximate; prioritize mGBA or hardware behavior.
- **Export button does nothing:** ensure you're running the current `editor/visual_editor.py` and that saving the project succeeded.
- **Projects with textures fail after moving:** use File → Save all assets IN project, or Package portable project, so dependencies travel with the project.
