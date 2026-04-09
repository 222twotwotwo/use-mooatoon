"""
ue_nne_infer.py — 在 UE5 Output Log 里运行
功能：用 NNE 加载 mooatoon_model.onnx，对一张图片推理，把输出参数写入材质实例

依赖：
  - UE5.5 + NNE Plugin 已启用（Edit -> Plugins -> Neural Network Engine）
  - ONNX 文件已导入到 Content Browser（见下方说明）

【ONNX 导入步骤】
  1. 把 mooatoon_model.onnx 复制到:
     D:/unreal/MooaToon-Engine-5.5_MooaToonProject/.../Content/ONNX/
  2. UE5 会自动识别并生成 mooatoon_model.uasset ✓（已完成）
  3. Content Browser 内部路径: /Game/ONNX/mooatoon_model
"""

import unreal
import os

# ─── 配置 ───────────────────────────────────────────────────────────────────────
NNE_ASSET_PATH  = "/Game/ONNX/mooatoon_model"     # ONNX 导入后的 Content 路径
INFER_IMAGE     = "D:/unreal/testcv/images/G1T8dBxbQAIa7hM.jpg"  # 要推理的参考图
MATERIAL_PATH   = "/Game/MooaToonSamples/Characters/UnityChanSD/Materials/MI_UnityChan_Hair"

# 输出参数顺序（与训练时 LABEL_COLS 一致）
PARAM_NAMES = ["shadow_r", "shadow_g", "shadow_b", "width_scale", "specular"]

# width_scale 反归一化（训练时归一化到 [0,1]，还原为 [0.5, 3.0]）
def denorm_width(v):
    return v * 2.5 + 0.5

# ─── NNE 推理 ──────────────────────────────────────────────────────────────────

def run_inference():
    # 1. 加载 NNE Model Asset
    nne_asset = unreal.load_asset(NNE_ASSET_PATH)
    if nne_asset is None:
        unreal.log_error(f"[NNE] 资产加载失败: {NNE_ASSET_PATH}")
        unreal.log_error("[NNE] 请先把 mooatoon_model.onnx 导入到 Content Browser")
        return

    # 2. 创建运行时 Model Instance
    runtime = unreal.NNERuntimeCPU.get_default_object() if hasattr(unreal, "NNERuntimeCPU") else None
    model_instance = unreal.NNEModelData(nne_asset)

    unreal.log("[NNE] 模型加载成功，开始推理...")

    # 3. 读取并预处理图片（归一化到 ImageNet 标准）
    import struct, array

    # UE Python 没有 PIL，用内置方法读图
    # 如果 PIL 可用则用 PIL 预处理
    try:
        from PIL import Image as PILImage
        import struct

        img = PILImage.open(INFER_IMAGE).convert("RGB").resize((224, 224))
        pixels = list(img.getdata())

        mean = [0.485, 0.456, 0.406]
        std  = [0.229, 0.224, 0.225]

        # CHW 格式，归一化
        tensor = []
        for c in range(3):
            for r, g, b in pixels:
                vals = [r/255.0, g/255.0, b/255.0]
                tensor.append((vals[c] - mean[c]) / std[c])

        input_data = array.array('f', tensor)
        unreal.log(f"[NNE] 图片预处理完成，tensor 长度: {len(tensor)}")

    except ImportError:
        unreal.log_error("[NNE] PIL 未安装，无法预处理图片")
        return

    # 4. 设置输入并推理
    # 注意：UE NNE Python API 在不同版本有差异，以下为 5.4/5.5 通用写法
    try:
        model_instance.set_inputs([input_data.tobytes()])
        model_instance.run()
        output = model_instance.get_outputs()[0]

        # 解析输出（5个float32）
        results = struct.unpack('5f', output[:20])
        unreal.log("[NNE] 推理结果:")
        for name, val in zip(PARAM_NAMES, results):
            unreal.log(f"  {name}: {val:.4f}")

        # 5. 写入材质
        apply_to_material(results)

    except Exception as e:
        unreal.log_error(f"[NNE] 推理失败: {e}")
        unreal.log_error("[NNE] 请检查 NNE API 是否与 UE 版本匹配")


def apply_to_material(results):
    shadow_r, shadow_g, shadow_b, width_scale_norm, specular = results

    # 反归一化 width_scale
    width_scale = denorm_width(width_scale_norm)

    mat = unreal.load_asset(MATERIAL_PATH)
    if mat is None:
        unreal.log_error(f"[NNE] 材质加载失败: {MATERIAL_PATH}")
        return

    mel = unreal.MaterialEditingLibrary
    color = unreal.LinearColor(r=shadow_r, g=shadow_g, b=shadow_b, a=1.0)
    mel.set_material_instance_vector_parameter_value(mat, "Shadow Color", color)
    mel.set_material_instance_scalar_parameter_value(mat, "Width Scale", width_scale)
    mel.set_material_instance_scalar_parameter_value(mat, "Specular", specular)
    unreal.EditorAssetLibrary.save_asset(mat.get_path_name())

    unreal.log(f"[NNE] 已写入材质:")
    unreal.log(f"  Shadow Color: ({shadow_r:.3f}, {shadow_g:.3f}, {shadow_b:.3f})")
    unreal.log(f"  Width Scale:  {width_scale:.3f}")
    unreal.log(f"  Specular:     {specular:.3f}")


run_inference()
