# SG3D Mini Golf — Collaborative Prototype ⛳

A small **editable** mini-golf game built with the normal SG3D Universal scripting API.
No golf-specific functionality is added to the engine.

## Play
- **Left / Right:** rotate the yellow aim arrow
- **Hold A:** charge the power bar; **release A:** hit the ball
- **B:** reset to the tee (penalty stroke after your first shot)
- **START:** restart the hole and clear strokes
- Get the rolling ball into the gold-ringed hole when it has slowed down.
- After finishing, press **A** to try again.

## Edit together
1. Run `RUN_EDITOR.bat` from the engine folder.
2. Open `examples/mini_golf/MiniGolf.sg3d.json`.
3. To edit the course, change `course.obj`, `obstacle.obj`, or add scene objects.
4. Change `examples/mini_golf/golf_ball.c` for mechanics. **This C source is ordinary project code**, not an engine feature.
5. Re-export GBA. `python tools/project_export.py examples/mini_golf/MiniGolf.sg3d.json --outdir generated` then `python build.py --main generated/main.c --output build/mini_golf.gba` also work.

### Where to modify gameplay
- `ROLL_FRICTION` (244): smaller = faster slowing down.
- `WALL_BOUNCE` (175): larger = bouncier walls.
- `MAX_CHARGE` (184): maximum shot strength.
- `START_X`, `START_Z`: initial tee position in 24.8 fixed point.
- Edit the **Hole and flag** object to move the target. The script looks up object 3's transform, not a hardcoded hole location.
- The ball is scene object 0; arrow is object 1; hole is object 3. If you reorder these, update the constants in the source.
- The HUD values depend on its item order: 1 strokes, 2 power, 4 win message.
- Rails/bumper are standard `solid` collision boxes (their visual OBJ matches their transforms).

### Known limitations
- The ball uses SG3D's AABB collider, not real sphere collision. Bounces can look square, especially around corners.
- No slope physics or spins; flat putting only.
- The gameplay C runs in the exported GBA ROM, **not** the desktop Play preview.
- The default camera is fixed. Add orbit/alternate camera later using ordinary scripts.
- Movement and friction are frame-based; actual golf speed varies with internal rendering FPS.
- Renderer code derives from upstream sources whose redistribution license must be clarified before public publishing.

## Collaboration ideas
Your first task could be designing **Hole 2** (different walls, obstacle, hole location), while we improve bouncing/controls and add a level-select menu. Or experiment with power, friction, colors, and a new golf ball mesh.
