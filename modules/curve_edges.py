import bpy
import gpu
import blf
import bmesh
from mathutils import Vector, kdtree
from bpy.types import Operator, Panel, PropertyGroup, SpaceView3D
from bpy.props import IntProperty, PointerProperty
from gpu_extras.batch import batch_for_shader
from bpy_extras import view3d_utils
from bpy.app.translations import pgettext_iface as tt_iface
from .curve_edges_utils import (
    find_edge_loops,
    order_vertices,
    calc_spline_points,
    calc_vertex_params,
    calc_control_points,
    is_closed_loop,
    redraw_3d_views,
    PASS_THROUGH_KEY,
)


text_lines = [
    "🐻Tips",
    "[Ctrl+Wheel][Shift+Wheel] Change Control Points",
    "[Ctrl+Click] Add or delete [Del] Delete Control Points",
    "[R] Reset Deform [M] Mirror toggle [H] Hide Spline",
]


def get_guide_lines(base_x=50, base_y=50, line_height=26):
    return [(base_x, base_y + i * line_height, tt_iface(text)) for i, text in enumerate(reversed(text_lines))]


class MESH_OT_mio3_curve_edges_base(Operator):
    bl_label = "Curve Edges"
    bl_options = {"REGISTER", "UNDO"}

    def update_points(self, context):
        context.window_manager.mio3ce.control_num = self.points

    points: IntProperty(name="Points", default=2, min=2, max=30, update=update_points, options={"HIDDEN"})

    _matrix_world = None

    _segments = 10  # 分割数
    _hit_radius = 16  # クリックしたときのヒット半径

    _x_mirror = False
    _verts_mirror_map = {}  # ミラー頂点マッピング
    _point_mirror_map = {}  # ミラー制御点マッピング

    _active_spline_index = -1
    _active_point_index = -1
    _spline_datas = []
    _selected_points = []  # [(spline_idx, point_idx)]
    _axis = None  # 軸制約

    _drag_start_mouse = None
    _drag_end_mouse = None
    _is_drag_mode = False  # ドラッグ移動中
    _is_grab_mode = False  # Gキー移動中
    _is_rect_mode = False  # 矩形選択
    _mouse_offset = None

    _skip_finish = False  # 確定をスキップするフラグ
    _store_points = []

    _col_point_default = (0.36, 0.79, 1.00, 1.0)
    _col_point_selected = (0.8, 0.8, 0.8, 1.0)
    _col_point_active = (0.8, 0.8, 0.8, 1.0)
    _col_spline = (0.0, 0.7, 1.0, 1.0)  # デフォルトのスプライン
    _col_active_spline = (0.0, 0.7, 1.0, 1.0)  # アクティブなスプライン

    _handle_3d = None
    _handle_2d = None

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == "MESH" and obj.mode == "EDIT"

    @classmethod
    def remove_handler(cls):
        if cls._handle_3d:
            SpaceView3D.draw_handler_remove(cls._handle_3d, "WINDOW")
            cls._handle_3d = None
        if cls._handle_2d:
            SpaceView3D.draw_handler_remove(cls._handle_2d, "WINDOW")
            cls._handle_2d = None

    def create_spline_mirror_map(self, spline_datas):
        """ミラー制御点マッピングをローカル座標で作成する"""
        matrix_world = self._matrix_world
        matrix_world_inv = matrix_world.inverted()
        self._point_mirror_map = {}
        for spline_idx, spline in enumerate(spline_datas):
            control_points = spline["control_points"]
            point_map = {}
            for i, point in enumerate(control_points):
                point_local = matrix_world_inv @ Vector(point)
                mirror_l = Vector((-point_local.x, point_local.y, point_local.z))
                mirror_w = matrix_world @ mirror_l
                for j, other_w in enumerate(control_points):
                    if i != j and (Vector(other_w) - mirror_w).length < 1e-4:
                        point_map[i] = j
                        break
            self._point_mirror_map[spline_idx] = point_map

    def create_spline_loops(self, context):
        """頂点からスプライン情報を作成する"""
        spline_datas = []
        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()

        if not (selected_verts := [v for v in bm.verts if v.select]):
            return None

        if not (edge_loops := find_edge_loops(selected_verts)):
            return None

        world_matrix = self._matrix_world
        for loop in edge_loops:
            ordered_verts = order_vertices(loop)
            if not ordered_verts or len(ordered_verts) < 3:
                continue

            is_closed = is_closed_loop(ordered_verts)
            world_co = [world_matrix @ v.co for v in ordered_verts]
            control_points = calc_control_points(world_co, self.points, is_closed)
            spline_points = calc_spline_points(control_points, self._segments, is_closed)
            vertex_params = calc_vertex_params(world_co, spline_points, is_closed)
            spline_datas.append(
                {
                    "vertex_params": vertex_params,
                    "local_co": [v.co.copy() for v in ordered_verts],
                    "vert_indices": [v.index for v in ordered_verts],
                    "control_points": control_points,
                    "spline_points": spline_points,
                    "is_closed": is_closed,
                }
            )

        # Xミラー用マッピング
        if self._x_mirror:
            self.create_spline_mirror_map(spline_datas)
            self._verts_mirror_map = {}
            kd = kdtree.KDTree(len(bm.verts))
            for i, v in enumerate(bm.verts):
                kd.insert(v.co, i)
            kd.balance()
            for v in selected_verts:
                mirror_co = Vector((-v.co.x, v.co.y, v.co.z))
                co_find = kd.find(mirror_co)
                if co_find[2] < 1e-4:
                    self._verts_mirror_map[v.index] = bm.verts[co_find[1]].index

        self._spline_datas = spline_datas
        return len(spline_datas)

    def update_vertices(self, context):
        """スプラインに沿って頂点位置を更新する"""
        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        matrix_world_inv = self._matrix_world.inverted()

        processed = set()
        for spline in self._spline_datas:
            spline_points = spline["spline_points"]
            vertex_params = spline["vertex_params"]
            vertex_indices = spline["vert_indices"]

            cumulative_lengths = [0.0]
            for p_prev, p_next in zip(spline_points[:-1], spline_points[1:]):
                seg_len = (Vector(p_next) - Vector(p_prev)).length
                cumulative_lengths.append(cumulative_lengths[-1] + seg_len)
            total_length = cumulative_lengths[-1] or 1e-9

            for param, vert_idx in zip(vertex_params, vertex_indices):
                if vert_idx in processed:
                    continue

                target_len = total_length * param["t"]

                segment_idx = 0
                for i in range(1, len(cumulative_lengths)):
                    if target_len <= cumulative_lengths[i]:
                        segment_idx = i - 1
                        break

                p1_len = cumulative_lengths[segment_idx]
                p2_len = cumulative_lengths[segment_idx + 1]
                segment_len = p2_len - p1_len or 1e-9
                local_t = (target_len - p1_len) / segment_len

                p1 = Vector(spline_points[segment_idx])
                p2 = Vector(spline_points[segment_idx + 1])
                new_world_pos = p1.lerp(p2, local_t)

                bm.verts[vert_idx].co = matrix_world_inv @ new_world_pos
                processed.add(vert_idx)

            if self._x_mirror:
                for vi, vert_index in enumerate(spline["vert_indices"]):
                    if vert_index in self._verts_mirror_map:
                        mirror_idx = self._verts_mirror_map[vert_index]
                        if mirror_idx not in processed:
                            mirror_vert = bm.verts[mirror_idx]
                            real_vert = bm.verts[vert_index]
                            mirror_vert.co = Vector((-real_vert.co.x, real_vert.co.y, real_vert.co.z))
                            processed.add(mirror_idx)

        bmesh.update_edit_mesh(obj.data)

    def move_control_point(self, context, mouse_pos, axis=None):
        """制御点を移動する"""
        if self._active_spline_index < 0 or self._active_point_index < 0:
            return

        region, rv3d = context.region, context.region_data
        matrix_world = self._matrix_world
        matrix_world_inv = matrix_world.inverted()

        active_orig_w = Vector(self._store_points[self._active_spline_index][self._active_point_index])
        view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse_pos)
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse_pos)
        denom = view_vector.dot(view_vector) or 1e-9
        t = (active_orig_w - ray_origin).dot(view_vector) / denom
        proj_w = ray_origin + view_vector * t

        active_orig_l = matrix_world_inv @ active_orig_w
        proj_l = matrix_world_inv @ proj_w
        offset_l = proj_l - active_orig_l

        if axis == "X":
            offset_l.y = offset_l.z = 0
        elif axis == "Y":
            offset_l.x = offset_l.z = 0
        elif axis == "Z":
            offset_l.x = offset_l.y = 0

        updated_splines = set()
        for s_idx, p_idx in self._selected_points:
            orig_w = Vector(self._store_points[s_idx][p_idx])
            orig_l = matrix_world_inv @ orig_w
            new_l = orig_l + offset_l
            new_w = matrix_world @ new_l
            self._spline_datas[s_idx]["control_points"][p_idx] = new_w.to_tuple()
            updated_splines.add(s_idx)

            if self._x_mirror:
                mirror_idx = self._point_mirror_map.get(s_idx, {}).get(p_idx)
                if mirror_idx is not None:
                    mirror_l = Vector((-new_l.x, new_l.y, new_l.z))
                    self._spline_datas[s_idx]["control_points"][mirror_idx] = (matrix_world @ mirror_l).to_tuple()

        for s_idx in updated_splines:
            sd = self._spline_datas[s_idx]
            sd["spline_points"] = calc_spline_points(sd["control_points"], self._segments, sd["is_closed"])

        self.update_vertices(context)

    def rebuild_spline(self, context, new_num):
        """指定ポイントでスプラインを再構築"""
        self.end_move_mode()
        self.points = new_num

        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        world_matrix = self._matrix_world

        self._selected_points = []
        self._active_point_index = -1

        for spline_idx, spline in enumerate(self._spline_datas):
            is_closed = spline["is_closed"]
            world_co = [world_matrix @ bm.verts[i].co for i in spline["vert_indices"]]
            spline["control_points"] = calc_control_points(world_co, new_num, is_closed)
            spline["spline_points"] = calc_spline_points(spline["control_points"], self._segments, is_closed)
            spline["vertex_params"] = calc_vertex_params(world_co, spline["spline_points"], is_closed)

        self.create_spline_mirror_map(self._spline_datas)
        self.update_vertices(context)

    def add_control_point(self, context, mouse_pos):
        """制御点を追加する"""
        region, rv3d = context.region, context.region_data
        spline_idx, segment_idx, segment_t = self.get_closest_spline(context, mouse_pos, self._hit_radius)
        if spline_idx is None:
            return False

        spline = self._spline_datas[spline_idx]
        control_points = spline["control_points"]
        spline_points = spline["spline_points"]
        is_closed = spline["is_closed"]

        p_new = Vector(spline_points[segment_idx]).lerp(Vector(spline_points[segment_idx + 1]), segment_t)

        matrix_world = self._matrix_world
        matrix_world_inv = matrix_world.inverted()
        p_new_local = matrix_world_inv @ p_new
        p_mirror_local = Vector((-p_new_local.x, p_new_local.y, p_new_local.z))
        p_mirror = matrix_world @ p_mirror_local

        def insert(cp_list, new_pt, closed_flag):
            if any((Vector(pt) - new_pt).length < 1e-4 for pt in cp_list):
                return None
            best, ins_idx = float("inf"), 0
            for j in range(len(cp_list)):
                a = Vector(cp_list[j])
                b = Vector(cp_list[(j + 1) % len(cp_list)] if closed_flag else cp_list[min(j + 1, len(cp_list) - 1)])
                ab = b - a
                t = 0 if ab.length_squared == 0 else max(0.0, min(1.0, (new_pt - a).dot(ab) / ab.length_squared))
                dist = (new_pt - (a + ab * t)).length
                if dist < best:
                    best, ins_idx = dist, j + 1
            cp_list.insert(ins_idx, new_pt.to_tuple())
            return ins_idx

        ins_idx_original = insert(control_points, p_new, is_closed)

        # ミラー側
        if self._x_mirror and ins_idx_original is not None:
            mouse_mirror_2d = view3d_utils.location_3d_to_region_2d(region, rv3d, p_mirror)
            spline_idx_m, _, _ = self.get_closest_spline(context, mouse_mirror_2d, self._hit_radius, spline_idx)
            if spline_idx_m == spline_idx:
                insert(control_points, p_mirror, is_closed)

        spline["spline_points"] = calc_spline_points(control_points, self._segments, is_closed)

        new_idx = None
        for idx, pt in enumerate(control_points):
            if (Vector(pt) - p_new).length_squared < 1e-6:
                new_idx = idx
                break
        if new_idx is None:
            new_idx = ins_idx_original

        self._selected_points = [(spline_idx, new_idx)]
        self._active_spline_index = spline_idx
        self._active_point_index = new_idx

        self.create_spline_mirror_map(self._spline_datas)
        self.update_vertices(context)
        return True

    def remove_control_points(self, context, points):
        """制御点を削除する"""
        points_to_remove = {}
        for spline_idx, point_idx in points:
            if spline_idx not in points_to_remove:
                points_to_remove[spline_idx] = set()
            points_to_remove[spline_idx].add(point_idx)
            if self._x_mirror:
                point_map = self._point_mirror_map.get(spline_idx, {})
                mirror_idx = point_map.get(point_idx)
                if mirror_idx is not None:
                    points_to_remove[spline_idx].add(mirror_idx)

        for spline_idx, point_indices in points_to_remove.items():
            spline = self._spline_datas[spline_idx]
            control_points = spline["control_points"]
            is_closed = spline["is_closed"]
            for point_idx in sorted(point_indices, reverse=True):
                if not is_closed:
                    if point_idx == 0 or point_idx == len(control_points) - 1:
                        continue
                if len(control_points) > 2 and 0 <= point_idx < len(control_points):
                    control_points.pop(point_idx)

        for spline in self._spline_datas:
            spline["spline_points"] = calc_spline_points(spline["control_points"], self._segments, spline["is_closed"])

        self._selected_points = []
        self._active_point_index = -1
        self._active_spline_index = -1

        self.create_spline_mirror_map(self._spline_datas)
        self.update_vertices(context)

    def toggle_display_spline(self, context):
        """スプラインの表示/非表示を切り替える"""
        props = context.window_manager.mio3ce
        props.hide_spline = not props.hide_spline
        redraw_3d_views(context)

    def reset_deform(self, context):
        """制御点を元の位置に戻す"""
        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)

        control_num = context.window_manager.mio3ce.control_num
        use_mirror = self._x_mirror
        mirror_map = self._verts_mirror_map
        world_matrix = self._matrix_world

        for spline in self._spline_datas:
            local_co = spline["local_co"]
            world_co = [world_matrix @ co for co in local_co]
            vert_indices = spline["vert_indices"]
            is_closed = spline["is_closed"]
            spline["control_points"] = calc_control_points(world_co, control_num, is_closed)
            spline["spline_points"] = calc_spline_points(spline["control_points"], self._segments, is_closed)
            spline["vertex_params"] = calc_vertex_params(world_co, spline["spline_points"], is_closed)

            for i, vert_index in enumerate(vert_indices):
                if i >= len(local_co) or vert_index >= len(bm.verts):
                    continue
                original = local_co[i]
                bm.verts[vert_index].co = original
                # Xミラー
                if use_mirror and vert_index in mirror_map:
                    mirror_idx = mirror_map[vert_index]
                    if mirror_idx < len(bm.verts):
                        bm.verts[mirror_idx].co = Vector((-original.x, original.y, original.z))

        bmesh.update_edit_mesh(obj.data)
        redraw_3d_views(context)

    def select_points_rect(self, context, shift=False):
        """ドラッグ矩形内の制御点を選択"""
        if not self._spline_datas or not self._drag_start_mouse or not self._drag_end_mouse:
            return

        x1, y1 = self._drag_start_mouse
        x2, y2 = self._drag_end_mouse
        xmin, xmax = sorted((x1, x2))
        ymin, ymax = sorted((y1, y2))

        region, rv3d = context.region, context.region_data

        selected = []

        for spline_idx, spline in enumerate(self._spline_datas):
            for point_idx, point in enumerate(spline["control_points"]):
                screen_co = view3d_utils.location_3d_to_region_2d(region, rv3d, point)
                if screen_co:
                    x, y = screen_co
                    if xmin <= x <= xmax and ymin <= y <= ymax:
                        selected.append((spline_idx, point_idx))

        if selected:
            if shift:
                current_set = set(self._selected_points)
                current_set.update(selected)
                self._selected_points = list(current_set)
            else:
                self._selected_points = selected

            if len(selected) == 1 and not shift:
                self._active_spline_index, self._active_point_index = selected[0]
            else:
                self._active_point_index = -1
        elif not shift:
            self._selected_points = []
            self._active_spline_index = -1
            self._active_point_index = -1

        redraw_3d_views(context)

    def get_closest_spline(self, context, mouse_pos, hit_radius, seatch_spline_idx=None):
        """マウス位置に最も近いスプラインを見つける"""
        region, rv3d = context.region, context.region_data
        search_point_vec = Vector(mouse_pos)

        min_dist = float("inf")
        spline_idx = segment_idx = None
        segment_t = 0.0

        for s_idx, spline in enumerate(self._spline_datas):
            if seatch_spline_idx is not None and s_idx != seatch_spline_idx:
                continue
            spline_points = spline["spline_points"]
            for i in range(len(spline_points) - 1):
                p1_2d = view3d_utils.location_3d_to_region_2d(region, rv3d, spline_points[i])
                p2_2d = view3d_utils.location_3d_to_region_2d(region, rv3d, spline_points[i + 1])
                if not p1_2d or not p2_2d:
                    continue
                seg_vec = p2_2d - p1_2d
                seg_len = seg_vec.length
                if seg_len == 0:
                    continue
                dir_vec = seg_vec / seg_len
                projection = (search_point_vec - p1_2d).dot(dir_vec)
                t = max(0.0, min(1.0, projection / seg_len))
                dist = (search_point_vec - (p1_2d + dir_vec * seg_len * t)).length
                if dist < min_dist:
                    min_dist = dist
                    spline_idx, segment_idx, segment_t = s_idx, i, t

        if spline_idx is None or min_dist >= hit_radius:
            return None, None, None

        return spline_idx, segment_idx, segment_t

    def get_closest_control_point(self, context, mouse_pos):
        """マウス位置に最も近い制御点を見つける"""
        region, rv3d = context.region, context.region_data

        search_radius_sq = self._hit_radius**2
        closest_dist = float("inf")
        closest_spline_index = -1
        closest_point_index = -1

        for spline_idx, spline in enumerate(self._spline_datas):
            for i, point in enumerate(spline["control_points"]):
                screen_co = view3d_utils.location_3d_to_region_2d(region, rv3d, point)
                if screen_co:
                    dist_sq = (screen_co[0] - mouse_pos[0]) ** 2 + (screen_co[1] - mouse_pos[1]) ** 2
                    if dist_sq < closest_dist and dist_sq < search_radius_sq:
                        closest_dist = dist_sq
                        closest_spline_index = spline_idx
                        closest_point_index = i

        return closest_spline_index, closest_point_index

    def finish_deform(self, context):
        self.__class__.remove_handler()
        self.end_move_mode("finish_deform")
        redraw_3d_views(context)
        self.report({"INFO"}, "Confirmed")
        return {"FINISHED"}

    def cancel_deform(self, context):
        self.__class__.remove_handler()
        redraw_3d_views(context)
        return {"CANCELLED"}

    @staticmethod
    def draw_3d(self, context, props):
        if props.hide_spline:
            return
        spline_shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        points_shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        for i, spline in enumerate(self._spline_datas):
            is_active_spline = i == self._active_spline_index
            # スプラインの描画
            spline_color = self._col_active_spline if is_active_spline else self._col_spline
            if spline["is_closed"]:
                batch = batch_for_shader(spline_shader, "LINE_LOOP", {"pos": spline["spline_points"]})
            else:
                batch = batch_for_shader(spline_shader, "LINE_STRIP", {"pos": spline["spline_points"]})
            gpu.state.line_width_set(2)
            spline_shader.bind()
            spline_shader.uniform_float("color", spline_color)
            batch.draw(spline_shader)
            # 制御点の描画
            for j, point in enumerate(spline["control_points"]):
                is_active = j == self._active_point_index and is_active_spline
                is_selected = (i, j) in self._selected_points
                if is_active:
                    color = self._col_point_active
                elif is_selected:
                    color = self._col_point_selected
                else:
                    color = self._col_point_default
                points_batch = batch_for_shader(points_shader, "POINTS", {"pos": [point]})
                gpu.state.point_size_set(10 if is_active else (8 if is_selected else 6))
                points_shader.bind()
                points_shader.uniform_float("color", color)
                points_batch.draw(points_shader)

        gpu.state.point_size_set(1.0)
        gpu.state.line_width_set(1.0)

    @staticmethod
    def draw_2d(self, context, props):
        font_id = 0
        blf.size(font_id, 16)
        blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
        for x, y, text in self._text_lines:
            blf.position(font_id, x, y, 0)
            blf.draw(font_id, text)

        if not self._is_rect_mode:
            return

        x1, y1 = self._drag_start_mouse
        x2, y2 = self._drag_end_mouse
        vertices = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "LINE_LOOP", {"pos": vertices})
        shader.bind()
        shader.uniform_float("color", (1.0, 1.0, 1.0, 1.0))
        batch.draw(shader)

    def invoke(self, context, event):
        cls = self.__class__
        cls.remove_handler()
        obj = context.active_object

        self._matrix_world = obj.matrix_world

        self._x_mirror = obj.data.use_mirror_x
        self.points = context.window_manager.mio3ce.control_num
        context.window_manager.mio3ce.hide_spline = False
        self._text_lines = get_guide_lines()

        if not self.create_spline_loops(context):
            return self.cancel_deform(context)

        self.update_vertices(context)

        props = context.window_manager.mio3ce
        cls._handle_3d = SpaceView3D.draw_handler_add(self.draw_3d, (self, context, props), "WINDOW", "POST_VIEW")
        cls._handle_2d = SpaceView3D.draw_handler_add(self.draw_2d, (self, context, props), "WINDOW", "POST_PIXEL")

        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        mouse_x = event.mouse_region_x
        mouse_y = event.mouse_region_y

        # クリック
        if event.type == "LEFTMOUSE":
            spline_idx, point_idx = self.get_closest_control_point(context, (mouse_x, mouse_y))
            point_key = (spline_idx, point_idx)
            if event.value == "PRESS":
                # Ctrl+クリック 制御点を追加・削除
                if event.ctrl:
                    if spline_idx >= 0 and point_idx >= 0:
                        self.remove_control_points(context, [(spline_idx, point_idx)])
                    else:
                        self.add_control_point(context, (mouse_x, mouse_y))
                elif spline_idx >= 0 and point_idx >= 0:
                    if event.shift:  # Shiftキー 追加・削除
                        if point_key not in self._selected_points:
                            self._selected_points.append(point_key)
                            self._active_spline_index = spline_idx
                            self._active_point_index = point_idx
                        else:
                            self._selected_points.remove(point_key)
                            self._active_spline_index = -1
                            self._active_point_index = -1
                    elif not self._is_drag_mode and not self._is_grab_mode and not self._is_rect_mode:
                        # 🍊選択とドラッグ監視開始
                        if point_key not in self._selected_points:
                            self._selected_points = [point_key]
                        self._active_spline_index = spline_idx
                        self._active_point_index = point_idx
                        self._drag_start_mouse = (mouse_x, mouse_y)
                        self._is_drag_mode = False  # 即時に動かさない
                # G移動モード中のクリックは移動確定
                elif self._is_grab_mode and event.value == "PRESS":
                    self.end_move_mode("Gキー移動確定")
                else:
                    # 何もないところ → 矩形選択
                    self._is_rect_mode = True
                    self._drag_start_mouse = (mouse_x, mouse_y)
                    self._drag_end_mouse = (mouse_x, mouse_y)
                redraw_3d_views(context)

            elif event.value == "RELEASE":
                if self._drag_start_mouse:
                    if self._drag_start_mouse == (mouse_x, mouse_y):
                        self._active_spline_index = spline_idx
                        self._active_point_index = point_idx
                        self._selected_points = [point_key]
                        # 選択範囲がなければ確定
                        if self._is_rect_mode:
                            hit_radius = 160  # 解除の範囲広め
                            spline_idx, _, _ = self.get_closest_spline(context, (mouse_x, mouse_y), hit_radius)
                            # クリック場所にスプラインがない
                            if spline_idx is None:
                                return self.finish_deform(context)
                    if self._is_rect_mode:
                        self._is_rect_mode = False
                        self._drag_end_mouse = (mouse_x, mouse_y)
                        self.select_points_rect(context, event.shift)
                    self.end_move_mode("RELEASE")
                redraw_3d_views(context)

        # ドラッグ・マウス移動
        elif event.type == "MOUSEMOVE":
            if self._is_rect_mode:
                self._drag_end_mouse = (mouse_x, mouse_y)
                context.area.tag_redraw()  # 消すと矩形が描画されない
            elif self._is_grab_mode and self._drag_start_mouse:
                adjusted_mouse_pos = (mouse_x - self._mouse_offset[0], mouse_y - self._mouse_offset[1])
                self.move_control_point(context, adjusted_mouse_pos, self._axis)
            # ドラッグ待ち
            elif self._drag_start_mouse and not self._is_drag_mode:
                dx = mouse_x - self._drag_start_mouse[0]
                dy = mouse_y - self._drag_start_mouse[1]
                if dx * dx + dy * dy > 3**2:  # (n)px以上動いたらドラッグ開始
                    # 🍏ドラッグ開始
                    self._is_drag_mode = True
                    self.store_points()
            elif self._is_drag_mode:
                self.move_control_point(context, (mouse_x, mouse_y), self._axis)

        # Gキー：移動モード開始
        elif event.type == "G" and event.value == "PRESS":
            if self._selected_points:
                # 🍏キー移動開始
                if self._active_spline_index < 0 or self._active_point_index < 0:
                    self._active_spline_index, self._active_point_index = self._selected_points[0]
                self._is_grab_mode = True
                self._drag_start_mouse = (mouse_x, mouse_y)

                spline = self._spline_datas[self._active_spline_index]
                active_pos = Vector(spline["control_points"][self._active_point_index])
                active_2d = view3d_utils.location_3d_to_region_2d(context.region, context.region_data, active_pos)
                self._mouse_offset = (mouse_x - active_2d.x, mouse_y - active_2d.y) if active_2d else (0, 0)
                self.store_points()

        # ホイール：制御点の数を変更
        elif event.type in {"WHEELUPMOUSE", "WHEELDOWNMOUSE"} and (event.ctrl or event.shift):
            if self._is_drag_mode or self._is_grab_mode:
                self.end_move_mode("ホイール時のキャンセル")
            if event.type == "WHEELUPMOUSE":
                new_num = min(30, self.points + 1)
            else:
                new_num = max(3, self.points - 1)
            if new_num != self.points:
                if event.shift:
                    self.reset_deform(context)
                self.rebuild_spline(context, new_num)
            return {"RUNNING_MODAL"}

        elif event.type in {"X", "Y", "Z"} and event.value == "PRESS":
            if self._is_grab_mode or self._is_drag_mode:
                if self._axis != event.type:
                    self.restore_points(context)
                    redraw_3d_views(context)
                self._axis = event.type

        elif event.type == "RIGHTMOUSE" and event.value == "PRESS":
            # 移動モード中の右クリックはキャンセル
            if self._is_grab_mode or self._is_drag_mode or self._is_rect_mode:
                self.restore_points(context)
                self.update_vertices(context)
                self.end_move_mode("移動キャンセル")
                redraw_3d_views(context)
            else:
                return self.finish_deform(context)

        elif event.type in {"RET", "NUMPAD_ENTER", "TAB"}:
            if self._skip_finish:
                self._skip_finish = False
            else:
                return self.finish_deform(context)

        elif event.type == "ESC" or (event.ctrl and event.type == "Z"):
            self.reset_deform(context)
            return self.cancel_deform(context)

        elif event.type == "R" and event.value == "PRESS":
            self.reset_deform(context)
            self.rebuild_spline(context, self.points)

        elif event.type == "DEL" and event.value == "PRESS":
            self.remove_control_points(context, self._selected_points)

        elif event.type == "M" and event.value == "PRESS":
            self._x_mirror = not self._x_mirror

        elif event.type == "H" and event.value == "PRESS":
            self.toggle_display_spline(context)

        if event.type in PASS_THROUGH_KEY:
            return {"PASS_THROUGH"}

        return {"RUNNING_MODAL"}

    def end_move_mode(self, line=None):
        self._drag_start_mouse = None
        self._drag_end_mouse = None
        self._is_drag_mode = False
        self._is_grab_mode = False
        self._is_rect_mode = False
        self._mouse_offset = None
        self._axis = None
        self._store_points = []

    def store_points(self):
        self._store_points = []
        for spline in self._spline_datas:
            self._store_points.append(list(spline["control_points"]))

    def restore_points(self, context):
        for i, control_points in enumerate(self._store_points):
            if i < len(self._spline_datas):
                self._spline_datas[i]["control_points"] = control_points.copy()
                self._spline_datas[i]["spline_points"] = calc_spline_points(
                    control_points, self._segments, self._spline_datas[i]["is_closed"]
                ).copy()
        self.update_vertices(context)


class MESH_OT_mio3_curve_edges(MESH_OT_mio3_curve_edges_base):
    bl_idname = "mesh.mio3_curve_edges"
    bl_label = "Curve Edges"
    bl_description = "Deforms an edge loop with a spline curve"


class MESH_OT_mio3_curve_edges_quick(MESH_OT_mio3_curve_edges_base):
    bl_idname = "mesh.mio3_curve_edges_quick"
    bl_label = "Curve Edges"
    bl_description = "Omit the curve option for instant transformation"

    iterations: IntProperty(name="Iterations", default=3, min=1, max=10)

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        self._x_mirror = context.active_object.data.use_mirror_x
        self._matrix_world = context.active_object.matrix_world
        self.points = context.window_manager.mio3ce.control_num
        for i in range(self.iterations):
            if self.create_spline_loops(context):
                self.update_vertices(context)
        return {"FINISHED"}


classes = [
    MESH_OT_mio3_curve_edges,
    MESH_OT_mio3_curve_edges_quick,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    MESH_OT_mio3_curve_edges.remove_handler()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
