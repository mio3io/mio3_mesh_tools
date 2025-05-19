import bpy
from bpy.types import Operator
from ..utils import Mio3MTOperator
import bmesh
from mathutils import Vector
from bpy.types import Operator


class OBJECT_OT_mio3_origin_to_selection(Mio3MTOperator, Operator):
    bl_idname = "mesh.mio3_origin_to_selection"
    bl_label = "Origin → Active"
    bl_description = "原点をアクティブ要素に移動します"
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
        bm = bmesh.from_edit_mesh(obj.data)

        sel_verts = [v for v in bm.verts if v.select]
        if not sel_verts:
            return {"CANCELLED"}

        center = sum((v.co for v in sel_verts), Vector()) / len(sel_verts)

        for v in bm.verts:
            v.co -= center
        bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        delta_world = obj.matrix_world.to_3x3() @ center
        obj.location += delta_world
        obj.data.update()

        return {"FINISHED"}


def menu(self, context):
    layout = self.layout
    layout.separator()
    layout.operator("mesh.mio3_origin_to_selection")


def register():
    bpy.utils.register_class(OBJECT_OT_mio3_origin_to_selection)
    bpy.types.VIEW3D_MT_snap.append(menu)


def unregister():
    bpy.types.VIEW3D_MT_snap.remove(menu)
    bpy.utils.unregister_class(OBJECT_OT_mio3_origin_to_selection)
