import bpy
import bmesh
from mathutils import Vector
from bpy.props import IntProperty, BoolProperty
from ..utils import Mio3MTOperator, get_connected_vert_group


class OBJECT_OT_mio3_group_merge(Mio3MTOperator):
    bl_idname = "mesh.mio3_group_merg"
    bl_label = "Merge Vertices by Group"
    bl_description = "Merge selected vertices into groups of a specified size"
    bl_options = {"REGISTER", "UNDO"}

    marge_size: IntProperty(name="Size", default=2, min=2, max=10)
    offset: IntProperty(name="Offset", default=0, min=0, max=10)
    limit: BoolProperty(name="Limit Size", default=True)

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != "MESH":
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        selected_verts = [v for v in bm.verts if v.select]
        target_verts = get_connected_vert_group(selected_verts)
        ordered_verts, is_closed = self.get_ordered_verts(target_verts, self.marge_size)
        if not ordered_verts:
            return {"CANCELLED"}

        if is_closed:
            offset = self.offset % len(ordered_verts)
            ordered_verts = ordered_verts[offset:] + ordered_verts[:offset]
            limit = self.limit
        else:
            offset = 0
            limit = True

        groups = self.split_groups(ordered_verts, self.marge_size, limit)
        merge_cos = [self.get_merge_cos(group) for group in groups]

        for group, merge_co in zip(groups, merge_cos):
            valid_group = [v for v in group if v.is_valid]
            if len(valid_group) < 2:
                continue
            bmesh.ops.pointmerge(bm, verts=valid_group, merge_co=merge_co)

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}

    @staticmethod
    def get_merge_cos(group):
        n = len(group)
        if n % 2 == 1:
            center_idx = n // 2
            return group[center_idx].co
        else:
            return sum((v.co for v in group), Vector()) / n

    @staticmethod
    def split_groups(target_verts, marge_size, limit=True):
        v_len = len(target_verts)
        if not limit:
            extended_verts = target_verts + target_verts[: marge_size - 1]
            return [extended_verts[i : i + marge_size] for i in range(v_len)]

        num_full = v_len // marge_size
        remainder = v_len % marge_size
        if remainder == 0:
            return [target_verts[i * marge_size : (i + 1) * marge_size] for i in range(num_full)]

        sp_l = remainder // 2
        rp_r = remainder - sp_l
        groups = []

        idx = 0
        if sp_l > 0:
            groups.append(target_verts[: sp_l + marge_size - 1])
            idx = sp_l + marge_size - 1
        for _ in range(num_full - (1 if sp_l > 0 else 0) - (1 if rp_r > 0 else 0)):
            groups.append(target_verts[idx : idx + marge_size])
            idx += marge_size
        if rp_r > 0:
            groups.append(target_verts[idx:])
        groups = [g for g in groups if len(g) > 1]
        return groups

    @staticmethod
    def get_ordered_verts(target_verts, size):
        if len(target_verts) < 2 or len(target_verts) < size:
            return None

        end_points = [
            v for v in target_verts if sum(ov in target_verts for e in v.link_edges for ov in [e.other_vert(v)]) == 1
        ]

        if end_points:
            start_v = end_points[0]
        else:
            start_v = min(target_verts, key=lambda v: (-v.co.x, v.co.z, v.co.y))

        ordered_verts = [start_v]
        visited = {start_v}
        cur_v = start_v
        while len(ordered_verts) < len(target_verts):
            next_v = None
            for e in cur_v.link_edges:
                ov = e.other_vert(cur_v)
                if ov in target_verts and ov not in visited:
                    next_v = ov
                    break
            if next_v is None:
                break
            ordered_verts.append(next_v)
            visited.add(next_v)
            cur_v = next_v

        if len(ordered_verts) < size:
            return None
        return ordered_verts, not bool(end_points)


def register():
    bpy.utils.register_class(OBJECT_OT_mio3_group_merge)


def unregister():
    bpy.utils.unregister_class(OBJECT_OT_mio3_group_merge)
