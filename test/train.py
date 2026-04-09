"""
train.py — MooaToon 材质参数回归训练脚本
输入: 224x224 图片
输出: 5个材质参数 [shadow_r, shadow_g, shadow_b, width_scale, specular]
训练完成后自动导出 mooatoon_model.onnx
"""
import os
import torch
import torch.nn as nn
import pandas as pd
from PIL import Image
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as T
import torchvision.models as models

# ─── 配置 ──────────────────────────────────────────────────────────────────────
IMAGES_DIR  = "images"
LABELS_CSV  = "labels.csv"
EPOCHS      = 20
BATCH_SIZE  = 4
LR          = 1e-4
IMG_SIZE    = 224
LABEL_COLS  = ["shadow_r", "shadow_g", "shadow_b", "width_scale", "specular"]
ONNX_PATH   = "mooatoon_model.onnx"
DEVICE      = "cuda" if torch.cuda.is_available() else "cpu"

# width_scale 范围 [0.5, 3.0]，其余 [0, 1]，归一化到 [0,1] 方便训练
def normalize_labels(df):
    df = df.copy()
    df["width_scale"] = (df["width_scale"] - 0.5) / 2.5
    return df

# ─── Dataset ───────────────────────────────────────────────────────────────────
class MooaToonDataset(Dataset):
    def __init__(self, csv_path, images_dir, transform=None):
        self.df = normalize_labels(pd.read_csv(csv_path))
        self.images_dir = images_dir
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img_path = os.path.join(self.images_dir, row["image_filename"])
        img = Image.open(img_path).convert("RGB")
        if self.transform:
            img = self.transform(img)
        labels = torch.tensor(row[LABEL_COLS].values.astype("float32"))
        return img, labels

# ─── 数据增强 ──────────────────────────────────────────────────────────────────
transform = T.Compose([
    T.Resize((IMG_SIZE, IMG_SIZE)),
    T.RandomHorizontalFlip(),
    T.ColorJitter(brightness=0.1, contrast=0.1),
    T.ToTensor(),
    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# ─── 模型 ──────────────────────────────────────────────────────────────────────
def build_model(num_outputs=5):
    model = models.resnet18(weights=None)  # 小数据集不用预训练也能验证流程
    model.fc = nn.Sequential(
        nn.Linear(model.fc.in_features, 128),
        nn.ReLU(),
        nn.Dropout(0.3),
        nn.Linear(128, num_outputs),
        nn.Sigmoid(),  # 输出压到 [0,1]
    )
    return model

# ─── 训练 ──────────────────────────────────────────────────────────────────────
def train():
    print(f"Device: {DEVICE}")

    dataset = MooaToonDataset(LABELS_CSV, IMAGES_DIR, transform=transform)
    # 数据量少，不做 split，全部用于训练以验证流程
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True, drop_last=False)
    print(f"数据集: {len(dataset)} 张图片, {len(loader)} 个 batch")

    model = build_model(num_outputs=len(LABEL_COLS)).to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    criterion = nn.MSELoss()

    print(f"\n开始训练 ({EPOCHS} epochs)...\n")
    for epoch in range(1, EPOCHS + 1):
        model.train()
        total_loss = 0.0
        for imgs, labels in loader:
            imgs, labels = imgs.to(DEVICE), labels.to(DEVICE)
            optimizer.zero_grad()
            preds = model(imgs)
            loss = criterion(preds, labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        avg_loss = total_loss / len(loader)
        print(f"Epoch [{epoch:02d}/{EPOCHS}]  Loss: {avg_loss:.6f}")

    # 保存权重
    torch.save(model.state_dict(), "mooatoon_model.pth")
    print("\n模型已保存: mooatoon_model.pth")

    # 导出 ONNX（使用旧版 API，兼容性更好）
    model.eval()
    dummy_input = torch.randn(1, 3, IMG_SIZE, IMG_SIZE).to(DEVICE)
    with torch.no_grad():
        torch.onnx.export(
            model,
            dummy_input,
            ONNX_PATH,
            input_names=["image"],
            output_names=["params"],
            opset_version=12,
            dynamo=False,
        )
    print(f"ONNX exported: {ONNX_PATH}")
    print("\n>>> 训练完成，loss 持续下降说明流程正常 <<<")

if __name__ == "__main__":
    train()
