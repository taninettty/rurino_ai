# Rurino AI - 日文角色语音合成模型

基于 Style-Bert-VITS2 JP-Extra 训练的日文角色语音合成模型，支持无参考音频直接输出高质量语音。

## 🎵 Demo 试听

| 文件名 | 内容 |
|--------|------|
| [demo_1.wav](demo/demo_1.wav) | がじょうせん、かかでらしゃい |
| [demo_2.wav](demo/demo_2.wav) | こんにちは、私はエーアイです |
| [demo_3.wav](demo/demo_3.wav) | 本当にありがとうございます |

## 🚀 使用方法

### 1. 克隆仓库
```bash
git clone https://github.com/taninettty/rurino_ai.git
cd rurino_ai
git lfs pull
```

### 2. 安装依赖
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 生成语音
```bash
# 基础使用
python infer_final.py "こんにちは"

# 带参数
python infer_final.py "がじょうせん、かかでらしゃい" --noise 0.03

# 更多示例
python infer_final.py "とてもいいです！" --length 0.9 --pitch_scale 1.05
python infer_final.py "おはようございます" --intonation_scale 1.1
```

## 📋 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| --sdp_ratio | 0.3 | 时长随机性，越小越稳定 |
| --noise | 0.05 | 噪声注入，减少机械音 |
| --noise_w | 0.05 | 噪声权重 |
| --length | 1.0 | 语速，<1=快，>1=慢 |
| --pitch_scale | 1.0 | 音高缩放，>1=更高 |
| --intonation_scale | 1.0 | 语调缩放，>1=更夸张 |

## 📁 文件结构

```
rurino_ai/
├── infer_final.py              # 推理脚本
├── requirements.txt            # 依赖列表
├── config.json                 # 模型配置
├── bert/
│   └── deberta-v2-large-japanese-char-wwm/  # BERT模型
├── model_assets/
│   └── speaker_1/
│       ├── speaker_1_e24_s25000.safetensors  # 核心模型权重
│       ├── config.json                        # 模型配置
│       └── style_vectors.npy                  # 风格向量
└── demo/                      # 示例音频
    └── *.wav
```

## 🏋️ 训练信息

- **数据集**: 2108 条清洗后的日文语音数据
- **训练轮次**: 25 Epoch（最佳模型为 e24）
- **Batch Size**: 2
- **训练时长**: ~6.7 小时
- **硬件**: 单 GPU（8GB 显存）
- **数据预处理**: noisereduce 降噪增强

## ⚠️ 已知限制

- 仅支持日文文本输入
- 需要 NVIDIA GPU 进行推理（建议 ≥4GB 显存）
- 长文本生成可能出现断音，建议分段输入

## 🙏 致谢

本项目基于以下开源项目构建：

- [Style-Bert-VITS2](https://github.com/litagin02/Style-Bert-VITS2) - 主框架
- [DeBERTa-V2 Japanese](https://huggingface.co/cl-tohoku/deberta-v2-large-japanese-char-wwm) - BERT模型
- [PyOpenJTalk](https://github.com/r9y9/pyopenjtalk) - 日文 G2P
- [noisereduce](https://github.com/timsainb/noisereduce) - 音频降噪

## 📄 License

MIT License
