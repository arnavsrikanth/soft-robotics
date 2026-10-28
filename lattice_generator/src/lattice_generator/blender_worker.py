"""Executed only inside Blender, not imported by the command-line application."""

import sys
import bpy

stl_path, blend_path = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.wm.stl_import(filepath=stl_path, global_scale=1.0, use_scene_unit=False,
                      forward_axis="Y", up_axis="Z")
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 0.001
scene.unit_settings.length_unit = "MILLIMETERS"
obj = bpy.context.view_layer.objects.active
obj.name = "Lattice (coordinates in mm)"
obj["coordinate_unit"] = "mm"
obj["stl_export_note"] = "Export with global_scale=1 and use_scene_unit=False to retain millimeters."
material = bpy.data.materials.new("Lattice teal")
material.diffuse_color = (0.04, 0.40, 0.48, 1.0)
obj.data.materials.append(material)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == "VIEW_3D":
            area.spaces.active.region_3d.view_distance = max(obj.dimensions) * 2.2
            area.spaces.active.region_3d.view_location = obj.dimensions / 2
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
