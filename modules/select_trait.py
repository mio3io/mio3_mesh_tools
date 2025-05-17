import bpy
import bmesh
from bpy.types import Operator
from mathutils import kdtree
from bpy.props import BoolProperty, FloatProperty, EnumProperty
from ..utils import deselect_all, Mio3MTOperator


class MESH_OT_mio3_select_half(Mio3MTOperator, Operator):
    bl_idname = "mesh.mio3_select_half"
    bl_label = "Select Mesh by Direction"
    bl_description = "[Alt] Deselect"
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

        direction_index = {"X": 0, "Y": 1, "Z": 2}[self.direction[-1]]
        matrix = obj.matrix_world if self.orientation_type == "GLOBAL" else None

        if self.direction in {"-X", "-Y", "-Z"}:
            if not self.use_center:
                center_value = -self.center_threshold
                compare = lambda x: x < center_value
            else:
                center_value = self.center_threshold
                compare = lambda x: x <= center_value
        else:
            if not self.use_center:
                center_value = self.center_threshold
                compare = lambda x: x > center_value
            else:
                center_value = -self.center_threshold
                compare = lambda x: x >= center_value

        for v in bm.verts:
            co = v.co if matrix is None else matrix @ v.co
            if compare(co[direction_index]):
                if self.extend:
                    if not self.deselect:
                        v.select = True
                else:
                    v.select = not self.deselect

        bm.select_flush_mode()
        bmesh.update_edit_mesh(obj.data)
        self.print_time()
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout

        layout.row().prop(self, "direction", text="Direction", expand=True)

        layout.use_property_decorate = False
        layout.use_property_split = True
        layout.row().prop(self, "orientation_type", text="Orientation", expand=True)
        split = layout.split(factor=0.4, align=True)
        split.use_property_split = False

        layout.prop(self, "use_center")
        row = layout.row()
        row.prop(self, "center_threshold")
        if not self.use_center:
            row.enabled = False
        layout.prop(self, "deselect")
        layout.prop(self, "extend")


class MESH_OT_mio3_select_center(Mio3MTOperator, Operator):
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
    align: BoolProperty(name="Align", default=False)
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

        should_align = self.align and not self.deselect
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
        layout.prop(self, "align")


class MESH_OT_mio3_select_mirror(Mio3MTOperator, Operator):
    bl_idname = "mesh.mio3_select_mirror"
    bl_label = "Select the Mirrored Mesh"
    bl_description = "Select the Mirrored Mesh"
    bl_options = {"REGISTER", "UNDO"}

    axis: EnumProperty(name="Axis", items=[("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", "")])
    extend: BoolProperty(name="Extend", default=True)

    def execute(self, context):
        obj = context.active_object
        if obj.type != "MESH":
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()

        kd = kdtree.KDTree(len(bm.verts))
        for i, v in enumerate(bm.verts):
            kd.insert(v.co, i)
        kd.balance()

        selected_verts = {v for v in bm.verts if v.select}

        for v in selected_verts:
            mirror_co = v.co.copy()
            mirror_co.x = -mirror_co.x
            _, index, dist = kd.find(mirror_co)
            if dist < 1e-6:
                mirror_vert = bm.verts[index]
                mirror_vert.select = True

        bm.select_flush(True)

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}


class MESH_OT_mio3_select_flat(Mio3MTOperator, Operator):
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


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
