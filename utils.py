import time
from bpy.types import Operator
from mathutils import Vector, kdtree

DEBUG = False


def is_local(obj):
    return obj.library is None and obj.override_library is None


def is_local_obj(obj):
    return obj is not None and obj.library is None and obj.override_library is None


class Mio3MTDebug:
    _start_time = 0

    def start_time(self):
        if DEBUG:
            self._start_time = time.time()

    def print_time(self):
        if DEBUG:
            print("Time: {}".format(time.time() - self._start_time))

    def print(self, msg):
        if DEBUG:
            print(str(msg))


# 一般的なオペレーター
class Mio3MTOperator(Mio3MTDebug):
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return cls.is_local_obj(obj)

    def invoke(self, context, event):
        obj = context.active_object
        if not self.is_local_obj(obj):
            self.report({"WARNING"}, "Library cannot be edited")
            return {"CANCELLED"}
        return self.execute(context)

    @staticmethod
    def is_local(obj):
        return obj.library is None and obj.override_library is None

    @staticmethod
    def is_local_obj(obj):
        return obj is not None and obj.library is None and obj.override_library is None


def deselect_all(bm):
    for v in bm.verts:
        v.select = False
    bm.select_flush(False)


def find_x_mirror_verts(bm, selected_verts):
    kd = kdtree.KDTree(len(bm.verts))
    for i, v in enumerate(bm.verts):
        kd.insert(v.co, i)
    kd.balance()

    mirror_verts = set()
    for v in selected_verts:
        mirror_co = v.co.copy()
        mirror_co.x = -mirror_co.x
        _, index, dist = kd.find(mirror_co)
        if dist < 0.0001:
            mirror_vert = bm.verts[index]
            if mirror_vert not in selected_verts:
                mirror_verts.add(mirror_vert)

    return mirror_verts


def get_bone_by_weight(obj, armature, selected_verts):
    max_weight = 0
    result_bone = None

    for vert in selected_verts:
        mesh_vert = obj.data.vertices[vert.index]
        for group in mesh_vert.groups:
            if group.group < len(obj.vertex_groups):
                weight = group.weight
                if weight > max_weight:
                    bone_name = obj.vertex_groups[group.group].name
                    bone = armature.data.bones.get(bone_name)
                    if bone and bone.use_deform and not bone.hide:
                        max_weight = weight
                        result_bone = bone
    return result_bone


def get_bone_by_closest(obj, armature, selected_verts, bone_mapping, kd):
    closest_bone = None
    min_distance = float("inf")
    for vert in selected_verts:
        vert_world = obj.matrix_world @ obj.data.vertices[vert.index].co
        _, idx, dist = kd.find(vert_world)
        if dist < min_distance:
            min_distance = dist
            closest_bone = bone_mapping[idx]

    return closest_bone
