from . import curve_edges


def register():
    curve_edges.register(__name__)


def unregister():
    curve_edges.unregister(__name__)
