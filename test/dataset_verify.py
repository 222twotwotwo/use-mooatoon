import os
import pandas as pd
from PIL import Image

IMAGES_DIR = "images"
LABELS_CSV = "labels.csv"
IMG_SIZE = (224, 224)

def verify():
    # 1. 读取 CSV
    df = pd.read_csv(LABELS_CSV)
    print(f"[CSV] 共 {len(df)} 条记录，列: {list(df.columns)}")

    # 2. 检查文件存在性
    missing = []
    corrupt = []
    ok = []

    for idx, row in df.iterrows():
        path = os.path.join(IMAGES_DIR, row["image_filename"])
        if not os.path.exists(path):
            missing.append(row["image_filename"])
            continue
        try:
            img = Image.open(path).convert("RGB").resize(IMG_SIZE)
            ok.append((row["image_filename"], img.size))
        except Exception as e:
            corrupt.append((row["image_filename"], str(e)))

    # 3. 打印结果
    print(f"\n[OK]     {len(ok)} 张图片正常加载")
    if missing:
        print(f"[MISS]   {len(missing)} 张文件缺失:")
        for f in missing:
            print(f"         - {f}")
    if corrupt:
        print(f"[ERROR]  {len(corrupt)} 张图片损坏:")
        for f, e in corrupt:
            print(f"         - {f}: {e}")

    # 4. 标签范围检查
    print("\n[标签范围检查]")
    checks = {
        "shadow_r":    (0, 1),
        "shadow_g":    (0, 1),
        "shadow_b":    (0, 1),
        "width_scale": (0.5, 3.0),
        "specular":    (0, 1),
    }
    for col, (lo, hi) in checks.items():
        out = df[(df[col] < lo) | (df[col] > hi)]
        if not out.empty:
            print(f"  [{col}] {len(out)} 行超出范围 [{lo}, {hi}]")
        else:
            print(f"  [{col}] OK  min={df[col].min():.3f}  max={df[col].max():.3f}")

    # 5. 打印前3条样本
    print("\n[前3条样本]")
    print(df.head(3).to_string(index=False))

    if not missing and not corrupt:
        print("\n>>> 数据集验证通过，可以开始训练 <<<")
    else:
        print("\n>>> 数据集存在问题，请先修复 <<<")

if __name__ == "__main__":
    verify()
