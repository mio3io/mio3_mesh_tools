import bpy
from bpy.types import AddonPreferences
from bpy.props import FloatVectorProperty, IntProperty, StringProperty


class PREFERENCE_mio3me(AddonPreferences):
    bl_idname = __package__

    category: StringProperty(name="Category")

    col_spline_default: FloatVectorProperty(
        name="Default",
        subtype="COLOR",
        size=4,
        default=(0.0, 0.7, 1.0, 1.0),
    )
    col_spline_active: FloatVectorProperty(
        name="Active",
        subtype="COLOR",
        size=4,
        default=(0.0, 0.7, 1.0, 1.0),
    )
    col_point_default: FloatVectorProperty(
        name="Default",
        subtype="COLOR",
        size=4,
        default=(0.36, 0.79, 1.00, 1.0),
    )
    col_point_selected: FloatVectorProperty(
        name="Selected",
        subtype="COLOR",
        size=4,
        default=(0.8, 0.8, 0.8, 1.0),
    )
    col_point_active: FloatVectorProperty(
        name="Active",
        subtype="COLOR",
        size=4,
        default=(0.8, 0.8, 0.8, 1.0),
    )
    point_size_default: IntProperty(name="Default", default=8, min=4)
    point_size_selected: IntProperty(name="Selected", default=10, min=4)
    point_size_active: IntProperty(name="Active", default=10, min=4)

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False

        box = layout.box()
        box.label(text="Curve Edges", icon="COLOR")
        col = box.column()
        col.use_property_split = True
        col.label(text="Spline", icon="IPO_EASE_IN_OUT")
        col.prop(self, "col_spline_default")
        col.prop(self, "col_spline_active")
        col = box.column()
        col.use_property_split = True
        col.label(text="Point", icon="SNAP_MIDPOINT")
        col.prop(self, "col_point_default")
        col.prop(self, "col_point_selected")
        col.prop(self, "col_point_active")

        col = box.column()
        col.use_property_split = True
        col.label(text="Point Size", icon="SNAP_MIDPOINT")
        col.prop(self, "point_size_default")
        col.prop(self, "point_size_selected")
        col.prop(self, "point_size_active")


def register():
    bpy.utils.register_class(PREFERENCE_mio3me)


def unregister():
    bpy.utils.unregister_class(PREFERENCE_mio3me)
