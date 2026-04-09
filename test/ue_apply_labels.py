"""
ue_apply_labels.py — 在 UE5 Output Log 里运行
功能：读取 labels.csv，把参数批量写入对应的材质实例

用法：
  1. 在 UE5 菜单栏: Edit -> Preferences -> Plugins -> Python Script Plugin 确认已启用
  2. 菜单栏: Tools -> Execute Python Script -> 选择本文件
  或者直接在 Output Log 底部输入框粘贴代码运行

注意：
  - 本脚本假设所有图片对应同一个材质实例（UnityChan Hair 为示例）
  - 如果每张图对应不同材质，修改 MATERIAL_ASSET_PATH 为字典映射
"""

import unreal
import csv
import os

# ─── 配置 ───────────────────────────────────────────────────────────────────────

# labels.csv 路径（使用正斜杠）
LABELS_CSV = "D:/unreal/testcv/labels.csv"

# 默认材质实例路径（UE Content Browser 内部路径）
# 根据需要改成你要调的材质
DEFAULT_MATERIAL_PATH = "/Game/MooaToonSamples/Characters/UnityChanSD/Materials/MI_UnityChan_Hair"

# 参数名映射（CSV列名 -> UE材质参数名）
SCALAR_PARAMS = {
    "width_scale":  "Width Scale",
    "specular":     "Specular",
}
VECTOR_PARAMS = {
    # CSV里的r/g/b列前缀 -> UE材质参数名
    "shadow": "Shadow Color",  # 对应 shadow_r, shadow_g, shadow_b
}

# ─── 主逻辑 ─────────────────────────────────────────────────────────────────────

def apply_labels(csv_path, material_path):
    if not os.path.exists(csv_path):
        unreal.log_error(f"[MooaToon] CSV 不存在: {csv_path}")
        return

    mat = unreal.load_asset(material_path)
    if mat is None:
        unreal.log_error(f"[MooaToon] 材质加载失败: {material_path}")
        return

    mel = unreal.MaterialEditingLibrary

    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    unreal.log(f"[MooaToon] 读取到 {len(rows)} 条记录，开始应用最后一条到材质...")

    # 取最后一行作为"当前调好的参数"，或者你可以改成按文件名匹配
    row = rows[-1]
    unreal.log(f"[MooaToon] 应用参数来自: {row['image_filename']}")

    # 写入 Vector 参数（Shadow Color）
    for prefix, param_name in VECTOR_PARAMS.items():
        try:
            r = float(row[f"{prefix}_r"])
            g = float(row[f"{prefix}_g"])
            b = float(row[f"{prefix}_b"])
            color = unreal.LinearColor(r=r, g=g, b=b, a=1.0)
            mel.set_material_instance_vector_parameter_value(mat, param_name, color)
            unreal.log(f"[MooaToon]   {param_name} = ({r:.3f}, {g:.3f}, {b:.3f})")
        except KeyError as e:
            unreal.log_warning(f"[MooaToon] CSV 缺少列: {e}")

    # 写入 Scalar 参数
    for csv_col, param_name in SCALAR_PARAMS.items():
        if csv_col in row:
            try:
                val = float(row[csv_col])
                mel.set_material_instance_scalar_parameter_value(mat, param_name, val)
                unreal.log(f"[MooaToon]   {param_name} = {val:.3f}")
            except (KeyError, ValueError) as e:
                unreal.log_warning(f"[MooaToon] 参数写入失败 {csv_col}: {e}")

    # 保存材质实例
    unreal.EditorAssetLibrary.save_asset(mat.get_path_name())
    unreal.log("[MooaToon] 材质已保存 ✓")


def read_current_params(material_path):
    """读取当前材质实例的参数值，方便你抄到 CSV 里"""
    mat = unreal.load_asset(material_path)
    if mat is None:
        unreal.log_error(f"[MooaToon] 材质加载失败: {material_path}")
        return

    mel = unreal.MaterialEditingLibrary
    unreal.log(f"\n[MooaToon] 当前参数值 ({material_path}):")

    # 读 Vector 参数
    for prefix, param_name in VECTOR_PARAMS.items():
        color = mel.get_material_instance_vector_parameter_value(mat, param_name)
        unreal.log(f"  {param_name}: R={color.r:.4f}  G={color.g:.4f}  B={color.b:.4f}")
        unreal.log(f"  -> CSV格式: {color.r:.3f},{color.g:.3f},{color.b:.3f}")

    # 读 Scalar 参数
    for csv_col, param_name in SCALAR_PARAMS.items():
        val = mel.get_material_instance_scalar_parameter_value(mat, param_name)
        unreal.log(f"  {param_name}: {val:.4f}")
        unreal.log(f"  -> CSV格式: {val:.3f}")


# ─── 入口 ───────────────────────────────────────────────────────────────────────

# 运行模式：
#   "apply"  → 把 CSV 最后一行写入材质
#   "read"   → 读取当前材质参数（调完参数后用这个抄值）
MODE = "read"

if MODE == "apply":
    apply_labels(LABELS_CSV, DEFAULT_MATERIAL_PATH)
elif MODE == "read":
    read_current_params(DEFAULT_MATERIAL_PATH)
