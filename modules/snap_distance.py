import bpy
import bmesh
from bpy.types import Operator
from mathutils import kdtree
from bpy.props import BoolProperty, FloatProperty
from ..utils import Mio3MTOperator


class MIO3AS_OT_snap_distance(Mio3MTOperator, Operator):
    bl_idname = "mesh.mio3_snap_distance"
    bl_label = "Snap to Nearest Vertex"
    bl_description = "選択した頂点を一番近い頂点の位置にスナップします"
    bl_options = {"REGISTER", "UNDO"}

    max_distance: FloatProperty(
        name="Max Distance",
        default=0.005,
        min=0.0001,
        max=1.0,
        step=0.1,
        precision=4,
    )
    merge: BoolProperty(
        name="Merge Vertices",
        description="頂点をマージする（単一オブジェクト時のみ）",
        default=False,
    )

    def execute(self, context):
        objects = [obj for obj in context.selected_objects if obj.type == "MESH" and obj.mode == "EDIT"]
        if not objects:
            return {"CANCELLED"}

        source_verts = []
        target_verts = []
        meshes = set()

        for obj in objects:
            bm = bmesh.from_edit_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            meshes.add((obj, bm))
            for v in bm.verts:
                if v.select:
                    source_verts.append((obj, v))
                else:
                    target_verts.append((obj, v))

        if not source_verts or not target_verts:
            return {"CANCELLED"}

        kd = kdtree.KDTree(len(target_verts))
        for i, (obj, v) in enumerate(target_verts):
            kd.insert(obj.matrix_world @ v.co, i)
        kd.balance()

        move_mapping = {}
        for obj, v in source_verts:
            world_co = obj.matrix_world @ v.co
            hit_co, _, dist = kd.find(world_co)
            if dist <= self.max_distance:
                v.co = obj.matrix_world.inverted() @ hit_co
                move_mapping.setdefault(obj, []).append(v)

        if self.merge and len(objects) == 1:
            obj = objects[0]
            bm = next(bm for (o, bm) in meshes if o is obj)
            merged_vertices = move_mapping.get(obj, []) + [v for (_, v) in target_verts if _ is obj]
            if merged_vertices:
                bmesh.ops.remove_doubles(bm, verts=merged_vertices, dist=1e-6)

        for obj, bm in meshes:
            bm.normal_update()
            bmesh.update_edit_mesh(obj.data)

        return {"FINISHED"}


def menu(self, context):
    layout = self.layout
    layout.separator()
    layout.operator("mesh.mio3_snap_distance")


def register():
    bpy.utils.register_class(MIO3AS_OT_snap_distance)
    bpy.types.VIEW3D_MT_edit_mesh_merge.append(menu)


def unregister():
    bpy.utils.unregister_class(MIO3AS_OT_snap_distance)
    bpy.types.VIEW3D_MT_edit_mesh_merge.remove(menu)
