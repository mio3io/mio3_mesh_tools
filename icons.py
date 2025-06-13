import os
from bpy.utils import previews

BASE_DIR = os.path.dirname(__file__)
ICON_DIR = os.path.join(BASE_DIR, "icons")

icon_names = [
    "add",
    "remove",
    "vertical_edge",
    "horizontal_edge",
    "x_n",
    "x_p",
    "edge_rings",
    "edge_loops",
    "edge_between",
    "select_loops",
    "origin_to_active",
    "flat",
    "similar",
    "mirror",
    "center",
    "paws",
]

class IconSet:
    def __init__(self):
        self._icons = None
    
    def load(self):
        self._icons = previews.new()
        for name in icon_names:
            icon_path = os.path.join(ICON_DIR, "{}.png".format(name))
            if os.path.exists(icon_path):
                self._icons.load(name, icon_path, "IMAGE")
                setattr(self, name, self._icons[name].icon_id)

    def unload(self):
        if self._icons:
            previews.remove(self._icons)
            self._icons = None


icons = IconSet()


def register():
    icons.load()


def unregister():
    icons.unload()
