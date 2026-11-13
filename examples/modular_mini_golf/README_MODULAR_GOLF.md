# SG3D Mini Golf — Modular Course (user-supplied Blockbench tiles)

This playable example replaces the prototype's placeholder ball and course with the seven asset packs supplied by the user. The models were imported as OBJ/MTL/PNG with their original UVs and textures.

## Run / edit

1. Run `RUN_EDITOR.bat` from the SG3D-Studio root (install Python 3 and `python -m pip install Pillow`).
2. Open `examples/modular_mini_golf/MiniGolf_Modular.sg3d.json`.
3. Select objects and move/rotate tiles; **the C golf script reads tile transforms directly**, so its collision footprint follows those edits.
4. Export GBA in the editor, with devkitARM or Clang/LLD/llvm-objcopy installed. Or run `BUILD_MODULAR_MINIGOLF.bat`.
5. Custom C scripts run only in exported ROMs, not SG3D's PC Play preview.

## Controls

- LEFT/RIGHT: aim a shot (when ball is stopped)
- Hold A: charge, release A: shoot
- B: return to tee (+1 penalty stroke after shooting)
- START: restart hole and reset stroke count
- R: alternate between close follow and overview camera
- A after winning: replay

## Source models analysed

| Asset | Raw triangles | Trimmed playable triangles | What it contains |
| --- | ---: | ---: | --- |
| Tile Straight | 36 | 26 | 1×1 flat path with left/right rim walls |
| Tile Turn L | 48 | 34 | 1×1 left bend with protective rail segments |
| Tile Turn R | 48 | 34 | 1×1 right bend, opposite of left |
| Tile Start or End | 48 | 34 | 1×1 end cap (closed at local -Z), used at both ends |
| tile 22 incline | 36 | 26 | 1×1 rising 0.5 unit along local +Z (about 26.6°, despite the 22° filename) |
| tile 45 incline | 36 | 26 | 1×1 rising 1.0 unit along local +Z (45°) |
| Ball | 20 | 20 | Small white icosphere about 0.20 world units across |

The 22° tile's rise measured from *actual vertex coordinates* is 0.5 over a horizontal run of 1, or arctan(0.5)=26.6°. Its filename is preserved as the artist's label.

**Rendering:** The original full box geometry includes rail bottoms and hidden sides. The trim deletes only some hidden rail underside/exterior faces and the floor underside, reducing costly triangle work without changing the playable top and inward rail geometry. All original OBJ files and textures are also included in `SG3D_Modular_MiniGolf_Source_Assets.zip` (separate download), should you want to edit them in Blockbench.

## Example course layout

```
                 End  (x=2, z=6; height=1.5)
                  | 
              45° ramp (x=2, z=5; base=.5)
                  |
              Flat (x=2, z=4; height=.5)
                  |
              22° ramp (x=2, z=3; base=0)
                  |
  Left bend ─ Straight ─ Right bend  (z=2)
      |
   Straight (x=0, z=1)
      |
   Tee / start (x=0, z=0)
```

All nine pieces in the demonstration together, plus the ball, arrow and cup, total **302 mesh triangles**. This is under SG3D's nominal 384-entry triangle draw queue before clipping. It isn't an FPS guarantee; the 3D engine still needs hardware/emulator tests.

## Customizing

This first gameplay script is in `golf_ball.c`, attached to object 0. It is editable C using SG3D's *generic* scripting API, not a special built-in golf controller.

- Nine tiles are stored in **objects 3 through 11**, in order.
- Each tile carries numeric properties `tile_kind` and `rise`, and its model/position/rotation in the scene are read at runtime.
- `tile_kind`: 0 = straight, 1 = end cap, 2 = left, 3 = right, 4 = incline.
- `rise`: floor height change across local Z (0, 0.5 or 1.0 for supplied ramps).
- Object 2 is the cup marker and sets the target location; object 3 is the tee for ball reset.
- To add/remove a tile beyond these nine, modify `TILE_COUNT` in `golf_ball.c` and maintain the consecutive tile ordering. To *rearrange* current tiles, no script changes are needed.
- The collision region currently assumes 1×1-sized tiles. Scaling tiles in the editor requires updating the collider math as well.
- Ramps are implemented in the game script because SG3D's standard physics uses AABB boxes, not tilted mesh collision.

## Verification

- OBJ assets and material textures loaded without missing-file warnings.
- SG3D exported the project to C and linked it into a valid `.gba` ROM.
- Path continuity across all 9 centers, 160 connection samples, bounds, and ramp heights checked in Python.
- SG3D desktop preview successfully rendered 301 visible/accepted triangles from 302 source triangles.
- Full existing SG3D regression suite: 108 tests run (106 passed, 2 skipped).
- **Not yet played in mGBA or on open_agb_firm.** Shot feel and collision corner cases still need hardware feedback.

**Redistribution note:** The full SG3D source contains extracted third-party assembly code with redistribution terms not verified, so don't publish the complete engine as open-source until those permissions are settled. The project-only package contains the supplied assets and our editable golf script, not engine source.
