import bpy
import bmesh
from mathutils import Vector
from bpy.props import EnumProperty, FloatProperty
from ..utils import Mio3MTOperator, find_x_mirror_vert_pairs


class MIO3AS_OT_edge_length(Mio3MTOperator):
    bl_idname = "mesh.mio3_edge_length"
    bl_label = "Equalize Edge Lengths"
    bl_description = "Equalize Edge Lengths"
    bl_options = {"REGISTER", "UNDO"}

    mode: EnumProperty(
        name="Type",
        items=[
            ("AVERAGE", "Average", ""),
            ("LONGEST", "Max", ""),
            ("SHORTEST", "Min", ""),
            ("CUSTOM", "Custom", ""),
        ],
        default="AVERAGE",
    )

    custom_length: FloatProperty(
        name="Length",
        description="Custom edge length",
        default=0.01,
        min=0.0001,
        # max=10,
        step=0.01,
        unit="LENGTH",
    )

    smooth_factor: FloatProperty(
        name="Smooth Factor",
        description="Factor for smooth length adjustment (0-1)",
        default=0.5,
        min=0.0,
        max=1.0,
    )

    def execute(self, context):
        self.start_time()
        obj = context.active_object

        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

        selected_edges = {e for e in bm.edges if e.select}
        if obj.data.use_mirror_x:
            selected_verts = {v for e in selected_edges for v in e.verts}
            mirror_vert_pairs = find_x_mirror_vert_pairs(bm, selected_verts)

        if not selected_edges:
            self.report({"WARNING"}, "No edges selected")
            return {"CANCELLED"}

        if self.mode == "LONGEST":
            target_length = max(e.calc_length() for e in selected_edges)
        elif self.mode == "SHORTEST":
            target_length = min(e.calc_length() for e in selected_edges)
        elif self.mode == "CUSTOM":
            target_length = self.custom_length
        else:
            target_length = sum(e.calc_length() for e in selected_edges) / len(selected_edges)

        for edge in selected_edges:
            v1, v2 = edge.verts
            mid_point = (v1.co + v2.co) / 2
            direction = (v2.co - v1.co).normalized()
            v1.co = mid_point - direction * (target_length / 2)
            v2.co = mid_point + direction * (target_length / 2)

            if obj.data.use_mirror_x:
                mirror_v1 = mirror_vert_pairs.get(v1)
                mirror_v2 = mirror_vert_pairs.get(v2)
                if mirror_v1 and mirror_v2:
                    mirror_mid_point = (mirror_v1.co + mirror_v2.co) / 2
                    mirror_direction = (mirror_v2.co - mirror_v1.co).normalized()
                    mirror_v1.co = mirror_mid_point - mirror_direction * (target_length / 2)
                    mirror_v2.co = mirror_mid_point + mirror_direction * (target_length / 2)

        bmesh.update_edit_mesh(obj.data)
        self.print_time()
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        layout.use_property_split = True
        layout.prop(self, "mode", expand=True)
        row = layout.row()
        row.prop(self, "custom_length")
        row.enabled = self.mode == "CUSTOM"
        if self.mode == "SMOOTH":
            layout.prop(self, "smooth_factor")


def register():
    bpy.utils.register_class(MIO3AS_OT_edge_length)


def unregister():
    bpy.utils.unregister_class(MIO3AS_OT_edge_length)
