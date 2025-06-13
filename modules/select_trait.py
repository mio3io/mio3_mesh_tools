import bpy
import bmesh
import numpy as np
from bpy.props import BoolProperty, FloatProperty, EnumProperty
from ..utils import Mio3MTOperator, deselect_all


class MESH_OT_mio3_select_half(Mio3MTOperator):
    bl_idname = "mesh.mio3_select_half"
    bl_label = "Select Mesh by Direction"
    bl_description = "Select Mesh by Direction"
    bl_options = {"REGISTER", "UNDO"}

    use_center: BoolProperty(name="Include Center", default=False)
    center_threshold: FloatProperty(
        name="Threshold",
        default=0.0001,
        min=0.0,
        max=0.1,
        step=0.01,
        precision=4,
    )
    direction: EnumProperty(
        name="Direction",
        items=[
            ("-X", "Left", ""),
            ("+X", "Right", ""),
            ("-Y", "Front", ""),
            ("+Y", "Back", ""),
            ("+Z", "Top", ""),
            ("-Z", "Bottom", ""),
        ],
        default="-X",
    )
    orientation_type: EnumProperty(
        name="Orientation",
        items=[("LOCAL", "Local", ""), ("GLOBAL", "Global", "")],
        default="LOCAL",
    )

    deselect: BoolProperty(name="Deselect", default=False)
    extend: BoolProperty(name="Extend", default=False)

    def invoke(self, context, event):
        if event.shift:
            self.extend = True
        return self.execute(context)

    def execute(self, context):
        self.start_time()
        obj = context.active_object
        mesh_select_mode = context.tool_settings.mesh_select_mode[:]
        context.tool_settings.mesh_select_mode = (True, False, False)

        bpy.ops.object.mode_set(mode="OBJECT", toggle=False)

        mesh = obj.data
        n_verts = len(mesh.vertices)
        n_edges = len(mesh.edges)
        n_polys = len(mesh.polygons)

        # 選択解除
        select_array = np.zeros(n_verts, dtype=bool)
        if not self.extend and not self.deselect:
            mesh.edges.foreach_set("select", np.zeros(n_edges, dtype=bool))
            mesh.polygons.foreach_set("select", np.zeros(n_polys, dtype=bool))

        direction_index = {"X": 0, "Y": 1, "Z": 2}[self.direction[-1]]
        matrix = obj.matrix_world if self.orientation_type == "GLOBAL" else None

        co = np.empty(n_verts * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", co)
        co = co.reshape((n_verts, 3))
        if matrix is not None:
            co = np.dot(co, np.array(matrix.to_3x3()).T) + np.array(matrix.to_translation())

        if self.direction in {"-X", "-Y", "-Z"}:
            if not self.use_center:
                mask = co[:, direction_index] < -self.center_threshold
            else:
                mask = co[:, direction_index] <= self.center_threshold
        else:
            if not self.use_center:
                mask = co[:, direction_index] > self.center_threshold
            else:
                mask = co[:, direction_index] >= -self.center_threshold

        select_array = np.zeros(n_verts, dtype=bool)
        select_array[mask] = True

        mesh.vertices.foreach_set("select", select_array)

        bpy.ops.object.mode_set(mode="EDIT", toggle=False)
        context.tool_settings.mesh_select_mode = mesh_select_mode
        self.print_time()
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.row().prop(self, "direction", text="Direction", expand=True)
        layout.use_property_decorate = False
        layout.use_property_split = True
        layout.row().prop(self, "orientation_type", text="Orientation", expand=True)
        layout.prop(self, "use_center")
        row = layout.row()
        row.prop(self, "center_threshold")
        if not self.use_center:
            row.enabled = False
        # layout.prop(self, "deselect")
        layout.prop(self, "extend")


class MESH_OT_mio3_select_center(Mio3MTOperator):
    bl_idname = "mesh.mio3_select_center"
    bl_label = "Select the Mesh Center"
    bl_description = "[Alt] Deselect"
    bl_options = {"REGISTER", "UNDO"}

    center_threshold: FloatProperty(
        name="Threshold",
        default=0.0001,
        min=0.0,
        max=0.1,
        step=0.01,
        precision=4,
    )

    axis: EnumProperty(name="Axis", items=[("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", "")])
    deselect: BoolProperty(name="Deselect", default=False)
    snap: BoolProperty(
        name="Snap vertices to zero axis", description="Snap vertices within threshold to zero axis", default=False
    )
    extend: BoolProperty(name="Extend", default=False)

    def invoke(self, context, event):
        if event.shift:
            self.extend = True
        if event.alt:
            self.deselect = True
        return self.execute(context)

    def execute(self, context):
        self.start_time()

        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        bm.select_mode = {"VERT"}

        if not self.extend and not self.deselect:
            deselect_all(bm)

        center_threshold = self.center_threshold
        axis_index = {"X": 0, "Y": 1, "Z": 2}[self.axis]

        should_align = self.snap and not self.deselect
        for v in bm.verts:
            if abs(v.co[axis_index]) <= center_threshold:
                v.select = not self.deselect
                if should_align:
                    v.co[axis_index] = 0

        bm.select_flush_mode()
        bmesh.update_edit_mesh(obj.data)
        self.print_time()
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        layout.use_property_split = True
        layout.row().prop(self, "axis", text="Axis", expand=True)
        layout.prop(self, "center_threshold")
        layout.prop(self, "deselect")
        layout.prop(self, "extend")
        layout.prop(self, "snap")


class MESH_OT_mio3_select_mirror(Mio3MTOperator):
    bl_idname = "mesh.mio3_select_mirror"
    bl_label = "Select the Mirrored Mesh"
    bl_description = "Select the Mirrored Mesh"
    bl_options = {"REGISTER", "UNDO"}

    axis: EnumProperty(
        name="Axis",
        items=[("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", "")],
        options={"ENUM_FLAG"},
        default={"X"},
    )
    extend: BoolProperty(name="Extend", default=True)

    def execute(self, context):
        bpy.ops.mesh.select_mirror(axis=self.axis, extend=self.extend)
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        layout.use_property_split = True
        layout.row().prop(self, "axis", text="Axis", expand=True)
        layout.prop(self, "extend")


class MESH_OT_mio3_select_flat(Mio3MTOperator):
    bl_idname = "mesh.mio3_select_flat"
    bl_label = "つながるフラットな面を選択"
    bl_description = "つながったフラットな面を選択します"
    bl_options = {"REGISTER", "UNDO"}

    angle_threshold: FloatProperty(
        name="許容角度差",
        default=0.174533,
        min=0.0,
        step=100.0,
        precision=1,
        unit="ROTATION",
    )

    def execute(self, context):
        obj = context.active_object
        if obj.type != "MESH":
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()

        threshold = self.angle_threshold
        seed_faces = {f for f in bm.faces if f.select}
        if not seed_faces:
            return {"CANCELLED"}

        visited = set()
        stack = list(seed_faces)

        while stack:
            face = stack.pop()
            if face in visited:
                continue
            visited.add(face)
            face.select_set(True)

            for edge in face.edges:
                for linked in edge.link_faces:
                    if linked in visited:
                        continue
                    if face.normal.angle(linked.normal) <= threshold:
                        stack.append(linked)

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}


classes = [
    MESH_OT_mio3_select_half,
    MESH_OT_mio3_select_center,
    MESH_OT_mio3_select_mirror,
    MESH_OT_mio3_select_flat,
]

translation_dict = {
    "ja_JP": {
        ("Operator", "Select Mesh by Direction"): "方向でメッシュを選択",
        ("Operator", "Select the Mesh Center"): "中心のメッシュを選択",
        ("*", "[Alt] Deselect"): "[Alt]選択解除",
        ("Operator", "Select the Mirrored Mesh"): "ミラー方向のメッシュを選択",
        ("*", "Select the Mirrored Mesh"): "ミラー方向のメッシュを選択",
        ("*", "Include Center"): "中心を含む",
        ("*", "Snap vertices to zero axis"): "頂点をゼロ軸にスナップ",
        ("*", "Snap vertices within threshold to zero axis"): "しきい値内に含まれる頂点をゼロ軸にスナップします",
    }
}


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.translations.register(__name__, translation_dict)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    bpy.app.translations.unregister(__name__)
