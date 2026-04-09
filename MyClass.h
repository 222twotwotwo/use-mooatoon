// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "NNEModelData.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "MyClass.generated.h"

/**
 * MooaToon 材质参数推理库
 * 输入: UNNEModelData (mooatoon_model.onnx)
 * 输出: 5个材质参数 Shadow Color(RGB) + Width Scale + Specular
 */
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
	/**
	 * 用 ONNX 模型推理材质参数
	 * @param ModelData   Content Browser 里导入的 mooatoon_model.onnx 资产
	 * @param InputPixels 224x224 RGB 图片像素，已归一化为 float（CHW 格式，长度 150528）
	 * @param OutParams   推理结果：阴影色 + 描边宽度 + 高光强度
	 * @return 推理是否成功
	 */
	UFUNCTION(BlueprintCallable, Category = "MooaToon|Inference")
	static bool RunMooaToonInference(
		UNNEModelData* ModelData,
		const TArray<float>& InputPixels,
		FMooaToonParams& OutParams
	);

	/**
	 * 把推理结果写入材质实例参数
	 * @param MaterialInstance 目标材质实例
	 * @param Params           RunMooaToonInference 的输出
	 */
	UFUNCTION(BlueprintCallable, Category = "MooaToon|Inference")
	static void ApplyParamsToMaterial(
		UMaterialInstanceDynamic* MaterialInstance,
		const FMooaToonParams& Params
	);

	/**
	 * 一步到位：直接修改场景中角色指定槽位的材质参数（手填数值，不经过 ONNX）
	 * @param TargetActor    要修改材质的角色（从场景拖入）
	 * @param ShadowColor    阴影色 RGB（线性颜色，范围 0~1）
	 * @param WidthScale     描边宽度（范围 0.5~3.0）
	 * @param Specular       高光强度（范围 0~1）
	 * @param ElementIndex   材质槽位索引（默认 0）
	 */
	UFUNCTION(BlueprintCallable, Category = "MooaToon", meta = (AdvancedDisplay = "ElementIndex"))
	static void SetMooaToonParams(
		AActor* TargetActor,
		FLinearColor ShadowColor,
		float WidthScale  = 1.0f,
		float Specular    = 0.5f,
		int32 ElementIndex = 0
	);

	/**
	 * 从磁盘读取 PNG/JPG，缩放到 224×224，做 ImageNet 归一化，输出 CHW float 数组
	 * @param ImagePath   绝对路径，例如 "D:/unreal/.../Content/images/xxx.png"
	 * @param OutPixels   输出 float 数组，长度 150528（3×224×224）
	 * @return 是否成功
	 */
	UFUNCTION(BlueprintCallable, Category = "MooaToon|Inference")
	static bool LoadImageToPixels(const FString& ImagePath, TArray<float>& OutPixels);

	/**
	 * 完整推理链路：ONNX 推理图片 → 自动写入角色材质
	 * 蓝图一个节点完成全流程
	 * @param ModelData    Content Browser 里的 mooatoon_model 资产
	 * @param InputPixels  224x224 RGB 图片，ImageNet 归一化后的 CHW float 数组（长度 150528）
	 * @param TargetActor  要修改材质的角色
	 * @param ElementIndex 材质槽位索引（默认 0）
	 * @return 推理是否成功
	 */
	UFUNCTION(BlueprintCallable, Category = "MooaToon", meta = (AdvancedDisplay = "ElementIndex"))
	static bool InferAndApply(
		UNNEModelData* ModelData,
		const TArray<float>& InputPixels,
		AActor* TargetActor,
		int32 ElementIndex = 0
	);
};
