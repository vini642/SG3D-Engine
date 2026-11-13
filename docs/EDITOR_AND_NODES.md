# Editor and game features

SG3D Studio offers:

- **Hierarchy / inspector:** add, import, duplicate or delete objects; configure transforms, textures, raster modes, physics and character facing.
- **Scenes:** add/rename/switch scenes; set a startup scene; global variables can persist across transitions.
- **Node scripts:** event-flow wires and numeric/data wires. Use input events, math, variable reads/writes, object/camera actions, collision events, audio and animations.
- **Camera / Sky:** enable third-person orbit with camera-relative walking, or a racing-follow camera; choose a panoramic PNG background.
- **Vehicle scripting:** use the racing-controller preset as a starting graph rather than hand-authoring steering/drag behavior.
- **Animations:** bake simple object position/rotation/scale keyframes into tables during export.
- **HUD:** overlay text, counters, progress bars, icons, rectangles and simple dialogue; native GBA OBJ sprites are used for sharp text/images.
- **Asset sharing:** package OBJ/MTL/PNG/WAV dependencies into a portable ZIP, or embed assets into one `.sg3d.json` project.

## Known design limits

The runtime has a small CPU and memory budget. Models use a low-poly format and approximately 120×80 internal 3D pixels. Scene collision is axis-aligned boxes. Different gameplay genres can be prototyped with nodes, but there is no general-purpose visual programming IDE equivalent to large desktop game engines.

## Suggested workflow

Start with a cube, write a short On Update graph, test PC Play, then export to mGBA. Enable the profiler while testing a complex level, and split static scenery into independently cullable objects.
