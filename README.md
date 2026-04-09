

**环境：**  
- *pyhton库：* pytorch,   pillow,  pandas
- *mooatoon引擎*
- *visual studio 2022*

**思路：**
1. 在ue编辑器里查看unitychan示例模型根据收集来的插图调整Shadow Color, Width Scale等参数，使用这些参数训练好ONNX模型
2. 在ue内部调用ONNX模型生成的参数，写入实际材质参数



**1.** ONNX训练模型

- 根据收集图的Shadow Color, Width Scale 调整ue里unitychan人物的参数，觉得很像了就记录在labels.csv表里面，与图片一一对应,目前表里的是垃圾数据，需要自己手动调整
- csv表填完之和开始训练onnx模型，运行train.py导出onnx，最后将其拖入ue编辑器
- 选择你想要的风格图片，在Content创建images目录放入
- 详细使用请查看[use-mooatoon/test/README.md at main · 222twotwotwo/use-mooatoon](https://github.com/222twotwotwo/use-mooatoon/blob/main/test/README.md)


**2.** ue中使用ONNX模型
- 使用[mooatoon示例项目](https://github.com/Jason-Ma-0012/MooaToon-Engine/tree/5.5_MooaToonProject)下载5.5版本使用mooatoon引擎打开在顶部栏**选中**  “工具”  在里面选择 **新建c++类**  创建一个空的c++类命名为*MyClass*
  - 此时蓝图项目便转为c++项目使用**visual studio**打开

- 构造MyClass方法，直接复制粘贴github中的文件即可
    - 负责在蓝图中暴露接口使其材质示例可以使用参数，并运行ONNX模型
    - 定义蓝图可用结构体 MooaToonParams，封装推理输出的 5 个材质参数：
    - ShadowR / ShadowG / ShadowB：阴影色 RGB（线性，0~1）
    - WidthScale：描边宽度（原始范围 0.5~3.0）
    - Specular：高光强度（0~1）

- 在ue编辑器中选择一个角色拖入场景中, 以unitychan为例， 打开关卡蓝图，然后找到Event Beginplay双击选中进入蓝图页面，拉出**Event Beginplay**的输出接口松开后获得一个小框，在其中搜索**Load Image to Pixels**创建，**Image Path**则是你之前存放图像的地方，使用绝对路径,接下来**Event Beginplay**再拉一条搜索 **Infer and Apply**  进行链接， 返回视口页面也就是地图页面，选中人物再返回，右键空白处找到 **Create a reference [名字]** 按下创建，将其输出引脚接入**Infer and Apply**的 **Target Actor**输入引脚，**Model Data**选择你之前导入的*ONNX*, 最后将 **OUt Pixels** 与 **Input Pixels**链接，完成

  编译后运行可在输出日志里可以找到：
	LogMooaToon: [MooaToon] LoadImageToPixels 成功: D:/unreal/MooaToon-Engine-5.5_MooaToonProject/MooaToon-Engine-5.5_MooaToonProject/Content/images/a0673306d0ee799c481cd152fde65f89.png (811x1185 → 224x224)
	
	LogMooaToon: [MooaToon] 推理成功: Shadow=(0.244,0.206,0.222) Width=1.378 Specular=0.367


  编译后运行打开在**元素0**这一栏的材质可在细节面板找到输入的参数
