# Style-Bert-VITS2 日文语音模型

## 瑠璃乃 Live2D 制作

[当前制作目标与下一步](live2d/CURRENT_WORK.md)：正在补齐 [正脸中立底模](live2d/FRONT_NEUTRAL_V034.md)，已提供可编辑工程与实际运行模型，目前为静态正脸，眨眼、嘴型及转头尚未绑定。原 [左视图四马尾与身体侧摆](live2d/BODY_HAIR_V034.md) 原型另行保留。

[人物素材与 Cubism 交接](live2d/README.md) · [桌宠模型接入程序](desktop/README.md)。已提供 [v0.3.3 可运行绑定测试稿](live2d/RIG_DRAFT.md)，支持眨眼、口型与小幅转头；头发边缘和变形仍在精修。

## 使用方法

### 1. 安装依赖
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 生成语音
```bash
python infer_final.py "こんにちは"
python infer_final.py "がじょうせん、かかでらしゃい" --noise 0.03
```

### 参数说明
| 参数 | 默认值 | 说明 |
|------|--------|------|
| --sdp_ratio | 0.3 | 时长随机性 |
| --noise | 0.05 | 噪声注入，减少机械音 |
| --noise_w | 0.05 | 噪声权重 |
| --length | 1.0 | 语速，<1=快，>1=慢 |
| --pitch_scale | 1.0 | 音高缩放 |
| --intonation_scale | 1.0 | 语调缩放 |

## 文件说明
- speaker_1_e24_s25000.safetensors - 模型权重
- config.json - 模型配置
- style_vectors.npy - 风格向量
- bert/deberta-v2-large-japanese-char-wwm/ - BERT模型
