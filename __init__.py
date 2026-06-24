bl_info = {
    "name": "Save to FBX Export",
    "author": "Local",
    "version": (1, 0, 2),
    "blender": (3, 6, 0),
    "location": "Ctrl+S",
    "description": "Save the current Blender file and export a Unity-oriented FBX next to it.",
    "category": "Import-Export",
}

import os

import bpy
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, StringProperty


_is_exporting_after_save = False


def _addon_preferences():
    return bpy.context.preferences.addons[__name__].preferences


def _with_existing_export_properties(kwargs):
    properties = bpy.ops.export_scene.fbx.get_rna_type().properties
    return {key: value for key, value in kwargs.items() if key in properties}


def _enable_fbx_exporter():
    try:
        bpy.ops.export_scene.fbx.get_rna_type()
        return True
    except Exception:
        pass

    try:
        bpy.ops.preferences.addon_enable(module="io_scene_fbx")
        bpy.ops.export_scene.fbx.get_rna_type()
        return True
    except Exception:
        return False


def _blend_path_with_extension(path):
    if not path.lower().endswith(".blend"):
        return f"{path}.blend"
    return path


def _fbx_path_for_blend(blend_path, preferences):
    blend_dir = os.path.dirname(blend_path)
    base_name = os.path.splitext(os.path.basename(blend_path))[0]

    if preferences.use_custom_export_directory and preferences.export_directory:
        export_dir = bpy.path.abspath(preferences.export_directory)
    else:
        export_dir = blend_dir

    return os.path.join(export_dir, f"{base_name}.fbx")


def _object_types(preferences):
    types = {"EMPTY", "MESH", "ARMATURE"}
    if preferences.export_cameras_and_lights:
        types.update({"CAMERA", "LIGHT"})
    return types


def _export_unity_fbx(preferences, reporter=None):
    if not bpy.data.filepath:
        return False

    if not _enable_fbx_exporter():
        if reporter:
            reporter({"ERROR"}, "Blender FBX exporter is unavailable.")
        else:
            print("Save to FBX Export: Blender FBX exporter is unavailable.")
        return False

    fbx_path = _fbx_path_for_blend(bpy.data.filepath, preferences)
    fbx_dir = os.path.dirname(fbx_path)
    if fbx_dir:
        os.makedirs(fbx_dir, exist_ok=True)

    export_kwargs = _with_existing_export_properties(
        {
            "filepath": fbx_path,
            "check_existing": False,
            "use_selection": preferences.use_selection,
            "use_visible": preferences.use_visible,
            "object_types": _object_types(preferences),
            "apply_unit_scale": True,
            "apply_scale_options": "FBX_SCALE_UNITS",
            "axis_forward": "-Z",
            "axis_up": "Y",
            "use_space_transform": True,
            "bake_space_transform": preferences.apply_unity_axis_transform,
            "add_leaf_bones": False,
            "primary_bone_axis": "Y",
            "secondary_bone_axis": "X",
            "use_armature_deform_only": True,
            "bake_anim": preferences.bake_animation,
        }
    )

    try:
        export_result = bpy.ops.export_scene.fbx(**export_kwargs)
    except Exception as exc:
        if reporter:
            reporter({"ERROR"}, f"FBX export failed: {exc}")
        else:
            print(f"Save to FBX Export: FBX export failed: {exc}")
        return False

    if "FINISHED" not in export_result:
        if reporter:
            reporter({"ERROR"}, "FBX export did not finish.")
        else:
            print("Save to FBX Export: FBX export did not finish.")
        return False

    if reporter:
        reporter({"INFO"}, f"Exported Unity FBX: {fbx_path}")
    else:
        print(f"Save to FBX Export: Exported Unity FBX: {fbx_path}")
    return True


@persistent
def _export_after_save(_dummy):
    global _is_exporting_after_save

    if _is_exporting_after_save:
        return

    _is_exporting_after_save = True
    try:
        _export_unity_fbx(_addon_preferences())
    finally:
        _is_exporting_after_save = False


class SAVE_TO_FBX_EXPORT_preferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    use_selection: BoolProperty(
        name="Export selected objects only",
        description="Only export selected objects to FBX",
        default=False,
    )
    use_visible: BoolProperty(
        name="Export visible objects only",
        description="Only export visible objects to FBX",
        default=False,
    )
    bake_animation: BoolProperty(
        name="Bake animation",
        description="Bake supported scene animation into the exported FBX",
        default=True,
    )
    apply_unity_axis_transform: BoolProperty(
        name="Apply Unity axis transform",
        description="Bake Blender-to-Unity axis conversion into the FBX so Unity does not need an extra X rotation",
        default=True,
    )
    export_cameras_and_lights: BoolProperty(
        name="Export cameras and lights",
        description="Include cameras and lights in the exported FBX",
        default=False,
    )
    use_custom_export_directory: BoolProperty(
        name="Use custom export directory",
        description="Export FBX files to a custom directory instead of next to the .blend file",
        default=False,
    )
    export_directory: StringProperty(
        name="Export directory",
        description="Directory for exported FBX files. Blender-relative paths such as //Exports are supported",
        subtype="DIR_PATH",
        default="",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "use_selection")
        layout.prop(self, "use_visible")
        layout.prop(self, "bake_animation")
        layout.prop(self, "apply_unity_axis_transform")
        layout.prop(self, "export_cameras_and_lights")
        layout.prop(self, "use_custom_export_directory")

        row = layout.row()
        row.enabled = self.use_custom_export_directory
        row.prop(self, "export_directory")


class SAVE_TO_FBX_EXPORT_OT_save_and_export(bpy.types.Operator):
    bl_idname = "wm.save_blend_and_export_unity_fbx"
    bl_label = "Save Blend and Export Unity FBX"
    bl_description = "Save the current .blend file and export an FBX using Unity-friendly axes"
    bl_options = {"REGISTER"}

    filepath: StringProperty(
        name="Blend file path",
        subtype="FILE_PATH",
        default="",
    )

    def invoke(self, context, event):
        if not bpy.data.filepath:
            return bpy.ops.wm.save_as_mainfile("INVOKE_DEFAULT")

        return self.execute(context)

    def execute(self, context):
        if not self.filepath and not bpy.data.filepath:
            return bpy.ops.wm.save_as_mainfile("INVOKE_DEFAULT")

        blend_path = _blend_path_with_extension(self.filepath or bpy.data.filepath)
        blend_dir = os.path.dirname(blend_path)

        if blend_dir:
            os.makedirs(blend_dir, exist_ok=True)

        save_result = bpy.ops.wm.save_as_mainfile(filepath=blend_path)
        if "FINISHED" not in save_result:
            self.report({"ERROR"}, "Blender file was not saved; FBX export was skipped.")
            return {"CANCELLED"}

        self.report({"INFO"}, "Saved .blend. FBX export runs after save.")
        return {"FINISHED"}


def _draw_file_menu(self, context):
    self.layout.operator(SAVE_TO_FBX_EXPORT_OT_save_and_export.bl_idname, icon="EXPORT")


def _is_plain_ctrl_s(kmi):
    return (
        kmi.type == "S"
        and kmi.value == "PRESS"
        and kmi.ctrl
        and not kmi.shift
        and not kmi.alt
        and not kmi.oskey
    )


def _restore_plain_ctrl_s_save_keymaps():
    window_manager = bpy.context.window_manager
    save_operator_ids = {"wm.save_as_mainfile", "wm.save_mainfile"}

    for keyconfig in (window_manager.keyconfigs.user, window_manager.keyconfigs.default):
        if not keyconfig:
            continue

        keymap = keyconfig.keymaps.get("Window")
        if not keymap:
            continue

        for keymap_item in keymap.keymap_items:
            if keymap_item.idname in save_operator_ids and _is_plain_ctrl_s(keymap_item):
                keymap_item.active = True


def _register_save_handler():
    if _export_after_save not in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.append(_export_after_save)


def _unregister_save_handler():
    if _export_after_save in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(_export_after_save)


classes = (
    SAVE_TO_FBX_EXPORT_preferences,
    SAVE_TO_FBX_EXPORT_OT_save_and_export,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file.append(_draw_file_menu)
    _restore_plain_ctrl_s_save_keymaps()
    _register_save_handler()


def unregister():
    _unregister_save_handler()
    bpy.types.TOPBAR_MT_file.remove(_draw_file_menu)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
