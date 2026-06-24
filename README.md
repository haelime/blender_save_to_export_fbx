# Save to FBX Export

Blender add-on that keeps Blender's normal save behavior and runs an automatic FBX export after each save:

1. Save the current `.blend` file.
2. Export an `.fbx` file with the same base name.

The default FBX export is set for Unity:

- Forward: `-Z`
- Up: `Y`
- Leaf bones: disabled
- Unit scale: enabled

By default, `MyScene.blend` exports `MyScene.fbx` in the same directory.

## Install

### Blender 4.2+

Install the folder or a zip of this folder through Blender's add-on or extension install UI.

### Blender 3.6+

Install `__init__.py` or a zip of this folder through `Edit > Preferences > Add-ons > Install...`.

## Usage

Enable the add-on, then press `Ctrl+S`.

If the file has never been saved, Blender opens its normal save file picker first. After the `.blend` save completes, the `.fbx` is exported.

You can also run the action from `File > Save Blend and Export Unity FBX`.

## Preferences

The add-on preferences support:

- Export selected objects only
- Export visible objects only
- Bake animation
- Include cameras and lights
- Custom FBX export directory
