import bpy

addon_keymaps = []


def register():

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name="Mesh", space_type="EMPTY")
        kmi = km.keymap_items.new(
            "mesh.mio3_select_edges",
            "NUMPAD_PLUS",
            "PRESS",
            ctrl=True,
            shift=False,
            alt=True,
        )
        addon_keymaps.append((km, kmi))

        kmi = km.keymap_items.new(
            "mesh.mio3_select_edges",
            "NUMPAD_MINUS",
            "PRESS",
            ctrl=True,
            shift=False,
            alt=True,
        )
        addon_keymaps.append((km, kmi))

        kmi = km.keymap_items.new(
            "mesh.mio3_select_between",
            "NUMPAD_ASTERIX",
            "PRESS",
            ctrl=True,
            shift=False,
            alt=True,
        )
        addon_keymaps.append((km, kmi))


def unregister():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
