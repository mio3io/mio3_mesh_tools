import bpy

translation_dict = {
    "ja_JP": {
        ("Operator", "Loops"): "ループ",
        ("Operator", "Rings"): "リング",
        ("Operator", "Between Rings"): "間のリング",

        ("*", "Curve Edges"): "カーブエッジ",
        ("Operator", "Curve Edges"): "カーブエッジ",
        ("Operator", "Quickly"): "即時",
        ("*", "Deforms an edge loop with a spline curve"): "スプラインカーブでエッジループを変形します",
        ("*", "Omit the curve option for instant transformation"): "カーブオプションを省略して即時変形します",
        ("*", "Control Points"): "制御点",
        ("*", "Confirmed"): "確定しました",

        ("Operator", "Select Mesh by Direction"): "方向でメッシュを選択",
        ("Operator", "Select the Mesh Center"): "中心のメッシュを選択",
        ("*", "[Alt] Deselect"): "[Alt]選択解除",
        ("Operator", "Select the Mirrored Mesh"): "ミラー方向のメッシュを選択",
        ("*", "Select the Mirrored Mesh"): "ミラー方向のメッシュを選択",
        ("*", "Edge Rings"): "辺リング",
        ("*", "Include Center"): "中心を含む",

        ("Operator", "Select Edge More/Less"): "エッジ選択を拡大/縮小",
        ("*", "Expand or reduce the selection of edge loops(rings)\n[Shift] Select All\n[Alt] Reduce by one"): "辺の選択を拡大/縮小します\n[Shift]すべて選択\n[Alt]1つ縮小",

        ("*", "One More"): "1つ拡大",
        ("*", "One Less"): "1つ縮小",
        ("Operator", "Between Edge Rings"): "間の辺リング",
        ("*", "Select edge rings between selected edges"): "選択された辺の間にある辺リングを選択します",

        ("Operator", ""): "方向で選択を解除",
        ("Operator", "Select Edges by Vector"): "ベクトルで辺を選択",
        ("*", "Select edges from the selection based on vectors of any bone"): "選択範囲から任意のボーンのベクトルに基づき辺を選択します",

        ("Operator", "Select Edges by View"): "ビュー方向で辺を選択",
        ("*", "Select edges from the selection based on view direction"): "選択範囲からビュー方向に基づき辺を選択します",

        ("*", "Selected Boundary"): "選択した境界",
        ("*", "Weight Bone"): "ウェイトのあるボーン",
        ("*", "Closest Bone"): "近接のボーン",
        ("*", "Select Bone"): "選択のボーン",

        ("Operator", "Normal Symmetrize"): "ノーマルを対称化",
        ("Operator", "Equalize Edge Lengths"): "辺の長さを揃える",
        ("Operator", "Origin → Active"): "原点 → アクティブ",
        ("Operator", "Snap to Nearest Vertex"): "近接頂点にスナップ",

        # GPU GUI
        ("*", "🐻Tips"): "🐻Tips",
        ("*", "[Click] Confirm"): "[Click] 確定",
        ("*", "[R] Reset Deform [M] Mirror toggle [H] Hide Spline"): "[R] 変形リセット [M] ミラー切り替え [H] スプライン非表示",
        ("*", "[Ctrl+Wheel][Shift+Wheel] Change Control Points"): "[Ctrl+ホイール][Shift+ホイール]ポイント数変更",
        ("*", "[Ctrl+Click] Add or delete [Del] Delete Control Points"): "[Ctrl+クリック]追加or削除 [Del]制御点を削除",

    }
}  # fmt: skip


def register():
    bpy.app.translations.register(__package__, translation_dict)


def unregister():
    bpy.app.translations.unregister(__package__)
