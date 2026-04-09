"""
infer_test.py — 纯 Python 推理验证（不需要 UE）
功能：加载 mooatoon_model.onnx，对 images/ 里任意一张图推理，打印输出参数
用于在进入 UE 之前先确认 ONNX 模型输出是否正常
"""

import onnxruntime as ort
import numpy as np
from PIL import Image
import sys
import os

ONNX_PATH  = "mooatoon_model.onnx"
IMAGES_DIR = "images"
PARAM_NAMES = ["shadow_r", "shadow_g", "shadow_b", "width_scale_norm", "specular"]
IMG_SIZE   = 224
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)

def preprocess(img_path):
    img = Image.open(img_path).convert("RGB").resize((IMG_SIZE, IMG_SIZE))
    x = np.array(img, dtype=np.float32) / 255.0      # HWC, [0,1]
    x = (x - MEAN) / STD                              # 归一化
    x = x.transpose(2, 0, 1)[np.newaxis, :]           # -> NCHW
    return x

def denorm_width(v):
    return v * 2.5 + 0.5

def infer(img_path):
    sess = ort.InferenceSession(ONNX_PATH, providers=["CPUExecutionProvider"])
    x = preprocess(img_path)
    outputs = sess.run(["params"], {"image": x})
    preds = outputs[0][0]  # shape (5,)

    print(f"\n图片: {os.path.basename(img_path)}")
    print("─" * 40)
    for name, val in zip(PARAM_NAMES, preds):
        print(f"  {name:20s} = {val:.4f}")

    # 反归一化 width_scale
    ws = denorm_width(float(preds[3]))
    print(f"\n  [UE参数]")
    print(f"  Shadow Color     = ({preds[0]:.3f}, {preds[1]:.3f}, {preds[2]:.3f})")
    print(f"  Width Scale      = {ws:.3f}  (原始范围 0.5~3.0)")
    print(f"  Specular         = {preds[4]:.3f}")

if __name__ == "__main__":
    # 用法: python infer_test.py [图片文件名]
    if len(sys.argv) > 1:
        img_path = os.path.join(IMAGES_DIR, sys.argv[1])
    else:
        # 默认取第一张
        files = [f for f in os.listdir(IMAGES_DIR) if f.lower().endswith(('.png','.jpg','.jpeg'))]
        img_path = os.path.join(IMAGES_DIR, sorted(files)[0])

    if not os.path.exists(img_path):
        print(f"文件不存在: {img_path}")
        sys.exit(1)

    infer(img_path)
