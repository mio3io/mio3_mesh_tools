from .modules import curve_edges
from .modules import normal_symmetrize
from .modules import select_edge_loop
from .modules import select_trait
from .modules import edge_length
from .modules import origin
from .modules import group_merge

from . import main_ui
from . import translation
from . import icons
from . import keymaps
from . import preferences


module_list = [
    preferences,
    select_edge_loop,
    select_trait,
    curve_edges,
    normal_symmetrize,
    edge_length,
    group_merge,
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
