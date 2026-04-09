"""
ue_record_params.py — 调好参数后，在 UE5 里运行这个脚本
功能：读取当前材质实例的参数值，自动追加到 labels.csv

用法（两步工作流）：
  Step 1: 在 UE5 里手动调好材质参数，觉得"很像参考图了"
  Step 2: 修改下方 IMAGE_FILENAME 为当前参考图文件名
  Step 3: Tools -> Execute Python Script -> 选择本文件
  -> 自动把参数追加到 labels.csv

这样就不需要手动抄数字了。
"""

import unreal
import csv
import os

# ─── 每次运行前修改这里 ──────────────────────────────────────────────────────────
IMAGE_FILENAME = "ref_01.jpg"   # 改成当前对照的参考图文件名

# 材质实例路径（按需改）
MATERIAL_PATHS = {
    "hair": "/Game/MooaToonSamples/Characters/UnityChanSD/Materials/MI_UnityChan_Hair",
    "body": "/Game/MooaToonSamples/Characters/UnityChanSD/Materials/MI_UnityChan_Body_Blue",
    "base": "/Game/MooaToonSamples/Characters/UnityChanSD/Materials/MI_UnityChan_Base",
}
TARGET = "hair"  # 改成你当前在调的材质："hair" / "body" / "base"

LABELS_CSV = "D:/unreal/testcv/labels.csv"

# ─── 逻辑 ───────────────────────────────────────────────────────────────────────

def record():
    mat = unreal.load_asset(MATERIAL_PATHS[TARGET])
    if mat is None:
        unreal.log_error(f"[MooaToon] 材质加载失败")
        return

    mel = unreal.MaterialEditingLibrary

    shadow = mel.get_material_instance_vector_parameter_value(mat, "Shadow Color")
    width  = mel.get_material_instance_scalar_parameter_value(mat, "Width Scale")
    spec   = mel.get_material_instance_scalar_parameter_value(mat, "Specular")

    row = {
        "image_filename": IMAGE_FILENAME,
        "shadow_r":       round(shadow.r, 4),
        "shadow_g":       round(shadow.g, 4),
        "shadow_b":       round(shadow.b, 4),
        "width_scale":    round(width, 4),
        "specular":       round(spec, 4),
    }

    fieldnames = ["image_filename", "shadow_r", "shadow_g", "shadow_b", "width_scale", "specular"]
    file_exists = os.path.exists(LABELS_CSV)

    with open(LABELS_CSV, "a", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    unreal.log(f"[MooaToon] 已记录: {row}")
    unreal.log(f"[MooaToon] 写入: {LABELS_CSV}")

record()
