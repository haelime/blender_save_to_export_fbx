bl_info = {
    "name": "Save to FBX Export",
    "author": "Local",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "Ctrl+S",
    "description": "Save the current Blender file and export a Unity-oriented FBX next to it.",
    "category": "Import-Export",
}

import os

import bpy
from bpy.props import BoolProperty, StringProperty


_addon_keymaps = []
_disabled_save_keymaps = []


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


def _default_unsaved_blend_path():
    return os.path.join(os.path.expanduser("~"), "untitled.blend")


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
            self.filepath = _default_unsaved_blend_path()
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}

        return self.execute(context)

    def execute(self, context):
        preferences = _addon_preferences()
        blend_path = _blend_path_with_extension(self.filepath or bpy.data.filepath)
        blend_dir = os.path.dirname(blend_path)

        if blend_dir:
            os.makedirs(blend_dir, exist_ok=True)

        save_result = bpy.ops.wm.save_as_mainfile(filepath=blend_path)
        if "FINISHED" not in save_result:
            self.report({"ERROR"}, "Blender file was not saved; FBX export was skipped.")
            return {"CANCELLED"}

        if not _enable_fbx_exporter():
            self.report({"ERROR"}, "Blender FBX exporter is unavailable.")
            return {"CANCELLED"}

        fbx_path = _fbx_path_for_blend(blend_path, preferences)
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
                "bake_space_transform": False,
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
            self.report({"ERROR"}, f"FBX export failed: {exc}")
            return {"CANCELLED"}

        if "FINISHED" not in export_result:
            self.report({"ERROR"}, "FBX export did not finish.")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Saved .blend and exported FBX: {fbx_path}")
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


def _disable_existing_ctrl_s_save_keymaps():
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
                _disabled_save_keymaps.append((keymap_item, keymap_item.active))
                keymap_item.active = False


def _restore_existing_ctrl_s_save_keymaps():
    while _disabled_save_keymaps:
        keymap_item, was_active = _disabled_save_keymaps.pop()
        try:
            keymap_item.active = was_active
        except ReferenceError:
            pass


def _register_ctrl_s_keymap():
    window_manager = bpy.context.window_manager
    keyconfig = window_manager.keyconfigs.addon
    if not keyconfig:
        return

    keymap = keyconfig.keymaps.new(name="Window", space_type="EMPTY")
    keymap_item = keymap.keymap_items.new(
        SAVE_TO_FBX_EXPORT_OT_save_and_export.bl_idname,
        type="S",
        value="PRESS",
        ctrl=True,
    )
    _addon_keymaps.append((keymap, keymap_item))


def _unregister_ctrl_s_keymap():
    while _addon_keymaps:
        keymap, keymap_item = _addon_keymaps.pop()
        keymap.keymap_items.remove(keymap_item)


classes = (
    SAVE_TO_FBX_EXPORT_preferences,
    SAVE_TO_FBX_EXPORT_OT_save_and_export,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file.append(_draw_file_menu)
    _disable_existing_ctrl_s_save_keymaps()
    _register_ctrl_s_keymap()


def unregister():
    _unregister_ctrl_s_keymap()
    _restore_existing_ctrl_s_save_keymaps()
    bpy.types.TOPBAR_MT_file.remove(_draw_file_menu)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
