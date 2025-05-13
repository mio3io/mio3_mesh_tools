import bpy
from . import curve_edges

translation_dict = {
    "ja_JP": {
        ("Operator", "Curve Edges"): "カーブエッジ",
        ("*", "Deforms an edge loop with a spline curve"): "スプラインカーブでエッジループを変形します",
        ("*", "Omit the curve option for instant transformation"): "カーブオプションを省略して即時変形します",
        ("*", "Control Points"): "制御点",
        ("Operator", "Quickly"): "即時",
        ("*", "Confirmed"): "確定しました",
        ("WorkSpace",
            "🐻[Click] Confirm / 🍎[Ctrl+Wheel][Shift+Wheel] Change Control Points [Ctrl+Click] Add or delete [Del] Delete Control Points /🎃[M] Mirror toggle 🍇[R] Reset Deform"):
            "🐻[クリック]確定 / 🍎[Ctrl+ホイール][Shift+ホイール]ポイント数変更 [Ctrl+クリック]追加or削除 [Del]制御点を削除 /🎃[M]ミラー切り替え 🍇[R]変形リセット",
    }
}  # fmt: skip

def register():
    bpy.app.translations.register(__package__, translation_dict)
    curve_edges.register(__name__)


def unregister():
    curve_edges.unregister(__name__)
    bpy.app.translations.unregister(__package__)
