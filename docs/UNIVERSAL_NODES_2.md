# Universal Node Scripting 2.0 — Preview

## The idea

SG3D's node system now compiles **generic logic** into the same native ARM C project as user-authored C scripts. There is no node interpreter on the GBA. The rendering engine, hardware UI and existing scenes are unchanged. Gameplay can be authored using reusable functions, value graphs, bounded loops, vectors, properties and numeric arrays, without selecting a "platformer" or "racing" engine mode.

## Getting started

1. Open `RUN_EDITOR.bat` and load `examples/universal_nodes2_explore.sg3d.json`.
2. Click **Node Scripts** to see connected events and actions.
3. **Aqua** = execution order; **orange** = 8.8 fixed-point number; **purple** = Boolean; **green** = 3-component vector.
4. Click a source output socket, then its destination input socket. Right-click a wire to disconnect. Use **Validate graph** before exporting.
5. Press **Play** for a rough PC preview; **Export GBA** for the actual GBA runtime.
6. In the exploration example, D-pad UP/DOWN moves along the object's local forward axis, LEFT/RIGHT rotates; A toggles the object's scale. A reusable function doubles a numeric argument and adds 2, and a bounded loop updates a variable at startup.
7. Open `examples/universal_nodes2_drive.sg3d.json` for a hand-built, node-only car: A accelerates, B reverses/brakes, LEFT/RIGHT steer. It uses only GetVariable, MathMultiply, MathClamp, SetVariable, MoveLocal, and RotateObject. There is **no DriveVehicle node** in this graph.
8. Open `examples/universal_nodes2_vectors_arrays.sg3d.json` for a working example of MakeVector, GetObjectVector, VectorAdd, VectorX/Y/Z, GetArray and SetArray. Hold A to move, press B to copy an array value into a variable.

## Structured flow

- `IfBool` chooses its true/false execution branches based on a Boolean wire.
- `Repeat` runs its **body** output up to 64 times (the count is evaluated when reached) then follows **next**. `LoopIndex` returns the zero-based iteration number as a numeric value.
- `WhileBool` re-evaluates a Boolean expression for each iteration, stopping when it is false **or** after 64 iterations.
- `BreakLoop` exits the nearest structured loop. Regular arbitrary execution-wire cycles remain disallowed so accidental infinite loops cannot lock the GBA.
- `FunctionDefinition` names a reusable graph. `CallFunction` supplies **one 8.8 numeric argument** and may store the returned value in a declared variable; `FunctionArgument` reads that argument; `ReturnFunction` returns a numeric value. Recursive calls are rejected, and graph expansion is limited.

### Example: reusable function

`FunctionDefinition: MultiplyBy2 → ReturnFunction`

Connect `FunctionArgument` to `MathMultiply.a`, set `MathMultiply.b = 2`, connect its output to `ReturnFunction.value`.

Elsewhere: `OnStart → CallFunction(name=MultiplyBy2, argument=5, result=score)`. After Start, `score` will equal 10.

## Data sockets

- Numeric: Number, MathAdd/Subtract/Multiply/Divide, MathClamp, MathAbs/Min/Max, Get/SetVariable, GetProperty, GetObjectX/Y/Z, velocities, camera position and rotation.
- Boolean: Boolean, Compare, LogicAnd/Or/Not, NonZero, GetKeyHeld, KeyPressed, IsGrounded, IfBool.
- Vector: MakeVector, GetObjectVector, GetCameraVector, VectorAdd/Subtract/Scale, VectorX/Y/Z, MoveObjectVector and SetObjectVector.
- Numeric arrays: press **Arrays...** in the node editor to create or edit arrays of 1–64 numbers. Use `GetArray`, `SetArray`, and `ArrayLength` with a numeric index. Out-of-bounds reads return zero; out-of-bounds writes are ignored.
- World access: MoveObject / MoveLocal / MoveRelative / MoveObjectVector, SetObjectPosition / SetObjectVector / SetObjectRotation / SetObjectScale, SetVelocity3D, SetCameraPosition / SetCameraRotation, FollowObject, JumpObject, LoadScene.

**Types:** Booleans can be interpreted as 0/1 numbers for backward compatibility. Number-to-Boolean requires `NonZero` or `Compare`. Vectors never implicitly turn into numbers: use VectorX/Y/Z.

## GBA details & limits

- Numbers in generated C use signed **24.8 fixed-point** (256 = 1.0); the node inspector accepts ordinary decimals.
- Vector components are three 24.8 fixed-point values. The visual editor doesn't support arbitrary user-defined structures yet.
- **Per-project limits:** up to 16 numeric arrays, 64 entries each, and 256 nodes per scene graph. Nested functions are inlined in generated C (max depth 8); no recursion, no arbitrary wire cycles.
- These are safe, bounded primitive arrays, **not** parity with C pointers, dynamic data structures or GBA register access.
- C component scripts can still do more, and the PC Preview is an approximation; its simulations aren't a hardware emulator.
- User-defined C functions cannot yet be automatically exposed as new visual node types. General reusable node functions currently take one numeric argument and one numeric return value, not arbitrary signatures.
- The existing rasterizer and optimizations were not changed by this feature update.
- Multi-scene projects share global numeric variables and arrays through the generated dispatcher; new scenes still have their own meshes, objects and scripts.

## Build from source (without editor)

```bash
python tools/project_export.py examples/universal_nodes2_drive.sg3d.json --outdir generated
python build.py --main generated/main.c --output build/nodes2_drive.gba
```

`python -m unittest discover -p 'tests*.py'` runs the regression suite. Linux GUI tests require `xvfb-run -a`.

## Release status

This is a feature-development preview, not a promise of complete node/C parity or hardware-verified performance. Also, the upstream rasterizer's licensing/redistribution permissions still need resolution before publishing complete source publicly. See `LICENSE_STATUS.md`.
