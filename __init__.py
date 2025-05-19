from .modules import curve_edges
from .modules import normal_symmetrize
from .modules import select_edge_loop
from .modules import select_trait
from .modules import edge_length
from .modules import snap_distance
from .modules import origin

from . import main_ui
from . import translation
from . import icons
from . import keymaps


module_list = [
    select_edge_loop,
    select_trait,
    curve_edges,
    normal_symmetrize,
    edge_length,
    snap_distance,
    origin,
    icons,
    main_ui,
    keymaps,
    translation,
]


def register():
    for module in module_list:
        module.register()


def unregister():
    for module in reversed(module_list):
        module.unregister()
