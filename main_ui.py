import bpy
from bpy.types import Panel, Menu, PropertyGroup
from bpy.props import BoolProperty, IntProperty, PointerProperty
from .icons import icons
from .utils import is_local_obj


class MIO3_PT_mesh_tools(Panel):
    bl_label = "Mio3 Mesh Tools"
    bl_idname = "MIO3_PT_mesh_tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Mio3"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return is_local_obj(obj) and obj.mode == "EDIT"

    def draw(self, context):
        pass


class MIO3_PT_mesh_select(Panel):
    bl_label = "Select"
    bl_idname = "MIO3_PT_mesh_select"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Mio3"
    bl_parent_id = "MIO3_PT_mesh_tools"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        col = self.layout.column(align=True)
        row = col.split(factor=0.58, align=True)

        row.scale_x = 1.1
        row.scale_y = 1.1
        sub = row.grid_flow(columns=3, align=True)
        sub.operator("mesh.mio3_select_half", text="", icon_value=icons.x_n).direction = "-X"
        sub.operator("mesh.mio3_select_center", text="", icon_value=icons.center)
        sub.operator("mesh.mio3_select_half", text="", icon_value=icons.x_p).direction = "+X"
        row.operator("mesh.mio3_select_mirror", text="Mirror", icon_value=icons.mirror)

        col.separator(factor=0.5)
        row = col.row(align=True)
        row.operator("mesh.mio3_select_edges", text="Edge Loops", icon_value=icons.edge_loops).ring = False
        row.operator("mesh.mio3_select_edges", text="Edge Rings", icon_value=icons.edge_rings).ring = True
        col.operator("mesh.mio3_select_between", icon_value=icons.edge_between)

        col.separator(factor=0.5)
        split = col.split(factor=0.5, align=True)
        split.label(text="Vector", icon="EMPTY_ARROWS")
        row = split.grid_flow(columns=3, align=True)
        row.operator("mesh.mio3_select_edge_view", text="", icon_value=icons.horizontal_edge).axis = "X"
        row.operator("mesh.mio3_select_edge_view", text="", icon_value=icons.vertical_edge).axis = "Y"
        row.operator("mesh.mio3_select_edge_vector", text="", icon="BONE_DATA")


class MIO3_PT_curve_edge_loop(Panel):
    bl_label = "Curve Edges"
    bl_idname = "MIO3_PT_curve_edge_loop"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Mio3"
    bl_parent_id = "MIO3_PT_mesh_tools"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=False)
        split = col.split(factor=0.7, align=True)
        split.operator("mesh.mio3_curve_edges")
        split.operator("mesh.mio3_curve_edges_quick", text="Quickly")
        split = col.split(factor=0.55, align=True)
        split.label(text="Control Points", icon="HANDLE_ALIGNED")
        split.prop(context.window_manager.mio3ce, "control_num", text="")


class MIO3_PG_curve_edge_loop(PropertyGroup):
    control_num: IntProperty(name="Control Points", default=3, min=2, max=30)
    hide_spline: BoolProperty(name="Hide Cueve", default=False)


class MIO3_PT_mesh_utils(Panel):
    bl_label = "Utility"
    bl_idname = "MIO3_PT_mesh_utils"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Mio3"
    bl_parent_id = "MIO3_PT_mesh_tools"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=False)
        col.operator("mesh.mio3_normal_symmetrize")
        col.operator("mesh.mio3_snap_distance")
        col.operator("mesh.mio3_edge_length")
        col.operator("mesh.mio3_origin_to_selection")


classes = [
    MIO3_PT_mesh_tools,
    MIO3_PT_mesh_select,
    MIO3_PT_curve_edge_loop,
    MIO3_PG_curve_edge_loop,
    MIO3_PT_mesh_utils,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.mio3ce = PointerProperty(type=MIO3_PG_curve_edge_loop)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.WindowManager.mio3ce
