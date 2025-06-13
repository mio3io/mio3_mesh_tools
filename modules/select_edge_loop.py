import bpy
import bmesh
import math
from collections import deque
from bpy.props import BoolProperty, FloatProperty, EnumProperty
from ..utils import Mio3MTOperator, deselect_all, get_bone_by_weight, get_bone_by_closest
from mathutils import kdtree, Vector
from bpy_extras import view3d_utils


# select_more_op = bpy.ops.mesh.select_more.get_rna_type()
# select_less_op = bpy.ops.mesh.select_less.get_rna_type()


def mio3_select_edge_loop_more(obj):
    bm = bmesh.from_edit_mesh(obj.data)
    selected_edges = {e for e in bm.edges if e.select}

    new_selecte_dges = set()
    for edge in selected_edges:
        for vert in edge.verts:
            connected_edges = [e for e in vert.link_edges if e != edge]
            if len(connected_edges) != 3:
                continue
            for e in connected_edges:
                if len(e.link_faces) == 2 and len(edge.link_faces) == 2:
                    shared_faces = set(e.link_faces) & set(edge.link_faces)
                    if not shared_faces and not e.select:
                        new_selecte_dges.add(e)
                        break

    for new_edge in new_selecte_dges:
        new_edge.select = True

    bmesh.update_edit_mesh(obj.data)


def mio3_select_edge_ring_more(obj):
    bm = bmesh.from_edit_mesh(obj.data)
    selected_edges = {e for e in bm.edges if e.select}

    new_selecte_dges = set()
    for edge in selected_edges:
        ring_edges = set()
        for vert in edge.verts:
            for face in vert.link_faces:
                if edge not in face.edges:
                    continue
                opposite_edge = []
                for e in face.edges:
                    if e == edge:
                        continue
                    verts_not_in_edge = e.verts[0] not in edge.verts and e.verts[1] not in edge.verts
                    if verts_not_in_edge:
                        opposite_edge.append(e)
                if opposite_edge:
                    ring_edges.add(opposite_edge[0])

        new_selecte_dges.update(ring_edges - selected_edges)

    for new_edge in new_selecte_dges:
        new_edge.select = True

    bmesh.update_edit_mesh(obj.data)


def mio3_select_edge_loop_less(obj):
    bm = bmesh.from_edit_mesh(obj.data)
    selected_edges = {e for e in bm.edges if e.select}

    deselect_edges = set()
    for edge in selected_edges:
        count_selected = sum(1 for v in edge.verts for e in v.link_edges if e.select)
        if count_selected <= 3:
            deselect_edges.add(edge)

    for edge in deselect_edges:
        edge.select = False

    active_element = bm.select_history.active
    if not (isinstance(active_element, bmesh.types.BMEdge) and active_element.select):
        bm.select_history.clear()

    bmesh.update_edit_mesh(obj.data)


def mio3_select_edge_ring_less(obj):
    bm = bmesh.from_edit_mesh(obj.data)
    selected_edges = {e for e in bm.edges if e.select}

    deselect_edges = set()
    for edge in selected_edges:
        count_selected_ring = 0
        for face in edge.link_faces:
            for face_edge in face.edges:
                if face_edge.select and face_edge != edge:
                    count_selected_ring += 1
                    break
        if count_selected_ring <= 1:
            deselect_edges.add(edge)

    for edge in deselect_edges:
        edge.select = False

    active_element = bm.select_history.active
    if not (isinstance(active_element, bmesh.types.BMEdge) and active_element.select):
        bm.select_history.clear()

    bmesh.update_edit_mesh(obj.data)


class MESH_OT_mio3_select_edges(Mio3MTOperator):
    bl_idname = "mesh.mio3_select_edges"
    bl_label = "Select Edge More/Less"
    bl_description = "Expand or reduce the selection of edge loops(rings)\n[Shift] Select All\n[Alt] Reduce by one"
    bl_options = {"REGISTER", "UNDO"}
    ring: BoolProperty(name="Edge Rings", default=True)
    mode: EnumProperty(
        name="Mode",
        items=[("MORE", "One More", ""), ("LESS", "One Less", ""), ("EXPAND", "Expand", "")],
        options={"HIDDEN", "SKIP_SAVE"},
    )

    def invoke(self, context, event):
        if event.type == "NUMPAD_PLUS":
            self.mode = "MORE"
        elif event.type == "NUMPAD_MINUS":
            self.mode = "LESS"
        else:
            self.mode = "EXPAND" if event.shift else "LESS" if event.alt else "MORE"
        return self.execute(context)

    def execute(self, context):
        obj = context.active_object
        if self.ring:
            if self.mode == "EXPAND":
                bpy.ops.mesh.loop_multi_select("EXEC_DEFAULT", ring=True)
            elif self.mode == "MORE":
                mio3_select_edge_ring_more(obj)
            elif self.mode == "LESS":
                mio3_select_edge_ring_less(obj)
        else:
            if self.mode == "EXPAND":
                bpy.ops.mesh.loop_multi_select("EXEC_DEFAULT", ring=False)
            elif self.mode == "MORE":
                mio3_select_edge_loop_more(obj)
            elif self.mode == "LESS":
                mio3_select_edge_loop_less(obj)
        return {"FINISHED"}


class MESH_OT_mio3_select_between(Mio3MTOperator):
    bl_idname = "mesh.mio3_select_between"
    bl_label = "Between Edge Rings"
    bl_description = "Select edge rings between selected edges"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        obj.update_from_editmode()

        context.tool_settings.mesh_select_mode = (False, True, False)

        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()

        selected_edges = {e for e in bm.edges if e.select}
        edge_loops = self.find_connected_edges(selected_edges)
        if len(edge_loops) < 2:
            return {"CANCELLED"}

        self.select_between_loops(edge_loops)

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}

    def find_connected_edges(self, edges):
        edge_loops = []
        ungrouped = set(edges)
        while ungrouped:
            current = ungrouped.pop()
            group = [current]
            stack = [current]
            while stack:
                edge = stack.pop()
                for vert in edge.verts:
                    for connected in vert.link_edges:
                        if connected in ungrouped:
                            ungrouped.remove(connected)
                            group.append(connected)
                            stack.append(connected)
            edge_loops.append(group)
        return edge_loops

    def select_between_loops(self, edge_loops):
        for i in range(len(edge_loops) - 1):
            start_loop = edge_loops[i]
            end_loop = edge_loops[i + 1]
            path_list = self.find_between_edges(start_loop, end_loop)
            for path in path_list:
                for edge in path:
                    edge.select = True

    def find_between_edges(self, start_loop, end_loop):
        queue = deque([(e, [e]) for e in start_loop])
        visited = set(start_loop)
        valid_paths = []

        while queue:
            current_edge, path = queue.popleft()

            if current_edge in end_loop:
                if path[0] in start_loop and path[-1] in end_loop:
                    valid_paths.append(path)
                continue

            ring_edges = set()
            for face in current_edge.link_faces:
                if len(face.edges) == 4:
                    edges = list(face.edges)
                    if current_edge in edges:
                        idx = edges.index(current_edge)
                        opposite_edge = edges[(idx + 2) % 4]
                        ring_edges.add(opposite_edge)

            for next_edge in ring_edges:
                if next_edge not in visited:
                    visited.add(next_edge)
                    queue.append((next_edge, path + [next_edge]))

        return valid_paths


class MESH_OT_mio3_select_edge_filter(Mio3MTOperator):
    bl_idname = "mesh.mio3_select_edge_filter"
    bl_label = "方向で選択を解除"
    bl_description = "方向でエッジループの選択を解除します"
    bl_options = {"REGISTER", "UNDO"}
    axis: EnumProperty(
        name="Axis",
        options={"ENUM_FLAG"},
        items=(
            ("X", "X", ""),
            ("Y", "Y", ""),
            ("Z", "Z", ""),
        ),
        default={"X", "Y"},
    )

    def execute(self, context):
        obj = context.active_object
        context.tool_settings.mesh_select_mode = (False, True, False)
        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()

        selected_edges = {e for e in bm.edges if e.select}

        deselect_all(bm)

        for edge in selected_edges:
            v1, v2 = edge.verts
            edge_vector = v2.co - v1.co
            selected = False
            max_component = max(abs(edge_vector.x), abs(edge_vector.y), abs(edge_vector.z))
            if "X" in self.axis and abs(edge_vector.x) == max_component:
                selected = True
            elif "Y" in self.axis and abs(edge_vector.y) == max_component:
                selected = True
            elif "Z" in self.axis and abs(edge_vector.z) == max_component:
                selected = True
            edge.select = selected

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}


class MESH_OT_mio3_select_edge_vector(Mio3MTOperator):
    bl_idname = "mesh.mio3_select_edge_vector"
    bl_label = "Select Edges by Vector"
    bl_description = "Select edges from the selection based on vectors of any bone"
    bl_options = {"REGISTER", "UNDO"}
    angle_threshold: FloatProperty(
        name="Threshold",
        description="ベクトルとの最大角度",
        default=60.0,
        min=0.0,
        max=90.0,
        step=100.0,
    )
    bone_type: EnumProperty(
        name="Target",
        default="WEIGHT",
        items=[
            ("BOUNDARY", "Selected Boundary", ""),
            ("WEIGHT", "Weight Bone", ""),
            ("CLOSEST", "Closest Bone", ""),
            ("SELECT", "Select Bone", ""),
        ],
    )
    vartical: BoolProperty(name="Vertical", default=False)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "MESH" and obj.mode == "EDIT"

    def execute(self, context):
        self.start_time()
        obj = context.active_object
        context.tool_settings.mesh_select_mode = (False, True, False)

        armature = obj.find_armature()

        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()

        if not armature or self.bone_type == "BOUNDARY":
            self.bone_type = "BOUNDARY"
            selected_edges = {e for e in bm.edges if e.select}
            selected_faces = {f for f in bm.faces if f.select}
            boundary_edges = {e for e in bm.edges if len({f for f in e.link_faces if f in selected_faces}) == 1}

            groups = []
            remaining = set(boundary_edges)
            while remaining:
                current_group = []
                start_edge = remaining.pop()
                current_group.append(start_edge)
                current_vert = start_edge.verts[1]

                while True:
                    next_edge = next((e for e in current_vert.link_edges if e in remaining), None)
                    if not next_edge:
                        break
                    current_group.append(next_edge)
                    remaining.remove(next_edge)
                    current_vert = next_edge.verts[0] if next_edge.verts[1] == current_vert else next_edge.verts[1]
                groups.append(current_group)

            if len(groups) == 2:
                centers = []
                for group in groups:
                    vertices = set()
                    for edge in group:
                        vertices.add(edge.verts[0])
                        vertices.add(edge.verts[1])

                    center = Vector()
                    for vert in vertices:
                        center += vert.co
                    center /= len(vertices)
                    centers.append(center)

                direction = (centers[1] - centers[0]).normalized()

                cos_threshold = math.cos(math.radians(self.angle_threshold))
                for edge in selected_edges:
                    v1, v2 = edge.verts
                    edge_vector = v2.co - v1.co
                    edge_vector.normalize()

                    if self.vartical:
                        edge.select = abs(edge_vector.dot(direction)) > cos_threshold
                    else:
                        edge.select = abs(edge_vector.dot(direction)) < cos_threshold
            else:
                self.report({"WARNING"}, "Boundary edges are not divided into two groups")
        else:
            kd = None
            bone_mapping = []
            if self.bone_type == "CLOSEST":
                bone_coords = []
                for bone in armature.data.bones:
                    if bone.use_deform and not bone.hide:
                        head_world = armature.matrix_world @ bone.head_local
                        tail_world = armature.matrix_world @ bone.tail_local
                        bone_coords.extend([head_world, tail_world])
                        bone_mapping.extend([bone, bone])
                size = len(bone_coords)
                kd = kdtree.KDTree(size)
                for i, v in enumerate(bone_coords):
                    kd.insert(v, i)
                kd.balance()

            selected_edges = {e for e in bm.edges if e.select}
            cos_threshold = math.cos(math.radians(self.angle_threshold))
            for edge in selected_edges:
                if self.bone_type == "WEIGHT":
                    bone = get_bone_by_weight(obj, armature, edge.verts)
                elif self.bone_type == "CLOSEST":
                    bone = get_bone_by_closest(obj, armature, edge.verts, bone_mapping, kd)
                else:
                    bone = armature.data.bones.active
                if not bone:
                    continue
                direction = (bone.tail_local - bone.head_local).normalized()
                v1, v2 = edge.verts
                edge_vector = v2.co - v1.co
                edge_vector.normalize()

                if self.vartical:
                    edge.select = abs(edge_vector.dot(direction)) > cos_threshold
                else:
                    edge.select = abs(edge_vector.dot(direction)) < cos_threshold

        bm.select_flush(False)
        bmesh.update_edit_mesh(obj.data)
        self.print_time()
        return {"FINISHED"}


class MESH_OT_mio3_select_edge_view(Mio3MTOperator):
    bl_idname = "mesh.mio3_select_edge_view"
    bl_label = "Select Edges by View"
    bl_description = "Select edges from the selection based on view direction"
    bl_options = {"REGISTER", "UNDO"}

    axis: EnumProperty(
        name="Axis",
        items=(
            ("X", "Horizontal", ""),
            ("Y", "Vertical", ""),
        ),
        options={"HIDDEN"},
    )
    invert: BoolProperty(name="Invert", default=False)

    def execute(self, context):
        obj = context.active_object
        context.tool_settings.mesh_select_mode = (False, True, False)

        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()

        region = context.region
        rv3d = context.space_data.region_3d
        matrix_world = obj.matrix_world

        view_forward = rv3d.view_rotation @ Vector((0, 0, -1))

        selected_edges = {e for e in bm.edges if e.select}
        deselect_all(bm)

        for edge in selected_edges:
            v1, v2 = edge.verts

            v1_co = v1.co.copy()
            v2_co = v2.co.copy()

            edge_vector = v2_co - v1_co
            edge_vector.normalize()

            v1_world = matrix_world @ v1_co
            v2_world = matrix_world @ v2_co

            edge_vector_world = (v2_world - v1_world).normalized()

            depth_component = abs(edge_vector_world.dot(view_forward))

            v1_screen = view3d_utils.location_3d_to_region_2d(region, rv3d, v1_world)
            v2_screen = view3d_utils.location_3d_to_region_2d(region, rv3d, v2_world)

            selected = False

            if v1_screen is not None and v2_screen is not None:
                edge_vector_2d = v2_screen - v1_screen
                length_2d = edge_vector_2d.length

                if length_2d > 0.001:
                    edge_vector_2d.normalize()

                    x_abs = abs(edge_vector_2d.x)
                    y_abs = abs(edge_vector_2d.y)

                    if depth_component > 0.7:
                        selected = True
                    else:
                        if self.axis == "X" and x_abs >= y_abs:
                            selected = True
                        elif self.axis == "Y" and y_abs > x_abs:
                            selected = True
                else:
                    selected = True

            if self.invert:
                edge.select = not selected
            else:
                edge.select = selected

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}


classes = [
    MESH_OT_mio3_select_edges,
    MESH_OT_mio3_select_between,
    MESH_OT_mio3_select_edge_filter,
    MESH_OT_mio3_select_edge_vector,
    MESH_OT_mio3_select_edge_view,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
