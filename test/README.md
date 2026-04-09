# HybriToon Dataset — MooaToon 材质参数预测

## 项目概述

本项目的目标是训练一个神经网络模型：

```
输入：日式风格插画图片（224×224 RGB）
输出：UE5 MooaToon 材质的 5 个参数
```

训练好的模型导出为 ONNX，在 UE5 的 NNE（Neural Network Engine）中加载。
实际使用时，在 Python 端对参考图推理得到参数值，通过蓝图节点写入 MooaToon 材质，
实现"给一张参考图，自动推理出匹配的材质参数"的效果。

---

## 目录结构

```
D:/unreal/testcv/
│
├── images/                   # 参考图片（日式插画，PNG/JPG）
│   ├── ref_01.jpg
│   └── ...
│
├── labels.csv                # 数据集标签文件
│
├── dataset_verify.py         # 数据集验证脚本
├── train.py                  # 模型训练 + ONNX 导出脚本
├── infer_test.py             # 本地推理验证脚本
│
├── ue_record_params.py       # [UE内运行] 调好材质后记录参数到 CSV
├── ue_apply_labels.py        # [UE内运行] 把 CSV 参数写入材质实例
├── ue_nne_infer.py           # [UE内运行] NNE 推理脚本（受限，见说明）
│
├── mooatoon_model.pth        # PyTorch 模型权重（训练产物）
└── mooatoon_model.onnx       # ONNX 模型（导出产物，供 UE5 NNE 加载）
```

UE5 项目 C++ 源码位置：
```
D:/unreal/MooaToon-Engine-5.5_MooaToonProject/.../Source/MooaToon_Project/
├── MyClass.h                 # 蓝图函数库声明
├── MyClass.cpp               # 推理 + 材质写入实现
└── MooaToon_Project.Build.cs # 模块依赖声明
```

---

## 标签文件格式

`labels.csv` 的每一行对应一张图片和一组 MooaToon 材质参数：

```csv
image_filename,shadow_r,shadow_g,shadow_b,width_scale,specular
ref_01.jpg,0.2,0.1,0.3,1.5,0.8
ref_02.jpg,0.4,0.5,0.6,1.2,0.3
```

| 列名 | 对应 UE 材质参数 | 取值范围 | 说明 |
|------|----------------|----------|------|
| `shadow_r` | Shadow Color (R) | [0, 1] | 阴影色红通道 |
| `shadow_g` | Shadow Color (G) | [0, 1] | 阴影色绿通道 |
| `shadow_b` | Shadow Color (B) | [0, 1] | 阴影色蓝通道 |
| `width_scale` | Width Scale | [0.5, 3.0] | 描边宽度 |
| `specular` | Specular | [0, 1] | 高光强度 |

> 注意：`width_scale` 在训练时归一化到 [0,1]，推理时自动反归一化还原为 [0.5, 3.0]。

---

## 各脚本说明

### `dataset_verify.py` — 数据集验证

**作用**：训练前跑一次，确认数据没有问题。

检查内容：
- CSV 中每个文件名对应的图片是否存在
- 图片能否正常打开（检测损坏文件）
- 各列参数值是否在合理范围内
- 打印前 3 条样本预览

**用法**：
```bash
cd D:/unreal/testcv
python dataset_verify.py
```

**期望输出**：
```
[CSV] 共 38 条记录
[OK]  38 张图片正常加载
[标签范围检查] 全部 OK
>>> 数据集验证通过，可以开始训练 <<<
```

---

### `train.py` — 模型训练 + ONNX 导出

**作用**：读取图片和标签，训练回归神经网络，训练完成后自动导出 ONNX。

**模型结构**：
```
ResNet18 骨干网络（不使用预训练权重）
    ↓
全连接层 (512 → 128 → 5)
    ↓
Sigmoid 激活（输出压到 [0,1]）
```

**训练配置**（在文件顶部修改）：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `EPOCHS` | 20 | 训练轮数 |
| `BATCH_SIZE` | 4 | 批大小（数据少时保持 4） |
| `LR` | 1e-4 | Adam 学习率 |
| `IMG_SIZE` | 224 | 图片缩放尺寸 |

**用法**：
```bash
cd D:/unreal/testcv
python train.py
```

**期望输出**：
```
Device: cpu
数据集: 38 张图片, 10 个 batch

Epoch [01/20]  Loss: 0.063324
...
Epoch [20/20]  Loss: 0.018778

模型已保存: mooatoon_model.pth
ONNX exported: mooatoon_model.onnx
```

**判断训练是否正常**：loss 整体呈下降趋势即为正常，不要求单调递减。

> 当前使用随机占位标签训练，替换为真实标注数据后模型才具备实际意义。

---

### `infer_test.py` — 本地推理验证

**作用**：不需要打开 UE5，直接用 ONNX 模型对一张图片推理，验证模型输出是否正常。

**用法**：
```bash
# 对第一张图推理（默认）
python infer_test.py

# 指定图片
python infer_test.py G1T8dBxbQAIa7hM.jpg
```

**期望输出**：
```
图片: G1T8dBxbQAIa7hM.jpg
────────────────────────────────────────
  shadow_r             = 0.2362
  shadow_g             = 0.1080
  shadow_b             = 0.1682
  width_scale_norm     = 0.2117
  specular             = 0.6962

  [UE参数]
  Shadow Color     = (0.236, 0.108, 0.168)
  Width Scale      = 1.029  (原始范围 0.5~3.0)
  Specular         = 0.696
```

---

### `ue_record_params.py` — [UE内运行] 调参记录

**作用**：在 UE5 里手动调好材质参数后，运行此脚本自动读取当前参数值并追加到 `labels.csv`。

**每次标注一张图的操作流程**：

```
1. 打开参考图（副屏或旁边的窗口）
2. 在 UE5 Content Browser 双击材质实例（如 MI_UnityChan_Hair）
3. 拖动滑块，肉眼比对参考图，调节：
   - Shadow Color（阴影色）
   - Width Scale（描边宽度）
   - Specular（高光强度）
4. 觉得"差不多像了"后，修改脚本顶部：
   IMAGE_FILENAME = "当前参考图的文件名.jpg"
   TARGET = "hair"  # 或 "body" / "base"
5. UE5 菜单: Tools → Execute Python Script → 选择本文件
6. Output Log 里看到 "[MooaToon] 已记录" 说明成功
```

**需要在 UE5 里启用 Python 插件**：
```
Edit → Plugins → 搜索 "Python Editor Script Plugin" → 勾选 → 重启 UE
```

---

### `ue_apply_labels.py` — [UE内运行] CSV 写入材质

**作用**：把 `labels.csv` 里的参数值写入 UE5 材质实例，用于验证标注是否正确。

**两种运行模式**（修改文件底部的 `MODE` 变量）：

| MODE | 行为 |
|------|------|
| `"read"` | 读取当前材质参数，打印到 Output Log（默认） |
| `"apply"` | 把 CSV 最后一行的参数写入材质并保存 |

**用法**：
```
UE5: Tools → Execute Python Script → 选择 ue_apply_labels.py
```

---

## UE5 C++ 蓝图库

### 概述

NNE 推理 API 是纯 C++ 接口，Python 无法直接调用。因此实现了一个
`BlueprintFunctionLibrary`，把推理和材质写入封装成蓝图节点。

### 文件位置

```
Source/MooaToon_Project/
├── MyClass.h               # 函数声明
├── MyClass.cpp             # 函数实现
└── MooaToon_Project.Build.cs  # 依赖模块
```

### 暴露的蓝图函数

| 函数名 | 分类 | 说明 |
|--------|------|------|
| `SetMooaToonParams` | MooaToon | 手填参数值直接写入材质，不经过 ONNX |
| `RunMooaToonInference` | MooaToon\|Inference | 调用 NNE 对 float 数组推理，返回参数结构体 |
| `ApplyParamsToMaterial` | MooaToon\|Inference | 把参数结构体写入动态材质实例 |
| `InferAndApply` | MooaToon | 完整链路：推理 + 写入材质，一步完成 |

---

### 第一步：创建 C++ 类

在 UE5 编辑器里：

```
顶部菜单 → Tools → New C++ Class
→ 父类选择 "Blueprint Function Library"
→ 类名填: MyClass
→ 点击 Create Class
```

UE 自动生成：
```
Source/MooaToon_Project/MyClass.h
Source/MooaToon_Project/MyClass.cpp
```

---

### 第二步：修改 MyClass.h

将自动生成的内容完全替换为：

```cpp
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "NNEModelData.h"
#include "MyClass.generated.h"

USTRUCT(BlueprintType)
struct FMooaToonParams
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "MooaToon")
    float ShadowR = 0.f;

    UPROPERTY(BlueprintReadOnly, Category = "MooaToon")
    float ShadowG = 0.f;

    UPROPERTY(BlueprintReadOnly, Category = "MooaToon")
    float ShadowB = 0.f;

    UPROPERTY(BlueprintReadOnly, Category = "MooaToon")
    float WidthScale = 1.f;

    UPROPERTY(BlueprintReadOnly, Category = "MooaToon")
    float Specular = 0.5f;
};

UCLASS()
class MOOATOON_PROJECT_API UMyClass : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category = "MooaToon|Inference")
    static bool RunMooaToonInference(
        UNNEModelData* ModelData,
        const TArray<float>& InputPixels,
        FMooaToonParams& OutParams
    );

    UFUNCTION(BlueprintCallable, Category = "MooaToon|Inference")
    static void ApplyParamsToMaterial(
        UMaterialInstanceDynamic* MaterialInstance,
        const FMooaToonParams& Params
    );

    UFUNCTION(BlueprintCallable, Category = "MooaToon",
        meta = (AdvancedDisplay = "ElementIndex"))
    static void SetMooaToonParams(
        AActor* TargetActor,
        FLinearColor ShadowColor,
        float WidthScale   = 1.0f,
        float Specular     = 0.5f,
        int32 ElementIndex = 0
    );

    UFUNCTION(BlueprintCallable, Category = "MooaToon",
        meta = (AdvancedDisplay = "ElementIndex"))
    static bool InferAndApply(
        UNNEModelData* ModelData,
        const TArray<float>& InputPixels,
        AActor* TargetActor,
        int32 ElementIndex = 0
    );
};
```

---

### 第三步：修改 MyClass.cpp

完整内容：

```cpp
#include "MyClass.h"
#include "NNE.h"
#include "NNEModelData.h"
#include "NNERuntimeCPU.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Components/SkeletalMeshComponent.h"

DEFINE_LOG_CATEGORY_STATIC(LogMooaToon, Log, All);

bool UMyClass::RunMooaToonInference(
    UNNEModelData* ModelData,
    const TArray<float>& InputPixels,
    FMooaToonParams& OutParams)
{
    if (!ModelData) { return false; }
    if (InputPixels.Num() != 224 * 224 * 3) { return false; }

    TWeakInterfacePtr<INNERuntimeCPU> Runtime =
        UE::NNE::GetRuntime<INNERuntimeCPU>(TEXT("NNERuntimeORTCpu"));
    if (!Runtime.IsValid()) { return false; }

    TSharedPtr<UE::NNE::IModelCPU> Model = Runtime->CreateModelCPU(ModelData);
    if (!Model.IsValid()) { return false; }

    TSharedPtr<UE::NNE::IModelInstanceCPU> Instance = Model->CreateModelInstanceCPU();
    if (!Instance.IsValid()) { return false; }

    TArray<uint32> Shape = { 1, 3, 224, 224 };
    Instance->SetInputTensorShapes({ UE::NNE::FTensorShape::Make(Shape) });

    UE::NNE::FTensorBindingCPU In;
    In.Data = (void*)InputPixels.GetData();
    In.SizeInBytes = InputPixels.Num() * sizeof(float);

    TArray<float> Out;
    Out.SetNumZeroed(5);
    UE::NNE::FTensorBindingCPU OutBinding;
    OutBinding.Data = Out.GetData();
    OutBinding.SizeInBytes = Out.Num() * sizeof(float);

    if (Instance->RunSync({ In }, { OutBinding }) !=
        UE::NNE::IModelInstanceCPU::ERunSyncStatus::Ok)
    { return false; }

    OutParams.ShadowR    = Out[0];
    OutParams.ShadowG    = Out[1];
    OutParams.ShadowB    = Out[2];
    OutParams.WidthScale = Out[3] * 2.5f + 0.5f;  // 反归一化
    OutParams.Specular   = Out[4];
    return true;
}

void UMyClass::ApplyParamsToMaterial(
    UMaterialInstanceDynamic* Mat,
    const FMooaToonParams& Params)
{
    if (!Mat) { return; }
    Mat->SetVectorParameterValue(TEXT("Shadow Color"),
        FLinearColor(Params.ShadowR, Params.ShadowG, Params.ShadowB, 1.f));
    Mat->SetScalarParameterValue(TEXT("Width Scale"), Params.WidthScale);
    Mat->SetScalarParameterValue(TEXT("Specular"),    Params.Specular);
}

void UMyClass::SetMooaToonParams(
    AActor* TargetActor,
    FLinearColor ShadowColor,
    float WidthScale,
    float Specular,
    int32 ElementIndex)
{
    if (!TargetActor) { return; }
    USkeletalMeshComponent* Mesh =
        TargetActor->FindComponentByClass<USkeletalMeshComponent>();
    if (!Mesh) { return; }

    UMaterialInstanceDynamic* DynMat =
        Mesh->CreateAndSetMaterialInstanceDynamic(ElementIndex);
    if (!DynMat) { return; }

    DynMat->SetVectorParameterValue(TEXT("Shadow Color"), ShadowColor);
    DynMat->SetScalarParameterValue(TEXT("Width Scale"),  WidthScale);
    DynMat->SetScalarParameterValue(TEXT("Specular"),     Specular);

    UE_LOG(LogMooaToon, Log,
        TEXT("[MooaToon] Shadow=(%.3f,%.3f,%.3f) Width=%.3f Spec=%.3f"),
        ShadowColor.R, ShadowColor.G, ShadowColor.B, WidthScale, Specular);
}

bool UMyClass::InferAndApply(
    UNNEModelData* ModelData,
    const TArray<float>& InputPixels,
    AActor* TargetActor,
    int32 ElementIndex)
{
    FMooaToonParams Params;
    if (!RunMooaToonInference(ModelData, InputPixels, Params)) { return false; }

    FLinearColor Shadow(Params.ShadowR, Params.ShadowG, Params.ShadowB, 1.f);
    SetMooaToonParams(TargetActor, Shadow, Params.WidthScale, Params.Specular, ElementIndex);
    return true;
}
```

---

### 第四步：修改 MooaToon_Project.Build.cs

找到 `PublicDependencyModuleNames` 和 `PrivateDependencyModuleNames`，改为：

```csharp
PublicDependencyModuleNames.AddRange(new string[] {
    "Core", "CoreUObject", "Engine", "InputCore",
    "NNE"
});

PrivateDependencyModuleNames.AddRange(new string[] {
    "NNERuntimeORT"
});
```

> 注意：模块名是 `NNERuntimeORT`，不是 `NNERuntimeCPU`（后者在此版本引擎不存在）。

---

### 第五步：编译

**必须先关闭 UE5 编辑器**，否则 Live Coding 会锁住编译进程。

在 Visual Studio 里：
```
Solution Explorer → 右键 MooaToon_Project → Build
配置: Development Editor | Win64
```

编译成功标志：
```
Output 窗口: Build succeeded
Binaries/Win64/UnrealEditor-MooaToon_Project.dll 文件更新
```

常见错误及处理：

| 错误 | 原因 | 解决 |
|------|------|------|
| `Could not find module 'NNERuntimeCPU'` | 模块名错误 | 改为 `NNERuntimeORT` |
| `Unable to build while Live Coding is active` | UE 编辑器未关闭 | 关闭 UE 再编译 |
| `Hot-reloadable files are expected to contain a hyphen` | 从 VS Build Solution 触发了 HotReload | 右键单个项目 Build，不要 Build Solution |

---

### 第六步：把 ONNX 导入 UE5

将训练好的模型文件复制到 UE5 项目的 Content 目录：

```
来源: D:/unreal/testcv/mooatoon_model.onnx

目标: D:/unreal/MooaToon-Engine-5.5_MooaToonProject/
      MooaToon-Engine-5.5_MooaToonProject/Content/ONNX/mooatoon_model.onnx
```

UE5 重新打开后会自动生成 `mooatoon_model.uasset`。

Content Browser 内部路径：`/Game/ONNX/mooatoon_model`

---

## 蓝图操作详细步骤

### 方式 A：手填参数值（调试验证，立即可用）

适用场景：用 `infer_test.py` 推理出参数后，在 UE5 里验证效果。

**操作步骤**：

**1. 获取推理参数**
```bash
cd D:/unreal/testcv
python infer_test.py G1T8dBxbQAIa7hM.jpg
```
记录输出的三组数值：
```
Shadow Color = (0.236, 0.108, 0.168)
Width Scale  = 1.029
Specular     = 0.696
```

**2. 打开关卡蓝图**
```
UE5 顶部菜单 → Blueprints → Open Level Blueprint
```

**3. 在视口选中 UnityChan 角色**，回到蓝图编辑器，右键空白处：
```
搜索 "Create a Reference to [UnityChan角色名]"
→ 点击生成角色引用节点（蓝色节点）
```

**4. 添加 BeginPlay 节点**

右键空白处搜索 `Event BeginPlay`，添加。

**5. 添加 SetMooaToonParams 节点**

右键空白处搜索 `Set MooaToon Params`，添加。

**6. 连线**

```
连接规则（两种引脚不能混接）：
  白色引脚（执行）→ 只接白色引脚
  蓝色引脚（数据）→ 只接蓝色引脚

具体连法：
  Event BeginPlay [白色输出] ──────────────→ Set MooaToon Params [白色输入]
  UnityChan引用   [蓝色输出] ──────────────→ Set MooaToon Params [Target Actor]
```

**7. 填入数值**

在 `Set MooaToon Params` 节点上直接点击输入框填值：
```
Shadow Color → 展开 R/G/B 分别填: 0.236 / 0.108 / 0.168
Width Scale  → 1.029
Specular     → 0.696
Element Index → 0（默认，Hair 槽位不是0时修改）
```

**8. 编译蓝图并运行**
```
蓝图编辑器左上角 → Compile（编译按钮）
UE5 工具栏 → Play（▶）
```

运行后 UnityChan 材质参数生效，Output Log 出现：
```
[MooaToon] Shadow=(0.236,0.108,0.168) Width=1.029 Spec=0.696
```

---

**如果材质没有变化**，通常是槽位 ElementIndex 不对：
```
选中 UnityChan → Details 面板 → 找到 Materials 列表
查看 Hair 对应的 Index 编号（可能是 1、2、3 等）
把 Set MooaToon Params 的 Element Index 改成对应数字
```

---

### 方式 B：完整 ONNX 推理链路（InferAndApply）

适用场景：已有图片 float 数组，想在 UE5 内部完成推理。

蓝图节点连法与方式 A 类似，区别是使用 `Infer And Apply` 节点：

```
Event BeginPlay ──→ Infer And Apply
                        Model Data   ← 把 /Game/ONNX/mooatoon_model 拖进来
                        Input Pixels ← float 数组（150528个元素，CHW格式）
                        Target Actor ← UnityChan 引用
                        Element Index ← 0
```

> `Input Pixels` 需要外部提供预处理后的 float 数组（224×224×3，ImageNet 归一化）。
> 当前蓝图没有图片解码节点，建议先用方式 A 验证流程。

---

## 完整数据流向

```
【离线阶段 - Python】

参考图片 (images/)
    ↓ 手动标注 / ue_record_params.py 自动记录
labels.csv
    ↓
python train.py
    ↓
mooatoon_model.onnx
    ↓
python infer_test.py → 打印推理参数值


【运行阶段 - UE5】

infer_test.py 的输出参数
    ↓ 手动填入蓝图
Set MooaToon Params 节点
    ↓ C++ 内部
CreateAndSetMaterialInstanceDynamic
    ↓
SetVectorParameterValue("Shadow Color", ...)
SetScalarParameterValue("Width Scale", ...)
SetScalarParameterValue("Specular", ...)
    ↓
MooaToon 材质实时生效
```

---

## 环境依赖

```bash
pip install torch torchvision pillow pandas onnx onnxruntime
```

| 包 | 版本（已测试） | 用途 |
|----|--------------|------|
| torch | 2.11.0+cpu | 训练、ONNX 导出 |
| torchvision | 对应版本 | ResNet18 模型、数据增强 |
| Pillow | 12.1.1 | 图片读取 |
| pandas | 3.0.2 | CSV 读写 |
| onnx | 1.21.0 | ONNX 格式校验 |
| onnxruntime | 最新 | 本地推理验证 |

Python 版本：3.11（Windows）

---

## UE5 环境

| 项目 | 路径 |
|------|------|
| MooaToon 引擎 | `E:/MooaToon-Engine-5.5/MooaToon-Engine-5.5/` |
| MooaToon 项目 | `D:/unreal/MooaToon-Engine-5.5_MooaToonProject/` |
| ONNX 资产位置 | `Content/ONNX/mooatoon_model.uasset` |
| UE 内部路径 | `/Game/ONNX/mooatoon_model` |
| 测试角色材质 | `/Game/MooaToonSamples/Characters/UnityChanSD/Materials/` |
| C++ 源码 | `Source/MooaToon_Project/MyClass.h / .cpp` |

---

## 已确认的 MooaToon 材质参数名

从 `.uasset` 二进制中提取，区分大小写：

| UE 参数名 | 类型 | 所在材质实例 |
|-----------|------|------------|
| `Shadow Color` | Vector (RGB) | MI_UnityChan_Hair / Body |
| `Width Scale` | Scalar | MI_UnityChan_Outline |
| `Specular` | Scalar | MI_UnityChan_Hair |
| `Base Color` | Vector | MI_UnityChan_Base |
| `Rim Light Intensity` | Scalar | MI_UnityChan_Base |
| `Specular Color` | Vector | MI_UnityChan_Hair |
