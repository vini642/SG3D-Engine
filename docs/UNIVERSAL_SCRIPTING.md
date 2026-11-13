# SG3D Universal Scripting — Preview

This preview makes game logic **user-authored** rather than limited to SG3D's built-in platformer and racing behaviors. The graphics renderer, asset import, physics, HUD, animation, sound, and previous node graphs remain available.

## What changed

- **C scripts are components**: any object can attach up to eight `.c` files. A single script may be reused on many objects. The filename defines its callback names.
- **Empty objects** have no mesh or texture and can be used for scene managers, cameras, timers, AI, or collision sensors.
- **Object properties**: up to 16 numeric name/value pairs per object, stored in signed 24.8 fixed-point units. Both C and visual nodes can read and write them.
- **Nodes**: `GetProperty` and `SetProperty` are added; all older node types remain for compatibility.
- **Portable/embedded projects**: `.c` assets are included alongside meshes, textures, sound, and skyboxes.

## Quick start (no genre presets)

1. Run `RUN_EDITOR.bat`, and open `examples/universal_three_controllers.sg3d.json`.
2. Select an object in the hierarchy, then click **C Scripts** (or **Custom properties + C scripts...** in the Inspector).
3. Choose **New .c** to generate the callbacks, **Attach .c** to reuse a script, **Edit code** to edit it, and write numeric values in **Properties**. `C Scripts` attaches components only to the selected object.
4. Save your `.sg3d.json` project, then **Export GBA**. Requires devkitARM or LLVM tools compatible with the GBA toolchain.
5. To share: use **Save all assets IN project...** or **Package portable project...**. Both include your custom C sources.

You can also build from the terminal:

```bash
python tools/project_export.py examples/universal_three_controllers.sg3d.json
python build.py --main generated/main.c --output build/universal_demo.gba
```

### Test ROM controls

The demo contains three separate scenes. Press **SELECT** to cycle to the next scene:

- **Explore**: D-pad camera-relative movement; A to jump.
- **Race**: A throttle, B reverse/brake, left/right steer; speed, acceleration and maximum speed live in object properties.
- **Fly**: L/R yaw, up/down pitch, A/B ascend/descend, forward travel every update.

Every behavior is implemented by the example `.c` files, not by a special mode inside the SG3D runtime. The primitive models are placeholders; you can replace them with your own OBJ assets.

## Script naming and callbacks

If the attached source file is `hover_vehicle.c`, it must define **all three** functions:

```c
#include "sg3d_script.h"
void hover_vehicle_Start(SG3DScriptContext *ctx, unsigned self) { }
void hover_vehicle_Update(SG3DScriptContext *ctx, unsigned self) { }
void hover_vehicle_Collision(SG3DScriptContext *ctx, unsigned self, unsigned other) { }
```

`self` is the owning object index in the current scene. `other` is the object index that has just begun touching it. Unused functions can have empty bodies. Filenames must use only C identifier characters (`my_script.c`); filenames must be unique across scripts used in a project. One source is compiled once and can be attached to multiple objects.

Callbacks execute in this order: start callbacks on scene entry, then update callbacks before the existing visual-node `OnUpdate` logic and physics; collision-begin callbacks after physics. Node graph collision events also continue to work. Properties reset when a scene is entered. Global numeric variables already supported by visual nodes persist between scenes.

## API reference

See [`engine/sg3d_script.h`](../engine/sg3d_script.h). Selected functions:

| Function | Purpose |
|---|---|
| `sg3d_key_held(ctx, SG3D_KEY_A)` | Current held input |
| `sg3d_key_pressed(ctx, SG3D_KEY_A)` | Newly pressed this frame |
| `sg3d_object(ctx, index)` | Pointer to the object's transform |
| `sg3d_body(ctx, index)` | Pointer to physics state/velocity |
| `sg3d_move_object(ctx, index, x, y, z)` | Collision-aware world displacement |
| `sg3d_move_local(ctx, index, side, forward)` | Displacement relative to object's yaw |
| `sg3d_move_camera_space(ctx, index, side, forward)` | Displacement relative to camera yaw |
| `sg3d_rotate_object(ctx, index, yaw, pitch)` | Rotation in 8-bit angle units |
| `sg3d_set_velocity(ctx, index, x, y, z)` | Set physics velocity |
| `sg3d_jump_object(ctx, index, impulse)` | Jump if grounded |
| `sg3d_is_grounded(ctx, index)` | Ground contact |
| `sg3d_is_touching(ctx, a, b)` | Current touching state |
| `sg3d_get_property(ctx, index, "speed")` | Fixed-point custom value |
| `sg3d_set_property(ctx, index, "speed", value)` | Update a declared property |
| `sg3d_load_scene(ctx, scene_index)` | Request a scene switch (multi-scene only) |

`ctx->camera` provides editable camera `x`, `y`, `z`, `yaw`, and `pitch`. You may also access an object's transform via `sg3d_object`, and the physics body through `sg3d_body`. Custom C uses the same underlying data as built-in nodes.

### Fixed-point rules

All positions, movement deltas, velocity, and custom properties use signed **24.8 fixed point**, meaning `256 == 1.0` world unit; `SG3D_UNIT(2)` equals 512. `SG3D_ANGLE(90)` returns 64 (quarter turn). Avoid costly or unavailable floating-point/libc functions inside GBA scripts. Bare-metal C code is compiled into the ROM using the project's freestanding ARM build.

### Current limits and compatibility

- Desktop **Play** mode simulates only existing node/physics logic; it does **not** execute arbitrary project C sources. To test custom C behavior, export and run the GBA ROM in mGBA or hardware.
- Existing built-in platformer/racing presets are retained solely for old-project compatibility. You can write entirely custom controllers instead.
- Currently up to eight attached C sources and 16 custom numeric properties per object. Custom properties are not arbitrary nested tables or strings.
- The node editor still has its prior 128-node/cycle restrictions. Native C scripts can use ordinary C control flow (loops, functions, state) subject to the GBA's memory and build-system limitations.
- Native source inclusion assumes self-contained `.c` files with `sg3d_script.h` and installed engine headers. Automatically collecting additional C headers/libraries and executing custom C in desktop preview remain future work.
- The 3D rasterizer, GBA hardware limits, AABB physics limitations, and licensing status of upstream extracted code are **unchanged**.

**License:** This preview contains code derived from upstream project `smg-gba` with unverified redistribution rights. Keep the full source in a **private** repository until permission is clarified. See `LICENSE_STATUS.md`.
