import numpy as np
from mathutils import Vector

# 押したときにデフォの処理をするキー "WHEELINMOUSE", "WHEELOUTMOUSE",
PASS_THROUGH_KEY = {
    "NUMPAD_0", "NUMPAD_1", "NUMPAD_3", "NUMPAD_4", "NUMPAD_5", "NUMPAD_7", "NUMPAD_9",
    "MOUSEMOVE", "INBETWEEN_MOUSEMOVE", "MIDDLEMOUSE", "WHEELUPMOUSE", "WHEELDOWNMOUSE", 
    "NUMPAD_PERIOD", "NUMPAD_SLASH",
} # fmt: skip


def redraw_3d_views(context):
    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            area.tag_redraw()


def is_closed_loop(vertices):
    first_vert = vertices[0]
    last_vert = vertices[-1]
    for edge in last_vert.link_edges:
        if edge.other_vert(last_vert) == first_vert:
            return True


def find_edge_loops(selected_verts):
    """選択された頂点からエッジループを見つける"""
    loops = []
    unprocessed = set(selected_verts)

    while unprocessed:
        start_vert = next(iter(unprocessed))
        loop = []
        queue = [start_vert]
        visited = set()

        while queue:
            vert = queue.pop(0)
            if vert in visited:
                continue

            visited.add(vert)
            loop.append(vert)
            for edge in vert.link_edges:
                if edge.select:
                    other_vert = edge.other_vert(vert)
                    if other_vert in unprocessed and other_vert not in visited:
                        queue.append(other_vert)

        if loop and len(loop) >= 2:
            loops.append(loop)
            unprocessed -= set(loop)
        else:
            unprocessed.remove(start_vert)

    return loops


def order_vertices(verts):
    """エッジで接続された頂点を順序付ける"""
    start_vert = None
    for v in verts:
        linked_selected = sum(1 for e in v.link_edges if e.select and e.other_vert(v) in verts)
        if linked_selected == 1:
            start_vert = v
            break

    if not start_vert:
        # X軸の中心に最も近い頂点から開始
        start_vert = min(verts, key=lambda v: (abs(v.co.x), abs(v.co.y), abs(v.co.z)))

    ordered = [start_vert]
    visited = {start_vert}

    current = start_vert
    while len(ordered) < len(verts):
        found_next = False
        for e in current.link_edges:
            if e.select:
                other = e.other_vert(current)
                if other in verts and other not in visited:
                    ordered.append(other)
                    visited.add(other)
                    current = other
                    found_next = True
                    break

        if not found_next:
            break

    return ordered


def calc_vertex_params(vertices, spline_points, is_closed=False):
    """各頂点のスプラインパラメータ（t値）を計算する"""
    parameters = []
    original_lengths = [0.0]
    total_original_length = 0.0

    for i in range(1, len(vertices)):
        p1 = Vector(vertices[i - 1])
        p2 = Vector(vertices[i])
        edge_lengths = (p2 - p1).length
        total_original_length += edge_lengths
        original_lengths.append(total_original_length)

    if is_closed and len(vertices) > 2:
        p1 = Vector(vertices[-1])
        p2 = Vector(vertices[0])
        edge_lengths = (p2 - p1).length
        total_original_length += edge_lengths

    if total_original_length <= 0:
        return parameters

    for i, vertex in enumerate(vertices):
        t_param = original_lengths[i] / total_original_length if total_original_length > 0 else 0
        parameters.append({"t": t_param, "distance": 0})

    return parameters


def calc_control_points(vertices, control_num, is_closed=False):
    """制御点の均等な位置を取得する"""
    vertices = np.asarray(vertices, dtype=np.float64)

    if is_closed:
        control_num = max(3, control_num)
    else:
        control_num = max(0, (control_num - 2))

    diffs = vertices[1:] - vertices[:-1]
    edge_lengths = np.linalg.norm(diffs, axis=1).tolist()

    if is_closed and len(vertices) > 2:
        edge_lengths.append(np.linalg.norm(vertices[0] - vertices[-1]))

    total_length = sum(edge_lengths)

    if total_length <= 0:
        return []

    def lerp_point(i, ratio):
        v1 = vertices[i]
        v2 = vertices[(i + 1) % len(vertices)] if is_closed else vertices[i + 1]
        return tuple((1 - ratio) * v1 + ratio * v2)

    if control_num == 1:
        steps = [total_length / 2]
    else:
        if is_closed:
            step = total_length / control_num
            steps = [step * i for i in range(control_num)]
        else:
            step = total_length / (control_num + 1)
            steps = [step * (i + 1) for i in range(control_num)]

    control_points = []
    if not is_closed:
        control_points.append(tuple(vertices[0]))

    current_distance = 0
    segment_index = 0

    for distance in steps:
        while segment_index < len(edge_lengths) and current_distance + edge_lengths[segment_index] < distance:
            current_distance += edge_lengths[segment_index]
            segment_index += 1

        if segment_index < len(edge_lengths):
            local_distance = distance - current_distance
            ratio = local_distance / edge_lengths[segment_index]
            vertex_index = segment_index % len(vertices)
            control_points.append(lerp_point(vertex_index, ratio))

    if not is_closed:
        control_points.append(tuple(vertices[-1]))

    return control_points


def calc_spline_points(control_points, segments=10, is_closed=False):
    """スプラインポイントを計算する"""
    if len(control_points) < 2:
        return control_points.copy()

    cp = np.asarray(control_points, dtype=np.float64)
    if is_closed:
        cp = np.vstack([cp[-1], cp, cp[:2]])
    else:
        cp = np.vstack([cp[0], cp, cp[-1], cp[-1]])

    def tangent(p_prev, p_next, t):
        return (1 - t) * (p_next - p_prev) * 0.5

    spline_points = []
    ts = np.linspace(0.0, 1.0, segments + 1)

    tension = -0.25  # 丸み
    for i in range(1, len(cp) - 2):
        p0, p1, p2, p3 = cp[i - 1], cp[i], cp[i + 1], cp[i + 2]

        m1 = tangent(p0, p2, tension)
        m2 = tangent(p1, p3, tension)

        d1 = np.linalg.norm(p2 - p1)
        d0 = np.linalg.norm(p1 - p0)
        max_len1 = min(d0, d1)  # clamp * min(d0, d1)
        len_m1 = np.linalg.norm(m1)
        if len_m1 > max_len1 and len_m1 > 0:
            m1 *= max_len1 / len_m1

        d2 = np.linalg.norm(p3 - p2)
        max_len2 = min(d1, d2)  # clamp * min(d1, d2)
        len_m2 = np.linalg.norm(m2)
        if len_m2 > max_len2 and len_m2 > 0:
            m2 *= max_len2 / len_m2

        for t in ts[:-1]:
            t2, t3 = t * t, t * t * t
            h00 = 2 * t3 - 3 * t2 + 1
            h10 = t3 - 2 * t2 + t
            h01 = -2 * t3 + 3 * t2
            h11 = t3 - t2
            point = (h00 * p1) + (h10 * m1) + (h01 * p2) + (h11 * m2)
            spline_points.append(tuple(point))

    spline_points.append(tuple(cp[-2]))
    if is_closed:
        spline_points.append(spline_points[0])

    return spline_points
