# SG3D Studio — Universal Nodes 3.0 Preview

## Goal

Allow authored node graphs to examine **any object**, query spatial relationships, and reuse logic, without adding one-off Mini Golf, racing, or platformer nodes.

Node graphs still compile to native C for the GBA; the original ARM 3D renderer has not been modified.

## What's added

| Category | Nodes |
|---|---|
| Objects | `ObjectRef`, `ObjectCount`, `ForEachObject`, `LoopObject` |
| Spatial transforms | `WorldToLocal`, `LocalToWorld` |
| Collision / geometry | `CircleSegmentOverlap`, `CircleSegmentNormal`, `SphereBoxOverlap`, `RaycastBox`, `ClosestPointBox`, `GetObjectHalfExtents` |
| Mathematics | `MathSinDeg`, `MathCosDeg`, `VectorDot`, `VectorDistanceSqXZ` |
| Multi-input function calls | `FunctionArgumentB`, `FunctionArgumentVector`, `FunctionArgumentObject`, plus extra ports on `CallFunction` |
| Custom events | `OnEvent`, `EmitEvent`, `EventValue`, `EventObject` |
| Reusable logic | Project-embedded function libraries; **Import library** and **Export functions** in the node editor |

New **blue sockets** carry object references. Other sockets remain aqua (flow), orange (number), purple (Boolean) and green (vector). Type-incompatible links are rejected during export.

## Example: find every course tile

1. Add an `OnStart` node connected to `ForEachObject`.
2. Set `ForEachObject.property` to `golf_tile`.
3. Connect its **body** output to an `AddVariable` node (increment `tile_count`).
4. Connect `LoopObject`'s **blue object output** to the **object input** of `GetProperty`, `GetObjectVector`, `WorldToLocal`, or another compatible node.
5. Use the remaining nodes to perform your gameplay logic. The loop visits all objects with `golf_tile >= 1` at runtime.

An empty `property` field visits every object. Objects are iterated in the hierarchy's index order.

## Example: test a ball against a rail

Use `GetObjectVector` on the ball, then `WorldToLocal` with the current tile reference. Feed that local position into `CircleSegmentOverlap.point`. The segment endpoints are two `MakeVector` nodes representing the rail's endpoints in tile-local XZ coordinates. The output is a purple Boolean suitable for `IfBool`.

`CircleSegmentNormal` supplies a **max-component-normalized** XZ contact direction (a fast fixed-point approximation; not exact Euclidean length 1). This works well for axis-aligned rails. `SphereBoxOverlap`, `RaycastBox`, and `ClosestPointBox` use **axis-aligned physics bounds**: a rotated mesh does *not* automatically have a rotated bounding box.

`WorldToLocal`/`LocalToWorld` account for position, yaw, pitch and scale, though the desktop preview's floating-point answers may differ slightly from the GBA's 8-bit angle and 8.8 fixed-point rounding.

## Generic functions and events

`CallFunction` accepts two numbers, one vector, and one object reference. Use `FunctionArgument`, `FunctionArgumentB`, `FunctionArgumentVector`, and `FunctionArgumentObject` inside the function graph. `ReturnFunction` still returns **one numeric value**; use shared variables/arrays/properties for extra outputs.

`EmitEvent` calls any `OnEvent` node with the same `event` name, passing one numeric and one optional object payload (`EventValue` / `EventObject`). Emission is compiled inline, so recursive event chains are rejected during compile instead of creating unbounded recursion on the GBA. Note: events are synchronous, not queued.

To share functions across scenes/projects, click **Export functions** in the node editor, then **Import library** in another project. This stores the library's function graph *inside* `.sg3d.json` as `node_components`, including in portable/embedded projects. Library names and function names must be unique. Library graphs may contain reusable functions and custom-event handlers, but not standalone `OnStart`/`OnUpdate` events.

## Files / example projects

- `examples/universal_nodes3_object_queries.sg3d.json`: 3-object scene testing filtered iteration, transforms and spatial queries.
- `examples/universal_nodes3_events_library.sg3d.json`: importing a function library and emitting an event to call it.
- `examples/MathFunctions.sg3dlib.json`: a standalone reusable graph library.
- `SG3D_MiniGolf_Nodes3_Diagnostics.sg3d.json`: the user's 21-object, 18-tile golf course with 155 node blocks. Adds **diagnostic** rail and local-transform queries to the older node-only golf gameplay, without attaching C scripts.

## Limits and what remains unfinished

- The Mini Golf diagnostics project **is not a full fidelity C-to-nodes port**: it does not yet replace the existing simplified ball motion with the precise slope, multi-substep, and reflected rail collision solver. Its ball may still pass through rails or ramps.
- Function returns are still numeric only; native C remains more flexible for arbitrary pointers, dynamic memory structures, and low-level hardware operations.
- The current node editor has a 256-node/512-connection graph cap; imported libraries count toward the cap. Complex games should divide their logic into functions, scenes, and libraries.
- Box queries are AABB-based; mesh triangle raycasting, arbitrary collision meshes, physics materials and true contact normals are not implemented.
- GBA script code uses 8.8 fixed point and signed integer operations; watch for overflow in very large worlds and avoid performing dozens of expensive queries every frame on real GBA hardware.
- The native code/ROMs have been build-tested and PC preview-tested, but **GBA gameplay and performance remain unverified**.
- Because SG3D still includes extracted upstream assembly whose redistribution license is not established, distribute this full source privately until permissions are clear.

## Running tests

```sh
python -m unittest discover -p 'tests*.py'
```

The desktop GUI tests require a graphical display. To export a sample, run `python tools/project_export.py examples/universal_nodes3_object_queries.sg3d.json`, then `python build.py --main generated/main.c` with a supported GBA cross-compiler.
