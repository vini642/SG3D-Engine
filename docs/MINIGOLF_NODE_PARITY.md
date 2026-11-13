# Mini Golf: C → Universal Nodes 2.0 parity test

This experiment uses **the user's collision-fixed 21-object Mini Golf course**, not the older 9-tile sample. Its full graphic course is unchanged; all 19 embedded OBJ/MTL/PNG assets remain in the single `.sg3d.json` file. The corrected reference script is `golf_ball.c` from the fixed project.

**IMPORTANT: This is NOT a mechanically faithful port of the complete C golf game.** It is a genuine *node-only* implementation of the subset SG3D Universal Nodes 2.0 can currently express. The project contains no attached user C scripts and no embedded `.c` file. The engine and its generated C runtime still use ordinary C and assembly, as always.

## What works in nodes now

| C behavior | Node implementation | Result |
|---|---|---|
| LEFT/RIGHT change aim | `OnKeyHeld`, `IfVariable`, `AddVariable`, `SetObjectRotation` | Implemented; 2 degrees per frame |
| A charges at 3 ticks/frame up to 85 | `OnUpdate`, `IfKeyHeld`, `MathClamp`, `SetVariable` | Implemented |
| Release A to launch (min 19 ticks) | `IfVariable charging`, `MathMax`, `MathDivide`, `MoveLocal` | Implemented, using local heading instead of 2 velocity components |
| Rolling drag (246 / 256) | `RollingDrag` reusable function (argument → `MathMultiply` → return) | Implemented; approximate 8.8 quantization |
| Stop under 2/256 | `IfVariable` | Implemented |
| Stroke counter and HUD bar | `AddVariable`, `SetUIValue` | Implemented |
| B reset / START reset | `ResetBall` reusable function; B penalizes an already-attempted hole | Implemented; start tile referenced by fixed index 19 |
| R overview camera | Variable-driven `SetCameraPosition`, `SetCameraRotation`, data-wire math | Implemented with smooth 1/4 follow |
| Aiming arrow tracks ball | `GetObjectX/Y/Z`, math, object transform nodes | Implemented |
| Cup completion | 2D XZ squared-distance data graph; only when sufficiently slow | **Approximation:** ignores height and uses 8.8 precision |
| A restart after completion | `IfVariable`, `CallFunction` | Implemented |

## What does NOT port faithfully

| Original `golf_ball.c` behavior | Why Nodes 2.0 cannot reproduce it generally yet |
|---|---|
| Discover all objects whose `golf_tile=1`, up to 64 | Node object references are fixed editor-selected indices, not dynamic IDs in a `ForEachObject` loop. `GetProperty` also needs a fixed object index. |
| Transform each ball position into **rotated tile-local coordinates** | No generic `WorldToLocalPoint`, 2D rotation, trig table, or variable-indexed transform accessor. `MoveLocal` solves movement in a heading but not arbitrary inverse transforms. |
| Determine nearest vertically compatible floor and ramp elevation | No geometry queries, tile footprint query, height sampler, or generic raycast/swept-sphere collision API. |
| Turn-specific side rails | No circle-vs-segment query or collider normal output; the scene's visual meshes are not automatically physics rail colliders. |
| Four substeps with separate X/Z wall reflections | `Repeat` exists, but it cannot call a geometry collision query that returns hit position, wall normal, and obstacle object. |
| Ramp gravity along rotated uphill direction | Missing general terrain contacts/normal and vector projection operations. |
| Fully faithful cup at correct elevation | The fallback win condition checks only horizontal proximity, because ball height never tracks the elevated tiles. |

**Consequence:** In the node ROM the ball can cross walls, fall off the visible course without being blocked, and visually roll through or below elevated ramps. These differences are intentional, not silently patched with native C. To play the accurate course, use the original collision-fixed C version.

## Stats and validation

- 142 graph nodes; 74 execution wires and 57 data wires.
- 10 shared numeric variables, 2 reusable node functions (`ResetBall`, `RollingDrag`).
- 21 scene objects, 230 imported source triangles, 5 material textures, 5 HUD elements.
- The current per-scene node limit is **256 nodes**.
- GBA ROM compiled and linked using unmodified Universal Nodes 2.0 compiler and runtime; exported scene reports **0 custom C sources**.
- PC preview smoke-test: aim, charging, release, motion, friction, B penalty/reset, START reset and overview toggle.
- Desktop node editor's old fixed-size scrollregion prevented editing the bottom half; this package includes a **UI-only** scrollbar sizing change in `editor/node_editor.py`. No new node types or runtime abilities were introduced.
- **Actual ROM behavior and frame rate in mGBA/open_agb_firm have not been verified here.**

## How to open and use

1. Extract the full engine ZIP or apply the `node_editor.py` patch to your matching Universal Nodes 2.0 engine.
2. In SG3D, open `examples/mini_golf_nodes/MiniGolf_NodesOnly.sg3d.json`, or use the separately provided single-file project.
3. Open **Node Scripts**. Use horizontal/vertical scrollbars to navigate; click **Validate graph**. Functions, camera logic, charging and rolling occupy different regions of the graph.
4. Use **Export GBA**. On the GBA: LEFT/RIGHT aim, hold/release A to shoot, B reset (penalty if you've already shot), START restart, R change camera. This is a **logic experiment**, not a substitute for the original physics-complete game.
5. Compare the node ROM and original C collision-fixed ROM with the exact same course layout.

## What to add to a UNIVERSAL engine next

Do not add a `GolfCollision` preset. To achieve C/node parity for *many* genres, the visual scripting language needs these reusable building blocks:

1. **Object references as typed values** with tag search, indexed access, and `ForEachObject`, so data-driven world traversal works.
2. **World ↔ local transforms and trigonometry**, plus dot products and normalize/length operations.
3. **General collision/geometry queries**: raycast, sphere-vs-segment, overlap and swept movement, results including contact normal and surface height.
4. **Functions with multiple typed inputs and return outputs**, local variables, mutable collections, and iteration across actual object arrays.
5. **Reusable subgraphs and object scripts** so long logic does not become a single unwieldy 142-node scene graph.
6. **Frame delta time and better debugging tools**, such as a node breakpoints/inspector and a visual simulation console.

The point of this test is to identify the missing *general-purpose primitives*, not to hardcode another game genre into SG3D.

## License

This is a private experimental package. The underlying rasterizer's upstream redistribution rights have not been verified; do not publish the complete engine as open-source until those rights are clarified.
