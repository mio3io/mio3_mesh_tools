import bpy


def get_preference_idname():
    return __package__


def get_preferences():
    return bpy.context.preferences.addons[__package__].preferences


def get_preference(name):
    return getattr(get_preferences(), name, None)
