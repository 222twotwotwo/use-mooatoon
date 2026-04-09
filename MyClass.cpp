// Fill out your copyright notice in the Description page of Project Settings.

#include "MyClass.h"
#include "NNE.h"
#include "NNEModelData.h"
#include "NNERuntimeCPU.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/MeshComponent.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "Modules/ModuleManager.h"
#include "Misc/FileHelper.h"

DEFINE_LOG_CATEGORY_STATIC(LogMooaToon, Log, All);

bool UMyClass::RunMooaToonInference(
	UNNEModelData* ModelData,
	const TArray<float>& InputPixels,
	FMooaToonParams& OutParams)
{
	// 1. 参数检查
	if (!ModelData)
	{
		UE_LOG(LogMooaToon, Error, TEXT("[MooaToon] ModelData 为空，请传入 ONNX 资产"));
		return false;
	}

	// 输入应为 224*224*3 = 150528 个 float
	constexpr int32 ExpectedSize = 224 * 224 * 3;
	if (InputPixels.Num() != ExpectedSize)
	{
		UE_LOG(LogMooaToon, Error, TEXT("[MooaToon] InputPixels 长度应为 %d，实际为 %d"),
			ExpectedSize, InputPixels.Num());
		return false;
	}

	// 2. 获取 CPU Runtime
	TWeakInterfacePtr<INNERuntimeCPU> RuntimeCPU =
		UE::NNE::GetRuntime<INNERuntimeCPU>(TEXT("NNERuntimeORTCpu"));

	if (!RuntimeCPU.IsValid())
	{
		UE_LOG(LogMooaToon, Error, TEXT("[MooaToon] 找不到 NNERuntimeORTCpu，请确认 NNE 插件已启用"));
		return false;
	}

	// 3. 创建模型实例
	TSharedPtr<UE::NNE::IModelCPU> ModelCPU = RuntimeCPU->CreateModelCPU(ModelData);
	if (!ModelCPU.IsValid())
	{
		UE_LOG(LogMooaToon, Error, TEXT("[MooaToon] 创建 ModelCPU 失败"));
		return false;
	}

	TSharedPtr<UE::NNE::IModelInstanceCPU> ModelInstance = ModelCPU->CreateModelInstanceCPU();
	if (!ModelInstance.IsValid())
	{
		UE_LOG(LogMooaToon, Error, TEXT("[MooaToon] 创建 ModelInstance 失败"));
		return false;
	}

	// 4. 设置输入 Shape：[1, 3, 224, 224]
	TArray<uint32> InputShape = { 1, 3, 224, 224 };
	UE::NNE::FTensorShape TensorShape = UE::NNE::FTensorShape::Make(InputShape);

	if (ModelInstance->SetInputTensorShapes({ TensorShape }) !=
		UE::NNE::IModelInstanceCPU::ESetInputTensorShapesStatus::Ok)
	{
		UE_LOG(LogMooaToon, Error, TEXT("[MooaToon] SetInputTensorShapes 失败"));
		return false;
	}

	// 5. 准备输入/输出 Tensor
	UE::NNE::FTensorBindingCPU InputBinding;
	InputBinding.Data = (void*)InputPixels.GetData();
	InputBinding.SizeInBytes = InputPixels.Num() * sizeof(float);

	// 输出：5 个 float [shadow_r, shadow_g, shadow_b, width_scale_norm, specular]
	TArray<float> OutputData;
	OutputData.SetNumZeroed(5);

	UE::NNE::FTensorBindingCPU OutputBinding;
	OutputBinding.Data = OutputData.GetData();
	OutputBinding.SizeInBytes = OutputData.Num() * sizeof(float);

	// 6. 推理
	if (ModelInstance->RunSync({ InputBinding }, { OutputBinding }) !=
		UE::NNE::IModelInstanceCPU::ERunSyncStatus::Ok)
	{
		UE_LOG(LogMooaToon, Error, TEXT("[MooaToon] RunSync 失败"));
		return false;
	}

	// 7. 解析输出，反归一化 width_scale（训练时归一化到[0,1]，原始范围[0.5, 3.0]）
	OutParams.ShadowR    = OutputData[0];
	OutParams.ShadowG    = OutputData[1];
	OutParams.ShadowB    = OutputData[2];
	OutParams.WidthScale = OutputData[3] * 2.5f + 0.5f;  // 反归一化
	OutParams.Specular   = OutputData[4];

	UE_LOG(LogMooaToon, Log, TEXT("[MooaToon] 推理成功: Shadow=(%.3f,%.3f,%.3f) Width=%.3f Specular=%.3f"),
		OutParams.ShadowR, OutParams.ShadowG, OutParams.ShadowB,
		OutParams.WidthScale, OutParams.Specular);

	return true;
}

void UMyClass::ApplyParamsToMaterial(
	UMaterialInstanceDynamic* MaterialInstance,
	const FMooaToonParams& Params)
{
	if (!MaterialInstance)
	{
		UE_LOG(LogMooaToon, Error, TEXT("[MooaToon] MaterialInstance 为空"));
		return;
	}

	// 写入 Shadow Color（Vector 参数）
	FLinearColor ShadowColor(Params.ShadowR, Params.ShadowG, Params.ShadowB, 1.f);
	MaterialInstance->SetVectorParameterValue(TEXT("Shadow Color"), ShadowColor);

	// 写入标量参数
	MaterialInstance->SetScalarParameterValue(TEXT("Width Scale"), Params.WidthScale);
	MaterialInstance->SetScalarParameterValue(TEXT("Specular"), Params.Specular);

	UE_LOG(LogMooaToon, Log, TEXT("[MooaToon] 材质参数已写入"));
}

void UMyClass::SetMooaToonParams(
	AActor* TargetActor,
	FLinearColor ShadowColor,
	float WidthScale,
	float Specular,
	int32 ElementIndex)
{
	if (!TargetActor)
	{
		UE_LOG(LogMooaToon, Error, TEXT("[MooaToon] SetMooaToonParams: TargetActor 为空"));
		return;
	}

	// 找骨骼网格体组件
	USkeletalMeshComponent* SkelMesh =
		TargetActor->FindComponentByClass<USkeletalMeshComponent>();

	if (!SkelMesh)
	{
		UE_LOG(LogMooaToon, Error,
			TEXT("[MooaToon] SetMooaToonParams: 在 %s 上找不到 SkeletalMeshComponent"),
			*TargetActor->GetName());
		return;
	}

	// 创建动态材质实例（如果已经是 DynMat 会直接复用）
	UMaterialInstanceDynamic* DynMat =
		SkelMesh->CreateAndSetMaterialInstanceDynamic(ElementIndex);

	if (!DynMat)
	{
		UE_LOG(LogMooaToon, Error,
			TEXT("[MooaToon] SetMooaToonParams: 创建 DynamicMaterialInstance 失败，ElementIndex=%d"),
			ElementIndex);
		return;
	}

	// 写入参数
	DynMat->SetVectorParameterValue(TEXT("Shadow Color"), ShadowColor);
	DynMat->SetScalarParameterValue(TEXT("Width Scale"),  WidthScale);
	DynMat->SetScalarParameterValue(TEXT("Specular"),     Specular);

	UE_LOG(LogMooaToon, Log,
		TEXT("[MooaToon] SetMooaToonParams 成功: Shadow=(%.3f,%.3f,%.3f) Width=%.3f Specular=%.3f"),
		ShadowColor.R, ShadowColor.G, ShadowColor.B, WidthScale, Specular);
}

bool UMyClass::InferAndApply(
	UNNEModelData* ModelData,
	const TArray<float>& InputPixels,
	AActor* TargetActor,
	int32 ElementIndex)
{
	// 1. 先推理
	FMooaToonParams Params;
	if (!RunMooaToonInference(ModelData, InputPixels, Params))
	{
		UE_LOG(LogMooaToon, Error, TEXT("[MooaToon] InferAndApply: 推理失败"));
		return false;
	}

	// 2. 再写入材质
	FLinearColor ShadowColor(Params.ShadowR, Params.ShadowG, Params.ShadowB, 1.f);
	SetMooaToonParams(TargetActor, ShadowColor, Params.WidthScale, Params.Specular, ElementIndex);

	UE_LOG(LogMooaToon, Log, TEXT("[MooaToon] InferAndApply 完成"));
	return true;
}

bool UMyClass::LoadImageToPixels(const FString& ImagePath, TArray<float>& OutPixels)
{
	// 1. 读取文件字节
	TArray<uint8> FileData;
	if (!FFileHelper::LoadFileToArray(FileData, *ImagePath))
	{
		UE_LOG(LogMooaToon, Error, TEXT("[MooaToon] LoadImageToPixels: 无法读取文件 %s"), *ImagePath);
		return false;
	}

	// 2. 解码 PNG/JPG
	IImageWrapperModule& ImageWrapperModule =
		FModuleManager::LoadModuleChecked<IImageWrapperModule>(TEXT("ImageWrapper"));

	EImageFormat Format = ImageWrapperModule.DetectImageFormat(FileData.GetData(), FileData.Num());
	if (Format == EImageFormat::Invalid)
	{
		UE_LOG(LogMooaToon, Error, TEXT("[MooaToon] LoadImageToPixels: 不支持的图片格式 %s"), *ImagePath);
		return false;
	}

	TSharedPtr<IImageWrapper> Wrapper = ImageWrapperModule.CreateImageWrapper(Format);
	if (!Wrapper.IsValid() || !Wrapper->SetCompressed(FileData.GetData(), FileData.Num()))
	{
		UE_LOG(LogMooaToon, Error, TEXT("[MooaToon] LoadImageToPixels: 解码失败 %s"), *ImagePath);
		return false;
	}

	TArray<uint8> RawRGBA;
	if (!Wrapper->GetRaw(ERGBFormat::RGBA, 8, RawRGBA))
	{
		UE_LOG(LogMooaToon, Error, TEXT("[MooaToon] LoadImageToPixels: GetRaw 失败"));
		return false;
	}

	const int32 SrcW = Wrapper->GetWidth();
	const int32 SrcH = Wrapper->GetHeight();

	// 3. 缩放到 224×224（双线性插值）
	constexpr int32 DstSize = 224;
	TArray<uint8> Resized;
	Resized.SetNumUninitialized(DstSize * DstSize * 4);

	for (int32 DstY = 0; DstY < DstSize; ++DstY)
	{
		for (int32 DstX = 0; DstX < DstSize; ++DstX)
		{
			const float SrcXf = (DstX + 0.5f) * SrcW / DstSize - 0.5f;
			const float SrcYf = (DstY + 0.5f) * SrcH / DstSize - 0.5f;

			const int32 X0 = FMath::Clamp((int32)FMath::FloorToFloat(SrcXf), 0, SrcW - 1);
			const int32 Y0 = FMath::Clamp((int32)FMath::FloorToFloat(SrcYf), 0, SrcH - 1);
			const int32 X1 = FMath::Clamp(X0 + 1, 0, SrcW - 1);
			const int32 Y1 = FMath::Clamp(Y0 + 1, 0, SrcH - 1);

			const float Tx = SrcXf - FMath::FloorToFloat(SrcXf);
			const float Ty = SrcYf - FMath::FloorToFloat(SrcYf);

			for (int32 C = 0; C < 3; ++C)
			{
				const float V00 = RawRGBA[(Y0 * SrcW + X0) * 4 + C];
				const float V10 = RawRGBA[(Y0 * SrcW + X1) * 4 + C];
				const float V01 = RawRGBA[(Y1 * SrcW + X0) * 4 + C];
				const float V11 = RawRGBA[(Y1 * SrcW + X1) * 4 + C];
				const float Val = V00 * (1 - Tx) * (1 - Ty)
				                + V10 * Tx * (1 - Ty)
				                + V01 * (1 - Tx) * Ty
				                + V11 * Tx * Ty;
				Resized[(DstY * DstSize + DstX) * 4 + C] = (uint8)FMath::Clamp(Val, 0.f, 255.f);
			}
			Resized[(DstY * DstSize + DstX) * 4 + 3] = 255;
		}
	}

	// 4. HWC → CHW + ImageNet 归一化
	// mean=[0.485,0.456,0.406]  std=[0.229,0.224,0.225]
	static constexpr float Mean[3] = { 0.485f, 0.456f, 0.406f };
	static constexpr float Std[3]  = { 0.229f, 0.224f, 0.225f };

	constexpr int32 PixelCount = DstSize * DstSize;
	OutPixels.SetNumUninitialized(3 * PixelCount);

	for (int32 C = 0; C < 3; ++C)
	{
		for (int32 I = 0; I < PixelCount; ++I)
		{
			const float Normalized = Resized[I * 4 + C] / 255.f;
			OutPixels[C * PixelCount + I] = (Normalized - Mean[C]) / Std[C];
		}
	}

	UE_LOG(LogMooaToon, Log, TEXT("[MooaToon] LoadImageToPixels 成功: %s (%dx%d → 224x224)"),
		*ImagePath, SrcW, SrcH);
	return true;
}
