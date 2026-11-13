## Universal Nodes 2.0 Preview (2026-10-24)

- Added structured Repeat / WhileBool / BreakLoop, reusable FunctionDefinition / CallFunction / FunctionArgument / ReturnFunction.
- Added typed Boolean and vector connections, comparisons, logic operations, numeric arrays, generic movement/camera/physics operations.
- PC Play preview now interprets the new node graphs; protected by an execution budget.
- Added three generic gameplay test projects and a two-scene arrays sample.
- Preserved backward compatibility and renderer optimizations; old projects do not require migration.
- Known limitations: one numeric argument/return per reusable function, no native runtime execution of custom C in PC preview, hardware validation pending.

# Universal Scripting Rework (pre-release)

- Generic per-object compiled C component callbacks: Start, Update, Collision.
- New public `sg3d_script.h` APIs, fixed-point numeric custom properties, and visual-node property access.
- Invisible logic-only objects and a code editor/attachment UI.
- Three independently authored example controllers (explore, race, free-flight).
- Packaged source assets in portable ZIP and embedded single-file projects.
- Existing rendering and legacy presets preserved for compatibility.

# Changelog

## 1.0 RC2 — Native HUD / camera and export fixes (2026-10)

- Native-resolution sprite UI for HUD text/images; corrected packed VRAM writes.
- Corrected third-person orbit camera aim/pitch and camera-relative movement.
- Prevented duplicate input handling with legacy `MovePlayer` node graphs.
- Fixed Export GBA for projects with embedded assets.
- Added racing movement, sky panoramas, and single-file asset-embedded projects.
- Retained optimized triangle renderer (depth buckets, object culling, fused transforms, vertex cache).

## 0.12–1.0 RC1

- Added physics, scene editor, node graphs, multi-scene games, rigid animation, PCM audio, HUD/profiler.
- Improved export workflow, portable projects, validation and build instructions.

See commit history after repository initialization for future development.

### Universal Nodes 3.0 preview (2026-10-30)
- Typed object references, scene-object iteration and dynamically addressed object/property nodes.
- World/local-space transforms, generic line-circle and AABB/raycast collision queries.
- Sine/cosine, spatial vector helpers and multi-input node functions.
- Named custom events and reusable node-function libraries across projects.
- Improved desktop preview parity and new regression tests. Original rasterizer unchanged.
