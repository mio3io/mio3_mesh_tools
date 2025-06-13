import bpy
import numpy as np
from bpy.types import Operator
from mathutils import Vector
from ..utils import Mio3MTOperator


class OBJECT_OT_mio3_origin_to_active(Mio3MTOperator, Operator):
    bl_idname = "mesh.mio3_origin_to_active"
    bl_label = "Origin → Active"
    bl_description = "Move the origin to the active element"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        obj = context.active_object
        if not self.is_local(obj):
            self.report({"WARNING"}, "Library cannot be edited")
            return {"CANCELLED"}
        if obj.type != "MESH":
            self.report({"WARNING"}, "Object is not a mesh")
            return {"CANCELLED"}
        return self.execute(context)

    def execute(self, context):
        obj = context.active_object

        bpy.ops.object.mode_set(mode="OBJECT")

        v_len = len(obj.data.vertices)
        co = np.empty(v_len * 3, dtype=np.float32)
        obj.data.vertices.foreach_get("co", co)
        co = co.reshape((v_len, 3))

        selected = np.array([v.select for v in obj.data.vertices])
        if not np.any(selected):
            return {"CANCELLED"}

        center = co[selected].mean(axis=0)

        delta_world = obj.matrix_world.to_3x3() @ Vector(center)
        obj.location += delta_world

        co -= center
        obj.data.vertices.foreach_set("co", co.ravel())
        obj.data.update()

        bpy.ops.object.mode_set(mode="EDIT")
        return {"FINISHED"}


def menu(self, context):
    layout = self.layout
    layout.separator()
    layout.operator("mesh.mio3_origin_to_active")


def register():
    bpy.utils.register_class(OBJECT_OT_mio3_origin_to_active)
    bpy.types.VIEW3D_MT_snap.append(menu)


def unregister():
    bpy.types.VIEW3D_MT_snap.remove(menu)
    bpy.utils.unregister_class(OBJECT_OT_mio3_origin_to_active)
