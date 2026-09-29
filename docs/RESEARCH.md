# 为什么选择这个项目

目标是在普通电脑 CPU 上完成中文跨模态检索与小规模诊断实验，不训练大模型。具体性能取决于内存、CPU 和运行负载。

## 调研对比

| 路线 | 公开依据 | 适用性 |
|---|---|---|
| Chinese-CLIP RN50 | 官方 77M 参数、权重 308,316,425 bytes；官方 API 提供 CPU 路径 | 原生中文，选择作为本项目主模型；不复现训练 |
| CLIP ViT-B/32 INT8 ONNX | Xenova 社区转换的图像 88.6MB 与文本 64.1MB 文件 | 依赖和文件较轻，可作为将来英文/部署对比；不是 OpenAI 官方 ONNX |
| MobileCLIP-S0 | Apple 官方小型图文模型 | 可后续对比；移动设备时延不能外推本机 Windows CPU |
| 纯网页规则/属性检索 | 颜色、形状、位置与手工语言规则 | 可以零模型教学，但受限语义不能冒充 CLIP；本项目选择真实 CPU 模型路线 |

来源：[Chinese-CLIP](https://github.com/OFA-Sys/Chinese-CLIP)、[RN50 文件目录](https://huggingface.co/OFA-Sys/chinese-clip-rn50/tree/main)、[CLIP ONNX 文件](https://huggingface.co/Xenova/clip-vit-base-patch32/tree/main/onnx)、[MobileCLIP](https://github.com/apple-aiml-research/ml-mobileclip)。

## 研究问题如何落到学习项目

1. 简短关键词和完整中文描述是否返回相同候选？固定图片库，只改变查询表达。
2. 颜色或物体属性改变后，模型是否找到了真正满足条件的图？记录具体错误图片，不只看平均分。
3. 直接输入否定句与“正向分数减去排除分数”是否有区别？固定排除权重，并保留退化案例。
4. 缓存解决了哪部分延迟？分别测首次建库、冷加载、热查询；不拿矩阵排序耗时冒充完整推理耗时。

否定理解已有研究：[Vision-Language Models Do Not Understand Negation（CVPR 2025）](https://openaccess.thecvf.com/content/CVPR2025/html/Alhamoud_Vision-Language_Models_Do_Not_Understand_Negation_CVPR_2025_paper.html)、[Seeing What’s Not There（ICLR 2026）](https://proceedings.iclr.cc/paper_files/paper/2026/hash/713051bc96d98f3a8e35a27823bf2813-Abstract-Conference.html)。本项目不宣称首次使用否定条件拆分或语义减法，也不声称复现以上论文的完整实验。

## 可复现与诚实展示

图库选用许可明确的实际图像，人工标注与模型分数不混用。固定模型版本，实际权重下载时验证 SHA-256。所有对照使用相同候选集和查询划分；人工描述基线拥有额外文本信息，因此只作为教学参照。小规模数据、博物馆风格、标注不完备与启发式否定解析都是实际边界。

后续最有价值的拓展是亲自增加困难图片对、人工审核多正例标注、增加不同风格图片，然后验证方法是否还能有效。仅修改页面或调几个参数不足以证明研究创新。
